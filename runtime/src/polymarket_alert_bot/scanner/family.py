from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class FamilyMarketSummary:
    market_id: str
    market_slug: str | None
    question: str
    outcome_name: str | None
    liquidity_usd: float | None

    def as_dict(self) -> dict[str, object]:
        return {
            "market_id": self.market_id,
            "market_slug": self.market_slug,
            "question": self.question,
            "outcome_name": self.outcome_name,
            "liquidity_usd": self.liquidity_usd,
        }


@dataclass(frozen=True)
class CandidateFamilySummary:
    event_id: str
    event_slug: str | None
    event_title: str | None
    event_category: str | None
    event_end_time: str | None
    total_markets: int
    sibling_count: int
    sibling_markets: tuple[FamilyMarketSummary, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "event_slug": self.event_slug,
            "event_title": self.event_title,
            "event_category": self.event_category,
            "event_end_time": self.event_end_time,
            "total_markets": self.total_markets,
            "sibling_count": self.sibling_count,
            "sibling_markets": [market.as_dict() for market in self.sibling_markets],
        }


def build_family_summary(
    event: Mapping[str, object],
    *,
    focus_market_id: str,
    sibling_limit: int = 3,
) -> CandidateFamilySummary:
    raw_markets = event.get("markets")
    markets = raw_markets if isinstance(raw_markets, list) else []
    siblings: list[FamilyMarketSummary] = []
    for raw_market in markets:
        if not isinstance(raw_market, Mapping):
            continue
        market_id = _optional_str(raw_market.get("id"))
        if market_id is None or market_id == focus_market_id:
            continue
        siblings.append(
            FamilyMarketSummary(
                market_id=market_id,
                market_slug=_optional_str(raw_market.get("slug")),
                question=_optional_str(raw_market.get("question")) or "",
                outcome_name=_optional_str(raw_market.get("outcome_name")),
                liquidity_usd=_to_float(raw_market.get("liquidity_usd")),
            )
        )
    siblings.sort(key=lambda item: (-(item.liquidity_usd or 0.0), item.market_id))
    return CandidateFamilySummary(
        event_id=_optional_str(event.get("id")) or "unknown-event",
        event_slug=_optional_str(event.get("slug")),
        event_title=_optional_str(event.get("title")),
        event_category=_optional_str(event.get("category")),
        event_end_time=_optional_str(event.get("end_time")),
        total_markets=len(markets),
        sibling_count=len(siblings),
        sibling_markets=tuple(siblings[: max(sibling_limit, 0)]),
    )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
