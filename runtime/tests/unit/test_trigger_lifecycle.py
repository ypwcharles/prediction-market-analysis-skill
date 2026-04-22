from __future__ import annotations

from datetime import UTC, datetime, timedelta

from polymarket_alert_bot.monitor.trigger_engine import (
    acknowledge_trigger,
    close_trigger,
    condition_met,
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


def test_condition_met_supports_string_eq_comparisons() -> None:
    trigger = {
        "comparison": "eq",
        "threshold_value": "quotes_available",
    }

    assert condition_met(
        trigger, observed_value="quotes_available", observed_state="quotes_available"
    )
    assert not condition_met(
        trigger, observed_value="quotes_missing", observed_state="quotes_missing"
    )


def test_evaluate_stored_trigger_supports_market_data_recheck_state_changes() -> None:
    now = datetime.now(UTC)
    trigger = {
        "id": "trg-4",
        "trigger_type": "market_data_recheck",
        "threshold_kind": "book_state",
        "comparison": "state_change",
        "threshold_value": "quotes_available",
        "requires_llm_recheck": 0,
        "state": "armed",
    }
    result = evaluate_stored_trigger(
        trigger,
        observations={"book_state": "quotes_available"},
        now=now,
    )

    assert result["fired"] is True
    assert result["requires_llm_recheck"] is False
    assert result["observation"] == "quotes_available"
    assert result["updated_trigger"]["state"] == "fired"


def test_price_threshold_with_llm_recheck_stays_mechanical_until_threshold_hits() -> None:
    now = datetime.now(UTC)
    trigger = {
        "id": "trg-5",
        "trigger_type": "price_threshold",
        "threshold_kind": "execution_cost",
        "comparison": "<=",
        "threshold_value": "200",
        "requires_llm_recheck": 1,
        "state": "armed",
    }

    result = evaluate_stored_trigger(
        trigger,
        observations={"execution_cost_bps": 350.0},
        now=now,
    )

    assert result["fired"] is False
    assert result["requires_llm_recheck"] is False
    assert result["observation"] == 350.0
    assert result["updated_trigger"]["state"] == "armed"


def test_price_threshold_with_llm_recheck_requests_recheck_only_after_threshold_hits() -> None:
    now = datetime.now(UTC)
    trigger = {
        "id": "trg-6",
        "trigger_type": "price_threshold",
        "threshold_kind": "execution_cost",
        "comparison": "<=",
        "threshold_value": "200",
        "requires_llm_recheck": 1,
        "state": "armed",
    }

    result = evaluate_stored_trigger(
        trigger,
        observations={"execution_cost_bps": 150.0},
        now=now,
    )

    assert result["fired"] is True
    assert result["requires_llm_recheck"] is True
    assert result["observation"] == 150.0
    assert result["updated_trigger"]["state"] == "fired"
    assert result["updated_trigger"]["last_fired_at"] == now.isoformat()
