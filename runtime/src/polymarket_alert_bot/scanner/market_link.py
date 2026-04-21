from __future__ import annotations

from urllib.parse import quote

POLYMARKET_EVENT_BASE_URL = "https://polymarket.com/event"


def build_polymarket_market_url(*, event_slug: str | None, market_slug: str | None) -> str | None:
    normalized_event_slug = _normalized_slug(event_slug)
    normalized_market_slug = _normalized_slug(market_slug)

    if normalized_event_slug and normalized_market_slug:
        return (
            f"{POLYMARKET_EVENT_BASE_URL}/"
            f"{quote(normalized_event_slug, safe='-_.~')}/"
            f"{quote(normalized_market_slug, safe='-_.~')}"
        )
    if normalized_event_slug:
        return f"{POLYMARKET_EVENT_BASE_URL}/{quote(normalized_event_slug, safe='-_.~')}"
    if normalized_market_slug:
        return f"{POLYMARKET_EVENT_BASE_URL}/{quote(normalized_market_slug, safe='-_.~')}"
    return None


def _normalized_slug(value: str | None) -> str | None:
    if value is None:
        return None
    slug = value.strip().strip("/")
    return slug or None
