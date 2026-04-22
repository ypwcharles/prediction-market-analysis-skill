from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import datetime

from polymarket_alert_bot.scanner.normalizer import ScanCandidate

UNKNOWN_DEADLINE_RANK = 2**62


def candidate_priority_key(
    candidate: ScanCandidate,
) -> tuple[int, int, int, int, float, float, str]:
    liquidity = candidate.liquidity_usd or 0.0
    spread_penalty = candidate.spread_bps if candidate.spread_bps is not None else 1_000_000.0
    degraded_rank = 1 if candidate.is_degraded else 0
    domain_rank = 0 if _is_supported_runtime_domain(candidate) else 1
    deadline_rank = _deadline_rank(candidate.event_end_time)
    family_rank = -candidate.family_summary.sibling_count
    return (
        degraded_rank,
        domain_rank,
        deadline_rank,
        family_rank,
        -liquidity,
        spread_penalty,
        candidate.market_id,
    )


def select_judgment_candidates(
    candidates: Sequence[ScanCandidate],
    *,
    max_candidates: int | None,
) -> tuple[ScanCandidate, ...]:
    ordered_candidates = tuple(sorted(candidates, key=candidate_priority_key))
    if max_candidates is None or max_candidates <= 0:
        return ordered_candidates
    return ordered_candidates[:max_candidates]


def _deadline_rank(event_end_time: str | None) -> int:
    if not event_end_time:
        return UNKNOWN_DEADLINE_RANK
    try:
        return int(datetime.fromisoformat(event_end_time.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return UNKNOWN_DEADLINE_RANK


def _is_supported_runtime_domain(candidate: ScanCandidate) -> bool:
    text = " ".join(
        filter(
            None,
            [
                candidate.event_title or "",
                candidate.question,
                candidate.rules_text or "",
                candidate.event_category or "",
            ],
        )
    ).lower()
    sports_markers = (
        "nba",
        "nfl",
        "mlb",
        "nhl",
        "world cup",
        "premier league",
        "uefa",
        "lineup",
        "injury report",
    )
    crypto_markers = (
        "bitcoin",
        "btc",
        "ethereum",
        "eth",
        "solana",
        "sol",
        "crypto",
        "etf",
        "on-chain",
    )
    politics_macro_markers = (
        "president",
        "election",
        "ceasefire",
        "taiwan",
        "trump",
        "fed",
        "tariff",
        "senate",
        "house",
        "ukraine",
        "china",
        "court",
        "cpi",
        "inflation",
        "rate cut",
    )
    return any(
        _text_matches_marker(text, marker)
        for marker in sports_markers + crypto_markers + politics_macro_markers
    )


def _text_matches_marker(text: str, marker: str) -> bool:
    if " " in marker or "-" in marker:
        return marker in text
    return re.search(rf"\b{re.escape(marker)}\b", text) is not None
