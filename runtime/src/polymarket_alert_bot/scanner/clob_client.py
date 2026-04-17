from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import httpx


DEFAULT_CLOB_BOOK_URL = "https://clob.polymarket.com/book"
DEFAULT_TIMEOUT_SECONDS = 8.0


@dataclass(frozen=True)
class BookSnapshot:
    token_id: str
    best_bid: float | None
    best_ask: float | None
    spread_bps: float | None
    slippage_bps: float | None
    is_degraded: bool
    degraded_reason: str | None


def degraded_snapshot(token_id: str, reason: str) -> BookSnapshot:
    return BookSnapshot(
        token_id=token_id,
        best_bid=None,
        best_ask=None,
        spread_bps=None,
        slippage_bps=None,
        is_degraded=True,
        degraded_reason=reason,
    )


def fetch_book(
    token_id: str,
    http_client: httpx.Client | None = None,
    *,
    url: str = DEFAULT_CLOB_BOOK_URL,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> BookSnapshot:
    close_client = False
    client = http_client
    if client is None:
        client = httpx.Client(timeout=timeout_seconds)
        close_client = True

    try:
        response = client.get(url, params={"token_id": token_id})
        if response.status_code == 404:
            return degraded_snapshot(token_id, "book_missing")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, Mapping):
            return degraded_snapshot(token_id, "book_malformed")
        return snapshot_from_book(token_id, payload)
    finally:
        if close_client:
            client.close()


def build_book_snapshots(payload: Mapping[str, Any] | Sequence[Any]) -> dict[str, BookSnapshot]:
    snapshots: dict[str, BookSnapshot] = {}
    books: Sequence[Any]
    if isinstance(payload, Mapping):
        if isinstance(payload.get("books"), list):
            books = payload["books"]
        else:
            books = []
    elif isinstance(payload, Sequence):
        books = payload
    else:
        books = []

    for raw_book in books:
        if not isinstance(raw_book, Mapping):
            continue
        token_id = _to_token(raw_book.get("token_id"))
        if token_id is None:
            continue
        snapshots[token_id] = snapshot_from_book(token_id, raw_book)
    return snapshots


def snapshot_from_book(token_id: str, payload: Mapping[str, Any]) -> BookSnapshot:
    bids = _extract_prices(payload.get("bids"))
    asks = _extract_prices(payload.get("asks"))
    if not bids or not asks:
        return degraded_snapshot(token_id, "book_missing_side")

    best_bid = max(bids)
    best_ask = min(asks)
    if best_ask < best_bid:
        return degraded_snapshot(token_id, "crossed_book")

    mid = (best_ask + best_bid) / 2.0
    if mid <= 0:
        return degraded_snapshot(token_id, "invalid_mid")

    spread_bps = ((best_ask - best_bid) / mid) * 10_000
    slippage_bps = spread_bps / 2.0
    return BookSnapshot(
        token_id=token_id,
        best_bid=best_bid,
        best_ask=best_ask,
        spread_bps=spread_bps,
        slippage_bps=slippage_bps,
        is_degraded=False,
        degraded_reason=None,
    )


def _extract_prices(levels: Any) -> list[float]:
    if not isinstance(levels, list):
        return []
    prices: list[float] = []
    for level in levels:
        if not isinstance(level, Mapping):
            continue
        price = level.get("price")
        try:
            parsed = float(price)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            prices.append(parsed)
    return prices


def _to_token(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
