from __future__ import annotations

import httpx

from polymarket_alert_bot.scanner.clob_client import fetch_book
from polymarket_alert_bot.scanner.gamma_client import fetch_events, normalize_events


class _FakeResponse:
    def __init__(self, payload, *, status_code: int = 200, raise_http: bool = False):
        self.status_code = status_code
        self._payload = payload
        self._raise_http = raise_http

    def raise_for_status(self) -> None:
        if self._raise_http:
            raise httpx.HTTPStatusError(
                "boom",
                request=httpx.Request("GET", "https://clob.example.test/book"),
                response=httpx.Response(self.status_code),
            )

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, params=None):
        self.calls.append((url, params))
        return _FakeResponse(self.payload)


class _FlakyClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None):
        self.calls.append((url, params))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_fetch_events_requests_open_active_markets() -> None:
    client = _FakeClient([])

    fetch_events(http_client=client, url="https://gamma.example.test/markets", limit=7)

    assert client.calls == [
        (
            "https://gamma.example.test/markets",
            {
                "limit": 7,
                "active": True,
                "closed": False,
                "order": "volume24hr",
                "ascending": False,
            },
        )
    ]


def test_normalize_events_accepts_market_payloads_with_clob_token_ids() -> None:
    raw_market_payload = [
        {
            "id": "market-1",
            "slug": "russia-ukraine-ceasefire-before-gta-vi-554",
            "question": "Russia-Ukraine Ceasefire before GTA VI?",
            "description": "Resolves YES if an official ceasefire agreement is announced before GTA VI release.",
            "active": True,
            "closed": False,
            "conditionId": "0xabc",
            "clobTokenIds": '["token-yes", "token-no"]',
            "liquidity": "64597.4311",
            "events": [
                {
                    "id": "event-1",
                    "slug": "russia-ukraine-ceasefire-before-gta-vi",
                    "title": "Russia-Ukraine Ceasefire before GTA VI",
                    "description": "Event-level description.",
                    "resolutionSource": "Official announcement",
                }
            ],
        }
    ]

    normalized = normalize_events(raw_market_payload)

    assert len(normalized) == 1
    assert normalized[0]["id"] == "event-1"
    assert normalized[0]["slug"] == "russia-ukraine-ceasefire-before-gta-vi"
    assert len(normalized[0]["markets"]) == 1
    market = normalized[0]["markets"][0]
    assert market["id"] == "market-1"
    assert market["token_id"] == "token-yes"
    assert market["status"] == "open"
    assert market["active"] is True


def test_fetch_book_retries_once_on_transient_http_error() -> None:
    import pytest

    client = _FlakyClient(
        [
            httpx.ReadTimeout("timeout"),
            _FakeResponse(
                {
                    "bids": [{"price": "0.40"}],
                    "asks": [{"price": "0.42"}],
                }
            ),
        ]
    )

    snapshot = fetch_book("token-1", http_client=client, url="https://clob.example.test/book")

    assert client.calls == [
        ("https://clob.example.test/book", {"token_id": "token-1"}),
        ("https://clob.example.test/book", {"token_id": "token-1"}),
    ]
    assert snapshot.token_id == "token-1"
    assert snapshot.best_bid == 0.40
    assert snapshot.best_ask == 0.42
    assert snapshot.spread_bps == pytest.approx(487.8048780487807)
    assert snapshot.slippage_bps == pytest.approx(243.90243902439034)
    assert snapshot.is_degraded is False
    assert snapshot.degraded_reason is None


def test_fetch_book_retries_transient_http_status_errors() -> None:
    client = _FlakyClient(
        [
            _FakeResponse({}, status_code=502, raise_http=True),
            _FakeResponse(
                {
                    "bids": [{"price": "0.40"}],
                    "asks": [{"price": "0.42"}],
                }
            ),
        ]
    )

    snapshot = fetch_book("token-1", http_client=client, url="https://clob.example.test/book")

    assert client.calls == [
        ("https://clob.example.test/book", {"token_id": "token-1"}),
        ("https://clob.example.test/book", {"token_id": "token-1"}),
    ]
    assert snapshot.is_degraded is False
    assert snapshot.degraded_reason is None


def test_fetch_book_does_not_retry_non_transient_http_status_errors() -> None:
    client = _FlakyClient(
        [
            _FakeResponse({}, status_code=400, raise_http=True),
            _FakeResponse(
                {
                    "bids": [{"price": "0.40"}],
                    "asks": [{"price": "0.42"}],
                }
            ),
        ]
    )

    snapshot = fetch_book("token-1", http_client=client, url="https://clob.example.test/book")

    assert client.calls == [
        ("https://clob.example.test/book", {"token_id": "token-1"}),
    ]
    assert snapshot.is_degraded is True
    assert snapshot.degraded_reason == "book_fetch_error"


def test_normalize_events_groups_market_rows_under_one_event() -> None:
    raw_market_payload = [
        {
            "id": "market-1",
            "slug": "candidate-a",
            "question": "Candidate A wins?",
            "description": "Market A description.",
            "active": True,
            "closed": False,
            "conditionId": "cond-a",
            "clobTokenIds": '["token-a-yes", "token-a-no"]',
            "liquidity": "64597.4311",
            "events": [
                {
                    "id": "event-1",
                    "slug": "election-2026",
                    "title": "Election 2026",
                    "description": "Event-level description.",
                    "resolutionSource": "Official announcement",
                }
            ],
        },
        {
            "id": "market-2",
            "slug": "candidate-b",
            "question": "Candidate B wins?",
            "description": "Market B description.",
            "active": True,
            "closed": False,
            "conditionId": "cond-b",
            "clobTokenIds": '["token-b-yes", "token-b-no"]',
            "liquidity": "54597.4311",
            "events": [
                {
                    "id": "event-1",
                    "slug": "election-2026",
                    "title": "Election 2026",
                    "description": "Event-level description.",
                    "resolutionSource": "Official announcement",
                }
            ],
        },
    ]

    normalized = normalize_events(raw_market_payload)

    assert len(normalized) == 1
    assert normalized[0]["id"] == "event-1"
    assert normalized[0]["slug"] == "election-2026"
    assert [market["id"] for market in normalized[0]["markets"]] == ["market-1", "market-2"]
