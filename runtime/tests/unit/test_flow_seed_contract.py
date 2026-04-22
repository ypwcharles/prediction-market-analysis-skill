from __future__ import annotations

from polymarket_alert_bot.flows.shared import _seed_candidate_facts, _seed_executable_fields
from polymarket_alert_bot.scanner.board_scan import AlertSeed
from polymarket_alert_bot.scanner.family import CandidateFamilySummary, FamilyStructuralFlag


def test_seed_candidate_facts_and_executable_fields_preserve_structural_scan_contract():
    seed = AlertSeed(
        id="alert-1",
        run_id="run-1",
        event_id="event-fed",
        event_title="Fed Rate Cuts 2026",
        event_category="Politics",
        event_end_time="2026-12-31T00:00:00Z",
        market_id="market-fed-june",
        token_id="token-fed-june",
        condition_id="cond-fed-june",
        event_slug="fed-cuts-2026",
        market_slug="fed-cut-by-june",
        question="Will the Fed cut rates by June?",
        outcome_name="YES",
        market_link="https://polymarket.com/event/fed-cuts-2026/fed-cut-by-june",
        alert_kind="scanner_seed",
        dedupe_key="scanner-seed::cond-fed-june",
        expression_key="event-fed::fed-cut-by-june",
        expression_summary="Will the Fed cut rates by June?",
        rules_text="Resolves YES if the Fed cuts rates on or before June 30.",
        best_bid_cents=60.0,
        best_ask_cents=62.0,
        mid_cents=61.0,
        last_price_cents=61.0,
        spread_bps=320.0,
        slippage_bps=180.0,
        is_degraded=False,
        degraded_reason=None,
        family_summary=CandidateFamilySummary(
            event_id="event-fed",
            event_slug="fed-cuts-2026",
            event_title="Fed Rate Cuts 2026",
            event_category="Politics",
            event_end_time="2026-12-31T00:00:00Z",
            total_markets=2,
            sibling_count=1,
            sibling_markets=(),
            surface_group_count=1,
            price_surface_depth=1,
            structural_flag_count=2,
            structural_signal_score=5,
            dominance_count=1,
            dominated_by_count=0,
            partition_anomaly_count=0,
            negative_implied_hazard_count=1,
            rule_scope_adjacency_count=0,
            structural_flags=(
                FamilyStructuralFlag(
                    flag_type="negative_implied_hazard",
                    detail="Later bucket is cheaper than the adjacent earlier bucket.",
                    peer_market_id="market-fed-may",
                ),
                FamilyStructuralFlag(
                    flag_type="dominates_adjacent_bucket",
                    detail="Later bucket is at least as broad and no more expensive than the earlier bucket.",
                    peer_market_id="market-fed-may",
                ),
            ),
        ),
        ranking_summary={
            "supported_runtime_domain": True,
            "deadline_available": True,
            "deadline_rank": 1798675200,
            "family_sibling_count": 1,
            "family_surface_group_count": 1,
            "family_price_surface_depth": 1,
            "family_structural_flag_count": 2,
            "family_structural_signal_score": 5,
            "family_dominance_count": 1,
            "family_dominated_by_count": 0,
            "family_partition_anomaly_count": 0,
            "family_negative_implied_hazard_count": 1,
            "family_rule_scope_adjacency_count": 0,
            "liquidity_usd": 8500.0,
            "spread_bps": 320.0,
            "is_degraded": False,
            "missing_deadline": False,
            "missing_category": False,
            "missing_outcome_name": False,
            "missing_family_context": False,
        },
        judgment_seed=None,
        evidence_seeds=(),
    )

    candidate_facts = _seed_candidate_facts(seed)
    executable_fields = _seed_executable_fields(seed)

    assert candidate_facts["family_summary"]["structural_flag_count"] == 2
    assert candidate_facts["family_summary"]["structural_flags"][0]["flag_type"] == (
        "negative_implied_hazard"
    )
    assert candidate_facts["ranking_summary"]["family_structural_signal_score"] == 5
    assert executable_fields == {
        "best_bid_cents": 60.0,
        "best_ask_cents": 62.0,
        "mid_cents": 61.0,
        "last_price_cents": 61.0,
        "max_entry_cents": 62.0,
        "spread_bps": 320.0,
        "slippage_bps": 180.0,
        "is_degraded": False,
        "degraded_reason": None,
    }
