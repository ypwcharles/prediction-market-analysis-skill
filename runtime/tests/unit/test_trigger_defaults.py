from __future__ import annotations

from polymarket_alert_bot.flows.shared import (
    _persisted_trigger_defaults,
    _persisted_trigger_requires_recheck,
)
from polymarket_alert_bot.judgment.result_parser import Trigger


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
