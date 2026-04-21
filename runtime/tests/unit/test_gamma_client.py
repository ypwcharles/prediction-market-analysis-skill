from __future__ import annotations

from polymarket_alert_bot.scanner.gamma_client import fetch_events, normalize_events


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, params=None):
        self.calls.append((url, params))
        return _FakeResponse(self.payload)


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
