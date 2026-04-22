from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from polymarket_alert_bot.config.settings import RuntimeConfig, RuntimePaths, load_runtime_config
from polymarket_alert_bot.models.enums import RunStatus, RunType
from polymarket_alert_bot.scanner.clob_client import (
    BookSnapshot,
    build_book_snapshots,
    degraded_snapshot,
    fetch_book,
)
from polymarket_alert_bot.scanner.family import CandidateFamilySummary
from polymarket_alert_bot.scanner.gamma_client import fetch_events, normalize_events
from polymarket_alert_bot.scanner.market_link import build_polymarket_market_url
from polymarket_alert_bot.scanner.normalizer import ScanCandidate, normalize_candidates
from polymarket_alert_bot.scanner.ranking import build_ranking_summary, select_judgment_candidates
from polymarket_alert_bot.storage.db import connect_db
from polymarket_alert_bot.storage.migrations import apply_migrations
from polymarket_alert_bot.storage.repositories import RuntimeRepository

MIN_LIQUIDITY_USD = 1_000.0
MAX_SPREAD_BPS = 800.0


@dataclass(frozen=True)
class ScanCoverage:
    total_events: int
    total_families: int
    total_markets: int
    total_candidates: int
    shortlisted_candidates: int
    tradable_candidates: int
    families_with_structural_flags: int
    structurally_flagged_candidates: int
    missing_deadline_candidates: int
    missing_category_candidates: int
    missing_outcome_candidates: int
    missing_family_context_candidates: int
    rejected_inactive: int
    rejected_low_liquidity: int
    rejected_wide_spread: int
    rejected_duplicate: int
    degraded_books: int

    @property
    def skipped(self) -> int:
        return (
            self.rejected_inactive
            + self.rejected_low_liquidity
            + self.rejected_wide_spread
            + self.rejected_duplicate
            + self.degraded_books
        )


@dataclass(frozen=True)
class ScanOutcome:
    coverage: ScanCoverage
    tradable: tuple[ScanCandidate, ...]
    degraded: tuple[ScanCandidate, ...]
    rejected: tuple[tuple[ScanCandidate, str], ...]


@dataclass(frozen=True)
class AlertSeed:
    id: str
    run_id: str
    event_id: str
    event_title: str | None
    event_category: str | None
    event_end_time: str | None
    market_id: str
    token_id: str
    condition_id: str | None
    event_slug: str | None
    market_slug: str | None
    question: str
    outcome_name: str | None
    market_link: str | None
    alert_kind: str
    dedupe_key: str
    expression_key: str
    expression_summary: str
    rules_text: str | None
    best_bid_cents: float | None
    best_ask_cents: float | None
    mid_cents: float | None
    last_price_cents: float | None
    spread_bps: float | None
    slippage_bps: float | None
    is_degraded: bool
    degraded_reason: str | None
    family_summary: CandidateFamilySummary
    ranking_summary: dict[str, Any]
    judgment_seed: dict[str, Any] | None
    evidence_seeds: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class ScanRunResult:
    run_id: str
    status: str
    degraded_reason: str | None
    outcome: ScanOutcome
    alert_seeds: tuple[AlertSeed, ...]


