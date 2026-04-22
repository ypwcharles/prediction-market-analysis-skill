from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import httpx

DEFAULT_GAMMA_EVENTS_URL = "https://gamma-api.polymarket.com/markets"
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
    active: bool = True,
    closed: bool = False,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> list[dict[str, Any]]:
    close_client = False
    client = http_client
    if client is None:
        client = httpx.Client(timeout=timeout_seconds, headers={"User-Agent": BROWSER_USER_AGENT})
        close_client = True

    try:
        try:
            response = client.get(
                url,
                params={
                    "limit": limit,
                    "active": active,
                    "closed": closed,
                    "order": "volume24hr",
                    "ascending": False,
                },
            )
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
    normalized_by_event_id: dict[str, dict[str, Any]] = {}
    normalized_order: list[str] = []
    for raw_event in raw_events:
        if not isinstance(raw_event, dict):
            continue
        raw_markets = raw_event.get("markets")
        if isinstance(raw_markets, list):
            event_context = raw_event
            event_id = _string_or_none(raw_event.get("id"))
        else:
            event_context = _extract_event_context_from_market(raw_event)
            raw_markets = [raw_event]
            event_id = (
                _string_or_none(event_context.get("id"))
                or _string_or_none(raw_event.get("questionID"))
                or _string_or_none(raw_event.get("id"))
            )
        event_slug = _string_or_none(event_context.get("slug"))
        event_title = _string_or_none(event_context.get("title")) or _string_or_none(
            event_context.get("question")
        )
        event_category = _string_or_none(event_context.get("category")) or _string_or_none(
            raw_event.get("category")
        )
        event_end_time = _extract_event_end_time(event_context, raw_event)
        event_rules_text = _compose_rules_text(
            event_context,
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

        if not isinstance(raw_markets, list):
            continue

        normalized_event = normalized_by_event_id.get(event_id)
        if normalized_event is None:
            normalized_event = {
                "id": event_id,
                "slug": event_slug,
                "title": event_title,
                "category": event_category,
                "end_time": event_end_time,
                "rules_text": event_rules_text,
                "markets": [],
            }
            normalized_by_event_id[event_id] = normalized_event
            normalized_order.append(event_id)
        else:
            normalized_event["rules_text"] = _merge_rules_text(
                normalized_event.get("rules_text"), event_rules_text
            )
            if not normalized_event.get("slug") and event_slug is not None:
                normalized_event["slug"] = event_slug
            if not normalized_event.get("title") and event_title is not None:
                normalized_event["title"] = event_title
            if not normalized_event.get("category") and event_category is not None:
                normalized_event["category"] = event_category
            if not normalized_event.get("end_time") and event_end_time is not None:
                normalized_event["end_time"] = event_end_time

        existing_market_ids = {
            market.get("id")
            for market in normalized_event["markets"]
            if isinstance(market, dict) and market.get("id") is not None
        }
        for raw_market in raw_markets:
            if not isinstance(raw_market, dict):
                continue
            market_id = _string_or_none(raw_market.get("id"))
            if market_id is None or market_id in existing_market_ids:
                continue
            token_id = _extract_token_id(raw_market)
            condition_id = _extract_condition_id(raw_market)
            market_slug = _string_or_none(raw_market.get("slug"))
            question = _string_or_none(raw_market.get("question")) or ""
            status = _derive_market_status(raw_market)
            active = bool(raw_market.get("active", False))
            liquidity_usd = _to_float(raw_market.get("liquidity"))
            outcome_name = _extract_outcome_name(raw_market)
            last_price = _extract_last_price(raw_market)
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

            normalized_event["markets"].append(
                {
                    "id": market_id,
                    "slug": market_slug,
                    "question": question,
                    "status": status,
                    "active": active,
                    "token_id": token_id,
                    "condition_id": condition_id,
                    "outcome_name": outcome_name,
                    "last_price": last_price,
                    "liquidity_usd": liquidity_usd,
                    "rules_text": rules_text,
                }
            )
            existing_market_ids.add(market_id)

    return [
        normalized_by_event_id[event_id]
        for event_id in normalized_order
        if normalized_by_event_id[event_id].get("markets")
    ]


def _extract_token_id(raw_market: dict[str, Any]) -> str | None:
    direct = _string_or_none(raw_market.get("token_id"))
    if direct is not None:
        return direct

    token_ids = _parse_string_list(raw_market.get("tokenIds"))
    if token_ids:
        return token_ids[0]

    clob_token_ids = _parse_string_list(raw_market.get("clobTokenIds"))
    if clob_token_ids:
        return clob_token_ids[0]

    outcome_tokens = raw_market.get("outcomeTokens")
    if isinstance(outcome_tokens, list):
        for token in outcome_tokens:
            if not isinstance(token, dict):
                continue
            maybe_id = _string_or_none(token.get("id"))
            if maybe_id is not None:
                return maybe_id
    return None


def _extract_event_context_from_market(raw_market: dict[str, Any]) -> dict[str, Any]:
    raw_events = raw_market.get("events")
    if isinstance(raw_events, list):
        for raw_event in raw_events:
            if isinstance(raw_event, dict):
                return raw_event
    return raw_market


def _derive_market_status(raw_market: dict[str, Any]) -> str:
    explicit = _string_or_none(raw_market.get("status"))
    if explicit is not None:
        return explicit.lower()
    closed = raw_market.get("closed")
    if isinstance(closed, bool):
        return "closed" if closed else "open"
    if bool(raw_market.get("active", False)):
        return "open"
    return "unknown"


def _parse_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [item for item in (_string_or_none(entry) for entry in value) if item]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return [item for item in (_string_or_none(entry) for entry in parsed) if item]
    return []


def _extract_condition_id(raw_market: dict[str, Any]) -> str | None:
    direct = _string_or_none(raw_market.get("condition_id"))
    if direct is not None:
        return direct
    camel = _string_or_none(raw_market.get("conditionId"))
    if camel is not None:
        return camel
    return None


def _extract_event_end_time(event_context: dict[str, Any], raw_event: dict[str, Any]) -> str | None:
    for field in (
        "endDate",
        "end_date",
        "endTime",
        "end_time",
        "endTimestamp",
        "end_timestamp",
    ):
        event_value = _string_or_none(event_context.get(field))
        if event_value is not None:
            return event_value
        raw_value = _string_or_none(raw_event.get(field))
        if raw_value is not None:
            return raw_value
    return None


def _extract_outcome_name(raw_market: dict[str, Any]) -> str | None:
    for field in ("outcome_name", "outcomeName", "outcome", "shortName", "groupItemTitle"):
        value = _string_or_none(raw_market.get(field))
        if value is not None:
            return value

    outcomes = _parse_string_list(raw_market.get("outcomes"))
    if outcomes:
        return outcomes[0]

    outcome_tokens = raw_market.get("outcomeTokens")
    if isinstance(outcome_tokens, list):
        for token in outcome_tokens:
            if not isinstance(token, dict):
                continue
            for field in ("outcome", "title", "name", "label"):
                value = _string_or_none(token.get(field))
                if value is not None:
                    return value
    return None


def _extract_last_price(raw_market: dict[str, Any]) -> float | None:
    for field in (
        "lastTradePrice",
        "last_trade_price",
        "lastPrice",
        "last_price",
        "price",
    ):
        value = _to_float(raw_market.get(field))
        if value is not None:
            return value
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
