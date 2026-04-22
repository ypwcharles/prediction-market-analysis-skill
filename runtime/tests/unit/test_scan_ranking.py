from __future__ import annotations

from polymarket_alert_bot.scanner.family import CandidateFamilySummary
from polymarket_alert_bot.scanner.normalizer import ScanCandidate
from polymarket_alert_bot.scanner.ranking import select_judgment_candidates


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


def _candidate(
    *,
    market_id: str,
    question: str,
    event_end_time: str | None,
    sibling_count: int = 0,
    event_title: str = "Election Event",
    event_category: str = "Politics",
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
        liquidity_usd=5_000.0,
        best_bid_cents=48.0,
        best_ask_cents=50.0,
        mid_cents=49.0,
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
        ),
    )
