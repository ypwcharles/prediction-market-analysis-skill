from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace

from polymarket_alert_bot.scanner.normalizer import ScanCandidate

ANCHOR_GAP_SLEEVE = "anchor_gap"

_ANCHOR_CENT_FIELDS = (
    "external_anchor_cents",
    "external_probability_cents",
    "external_fair_cents",
    "anchor_cents",
    "anchor_probability_cents",
    "probability_cents",
    "fair_cents",
)
_SOURCE_ID_FIELDS = ("source_id", "source", "platform", "venue", "name")
_URL_FIELDS = ("url", "market_url", "source_url")


def apply_external_anchors(
    candidates: Sequence[ScanCandidate],
    rows: Sequence[Mapping[str, object]],
    *,
    min_gap_cents: float,
) -> tuple[ScanCandidate, ...]:
    anchors: list[dict[str, str | float]] = []
    for row in rows:
        anchor = _normalize_anchor_row(row)
        if anchor is not None:
            anchors.append(anchor)
    if not anchors:
        return tuple(candidates)

    enriched: list[ScanCandidate] = []
    for candidate in candidates:
        matched_anchor = _match_anchor(candidate, anchors)
        if matched_anchor is None:
            enriched.append(candidate)
            continue

        external_anchor_cents = float(matched_anchor["external_anchor_cents"])
        market_anchor_cents = _market_anchor_cents(candidate)
        external_anchor_gap_cents = (
            external_anchor_cents - market_anchor_cents if market_anchor_cents is not None else None
        )
        scan_sleeves = candidate.scan_sleeves
        if (
            external_anchor_gap_cents is not None
            and abs(external_anchor_gap_cents) >= min_gap_cents
        ):
            scan_sleeves = _merge_sleeves(scan_sleeves, ANCHOR_GAP_SLEEVE)

        enriched.append(
            replace(
                candidate,
                external_anchor_cents=external_anchor_cents,
                external_anchor_source_id=_string_field(matched_anchor, "source_id"),
                external_anchor_url=_string_field(matched_anchor, "url"),
                external_anchor_gap_cents=external_anchor_gap_cents,
                scan_sleeves=scan_sleeves,
            )
        )
    return tuple(enriched)


def _normalize_anchor_row(row: Mapping[str, object]) -> dict[str, str | float] | None:
    external_anchor_cents = _first_probability_cents(row, _ANCHOR_CENT_FIELDS)
    if external_anchor_cents is None:
        return None

    anchor: dict[str, str | float] = {"external_anchor_cents": external_anchor_cents}
    for key in (
        "condition_id",
        "conditionId",
        "market_id",
        "token_id",
        "tokenId",
        "clob_token_id",
        "expression_key",
        "event_slug",
        "market_slug",
        "slug",
        "polymarket_condition_id",
        "polymarket_market_id",
        "polymarket_token_id",
        "polymarket_event_slug",
        "polymarket_market_slug",
    ):
        value = _text_or_none(row.get(key))
        if value is not None:
            anchor[key] = value

    source_id = _first_text(row, _SOURCE_ID_FIELDS)
    if source_id is not None:
        anchor["source_id"] = source_id
    url = _first_text(row, _URL_FIELDS)
    if url is not None:
        anchor["url"] = url
    return anchor


def _match_anchor(
    candidate: ScanCandidate,
    anchors: Sequence[Mapping[str, str | float]],
) -> Mapping[str, str | float] | None:
    for anchor in anchors:
        if _matches_any(
            candidate.condition_id,
            anchor,
            ("condition_id", "conditionId", "polymarket_condition_id"),
        ):
            return anchor
        if _matches_any(candidate.market_id, anchor, ("market_id", "polymarket_market_id")):
            return anchor
        if _matches_any(
            candidate.token_id,
            anchor,
            ("token_id", "tokenId", "clob_token_id", "polymarket_token_id"),
        ):
            return anchor
        if _matches_any(candidate.expression_key, anchor, ("expression_key",)):
            return anchor

        event_slug = _anchor_text(anchor, "event_slug", "polymarket_event_slug")
        market_slug = _anchor_text(anchor, "market_slug", "polymarket_market_slug", "slug")
        if (
            event_slug is not None
            and market_slug is not None
            and _same_text(candidate.event_slug, event_slug)
            and _same_text(candidate.market_slug, market_slug)
        ):
            return anchor
    return None


def _matches_any(
    candidate_value: str | None, anchor: Mapping[str, object], keys: Sequence[str]
) -> bool:
    if candidate_value is None:
        return False
    return any(_same_text(candidate_value, _anchor_text(anchor, key)) for key in keys)


def _market_anchor_cents(candidate: ScanCandidate) -> float | None:
    for value in (candidate.mid_cents, candidate.best_ask_cents, candidate.last_price_cents):
        if value is not None:
            return value
    return None


def _merge_sleeves(existing: Sequence[str], sleeve: str) -> tuple[str, ...]:
    sleeves = [existing_sleeve for existing_sleeve in existing if existing_sleeve != "unassigned"]
    if sleeve not in sleeves:
        sleeves.append(sleeve)
    return tuple(sleeves)


def _first_probability_cents(
    row: Mapping[str, object],
    keys: Sequence[str],
) -> float | None:
    for key in keys:
        cents = _to_probability_cents(row.get(key))
        if cents is not None:
            return cents
    return None


def _first_text(row: Mapping[str, object], keys: Sequence[str]) -> str | None:
    for key in keys:
        value = _text_or_none(row.get(key))
        if value is not None:
            return value
    return None


def _string_field(anchor: Mapping[str, object], key: str) -> str | None:
    value = anchor.get(key)
    return value if isinstance(value, str) else None


def _anchor_text(anchor: Mapping[str, object], *keys: str) -> str | None:
    for key in keys:
        value = _text_or_none(anchor.get(key))
        if value is not None:
            return value
    return None


def _same_text(left: str | None, right: str | None) -> bool:
    if left is None or right is None:
        return False
    return left.strip().casefold() == right.strip().casefold()


def _text_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_probability_cents(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        raw_value = value.strip()
        if not raw_value:
            return None
        is_percent = raw_value.endswith("%")
        if is_percent:
            raw_value = raw_value[:-1]
        try:
            numeric = float(raw_value)
        except ValueError:
            return None
        if is_percent:
            return round(numeric, 4)
    elif isinstance(value, (int, float)):
        numeric = float(value)
    else:
        return None

    if 0.0 <= numeric <= 1.0:
        return round(numeric * 100.0, 4)
    if 1.0 < numeric <= 100.0:
        return round(numeric, 4)
    return None
