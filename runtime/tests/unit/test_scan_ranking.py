from __future__ import annotations

from polymarket_alert_bot.scanner.family import CandidateFamilySummary
from polymarket_alert_bot.scanner.normalizer import ScanCandidate
from polymarket_alert_bot.scanner.ranking import build_ranking_summary, select_judgment_candidates


def test_select_judgment_candidates_prefers_supported_domain_and_nearer_deadline():
    candidates = (
        _candidate(
            market_id="market-generic",
            question="Will celebrity X post a teaser this week?",
            event_end_time="2026-12-01T00:00:00Z",
            event_title="Entertainment Event",
            event_category="Entertainment",
        ),
        _candidate(
            market_id="market-bitcoin-late",
            question="Will bitcoin hit $150k in 2026?",
            event_end_time="2026-12-31T00:00:00Z",
        ),
        _candidate(
            market_id="market-bitcoin-soon",
            question="Will bitcoin hit $150k in 2026?",
            event_end_time="2026-06-01T00:00:00Z",
        ),
    )

    selected = select_judgment_candidates(candidates, max_candidates=2)

    assert [candidate.market_id for candidate in selected] == [
        "market-bitcoin-soon",
        "market-bitcoin-late",
    ]


def test_select_judgment_candidates_prefers_richer_family_context_when_otherwise_equal():
    candidates = (
        _candidate(
            market_id="market-thin-family",
            question="Will Candidate A win the 2026 election?",
            event_end_time="2026-11-04T00:00:00Z",
            sibling_count=0,
        ),
        _candidate(
            market_id="market-rich-family",
            question="Will Candidate A win the 2026 election?",
            event_end_time="2026-11-04T00:00:00Z",
            sibling_count=3,
        ),
    )

    selected = select_judgment_candidates(candidates, max_candidates=1)

    assert [candidate.market_id for candidate in selected] == ["market-rich-family"]


def test_select_judgment_candidates_prefers_structural_signal_over_raw_liquidity():
    candidates = (
        _candidate(
            market_id="market-hot-board",
            question="Will bitcoin hit $150k in 2026?",
            event_end_time="2026-06-01T00:00:00Z",
            liquidity_usd=25_000.0,
            sibling_count=0,
        ),
        _candidate(
            market_id="market-structural",
            question="Will the Fed cut rates by June?",
            event_end_time="2026-06-01T00:00:00Z",
            liquidity_usd=4_500.0,
            sibling_count=2,
            surface_group_count=1,
            price_surface_depth=2,
            structural_flag_count=2,
            structural_signal_score=5,
            dominance_count=1,
            negative_implied_hazard_count=1,
        ),
    )

    selected = select_judgment_candidates(candidates, max_candidates=1)

    assert [candidate.market_id for candidate in selected] == ["market-structural"]


def test_build_ranking_summary_exposes_missing_metadata_without_dropping_candidate():
    candidate = _candidate(
        market_id="market-metadata-thin",
        question="Will bitcoin hit $150k in 2026?",
        event_end_time=None,
        sibling_count=0,
        event_category="",
    )

    summary = build_ranking_summary(candidate)

    assert summary.missing_deadline is True
    assert summary.missing_category is True
    assert summary.missing_outcome_name is False
    assert summary.missing_family_context is True
    assert summary.as_dict()["deadline_available"] is False
    assert summary.family_structural_flag_count == 0
    assert summary.family_structural_signal_score == 0


def test_build_ranking_summary_exposes_structural_family_metrics():
    candidate = _candidate(
        market_id="market-structural",
        question="Will the Fed cut rates by June?",
        event_end_time="2026-06-01T00:00:00Z",
        sibling_count=2,
        surface_group_count=1,
        price_surface_depth=2,
        structural_flag_count=2,
        structural_signal_score=5,
        dominance_count=1,
        negative_implied_hazard_count=1,
    )

    summary = build_ranking_summary(candidate)

    assert summary.family_surface_group_count == 1
    assert summary.family_price_surface_depth == 2
    assert summary.family_structural_flag_count == 2
    assert summary.family_structural_signal_score == 5
    assert summary.family_dominance_count == 1
    assert summary.family_negative_implied_hazard_count == 1


def _candidate(
    *,
    market_id: str,
    question: str,
    event_end_time: str | None,
    sibling_count: int = 0,
    event_title: str = "Election Event",
    event_category: str = "Politics",
    liquidity_usd: float = 5_000.0,
    surface_group_count: int = 0,
    price_surface_depth: int | None = None,
    structural_flag_count: int = 0,
    structural_signal_score: int = 0,
    dominance_count: int = 0,
    dominated_by_count: int = 0,
    partition_anomaly_count: int = 0,
    negative_implied_hazard_count: int = 0,
    rule_scope_adjacency_count: int = 0,
) -> ScanCandidate:
    return ScanCandidate(
        event_id="event-1",
        event_title=event_title,
        event_category=event_category,
        event_end_time=event_end_time,
        market_id=market_id,
        token_id=f"token-{market_id}",
        condition_id=f"cond-{market_id}",
        event_slug="event-1",
        market_slug=market_id,
        question=question,
        outcome_name="YES",
        status="open",
        active=True,
        liquidity_usd=liquidity_usd,
        best_bid_cents=48.0,
        best_ask_cents=50.0,
        mid_cents=49.0,
        last_price_cents=49.5,
        spread_bps=400.0,
        slippage_bps=200.0,
        is_degraded=False,
        degraded_reason=None,
        expression_summary=question,
        expression_key=f"event-1::{market_id}",
        rules_text="Rules text",
        family_summary=CandidateFamilySummary(
            event_id="event-1",
            event_slug="event-1",
            event_title=event_title,
            event_category=event_category,
            event_end_time=event_end_time,
            total_markets=sibling_count + 1,
            sibling_count=sibling_count,
            sibling_markets=(),
            surface_group_count=surface_group_count,
            price_surface_depth=price_surface_depth
            if price_surface_depth is not None
            else sibling_count,
            structural_flag_count=structural_flag_count,
            structural_signal_score=structural_signal_score,
            dominance_count=dominance_count,
            dominated_by_count=dominated_by_count,
            partition_anomaly_count=partition_anomaly_count,
            negative_implied_hazard_count=negative_implied_hazard_count,
            rule_scope_adjacency_count=rule_scope_adjacency_count,
        ),
    )
