from __future__ import annotations

from types import SimpleNamespace

from polymarket_alert_bot.flows.shared import _build_render_payload
from polymarket_alert_bot.judgment.result_parser import ParsedJudgment
from polymarket_alert_bot.runtime_flow import _finalize_alert_kind


def _parsed(alert_kind: str) -> ParsedJudgment:
    return ParsedJudgment(
        alert_kind=alert_kind,
        cluster_action="update",
        ttl_hours=1,
        citations=[],
        triggers=[],
        archive_payload={},
    )


def test_finalize_alert_kind_downgrades_strict_when_strict_gate_is_blocked() -> None:
    assert (
        _finalize_alert_kind(
            _parsed("strict"),
            SimpleNamespace(is_degraded=False),
            strict_allowed=False,
        )
        == "research"
    )


def test_finalize_alert_kind_keeps_reprice_when_strict_gate_is_blocked() -> None:
    assert (
        _finalize_alert_kind(
            _parsed("reprice"),
            SimpleNamespace(is_degraded=False),
            strict_allowed=False,
        )
        == "reprice"
    )


def test_build_render_payload_does_not_fabricate_external_anchor_from_model_fair_value() -> None:
    parsed = ParsedJudgment(
        alert_kind="strict",
        cluster_action="update",
        ttl_hours=1,
        theoretical_edge_cents=10.0,
        max_entry_cents=42.0,
        citations=[],
        triggers=[],
        archive_payload={"rule_adjusted_payout_cents": 52.0},
    )
    seed = SimpleNamespace(
        market_link=None,
        event_slug="fed-cuts-2026",
        market_slug="fed-cut-by-june",
        expression_summary="Will the Fed cut rates by June?",
        scan_sleeves=(),
        ranking_summary={},
        best_ask_cents=42.0,
        mid_cents=None,
        last_price_cents=None,
        external_anchor_cents=None,
        external_anchor_gap_cents=None,
    )

    payload = _build_render_payload(
        seed,
        parsed,
        "strict",
        "2026-04-23T12:00:00+00:00",
        "2026-04-23T18:00:00+00:00",
        "cluster-fed",
    )

    assert payload["anchor_stack"]["external_anchor_cents"] is None
    assert payload["anchor_stack"]["rule_adjusted_payout_cents"] == 52.0
    assert payload["anchor_stack"]["anchor_gap_cents"] == 10.0
