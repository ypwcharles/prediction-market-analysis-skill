from __future__ import annotations

from types import SimpleNamespace

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
    assert _finalize_alert_kind(
        _parsed("strict"),
        SimpleNamespace(is_degraded=False),
        strict_allowed=False,
    ) == "research"


def test_finalize_alert_kind_keeps_reprice_when_strict_gate_is_blocked() -> None:
    assert _finalize_alert_kind(
        _parsed("reprice"),
        SimpleNamespace(is_degraded=False),
        strict_allowed=False,
    ) == "reprice"
