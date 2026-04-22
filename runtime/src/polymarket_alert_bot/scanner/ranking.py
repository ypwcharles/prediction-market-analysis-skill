from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from polymarket_alert_bot.scanner.normalizer import ScanCandidate

UNKNOWN_DEADLINE_RANK = 2**62


@dataclass(frozen=True)
class CandidateRankingSummary:
    supported_runtime_domain: bool
    deadline_available: bool
    deadline_rank: int
    family_sibling_count: int
    liquidity_usd: float
    spread_bps: float | None
    is_degraded: bool
    missing_deadline: bool
    missing_category: bool
    missing_outcome_name: bool
    missing_family_context: bool

    def priority_key(self, *, market_id: str) -> tuple[int, int, int, int, float, float, str]:
        spread_penalty = self.spread_bps if self.spread_bps is not None else 1_000_000.0
        return (
            1 if self.is_degraded else 0,
            0 if self.supported_runtime_domain else 1,
            self.deadline_rank,
            -self.family_sibling_count,
            -self.liquidity_usd,
            spread_penalty,
            market_id,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "supported_runtime_domain": self.supported_runtime_domain,
            "deadline_available": self.deadline_available,
            "deadline_rank": self.deadline_rank,
            "family_sibling_count": self.family_sibling_count,
            "liquidity_usd": self.liquidity_usd,
            "spread_bps": self.spread_bps,
            "is_degraded": self.is_degraded,
            "missing_deadline": self.missing_deadline,
            "missing_category": self.missing_category,
            "missing_outcome_name": self.missing_outcome_name,
            "missing_family_context": self.missing_family_context,
        }


def candidate_priority_key(
    candidate: ScanCandidate,
) -> tuple[int, int, int, int, float, float, str]:
    return build_ranking_summary(candidate).priority_key(market_id=candidate.market_id)


def select_judgment_candidates(
    candidates: Sequence[ScanCandidate],
    *,
    max_candidates: int | None,
) -> tuple[ScanCandidate, ...]:
    ordered_candidates = tuple(sorted(candidates, key=candidate_priority_key))
    if max_candidates is None or max_candidates <= 0:
        return ordered_candidates
    return ordered_candidates[:max_candidates]


def build_ranking_summary(candidate: ScanCandidate) -> CandidateRankingSummary:
    deadline_rank = _deadline_rank(candidate.event_end_time)
    return CandidateRankingSummary(
        supported_runtime_domain=_is_supported_runtime_domain(candidate),
        deadline_available=deadline_rank != UNKNOWN_DEADLINE_RANK,
        deadline_rank=deadline_rank,
        family_sibling_count=candidate.family_summary.sibling_count,
        liquidity_usd=candidate.liquidity_usd or 0.0,
        spread_bps=candidate.spread_bps,
        is_degraded=candidate.is_degraded,
        missing_deadline=not candidate.event_end_time,
        missing_category=not candidate.event_category,
        missing_outcome_name=not candidate.outcome_name,
        missing_family_context=candidate.family_summary.sibling_count <= 0,
    )


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