def run_scan(
    paths: RuntimePaths,
    *,
    gamma_payload: Sequence[dict[str, Any]] | None = None,
    clob_payload: Mapping[str, Any] | Sequence[Any] | None = None,
    judgment_seed_inputs: Mapping[str, object] | None = None,
    evidence_seed_inputs: Mapping[str, object] | None = None,
    max_judgment_candidates: int | None = None,
) -> ScanRunResult:
    timestamp = datetime.now(UTC).isoformat()
    run_id = str(uuid4())

    outcome = _dry_outcome()
    if gamma_payload is not None:
        outcome = scan_board(gamma_payload, clob_payload or {"books": []})
    elif os.environ.get("POLYMARKET_ALERT_BOT_ENABLE_SCAN") == "1":
        outcome = _run_live_scan(load_runtime_config())

    status = RunStatus.CLEAN.value
    degraded_reason = None
    if outcome.coverage.degraded_books > 0 and outcome.coverage.total_candidates > 0:
        status = RunStatus.DEGRADED.value
        degraded_reason = "executable_checks_partial"

    alert_seeds = _build_alert_seeds(
        run_id,
        outcome,
        judgment_seed_inputs=judgment_seed_inputs or {},
        evidence_seed_inputs=evidence_seed_inputs or {},
        max_judgment_candidates=max_judgment_candidates,
    )

    conn = connect_db(paths.db_path)
    apply_migrations(conn)
    repository = RuntimeRepository(conn)
    repository.upsert_run(
        {
            "id": run_id,
            "run_type": RunType.SCAN.value,
            "status": status,
            "started_at": timestamp,
            "finished_at": timestamp,
            "degraded_reason": degraded_reason,
            "scanned_events": outcome.coverage.total_events,
            "scanned_families": outcome.coverage.total_families,
            "scanned_contracts": outcome.coverage.total_candidates,
            "shortlisted_candidates": outcome.coverage.shortlisted_candidates,
            "retrieved_shortlist_candidates": 0,
            "promoted_seed_count": len(alert_seeds),
            "families_with_structural_flags": outcome.coverage.families_with_structural_flags,
            "structurally_flagged_candidates": outcome.coverage.structurally_flagged_candidates,
            "missing_deadline_candidates": outcome.coverage.missing_deadline_candidates,
            "missing_category_candidates": outcome.coverage.missing_category_candidates,
            "missing_outcome_candidates": outcome.coverage.missing_outcome_candidates,
            "missing_family_context_candidates": outcome.coverage.missing_family_context_candidates,
            "rejection_reasons_json": _serialize_rejection_reasons(outcome.rejected),
            "strict_count": len(outcome.tradable),
            "research_count": len(outcome.degraded),
            "skipped_count": outcome.coverage.skipped,
            "heartbeat_sent": 0,
            "created_at": timestamp,
        }
    )
    _persist_alert_seeds(repository, alert_seeds, timestamp)
    return ScanRunResult(
        run_id=run_id,
        status=status,
        degraded_reason=degraded_reason,
        outcome=outcome,
        alert_seeds=alert_seeds,
    )


def scan_board(
    gamma_payload: Sequence[dict[str, Any]],
    clob_payload: Mapping[str, Any] | Sequence[Any],
) -> ScanOutcome:
    events = normalize_events(gamma_payload)
    candidates = normalize_candidates(events, build_book_snapshots(clob_payload))
    return _prefilter(events, candidates)


def _run_live_scan(config: RuntimeConfig) -> ScanOutcome:
    gamma_limit = max(config.gamma_limit, 1)
    raw_events = _fetch_live_events(config.gamma_events_url, gamma_limit)
    events = normalize_events(raw_events)
    books_by_token: dict[str, BookSnapshot] = {}
    for event in events:
        raw_markets = event.get("markets")
        if not isinstance(raw_markets, list):
            continue
        for market in raw_markets:
            if not isinstance(market, dict):
                continue
            token_id = market.get("token_id")
            if not isinstance(token_id, str) or token_id in books_by_token:
                continue
            books_by_token[token_id] = _fetch_live_book(token_id, config.clob_book_url)
    candidates = normalize_candidates(events, books_by_token)
    return _prefilter(events, candidates)


def _fetch_live_events(url: str, limit: int) -> list[dict[str, Any]]:
    try:
        return fetch_events(url=url, limit=limit, active=True, closed=False)
    except TypeError:
        # Support simplified monkeypatch stubs in tests.
        try:
            return fetch_events(url=url, limit=limit)
        except TypeError:
            return fetch_events()


def _fetch_live_book(token_id: str, url: str) -> BookSnapshot:
    try:
        snapshot = fetch_book(token_id, url=url)
    except TypeError:
        # Support simplified monkeypatch stubs that only accept token_id.
        snapshot = fetch_book(token_id)
    except Exception:
        return degraded_snapshot(token_id, "book_fetch_error")
    if isinstance(snapshot, BookSnapshot):
        return snapshot
    return degraded_snapshot(token_id, "book_malformed")


