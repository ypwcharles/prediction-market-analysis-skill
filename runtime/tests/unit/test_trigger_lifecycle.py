from __future__ import annotations

from datetime import UTC, datetime, timedelta

from polymarket_alert_bot.monitor.trigger_engine import (
    acknowledge_trigger,
    close_trigger,
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
