from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
import os
from typing import Any
from uuid import uuid4

from polymarket_alert_bot.config.settings import RuntimePaths
from polymarket_alert_bot.models.enums import RunStatus, RunType
from polymarket_alert_bot.scanner.clob_client import BookSnapshot, build_book_snapshots, fetch_book
from polymarket_alert_bot.scanner.gamma_client import fetch_events, normalize_events
from polymarket_alert_bot.scanner.normalizer import ScanCandidate, normalize_candidates
from polymarket_alert_bot.storage.db import connect_db
from polymarket_alert_bot.storage.migrations import apply_migrations
from polymarket_alert_bot.storage.repositories import RuntimeRepository


MIN_LIQUIDITY_USD = 1_000.0
MAX_SPREAD_BPS = 800.0


@dataclass(frozen=True)
class ScanCoverage:
    total_events: int
    total_markets: int
    total_candidates: int
    tradable_candidates: int
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


def run_scan(
    paths: RuntimePaths,
    *,
    gamma_payload: Sequence[dict[str, Any]] | None = None,
    clob_payload: Mapping[str, Any] | Sequence[Any] | None = None,
) -> str:
    timestamp = datetime.now(UTC).isoformat()
    run_id = str(uuid4())

    outcome = _dry_outcome()
    if gamma_payload is not None:
        outcome = scan_board(gamma_payload, clob_payload or {"books": []})
    elif os.environ.get("POLYMARKET_ALERT_BOT_ENABLE_SCAN") == "1":
        outcome = _run_live_scan()

    status = RunStatus.CLEAN.value
    degraded_reason = None
    if outcome.coverage.degraded_books > 0 and outcome.coverage.total_candidates > 0:
        status = RunStatus.DEGRADED.value
        degraded_reason = "executable_checks_partial"

    conn = connect_db(paths.db_path)
    apply_migrations(conn)
    RuntimeRepository(conn).upsert_run(
        {
            "id": run_id,
            "run_type": RunType.SCAN.value,
            "status": status,
            "started_at": timestamp,
            "finished_at": timestamp,
            "degraded_reason": degraded_reason,
            "scanned_events": outcome.coverage.total_events,
            "scanned_contracts": outcome.coverage.total_candidates,
            "strict_count": len(outcome.tradable),
            "research_count": len(outcome.degraded),
            "skipped_count": outcome.coverage.skipped,
            "heartbeat_sent": 0,
            "created_at": timestamp,
        }
    )
    return run_id


def scan_board(
    gamma_payload: Sequence[dict[str, Any]],
    clob_payload: Mapping[str, Any] | Sequence[Any],
) -> ScanOutcome:
    events = normalize_events(gamma_payload)
    candidates = normalize_candidates(events, build_book_snapshots(clob_payload))
    return _prefilter(events, candidates)


def _run_live_scan() -> ScanOutcome:
    raw_events = fetch_events()
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
            books_by_token[token_id] = fetch_book(token_id)
    candidates = normalize_candidates(events, books_by_token)
    return _prefilter(events, candidates)


def _prefilter(events: Sequence[dict[str, Any]], candidates: Sequence[ScanCandidate]) -> ScanOutcome:
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

    total_markets = sum(len(event.get("markets", [])) for event in events if isinstance(event.get("markets"), list))
    coverage = ScanCoverage(
        total_events=len(events),
        total_markets=total_markets,
        total_candidates=len(candidates),
        tradable_candidates=len(tradable),
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
            total_markets=0,
            total_candidates=0,
            tradable_candidates=0,
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