def _prefilter(
    events: Sequence[dict[str, Any]], candidates: Sequence[ScanCandidate]
) -> ScanOutcome:
    tradable: list[ScanCandidate] = []
    degraded: list[ScanCandidate] = []
    rejected: list[tuple[ScanCandidate, str]] = []
    seen_expression_keys: set[str] = set()

    rejected_inactive = 0
    rejected_low_liquidity = 0
    rejected_wide_spread = 0
    rejected_duplicate = 0
    degraded_books = 0

    for candidate in candidates:
        if not candidate.active or candidate.status not in {"open", "active"}:
            rejected_inactive += 1
            rejected.append((candidate, "inactive_or_closed"))
            continue

        if candidate.is_degraded:
            degraded_books += 1
            degraded.append(candidate)
            continue

        liquidity_usd = candidate.liquidity_usd or 0.0
        if liquidity_usd < MIN_LIQUIDITY_USD:
            rejected_low_liquidity += 1
            rejected.append((candidate, "low_liquidity"))
            continue

        spread_bps = candidate.spread_bps
        if spread_bps is None or spread_bps > MAX_SPREAD_BPS:
            rejected_wide_spread += 1
            rejected.append((candidate, "wide_spread"))
            continue

        if candidate.expression_key in seen_expression_keys:
            rejected_duplicate += 1
            rejected.append((candidate, "duplicate_expression"))
            continue

        seen_expression_keys.add(candidate.expression_key)
        tradable.append(candidate)

    total_markets = sum(
        len(event.get("markets", [])) for event in events if isinstance(event.get("markets"), list)
    )
    families_with_structural_flags = len(
        {
            candidate.event_id
            for candidate in candidates
            if candidate.family_summary.structural_flag_count > 0
        }
    )
    structurally_flagged_candidates = sum(
        1 for candidate in candidates if candidate.family_summary.structural_flag_count > 0
    )
    missing_deadline_candidates = sum(1 for candidate in candidates if not candidate.event_end_time)
    missing_category_candidates = sum(1 for candidate in candidates if not candidate.event_category)
    missing_outcome_candidates = sum(1 for candidate in candidates if not candidate.outcome_name)
    missing_family_context_candidates = sum(
        1 for candidate in candidates if candidate.family_summary.sibling_count <= 0
    )
    coverage = ScanCoverage(
        total_events=len(events),
        total_families=len(events),
        total_markets=total_markets,
        total_candidates=len(candidates),
        shortlisted_candidates=len(tradable) + len(degraded),
        tradable_candidates=len(tradable),
        families_with_structural_flags=families_with_structural_flags,
        structurally_flagged_candidates=structurally_flagged_candidates,
        missing_deadline_candidates=missing_deadline_candidates,
        missing_category_candidates=missing_category_candidates,
        missing_outcome_candidates=missing_outcome_candidates,
        missing_family_context_candidates=missing_family_context_candidates,
        rejected_inactive=rejected_inactive,
        rejected_low_liquidity=rejected_low_liquidity,
        rejected_wide_spread=rejected_wide_spread,
        rejected_duplicate=rejected_duplicate,
        degraded_books=degraded_books,
    )
    return ScanOutcome(
        coverage=coverage,
        tradable=tuple(tradable),
        degraded=tuple(degraded),
        rejected=tuple(rejected),
    )


def _dry_outcome() -> ScanOutcome:
    return ScanOutcome(
        coverage=ScanCoverage(
            total_events=0,
            total_families=0,
            total_markets=0,
            total_candidates=0,
            shortlisted_candidates=0,
            tradable_candidates=0,
            families_with_structural_flags=0,
            structurally_flagged_candidates=0,
            missing_deadline_candidates=0,
            missing_category_candidates=0,
            missing_outcome_candidates=0,
            missing_family_context_candidates=0,
            rejected_inactive=0,
            rejected_low_liquidity=0,
            rejected_wide_spread=0,
            rejected_duplicate=0,
            degraded_books=0,
        ),
        tradable=(),
        degraded=(),
        rejected=(),
    )


def _select_judgment_candidates(
    outcome: ScanOutcome,
    *,
    max_candidates: int | None,
) -> tuple[ScanCandidate, ...]:
    return select_judgment_candidates(
        tuple(outcome.tradable) + tuple(outcome.degraded),
        max_candidates=max_candidates,
    )


