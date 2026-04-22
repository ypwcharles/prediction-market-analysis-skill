from __future__ import annotations

from polymarket_alert_bot.scanner.family import build_family_summary


def test_build_family_summary_flags_negative_implied_hazard_and_dominance():
    event = {
        "id": "event-fed-cuts",
        "slug": "fed-cuts-2026",
        "title": "Fed Rate Cuts 2026",
        "category": "Politics",
        "end_time": "2026-12-31T00:00:00Z",
        "markets": [
            {
                "id": "mkt-fed-may",
                "slug": "fed-cut-by-may",
                "question": "Will the Fed cut rates by May?",
                "outcome_name": "YES",
                "liquidity_usd": 9500,
                "last_price": 0.63,
            },
            {
                "id": "mkt-fed-june",
                "slug": "fed-cut-by-june",
                "question": "Will the Fed cut rates by June?",
                "outcome_name": "YES",
                "liquidity_usd": 7200,
                "last_price": 0.61,
            },
        ],
    }

    summary = build_family_summary(event, focus_market_id="mkt-fed-june")

    flag_types = {flag.flag_type for flag in summary.structural_flags}
    assert summary.surface_group_count == 1
    assert summary.price_surface_depth == 1
    assert summary.structural_flag_count == 2
    assert summary.structural_signal_score == 5
    assert flag_types == {"dominates_adjacent_bucket", "negative_implied_hazard"}


def test_build_family_summary_flags_partition_overround():
    event = {
        "id": "event-election",
        "slug": "election-2026",
        "title": "Election 2026",
        "category": "Politics",
        "end_time": "2026-11-04T00:00:00Z",
        "markets": [
            {
                "id": "mkt-a",
                "slug": "candidate-a",
                "question": "Will Candidate A win the 2026 election?",
                "outcome_name": "Candidate A",
                "liquidity_usd": 6000,
                "last_price": 0.55,
            },
            {
                "id": "mkt-b",
                "slug": "candidate-b",
                "question": "Will Candidate B win the 2026 election?",
                "outcome_name": "Candidate B",
                "liquidity_usd": 5400,
                "last_price": 0.53,
            },
        ],
    }

    summary = build_family_summary(event, focus_market_id="mkt-a")

    assert summary.surface_group_count == 1
    assert summary.price_surface_depth == 1
    assert summary.partition_anomaly_count == 1
    assert summary.structural_flag_count == 1
    assert summary.structural_flags[0].flag_type == "partition_sum_overround"


def test_build_family_summary_ignores_same_outcome_variants_for_partition_sum():
    event = {
        "id": "event-election",
        "slug": "election-2026",
        "title": "Election 2026",
        "category": "Politics",
        "end_time": "2026-11-04T00:00:00Z",
        "markets": [
            {
                "id": "mkt-a-rules-1",
                "slug": "candidate-a-rules-1",
                "question": "Will Candidate A win the 2026 election?",
                "outcome_name": "Candidate A",
                "liquidity_usd": 6000,
                "last_price": 0.60,
                "rules_text": "Rule scope variant one.",
            },
            {
                "id": "mkt-a-rules-2",
                "slug": "candidate-a-rules-2",
                "question": "Will Candidate A win the 2026 election?",
                "outcome_name": "Candidate A",
                "liquidity_usd": 5400,
                "last_price": 0.59,
                "rules_text": "Rule scope variant two.",
            },
        ],
    }

    summary = build_family_summary(event, focus_market_id="mkt-a-rules-1")

    assert summary.partition_anomaly_count == 0
    assert {
        flag.flag_type
        for flag in summary.structural_flags
        if flag.flag_type == "partition_sum_overround"
    } == set()


def test_build_family_summary_ignores_same_rank_temporal_variants_for_dominance():
    event = {
        "id": "event-fed",
        "slug": "fed-cuts-2026",
        "title": "Fed Rate Cuts 2026",
        "category": "Politics",
        "end_time": "2026-12-31T00:00:00Z",
        "markets": [
            {
                "id": "mkt-fed-june-a",
                "slug": "fed-cut-by-june-a",
                "question": "Will the Fed cut rates by June?",
                "outcome_name": "YES",
                "liquidity_usd": 9500,
                "last_price": 0.60,
            },
            {
                "id": "mkt-fed-june-b",
                "slug": "fed-cut-by-june-b",
                "question": "Will the Fed cut rates by June?",
                "outcome_name": "YES",
                "liquidity_usd": 7200,
                "last_price": 0.59,
            },
        ],
    }

    summary = build_family_summary(event, focus_market_id="mkt-fed-june-a")

    assert summary.dominance_count == 0
    assert summary.dominated_by_count == 0
    assert summary.negative_implied_hazard_count == 0
