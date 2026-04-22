from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any


def _parse_numeric(value: str | float | int | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except ValueError:
        return None


def condition_met(
    trigger: dict[str, Any],
    observed_value: float | str | None = None,
    observed_state: str | None = None,
) -> bool:
    comparison = trigger["comparison"]
    threshold_value = trigger["threshold_value"]

    if comparison == "state_change":
        return observed_state == threshold_value

    actual = _parse_numeric(observed_value)
    expected = _parse_numeric(threshold_value)
    operations = {
        "<": lambda left, right: left < right,
        "<=": lambda left, right: left <= right,
        ">": lambda left, right: left > right,
        ">=": lambda left, right: left >= right,
        "eq": lambda left, right: left == right,
    }
    operation = operations.get(comparison)
    if comparison == "eq" and (actual is None or expected is None):
        return observed_state == str(threshold_value)
    if actual is None or expected is None:
        return False
    if operation is None:
        return False
    return operation(actual, expected)


def evaluate_trigger(
    trigger: dict[str, Any],
    *,
    observed_value: float | str | None = None,
    observed_state: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    updated = deepcopy(trigger)
    if updated["state"] not in {"armed", "rearmed"}:
        return updated
    if condition_met(updated, observed_value=observed_value, observed_state=observed_state):
        updated["state"] = "fired"
        updated["last_fired_at"] = now.isoformat()
    return updated


def acknowledge_trigger(trigger: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    updated = deepcopy(trigger)
    updated["state"] = "acknowledged"
    updated["updated_at"] = now.isoformat()
    return updated


def snooze_trigger(
    trigger: dict[str, Any], *, now: datetime | None = None, minutes: int = 60
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    updated = deepcopy(trigger)
    updated["state"] = "snoozed"
    updated["cooldown_until"] = (now + timedelta(minutes=minutes)).isoformat()
    updated["updated_at"] = now.isoformat()
    return updated


def rearm_trigger(
    trigger: dict[str, Any],
    *,
    now: datetime | None = None,
    condition_still_met: bool = False,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    updated = deepcopy(trigger)
    if updated["state"] != "snoozed":
        return updated
    cooldown_until = updated.get("cooldown_until")
    if cooldown_until and datetime.fromisoformat(cooldown_until) <= now and not condition_still_met:
        updated["state"] = "rearmed"
        updated["updated_at"] = now.isoformat()
    return updated


def close_trigger(trigger: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    updated = deepcopy(trigger)
    updated["state"] = "closed"
    updated["updated_at"] = now.isoformat()
    return updated


def is_narrative_trigger(trigger: dict[str, Any]) -> bool:
    requires_recheck = bool(trigger.get("requires_llm_recheck"))
    trigger_type = str(trigger.get("trigger_type", "")).strip().lower()
    threshold_kind = str(trigger.get("threshold_kind", "")).strip().lower()
    if requires_recheck:
        return True
    if "narrative" in trigger_type:
        return True
    return threshold_kind in {"narrative", "context", "news", "thesis"}


def observation_key_for_threshold(threshold_kind: str | None) -> str:
    normalized = str(threshold_kind or "").strip().lower()
    aliases = {
        "price": "price_cents",
        "price_cents": "price_cents",
        "edge": "executable_edge_cents",
        "executable_edge": "executable_edge_cents",
        "executable_edge_cents": "executable_edge_cents",
        "theoretical_edge": "theoretical_edge_cents",
        "theoretical_edge_cents": "theoretical_edge_cents",
        "spread": "spread_bps",
        "spread_bps": "spread_bps",
        "slippage": "slippage_bps",
        "slippage_bps": "slippage_bps",
        "position_size": "position_size_shares",
        "position_size_shares": "position_size_shares",
        "position_state": "position_status",
        "position_status": "position_status",
        "book_state": "book_state",
        "narrative": "narrative",
    }
    return aliases.get(normalized, normalized)


def evaluate_stored_trigger(
    trigger: dict[str, Any],
    *,
    observations: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    baseline = deepcopy(trigger)
    observation_key = observation_key_for_threshold(baseline.get("threshold_kind"))
    observation = observations.get(observation_key)
    if is_narrative_trigger(baseline):
        updated = deepcopy(baseline)
        if updated.get("state") in {"armed", "rearmed"}:
            updated["state"] = "fired"
            updated["last_fired_at"] = now.isoformat()
        return {
            "updated_trigger": updated,
            "fired": False,
            "requires_llm_recheck": True,
            "observation": observation,
        }

    observed_state = str(observation) if observation is not None else None
    updated = evaluate_trigger(
        baseline,
        observed_value=observation,
        observed_state=observed_state,
        now=now,
    )
    fired = baseline.get("state") in {"armed", "rearmed"} and updated.get("state") == "fired"
    return {
        "updated_trigger": updated,
        "fired": fired,
        "requires_llm_recheck": False,
        "observation": observation,
    }
