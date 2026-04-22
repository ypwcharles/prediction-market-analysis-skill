from __future__ import annotations

import json

from polymarket_alert_bot.scanner.board_scan import AlertSeed
from polymarket_alert_bot.scanner.family import CandidateFamilySummary, FamilyMarketSummary
from polymarket_alert_bot.sources.evidence_enricher import EvidenceItem
from polymarket_alert_bot.sources.semantic_relevance import (
    ParseError,
    SemanticRelevanceAdapter,
    parse_semantic_relevance_result,
)


def test_parse_semantic_relevance_result_accepts_decision_aliases() -> None:
    parsed = parse_semantic_relevance_result(
        {
            "items": [
                {
                    "source_id": "wire-1",
                    "relevance": "settlement relevant",
                    "stance": "conflicts",
                }
            ],
            "kept_source_ids": ["wire-1"],
        }
    )

    assert parsed.kept_source_ids == ["wire-1"]
    assert parsed.decisions[0].keep is True
    assert parsed.decisions[0].conflict_status == "active"


def test_parse_semantic_relevance_result_preserves_unset_keep_without_verdict() -> None:
    parsed = parse_semantic_relevance_result(
        {
            "items": [
                {
                    "source_id": "wire-1",
                    "stance": "supports",
                }
            ],
        }
    )

    assert parsed.decisions[0].keep is None
    assert parsed.decisions[0].conflict_status is None


def test_parse_semantic_relevance_result_rejects_non_object_payload() -> None:
    try:
        parse_semantic_relevance_result('["not", "an", "object"]')
    except ParseError:
        pass
    else:
        raise AssertionError("expected ParseError")


def test_semantic_relevance_adapter_filters_and_marks_conflicts() -> None:
    adapter = SemanticRelevanceAdapter(
        enabled=True,
        timeout_seconds=5,
        max_items=6,
        runner=lambda payload, timeout: {
            "kept_source_ids": ["wire-a", "wire-b"],
            "items": [
                {"source_id": "wire-a", "stance": "supports"},
                {"source_id": "wire-b", "stance": "conflicts"},
                {"source_id": "wire-c", "keep": False},
            ],
        },
    )

    result = adapter.filter_evidence(seed=_seed(), evidence_items=_evidence_items())

    assert result.degraded_reason is None
    assert [item.source_id for item in result.items] == ["wire-a", "wire-b"]
    assert result.items[0].conflict_status is None
    assert result.items[1].conflict_status == "active"


def test_semantic_relevance_adapter_treats_kept_source_ids_as_authoritative_without_explicit_keep() -> (
    None
):
    adapter = SemanticRelevanceAdapter(
        enabled=True,
        timeout_seconds=5,
        max_items=6,
        runner=lambda payload, timeout: {
            "kept_source_ids": ["wire-a"],
            "items": [
                {"source_id": "wire-a", "stance": "supports"},
                {"source_id": "wire-b", "stance": "conflicts"},
            ],
        },
    )

    result = adapter.filter_evidence(seed=_seed(), evidence_items=_evidence_items())

    assert result.degraded_reason is None
    assert [item.source_id for item in result.items] == ["wire-a"]


def test_semantic_relevance_adapter_treats_kept_source_ids_as_authoritative_even_with_positive_verdicts() -> (
    None
):
    adapter = SemanticRelevanceAdapter(
        enabled=True,
        timeout_seconds=5,
        max_items=6,
        runner=lambda payload, timeout: {
            "kept_source_ids": ["wire-a"],
            "items": [
                {"source_id": "wire-a", "relevance": "settlement relevant"},
                {"source_id": "wire-b", "relevance": "settlement relevant"},
            ],
        },
    )

    result = adapter.filter_evidence(seed=_seed(), evidence_items=_evidence_items())

    assert result.degraded_reason is None
    assert [item.source_id for item in result.items] == ["wire-a"]


def test_semantic_relevance_adapter_treats_dropped_source_ids_as_authoritative_without_explicit_keep() -> (
    None
):
    adapter = SemanticRelevanceAdapter(
        enabled=True,
        timeout_seconds=5,
        max_items=6,
        runner=lambda payload, timeout: {
            "dropped_source_ids": ["wire-b"],
            "items": [
                {"source_id": "wire-a", "stance": "supports"},
                {"source_id": "wire-b", "stance": "conflicts"},
            ],
        },
    )

    result = adapter.filter_evidence(seed=_seed(), evidence_items=_evidence_items())

    assert result.degraded_reason is None
    assert [item.source_id for item in result.items] == ["wire-a", "wire-c"]


