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
    order: str = "volume24hr",
    ascending: bool = False,
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
                    "order": order,
                    "ascending": ascending,
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
        event_created_at = _extract_created_at(event_context, raw_event)
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
                "created_at": event_created_at,
                "rules_text": event_rules_text,
                "scan_sleeves": _merge_scan_sleeves(event_context, raw_event),
                "markets": [],
            }
            normalized_by_event_id[event_id] = normalized_event
            normalized_order.append(event_id)
        else:
            normalized_event["rules_text"] = _merge_rules_text(
                normalized_event.get("rules_text"), event_rules_text
            )
            normalized_event["scan_sleeves"] = _merge_string_lists(
                normalized_event.get("scan_sleeves"),
                _merge_scan_sleeves(event_context, raw_event),
            )
            if not normalized_event.get("slug") and event_slug is not None:
                normalized_event["slug"] = event_slug
            if not normalized_event.get("title") and event_title is not None:
                normalized_event["title"] = event_title
            if not normalized_event.get("category") and event_category is not None:
                normalized_event["category"] = event_category
            if not normalized_event.get("end_time") and event_end_time is not None:
                normalized_event["end_time"] = event_end_time
            if not normalized_event.get("created_at") and event_created_at is not None:
                normalized_event["created_at"] = event_created_at
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
            status = _derive_market_status(raw_market)
            active = bool(raw_market.get("active", False))
            liquidity_usd = _to_float(raw_market.get("liquidity"))
            volume_24h_usd = _extract_volume_24h(raw_market)
            outcome_name = _extract_outcome_name(raw_market)
            last_price = _extract_last_price(raw_market)
            created_at = _extract_created_at(raw_market, event_context, raw_event)
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
            scan_sleeves = _merge_scan_sleeves(raw_market, raw_event, event_context)

            existing_market = next(
                (
                    market
                    for market in normalized_event["markets"]
                    if isinstance(market, dict) and market.get("id") == market_id
                ),
                None,
            )
            if existing_market is None:
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
                        "volume_24h_usd": volume_24h_usd,
                        "created_at": created_at,
                        "scan_sleeves": scan_sleeves,
                        "rules_text": rules_text,
                    }
                )
                continue

            existing_market["scan_sleeves"] = _merge_string_lists(
                existing_market.get("scan_sleeves"),
                scan_sleeves,
            )
            if not existing_market.get("slug") and market_slug is not None:
                existing_market["slug"] = market_slug
            if not existing_market.get("question") and question:
                existing_market["question"] = question
            if existing_market.get("status") in {None, "unknown"} and status != "unknown":
                existing_market["status"] = status
            if not existing_market.get("active") and active:
                existing_market["active"] = active
            if not existing_market.get("token_id") and token_id is not None:
                existing_market["token_id"] = token_id
            if not existing_market.get("condition_id") and condition_id is not None:
                existing_market["condition_id"] = condition_id
            if not existing_market.get("outcome_name") and outcome_name is not None:
                existing_market["outcome_name"] = outcome_name
            if existing_market.get("last_price") is None and last_price is not None:
                existing_market["last_price"] = last_price
            if existing_market.get("liquidity_usd") is None and liquidity_usd is not None:
                existing_market["liquidity_usd"] = liquidity_usd
            if existing_market.get("volume_24h_usd") is None and volume_24h_usd is not None:
                existing_market["volume_24h_usd"] = volume_24h_usd
            if not existing_market.get("created_at") and created_at is not None:
                existing_market["created_at"] = created_at
            existing_market["rules_text"] = _merge_rules_text(
                existing_market.get("rules_text"),
                rules_text,
            )

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


def _extract_created_at(*contexts: dict[str, Any]) -> str | None:
    for context in contexts:
        for field in (
            "createdAt",
            "created_at",
            "createdTime",
            "created_time",
            "publishTime",
            "publish_time",
        ):
            value = _string_or_none(context.get(field))
            if value is not None:
                return value
    return None


def _extract_volume_24h(raw_market: dict[str, Any]) -> float | None:
    for field in (
        "volume24hr",
        "volume24Hr",
        "volume24HR",
        "volume24h",
        "oneDayVolume",
        "one_day_volume",
    ):
        value = _to_float(raw_market.get(field))
        if value is not None:
            return value
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


def _merge_scan_sleeves(*contexts: dict[str, Any]) -> tuple[str, ...]:
    merged: list[str] = []
    for context in contexts:
        raw_sleeves = context.get("_scan_sleeves")
        if not isinstance(raw_sleeves, (list, tuple)):
            continue
        for raw_sleeve in raw_sleeves:
            sleeve = _string_or_none(raw_sleeve)
            if sleeve and sleeve not in merged:
                merged.append(sleeve)
    return tuple(merged)


def _merge_string_lists(
    existing: Any, incoming: Sequence[str] | tuple[str, ...]
) -> tuple[str, ...]:
    merged: list[str] = []
    for group in (existing, incoming):
        if not isinstance(group, (list, tuple)):
            continue
        for raw_value in group:
            value = _string_or_none(raw_value)
            if value and value not in merged:
                merged.append(value)
    return tuple(merged)


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
