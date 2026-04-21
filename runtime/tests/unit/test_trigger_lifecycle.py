from __future__ import annotations

from datetime import UTC, datetime, timedelta

from polymarket_alert_bot.monitor.trigger_engine import (
    acknowledge_trigger,
    close_trigger,
    evaluate_stored_trigger,
    evaluate_trigger,
    rearm_trigger,
    snooze_trigger,
)


def _trigger(state: str = "armed") -> dict[str, object]:
    return {
        "id": "trg-1",
        "threshold_kind": "price",
        "comparison": "<=",
        "threshold_value": "40",
        "state": state,
    }


def test_trigger_lifecycle_paths():
    now = datetime.now(UTC)
    fired = evaluate_trigger(_trigger(), observed_value=39, now=now)
    assert fired["state"] == "fired"

    acknowledged = acknowledge_trigger(fired, now=now)
    assert acknowledged["state"] == "acknowledged"

    snoozed = snooze_trigger(fired, now=now, minutes=5)
    assert snoozed["state"] == "snoozed"

    rearmed = rearm_trigger(
        snoozed,
        now=now + timedelta(minutes=6),
        condition_still_met=False,
    )
    assert rearmed["state"] == "rearmed"

    closed = close_trigger(rearmed, now=now)
    assert closed["state"] == "closed"


def test_evaluate_stored_trigger_fires_mechanical_from_observation():
    now = datetime.now(UTC)
    trigger = {
        "id": "trg-2",
        "trigger_type": "position_size",
        "threshold_kind": "position_size_shares",
        "comparison": ">=",
        "threshold_value": "10",
        "requires_llm_recheck": 0,
        "state": "armed",
    }
    result = evaluate_stored_trigger(
        trigger,
        observations={"position_size_shares": 12.0},
        now=now,
    )
    assert result["fired"] is True
    assert result["requires_llm_recheck"] is False
    assert result["observation"] == 12.0
    assert result["updated_trigger"]["state"] == "fired"


def test_evaluate_stored_trigger_marks_narrative_for_recheck():
    now = datetime.now(UTC)
    trigger = {
        "id": "trg-3",
        "trigger_type": "narrative_reassessment",
        "threshold_kind": "narrative",
        "comparison": "eq",
        "threshold_value": "escalation",
        "requires_llm_recheck": 1,
        "state": "armed",
    }
    result = evaluate_stored_trigger(
        trigger,
        observations={"narrative": "escalation"},
        now=now,
    )
    assert result["fired"] is False
    assert result["requires_llm_recheck"] is True
    assert result["observation"] == "escalation"
    assert result["updated_trigger"]["state"] == "fired"
    assert result["updated_trigger"]["last_fired_at"] == now.isoformat()