def test_semantic_relevance_adapter_treats_dropped_source_ids_as_authoritative_even_with_positive_verdicts() -> (
    None
):
    adapter = SemanticRelevanceAdapter(
        enabled=True,
        timeout_seconds=5,
        max_items=6,
        runner=lambda payload, timeout: {
            "dropped_source_ids": ["wire-b"],
            "items": [
                {"source_id": "wire-a", "relevance": "settlement relevant"},
                {"source_id": "wire-b", "relevance": "settlement relevant"},
            ],
        },
    )

    result = adapter.filter_evidence(seed=_seed(), evidence_items=_evidence_items())

    assert result.degraded_reason is None
    assert [item.source_id for item in result.items] == ["wire-a", "wire-c"]


def test_semantic_relevance_adapter_matches_nested_source_url_without_source_id() -> None:
    adapter = SemanticRelevanceAdapter(
        enabled=True,
        timeout_seconds=5,
        max_items=6,
        runner=lambda payload, timeout: {
            "items": [
                {
                    "source": {"url": "https://news.example.test/b"},
                    "claim_snippet": "Election authority says Candidate B was certified instead.",
                    "keep": False,
                }
            ],
        },
    )

    result = adapter.filter_evidence(seed=_seed(), evidence_items=_evidence_items())

    assert result.degraded_reason is None
    assert [item.source_id for item in result.items] == ["wire-a", "wire-c"]


def test_semantic_relevance_adapter_does_not_reappend_items_beyond_max_items() -> None:
    adapter = SemanticRelevanceAdapter(
        enabled=True,
        timeout_seconds=5,
        max_items=2,
        runner=lambda payload, timeout: {
            "kept_source_ids": ["wire-a"],
            "items": [
                {"source_id": "wire-a", "stance": "supports"},
                {"source_id": "wire-b", "keep": False},
            ],
        },
    )

    result = adapter.filter_evidence(seed=_seed(), evidence_items=_overflow_evidence_items())

    assert result.degraded_reason is None
    assert [item.source_id for item in result.items] == ["wire-a"]


def test_semantic_relevance_adapter_falls_back_on_malformed_output() -> None:
    adapter = SemanticRelevanceAdapter(
        enabled=True,
        timeout_seconds=5,
        max_items=6,
        runner=lambda payload, timeout: "not-json",
    )

    lexical_items = _evidence_items()
    result = adapter.filter_evidence(seed=_seed(), evidence_items=lexical_items)

    assert result.degraded_reason == "semantic_relevance_malformed_output"
    assert result.items == lexical_items


def test_semantic_relevance_adapter_reports_missing_runner_when_enabled() -> None:
    adapter = SemanticRelevanceAdapter(
        enabled=True,
        timeout_seconds=5,
        max_items=6,
    )

    lexical_items = _evidence_items()
    result = adapter.filter_evidence(seed=_seed(), evidence_items=lexical_items)

    assert result.degraded_reason == "semantic_relevance_runner_not_configured"
    assert result.items == lexical_items


def _evidence_items() -> tuple[EvidenceItem, ...]:
    return (
        EvidenceItem(
            source_id="wire-a",
            source_kind="news",
            fetched_at="2026-04-22T01:00:00Z",
            url="https://news.example.test/a",
            claim_snippet="Candidate A still lacks certified result.",
            tier="primary",
        ),
        EvidenceItem(
            source_id="wire-b",
            source_kind="news",
            fetched_at="2026-04-22T01:05:00Z",
            url="https://news.example.test/b",
            claim_snippet="Election authority says Candidate B was certified instead.",
            tier="primary",
        ),
        EvidenceItem(
            source_id="wire-c",
            source_kind="x",
            fetched_at="2026-04-22T01:10:00Z",
            url="https://x.com/example/status/1",
            claim_snippet="Random sports rumor.",
            tier="supplementary",
        ),
    )


def _overflow_evidence_items() -> tuple[EvidenceItem, ...]:
    return (
        *_evidence_items(),
        EvidenceItem(
            source_id="wire-d",
            source_kind="news",
            fetched_at="2026-04-22T01:12:00Z",
            url="https://news.example.test/d",
            claim_snippet="Overflow evidence should not bypass semantic gating.",
            tier="primary",
        ),
        EvidenceItem(
            source_id="wire-e",
            source_kind="x",
            fetched_at="2026-04-22T01:13:00Z",
            url="https://x.com/example/status/2",
            claim_snippet="Overflow x evidence should not bypass semantic gating.",
            tier="supplementary",
        ),
    )


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
        judgment_seed=json.loads("null"),
        evidence_seeds=(),
    )
