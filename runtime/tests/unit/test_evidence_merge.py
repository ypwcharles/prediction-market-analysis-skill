from __future__ import annotations

from polymarket_alert_bot.flows.shared import _merge_evidence
from polymarket_alert_bot.models.records import SourceRegistry
from polymarket_alert_bot.scanner.board_scan import AlertSeed
from polymarket_alert_bot.scanner.family import CandidateFamilySummary
from polymarket_alert_bot.sources.evidence_enricher import EvidenceItem, enrich_evidence


def test_merge_evidence_keeps_configured_primary_support_when_shortlist_retrieval_adds_items() -> (
    None
):
    configured = (
        _evidence_item(
            source_id="configured-1",
            source_kind="official",
            url="https://whitehouse.gov/statement-1",
            claim="Official statement one.",
            tier="primary",
        ),
        _evidence_item(
            source_id="configured-2",
            source_kind="news",
            url="https://reuters.com/story-2",
            claim="Official statement two.",
            tier="primary",
        ),
    )
    retrieved = (
        _evidence_item(
            source_id="retrieved-1",
            source_kind="x",
            url="https://x.com/polymarket/status/1",
            claim="Supplementary market chatter.",
            tier="supplementary",
        ),
    )

    merged = _merge_evidence(_seed(), configured, retrieved_items=retrieved)
    enriched = enrich_evidence(merged, SourceRegistry(version="test"))

    assert [item.source_id for item in merged] == [
        "configured-1",
        "configured-2",
        "retrieved-1",
    ]
    assert enriched.primary_support_count == 2
    assert enriched.supplementary_count == 1
    assert enriched.strict_allowed is True


def test_merge_evidence_keeps_seeded_items_ahead_of_configured_and_retrieved_items() -> None:
    configured = tuple(
        _evidence_item(
            source_id=f"configured-{index}",
            source_kind="news",
            url=f"https://news.example.test/configured-{index}",
            claim=f"Configured evidence {index}.",
            tier="primary",
        )
        for index in range(4)
    )
    retrieved = tuple(
        _evidence_item(
            source_id=f"retrieved-{index}",
            source_kind="x",
            url=f"https://x.com/example/status/{index}",
            claim=f"Retrieved evidence {index}.",
            tier="supplementary",
        )
        for index in range(4)
    )
    seed = _seed(
        evidence_seeds=(
            {
                "source_id": "seeded-evidence",
                "source_kind": "news",
                "url": "https://seed.example.test/1",
                "claim_snippet": "Operator seeded evidence.",
                "tier": "primary",
            },
        )
    )

    merged = _merge_evidence(seed, configured, retrieved_items=retrieved)

    assert [item.source_id for item in merged[:3]] == [
        "seeded-evidence",
        "configured-0",
        "configured-1",
    ]


def _seed(*, evidence_seeds: tuple[dict[str, object], ...] = ()) -> AlertSeed:
    return AlertSeed(
        id="alert-1",
        run_id="run-1",
        event_id="event-1",
        event_title="Example Event",
        event_category="Politics",
        event_end_time="2026-12-31T00:00:00Z",
        market_id="market-1",
        token_id="token-1",
        condition_id="condition-1",
        event_slug="example-event",
        market_slug="example-market",
        question="Will Example happen?",
        outcome_name="YES",
        market_link="https://polymarket.com/event/example-event/example-market",
        alert_kind="scanner_seed",
        dedupe_key="scanner-seed::condition-1",
        expression_key="event-1::example-market",
        expression_summary="Will Example happen?",
        rules_text="Rules text",
        best_bid_cents=48.0,
        best_ask_cents=50.0,
        mid_cents=49.0,
        last_price_cents=49.0,
        spread_bps=400.0,
        slippage_bps=200.0,
        is_degraded=False,
        degraded_reason=None,
        family_summary=CandidateFamilySummary(
            event_id="event-1",
            event_slug="example-event",
            event_title="Example Event",
            event_category="Politics",
            event_end_time="2026-12-31T00:00:00Z",
            total_markets=1,
            sibling_count=0,
            sibling_markets=(),
        ),
        ranking_summary={
            "supported_runtime_domain": True,
            "deadline_available": True,
            "deadline_rank": 1798675200,
            "family_sibling_count": 0,
            "liquidity_usd": 5000.0,
            "spread_bps": 400.0,
            "is_degraded": False,
            "missing_deadline": False,
            "missing_category": False,
            "missing_outcome_name": False,
            "missing_family_context": False,
        },
        judgment_seed=None,
        evidence_seeds=evidence_seeds,
    )


def _evidence_item(
    *,
    source_id: str,
    source_kind: str,
    url: str,
    claim: str,
    tier: str,
) -> EvidenceItem:
    return EvidenceItem(
        source_id=source_id,
        source_kind=source_kind,
        fetched_at="2026-04-22T00:00:00Z",
        url=url,
        claim_snippet=claim,
        tier=tier,
    )