def _build_alert_seeds(
    run_id: str,
    outcome: ScanOutcome,
    *,
    judgment_seed_inputs: Mapping[str, object],
    evidence_seed_inputs: Mapping[str, object],
    max_judgment_candidates: int | None,
) -> tuple[AlertSeed, ...]:
    seeds: list[AlertSeed] = []
    selected_candidates = _select_judgment_candidates(
        outcome,
        max_candidates=max_judgment_candidates,
    )
    for candidate in selected_candidates:
        judgment_seed = _resolve_judgment_seed(candidate, judgment_seed_inputs)
        evidence_seeds = _resolve_evidence_seeds(candidate, evidence_seed_inputs)
        alert_kind = "scanner_seed_degraded" if candidate.is_degraded else "scanner_seed"
        dedupe_key = f"scanner-seed::{candidate.expression_key}"
        seeds.append(
            AlertSeed(
                id=str(uuid5(NAMESPACE_URL, f"alert::{dedupe_key}")),
                run_id=run_id,
                event_id=candidate.event_id,
                event_title=candidate.event_title,
                event_category=candidate.event_category,
                event_end_time=candidate.event_end_time,
                market_id=candidate.market_id,
                token_id=candidate.token_id,
                condition_id=candidate.condition_id,
                event_slug=candidate.event_slug,
                market_slug=candidate.market_slug,
                question=candidate.question,
                outcome_name=candidate.outcome_name,
                market_link=build_polymarket_market_url(
                    event_slug=candidate.event_slug,
                    market_slug=candidate.market_slug,
                ),
                alert_kind=alert_kind,
                dedupe_key=dedupe_key,
                expression_key=candidate.expression_key,
                expression_summary=candidate.expression_summary,
                rules_text=candidate.rules_text,
                best_bid_cents=candidate.best_bid_cents,
                best_ask_cents=candidate.best_ask_cents,
                mid_cents=candidate.mid_cents,
                last_price_cents=candidate.last_price_cents,
                spread_bps=candidate.spread_bps,
                slippage_bps=candidate.slippage_bps,
                is_degraded=candidate.is_degraded,
                degraded_reason=candidate.degraded_reason,
                family_summary=candidate.family_summary,
                ranking_summary=build_ranking_summary(candidate).as_dict(),
                judgment_seed=judgment_seed,
                evidence_seeds=evidence_seeds,
            )
        )
    return tuple(seeds)


def _persist_alert_seeds(
    repository: RuntimeRepository,
    alert_seeds: Sequence[AlertSeed],
    created_at: str,
) -> None:
    for seed in alert_seeds:
        repository.insert_alert(
            {
                "id": seed.id,
                "run_id": seed.run_id,
                "event_id": seed.event_id,
                "market_id": seed.market_id,
                "token_id": seed.token_id,
                "condition_id": seed.condition_id,
                "alert_kind": seed.alert_kind,
                "delivery_mode": "deferred",
                "status": "seeded",
                "dedupe_key": seed.dedupe_key,
                "spread_bps": seed.spread_bps,
                "slippage_bps": seed.slippage_bps,
                "why_now": seed.expression_summary,
                "created_at": created_at,
            }
        )


def _resolve_judgment_seed(
    candidate: ScanCandidate,
    inputs: Mapping[str, object],
) -> dict[str, Any] | None:
    for key in _seed_lookup_keys(candidate):
        value = inputs.get(key)
        if isinstance(value, Mapping):
            return dict(value)
    return None


def _resolve_evidence_seeds(
    candidate: ScanCandidate,
    inputs: Mapping[str, object],
) -> tuple[dict[str, Any], ...]:
    for key in _seed_lookup_keys(candidate):
        value = inputs.get(key)
        if isinstance(value, Mapping):
            return (dict(value),)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            evidence: list[dict[str, Any]] = []
            for item in value:
                if isinstance(item, Mapping):
                    evidence.append(dict(item))
            if evidence:
                return tuple(evidence)
    return ()


def _seed_lookup_keys(candidate: ScanCandidate) -> tuple[str, ...]:
    keys: list[str] = []
    if candidate.condition_id:
        keys.append(candidate.condition_id)
    keys.extend(
        (
            candidate.expression_key,
            candidate.market_id,
            candidate.token_id,
        )
    )
    return tuple(keys)


def _serialize_rejection_reasons(rejected: Sequence[tuple[ScanCandidate, str]]) -> str:
    payload: list[dict[str, object]] = []
    for candidate, reason in rejected:
        payload.append(
            {
                "event_id": candidate.event_id,
                "market_id": candidate.market_id,
                "condition_id": candidate.condition_id,
                "event_slug": candidate.event_slug,
                "market_slug": candidate.market_slug,
                "question": candidate.question,
                "reason": reason,
            }
        )
    return json.dumps(payload, sort_keys=True)
