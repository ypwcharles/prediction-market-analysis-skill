from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx


DEFAULT_GAMMA_EVENTS_URL = "https://gamma-api.polymarket.com/events"
DEFAULT_TIMEOUT_SECONDS = 10.0
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def fetch_events(
    http_client: httpx.Client | None = None,
    *,
    url: str = DEFAULT_GAMMA_EVENTS_URL,
    limit: int = 200,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> list[dict[str, Any]]:
    close_client = False
    client = http_client
    if client is None:
        client = httpx.Client(timeout=timeout_seconds, headers={"User-Agent": BROWSER_USER_AGENT})
        close_client = True

    try:
        try:
            response = client.get(url, params={"limit": limit})
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            return []
        if not isinstance(payload, list):
            return []
        return [item for item in payload if isinstance(item, dict)]
    finally:
        if close_client:
            client.close()


def normalize_events(raw_events: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for raw_event in raw_events:
        event_id = _string_or_none(raw_event.get("id"))
        event_slug = _string_or_none(raw_event.get("slug"))
        event_title = _string_or_none(raw_event.get("title")) or _string_or_none(raw_event.get("question"))
        event_rules_text = _compose_rules_text(
            raw_event,
            fields=(
                "description",
                "rules",
                "resolution",
                "resolutionCriteria",
                "resolutionSource",
                "resolution_source",
            ),
        )
        if event_id is None:
            continue

        raw_markets = raw_event.get("markets")
        if not isinstance(raw_markets, list):
            continue

        normalized_markets: list[dict[str, Any]] = []
        for raw_market in raw_markets:
            if not isinstance(raw_market, dict):
                continue
            market_id = _string_or_none(raw_market.get("id"))
            if market_id is None:
                continue
            token_id = _extract_token_id(raw_market)
            condition_id = _extract_condition_id(raw_market)
            market_slug = _string_or_none(raw_market.get("slug"))
            question = _string_or_none(raw_market.get("question")) or ""
            status = _string_or_none(raw_market.get("status")) or "unknown"
            active = bool(raw_market.get("active", False))
            liquidity_usd = _to_float(raw_market.get("liquidity"))
            market_rules_text = _compose_rules_text(
                raw_market,
                fields=(
                    "description",
                    "rules",
                    "resolution",
                    "resolutionCriteria",
                    "resolutionSource",
                    "resolution_source",
                ),
            )
            rules_text = _merge_rules_text(event_rules_text, market_rules_text)

            normalized_markets.append(
                {
                    "id": market_id,
                    "slug": market_slug,
                    "question": question,
                    "status": status,
                    "active": active,
                    "token_id": token_id,
                    "condition_id": condition_id,
                    "liquidity_usd": liquidity_usd,
                    "rules_text": rules_text,
                }
            )

        if not normalized_markets:
            continue
        normalized.append(
            {
                "id": event_id,
                "slug": event_slug,
                "title": event_title,
                "rules_text": event_rules_text,
                "markets": normalized_markets,
            }
        )
    return normalized


def _extract_token_id(raw_market: dict[str, Any]) -> str | None:
    direct = _string_or_none(raw_market.get("token_id"))
    if direct is not None:
        return direct

    token_ids = raw_market.get("tokenIds")
    if isinstance(token_ids, list) and token_ids:
        return _string_or_none(token_ids[0])

    outcome_tokens = raw_market.get("outcomeTokens")
    if isinstance(outcome_tokens, list):
        for token in outcome_tokens:
            if not isinstance(token, dict):
                continue
            maybe_id = _string_or_none(token.get("id"))
            if maybe_id is not None:
                return maybe_id
    return None


def _extract_condition_id(raw_market: dict[str, Any]) -> str | None:
    direct = _string_or_none(raw_market.get("condition_id"))
    if direct is not None:
        return direct
    camel = _string_or_none(raw_market.get("conditionId"))
    if camel is not None:
        return camel
    return None


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _compose_rules_text(raw: dict[str, Any], *, fields: tuple[str, ...]) -> str | None:
    lines: list[str] = []
    seen: set[str] = set()
    for field in fields:
        value = raw.get(field)
        if value is None:
            continue
        text = str(value).strip()
        if not text or text in seen:
            continue
        lines.append(text)
        seen.add(text)
    return "\n".join(lines) if lines else None


def _merge_rules_text(*chunks: str | None) -> str | None:
    lines: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        if not chunk:
            continue
        for raw_line in chunk.splitlines():
            line = raw_line.strip()
            if not line or line in seen:
                continue
            lines.append(line)
            seen.add(line)
    return "\n".join(lines) if lines else None
