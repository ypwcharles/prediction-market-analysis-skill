from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
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
from polymarket_alert_bot.scanner.external_anchors import apply_external_anchors
from polymarket_alert_bot.scanner.family import CandidateFamilySummary
from polymarket_alert_bot.scanner.gamma_client import fetch_events, normalize_events
from polymarket_alert_bot.scanner.market_link import build_polymarket_market_url
from polymarket_alert_bot.scanner.normalizer import ScanCandidate, normalize_candidates
from polymarket_alert_bot.scanner.ranking import build_ranking_summary, select_judgment_candidates
from polymarket_alert_bot.sources.feed_loader import load_feed_rows
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
    rejected_one_sided_book: int
    rejected_duplicate: int
    degraded_books: int
    sleeve_input_counts: dict[str, int]
    sleeve_shortlist_counts: dict[str, int]
    external_anchor_degraded_reason: str | None = None

    @property
    def skipped(self) -> int:
        return (
            self.rejected_inactive
            + self.rejected_low_liquidity
            + self.rejected_wide_spread
            + self.rejected_one_sided_book
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
    scan_sleeves: tuple[str, ...] = ()
    volume_24h_usd: float | None = None
    created_at: str | None = None
    external_anchor_cents: float | None = None
    external_anchor_source_id: str | None = None
    external_anchor_url: str | None = None
    external_anchor_gap_cents: float | None = None


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
    external_anchor_payload: Sequence[Mapping[str, object]] | None = None,
    max_judgment_candidates: int | None = None,
) -> ScanRunResult:
    timestamp = datetime.now(UTC).isoformat()
    run_id = str(uuid4())

    outcome = _dry_outcome()
    if gamma_payload is not None:
        outcome = scan_board(
            gamma_payload,
            clob_payload or {"books": []},
            external_anchor_payload=external_anchor_payload,
        )
    elif os.environ.get("POLYMARKET_ALERT_BOT_ENABLE_SCAN") == "1":
        outcome = _run_live_scan(load_runtime_config())

    status = RunStatus.CLEAN.value
    degraded_reason = None
    degraded_reasons: list[str] = []
    if outcome.coverage.degraded_books > 0 and outcome.coverage.total_candidates > 0:
        degraded_reasons.append("executable_checks_partial")
    if outcome.coverage.external_anchor_degraded_reason:
        degraded_reasons.append(outcome.coverage.external_anchor_degraded_reason)
    if degraded_reasons:
        status = RunStatus.DEGRADED.value
        degraded_reason = "; ".join(degraded_reasons)

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
            "sleeve_input_counts_json": json.dumps(
                outcome.coverage.sleeve_input_counts,
                sort_keys=True,
            ),
            "sleeve_shortlist_counts_json": json.dumps(
                outcome.coverage.sleeve_shortlist_counts,
                sort_keys=True,
            ),
            "sleeve_promoted_counts_json": json.dumps(
                count_seed_sleeves(alert_seeds),
                sort_keys=True,
            ),
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
    *,
    external_anchor_payload: Sequence[Mapping[str, object]] | None = None,
    external_anchor_min_gap_cents: float = 5.0,
) -> ScanOutcome:
    events = normalize_events(gamma_payload)
    candidates: Sequence[ScanCandidate] = normalize_candidates(
        events,
        build_book_snapshots(clob_payload),
    )
    candidates = _apply_external_anchor_payload(
        candidates,
        external_anchor_payload,
        min_gap_cents=external_anchor_min_gap_cents,
    )
    return _prefilter(events, candidates)


def _run_live_scan(config: RuntimeConfig) -> ScanOutcome:
    gamma_limit = max(config.gamma_limit, 1)
    raw_events: list[dict[str, Any]] = []
    for sleeve, order, ascending in (
        ("hot_board", "volume24hr", False),
        ("short_dated", "endDate", True),
        ("newly_listed", "createdAt", False),
    ):
        raw_events.extend(
            _tag_scan_sleeve(
                _fetch_live_events(
                    config.gamma_events_url,
                    gamma_limit,
                    order=order,
                    ascending=ascending,
                ),
                sleeve=sleeve,
            )
        )
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
    candidates: Sequence[ScanCandidate] = normalize_candidates(events, books_by_token)
    external_anchor_rows, external_anchor_degraded_reason = _load_external_anchor_rows(config)
    candidates = _apply_external_anchor_payload(
        candidates,
        external_anchor_rows,
        min_gap_cents=config.external_anchor_min_gap_cents,
    )
    outcome = _prefilter(events, candidates)
    if external_anchor_degraded_reason is None:
        return outcome
    return ScanOutcome(
        coverage=replace(
            outcome.coverage,
            external_anchor_degraded_reason=external_anchor_degraded_reason,
        ),
        tradable=outcome.tradable,
        degraded=outcome.degraded,
        rejected=outcome.rejected,
    )


