from __future__ import annotations

import json

from polymarket_alert_bot.config.settings import load_runtime_config
from polymarket_alert_bot.models.records import SourceRegistry
from polymarket_alert_bot.scanner.board_scan import AlertSeed
from polymarket_alert_bot.scanner.family import CandidateFamilySummary, FamilyMarketSummary
from polymarket_alert_bot.sources.shortlist_retrieval import (
    _build_query_terms,
    _filter_rows,
    retrieve_shortlist_evidence,
)


def test_retrieve_shortlist_evidence_filters_to_candidate_relevant_rows(tmp_path, monkeypatch):
    news_feed = tmp_path / "news-feed.json"
    x_feed = tmp_path / "x-feed.json"
    news_feed.write_text(
        json.dumps(
            [
                {
                    "source_id": "news-a-1",
                    "url": "https://news.example.test/a-1",
                    "claim_snippet": "2026 Live Election polling update favors Candidate A.",
                    "tier": "primary",
                },
                {
                    "source_id": "news-unrelated",
                    "url": "https://news.example.test/unrelated",
                    "claim_snippet": "Snowstorm expected next week.",
                    "tier": "primary",
                },
            ]
        ),
        encoding="utf-8",
    )
    x_feed.write_text(
        json.dumps(
            [
                {
                    "source_id": "x-a-1",
                    "handle": "@polymarket",
                    "url": "https://x.com/polymarket/status/1",
                    "claim_snippet": "Candidate A market repricing after live election update.",
                },
                {
                    "source_id": "x-random",
                    "handle": "@randomtrader",
                    "url": "https://x.com/randomtrader/status/2",
                    "claim_snippet": "Candidate A rumor with no source.",
                },
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("POLYMARKET_ALERT_BOT_NEWS_FEED_URL", str(news_feed))
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_X_FEED_URL", str(x_feed))
    monkeypatch.delenv("POLYMARKET_ALERT_BOT_NEWS_SAMPLES_PATH", raising=False)
    monkeypatch.delenv("POLYMARKET_ALERT_BOT_X_SAMPLES_PATH", raising=False)

    result = retrieve_shortlist_evidence(
        _seed(),
        load_runtime_config(),
        registry=SourceRegistry(version="test", x_handles={"@polymarket"}),
    )

    assert result.degraded_reasons == ()
    assert {item.source_id for item in result.items} == {"news-a-1", "x-a-1"}


def test_retrieve_shortlist_evidence_reports_degraded_sources(tmp_path, monkeypatch):
    missing_news = tmp_path / "missing-news.json"
    missing_x = tmp_path / "missing-x.json"
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_NEWS_FEED_URL", str(missing_news))
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_X_FEED_URL", str(missing_x))
    monkeypatch.delenv("POLYMARKET_ALERT_BOT_NEWS_SAMPLES_PATH", raising=False)
    monkeypatch.delenv("POLYMARKET_ALERT_BOT_X_SAMPLES_PATH", raising=False)

    result = retrieve_shortlist_evidence(
        _seed(),
        load_runtime_config(),
        registry=SourceRegistry(version="test", x_handles={"@polymarket"}),
    )

    assert result.items == ()
    assert "shortlist_news_failed:FileNotFoundError" in result.degraded_reasons
    assert "shortlist_x_failed:FileNotFoundError" in result.degraded_reasons


def test_filter_rows_prefers_newer_evidence_when_scores_tie():
    rows = [
        {
            "source_id": "old",
            "url": "https://news.example.test/old",
            "claim_snippet": "2026 Live Election update for Candidate A.",
            "fetched_at": "2026-04-22T01:00:00Z",
        },
        {
            "source_id": "new",
            "url": "https://news.example.test/new",
            "claim_snippet": "2026 Live Election update for Candidate A.",
            "fetched_at": "2026-04-22T02:00:00Z",
        },
    ]

    filtered = _filter_rows(
        rows,
        phrases=("2026 live election", "candidate a"),
        tokens=("2026", "live", "election"),
    )

    assert [row["source_id"] for row in filtered] == ["new", "old"]


def test_build_query_terms_include_family_and_deadline_context():
    phrases, tokens = _build_query_terms(_seed())

    assert "november 4 2026" in phrases
    assert "will candidate b win in the live board?" in phrases
    assert "2026" in tokens
    assert "live" in tokens


def _seed() -> AlertSeed:
    return AlertSeed(
        id="alert-1",
        run_id="run-1",
        event_id="event-live-election",
        event_title="2026 Live Election",
        event_category="Politics",
        event_end_time="2026-11-04T05:00:00Z",
        market_id="mkt-live-tradable",
        token_id="token-live-tradable",
        condition_id="cond-live-a",
        event_slug="live-election-2026",
        market_slug="candidate-a-wins-live",
        question="Will Candidate A win in the live board?",
        outcome_name="Candidate A",
        market_link="https://polymarket.com/event/live-election-2026/candidate-a-wins-live",
        alert_kind="scanner_seed",
        dedupe_key="scanner-seed::cond-live-a",
        expression_key="event-live-election::candidate-a",
        expression_summary="Will Candidate A win in the live board?",
        rules_text="Resolves YES only if Candidate A is certified as winner.",
        best_bid_cents=49.0,
        best_ask_cents=51.0,
        mid_cents=50.0,
        last_price_cents=50.5,
        spread_bps=400.0,
        slippage_bps=200.0,
        is_degraded=False,
        degraded_reason=None,
        family_summary=CandidateFamilySummary(
            event_id="event-live-election",
            event_slug="live-election-2026",
            event_title="2026 Live Election",
            event_category="Politics",
            event_end_time="2026-11-04T05:00:00Z",
            total_markets=2,
            sibling_count=1,
            sibling_markets=(
                FamilyMarketSummary(
                    market_id="mkt-live-degraded",
                    market_slug="candidate-b-wins-live",
                    question="Will Candidate B win in the live board?",
                    outcome_name="Candidate B",
                    liquidity_usd=6800.0,
                ),
            ),
        ),
        ranking_summary={
            "supported_runtime_domain": True,
            "deadline_available": True,
            "deadline_rank": 1793768400,
            "family_sibling_count": 1,
            "liquidity_usd": 0.0,
            "spread_bps": 400.0,
            "is_degraded": False,
            "missing_deadline": False,
            "missing_category": False,
            "missing_outcome_name": False,
            "missing_family_context": False,
        },
        judgment_seed=None,
        evidence_seeds=(),
    )
