from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from polymarket_alert_bot.flows.shared import (
    _persisted_trigger_comparison,
    _persisted_trigger_defaults,
    _persisted_trigger_requires_recheck,
    _persisted_trigger_threshold_kind,
    _persisted_trigger_threshold_value,
)
from polymarket_alert_bot.judgment.result_parser import Trigger, parse_judgment_result
from polymarket_alert_bot.monitor.trigger_engine import evaluate_stored_trigger


def _trigger(*, trigger_type: str, kind: str = "generic") -> Trigger:
    return Trigger.model_validate(
        {
            "trigger_type": trigger_type,
            "kind": kind,
            "condition": "placeholder",
        }
    )


def test_persisted_trigger_defaults_use_machine_semantics_for_narrative_triggers() -> None:
    defaults = _persisted_trigger_defaults(_trigger(trigger_type="catalyst_checkpoint"))

    assert defaults == {
        "threshold_kind": "narrative",
        "comparison": "eq",
        "requires_llm_recheck": True,
    }


def test_persisted_trigger_defaults_use_machine_semantics_for_rule_change_aliases() -> None:
    defaults = _persisted_trigger_defaults(_trigger(trigger_type="rule_change"))

    assert defaults == {
        "threshold_kind": "narrative",
        "comparison": "eq",
        "requires_llm_recheck": True,
    }


def test_persisted_trigger_defaults_use_machine_semantics_for_market_data_rechecks() -> None:
    defaults = _persisted_trigger_defaults(_trigger(trigger_type="market_data_recheck"))

    assert defaults == {
        "threshold_kind": "book_state",
        "comparison": "state_change",
        "requires_llm_recheck": False,
    }


def test_explicit_market_data_recheck_fields_beat_hardcoded_defaults() -> None:
    trigger = Trigger.model_validate(
        {
            "trigger_type": "market_data_recheck",
            "kind": "market_data_recheck",
            "condition": "Recheck after quotes disappear",
            "threshold_kind": "book_state",
            "comparison": "state_change",
            "threshold_value": "quotes_missing",
            "requires_llm_recheck": False,
        }
    )

    assert _persisted_trigger_threshold_kind(trigger) == "book_state"
    assert _persisted_trigger_comparison(trigger) == "state_change"
    assert _persisted_trigger_threshold_value(trigger) == "quotes_missing"
    assert _persisted_trigger_requires_recheck(trigger) is False


def test_persisted_trigger_defaults_use_machine_semantics_for_price_thresholds() -> None:
    defaults = _persisted_trigger_defaults(_trigger(trigger_type="price_threshold"))

    assert defaults == {
        "threshold_kind": "execution_cost",
        "comparison": "<=",
        "requires_llm_recheck": True,
    }


def test_explicit_requires_llm_recheck_false_beats_trigger_defaults() -> None:
    trigger = Trigger.model_validate(
        {
            "trigger_type": "price_threshold",
            "kind": "price_threshold",
            "condition": "placeholder",
            "metadata": {"requires_llm_recheck": False},
        }
    )

    assert _persisted_trigger_requires_recheck(trigger) is False


def test_real_hermes_price_threshold_condition_derives_execution_cost_threshold() -> None:
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "real_hermes_monitor_output.json"
    parsed = parse_judgment_result(json.loads(fixture.read_text(encoding="utf-8")))
    trigger = next(t for t in parsed.triggers if t.trigger_type == "price_threshold")

    assert json.loads(_persisted_trigger_threshold_value(trigger)) == {
        "slippage_bps_max": 100.0,
        "spread_bps_max": 200.0,
    }


def test_real_hermes_price_threshold_condition_can_fire_after_threshold_derivation() -> None:
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "real_hermes_monitor_output.json"
    parsed = parse_judgment_result(json.loads(fixture.read_text(encoding="utf-8")))
    trigger = next(t for t in parsed.triggers if t.trigger_type == "price_threshold")
    now = datetime.now(UTC)

    persisted_trigger = {
        "id": "trg-real-fixture",
        "trigger_type": trigger.trigger_type,
        "threshold_kind": _persisted_trigger_defaults(trigger)["threshold_kind"],
        "comparison": _persisted_trigger_defaults(trigger)["comparison"],
        "threshold_value": _persisted_trigger_threshold_value(trigger),
        "requires_llm_recheck": 1 if _persisted_trigger_requires_recheck(trigger) else 0,
        "state": "armed",
    }

    result = evaluate_stored_trigger(
        persisted_trigger,
        observations={"spread_bps": 180.0, "slippage_bps": 90.0, "execution_cost_bps": 270.0},
        now=now,
    )

    assert result["fired"] is True
    assert result["requires_llm_recheck"] is True
    assert result["updated_trigger"]["state"] == "fired"


def test_real_hermes_price_threshold_condition_does_not_fire_on_sum_only_false_positive() -> None:
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "real_hermes_monitor_output.json"
    parsed = parse_judgment_result(json.loads(fixture.read_text(encoding="utf-8")))
    trigger = next(t for t in parsed.triggers if t.trigger_type == "price_threshold")
    now = datetime.now(UTC)

    persisted_trigger = {
        "id": "trg-real-fixture-false-positive",
        "trigger_type": trigger.trigger_type,
        "threshold_kind": _persisted_trigger_defaults(trigger)["threshold_kind"],
        "comparison": _persisted_trigger_defaults(trigger)["comparison"],
        "threshold_value": _persisted_trigger_threshold_value(trigger),
        "requires_llm_recheck": 1 if _persisted_trigger_requires_recheck(trigger) else 0,
        "state": "armed",
    }

    result = evaluate_stored_trigger(
        persisted_trigger,
        observations={"spread_bps": 50.0, "slippage_bps": 200.0, "execution_cost_bps": 250.0},
        now=now,
    )

    assert result["fired"] is False
    assert result["updated_trigger"]["state"] == "armed"