def _load_external_anchor_rows(config: RuntimeConfig) -> tuple[list[dict[str, object]], str | None]:
    source = config.external_anchor_feed_url or config.external_anchor_samples_path
    if source is None:
        return [], None
    try:
        return load_feed_rows(source), None
    except Exception as exc:
        return [], f"external_anchor_feed_failed:{exc.__class__.__name__}"


def _apply_external_anchor_payload(
    candidates: Sequence[ScanCandidate],
    external_anchor_payload: Sequence[Mapping[str, object]] | None,
    *,
    min_gap_cents: float,
) -> tuple[ScanCandidate, ...]:
    if not external_anchor_payload:
        return tuple(candidates)
    return apply_external_anchors(
        candidates,
        external_anchor_payload,
        min_gap_cents=min_gap_cents,
    )


def _fetch_live_events(
    url: str,
    limit: int,
    *,
    order: str,
    ascending: bool,
) -> list[dict[str, Any]]:
    try:
        return fetch_events(
            url=url,
            limit=limit,
            active=True,
            closed=False,
            order=order,
            ascending=ascending,
        )
    except TypeError:
        # Support simplified monkeypatch stubs in tests.
        try:
            return fetch_events(url=url, limit=limit, active=True, closed=False)
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
    rejected_one_sided_book = 0
    rejected_duplicate = 0
    degraded_books = 0

    for candidate in candidates:
        if not candidate.active or candidate.status not in {"open", "active"}:
            rejected_inactive += 1
            rejected.append((candidate, "inactive_or_closed"))
            continue

        if candidate.is_degraded:
            if candidate.degraded_reason == "book_missing_side":
                rejected_one_sided_book += 1
                rejected.append((candidate, "one_sided_book"))
                continue
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
        rejected_one_sided_book=rejected_one_sided_book,
        rejected_duplicate=rejected_duplicate,
        degraded_books=degraded_books,
        sleeve_input_counts=_count_candidate_sleeves(candidates),
        sleeve_shortlist_counts=_count_candidate_sleeves((*tradable, *degraded)),
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
            rejected_one_sided_book=0,
            rejected_duplicate=0,
            degraded_books=0,
            sleeve_input_counts={},
            sleeve_shortlist_counts={},
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
                scan_sleeves=candidate.scan_sleeves,
                volume_24h_usd=candidate.volume_24h_usd,
                created_at=candidate.created_at,
                external_anchor_cents=candidate.external_anchor_cents,
                external_anchor_source_id=candidate.external_anchor_source_id,
                external_anchor_url=candidate.external_anchor_url,
                external_anchor_gap_cents=candidate.external_anchor_gap_cents,
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


def _tag_scan_sleeve(raw_events: Sequence[dict[str, Any]], *, sleeve: str) -> list[dict[str, Any]]:
    tagged: list[dict[str, Any]] = []
    for raw_event in raw_events:
        event = dict(raw_event)
        event["_scan_sleeves"] = _merge_sleeves(event.get("_scan_sleeves"), sleeve)
        raw_markets = event.get("markets")
        if isinstance(raw_markets, list):
            markets: list[dict[str, Any]] = []
            for raw_market in raw_markets:
                if not isinstance(raw_market, dict):
                    continue
                market = dict(raw_market)
                market["_scan_sleeves"] = _merge_sleeves(market.get("_scan_sleeves"), sleeve)
                markets.append(market)
            event["markets"] = markets
        tagged.append(event)
    return tagged


def _merge_sleeves(existing: object, sleeve: str) -> tuple[str, ...]:
    sleeves: list[str] = []
    if isinstance(existing, (list, tuple)):
        for raw_sleeve in existing:
            value = str(raw_sleeve).strip()
            if value and value not in sleeves:
                sleeves.append(value)
    if sleeve not in sleeves:
        sleeves.append(sleeve)
    return tuple(sleeves)


def _count_candidate_sleeves(candidates: Sequence[ScanCandidate]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for sleeve in (
        "hot_board",
        "short_dated",
        "newly_listed",
        "family_inconsistency",
        "anchor_gap",
        "unassigned",
    ):
        counts[sleeve] = 0
    for candidate in candidates:
        sleeves = candidate.scan_sleeves or ("unassigned",)
        for sleeve in sleeves:
            counts[sleeve] = counts.get(sleeve, 0) + 1
    return {key: value for key, value in counts.items() if value > 0}


def count_seed_sleeves(alert_seeds: Sequence[AlertSeed]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for seed in alert_seeds:
        sleeves = seed.scan_sleeves or ("unassigned",)
        for sleeve in sleeves:
            counts[sleeve] = counts.get(sleeve, 0) + 1
    return counts
