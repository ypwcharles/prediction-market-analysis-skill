from __future__ import annotations

import json
from pathlib import Path

import httpx

from polymarket_alert_bot.sources.news_client import NewsClient
from polymarket_alert_bot.sources.x_client import XClient


def test_news_client_fetch_items_from_local_feed_preserves_row_timestamps(tmp_path: Path) -> None:
    feed_path = tmp_path / "news-feed.json"
    feed_path.write_text(
        json.dumps(
            [
                {
                    "source_id": "reuters_001",
                    "url": "https://www.reuters.com/world/example-news-1",
                    "claim_snippet": "Reuters says talks resumed.",
                    "tier": "primary",
                    "fetched_at": "2026-04-18T01:02:03Z",
                }
            ]
        ),
        encoding="utf-8",
    )

    items = NewsClient().fetch_items(feed_path)

    assert len(items) == 1
    assert items[0].source_id == "reuters_001"
    assert items[0].fetched_at == "2026-04-18T01:02:03Z"


def test_news_client_fetch_items_from_remote_feed() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=[
                {
                    "source_id": "ap_001",
                    "url": "https://apnews.com/story/example",
                    "claim_snippet": "AP says talks paused.",
                    "tier": "primary",
                }
            ],
        )
    )
    with httpx.Client(transport=transport) as client:
        items = NewsClient().fetch_items("https://feeds.example.test/news.json", http_client=client)

    assert len(items) == 1
    assert items[0].source_id == "ap_001"
    assert items[0].url == "https://apnews.com/story/example"


def test_x_client_fetch_items_filters_to_allowlisted_handles(tmp_path: Path) -> None:
    feed_path = tmp_path / "x-feed.json"
    feed_path.write_text(
        json.dumps(
            [
                {
                    "source_id": "post-1",
                    "handle": "@polymarket",
                    "url": "https://x.com/polymarket/status/1",
                    "claim_snippet": "Polymarket posted a market update.",
                },
                {
                    "source_id": "post-2",
                    "handle": "@randomtrader",
                    "url": "https://x.com/randomtrader/status/2",
                    "claim_snippet": "Random trader posted a rumor.",
                },
            ]
        ),
        encoding="utf-8",
    )

    items = XClient().fetch_items(feed_path, allowed_handles={"@polymarket"})

    assert len(items) == 1
    assert items[0].source_id == "post-1"
    assert items[0].url == "https://x.com/polymarket/status/1"


def test_x_client_extract_handle_from_url_when_feed_has_no_explicit_handle() -> None:
    handle = XClient.extract_handle(
        {
            "source_id": "post-1",
            "url": "https://x.com/Polymarket/status/123456789",
            "claim_snippet": "Account posted a signal.",
        }
    )

    assert handle == "@polymarket"
