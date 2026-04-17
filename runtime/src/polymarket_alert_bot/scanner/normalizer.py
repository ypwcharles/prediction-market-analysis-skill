from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from polymarket_alert_bot.scanner.clob_client import BookSnapshot, degraded_snapshot


@dataclass(frozen=True)
class ScanCandidate:
    event_id: str
    market_id: str
    token_id: str
    event_slug: str | None
    market_slug: str | None
    question: str
    status: str
    active: bool
    liquidity_usd: float | None
    spread_bps: float | None
    slippage_bps: float | None
    is_degraded: bool
    degraded_reason: str | None
    expression_summary: str
    expression_key: str


def normalize_candidates(
    events: Sequence[Mapping[str, object]],
    books_by_token: Mapping[str, BookSnapshot],
) -> list[ScanCandidate]:
    candidates: list[ScanCandidate] = []
    for event in events:
        event_id = _require_str(event.get("id"))
        if event_id is None:
            continue
        event_slug = _optional_str(event.get("slug"))
        raw_markets = event.get("markets")
        if not isinstance(raw_markets, list):
            continue

        for market in raw_markets:
            if not isinstance(market, Mapping):
                continue
            market_id = _require_str(market.get("id"))
            token_id = _require_str(market.get("token_id"))
            if market_id is None or token_id is None:
                continue

            question = _optional_str(market.get("question")) or ""
            status = (_optional_str(market.get("status")) or "unknown").lower()
            active = bool(market.get("active", False))
            market_slug = _optional_str(market.get("slug"))
            liquidity_usd = _to_float(market.get("liquidity_usd"))

            snapshot = books_by_token.get(token_id)
            if snapshot is None:
                snapshot = degraded_snapshot(token_id, "book_missing")
            expression_summary = _build_expression_summary(question, market_slug)
            expression_key = _build_expression_key(event_slug, expression_summary)

            candidates.append(
                ScanCandidate(
                    event_id=event_id,
                    market_id=market_id,
                    token_id=token_id,
                    event_slug=event_slug,
                    market_slug=market_slug,
                    question=question,
                    status=status,
                    active=active,
                    liquidity_usd=liquidity_usd,
                    spread_bps=snapshot.spread_bps,
                    slippage_bps=snapshot.slippage_bps,
                    is_degraded=snapshot.is_degraded,
                    degraded_reason=snapshot.degraded_reason,
                    expression_summary=expression_summary,
                    expression_key=expression_key,
                )
            )
    return candidates


def _build_expression_summary(question: str, market_slug: str | None) -> str:
    if question.strip():
        return question.strip()
    return (market_slug or "unknown-expression").strip()


def _build_expression_key(event_slug: str | None, expression_summary: str) -> str:
    event_piece = (event_slug or "unknown-event").strip().lower()
    summary_piece = " ".join(expression_summary.split()).lower()
    return f"{event_piece}::{summary_piece}"


def _require_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_str(value: object) -> str | None:
    return _require_str(value)


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
