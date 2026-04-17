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


def condition_met(trigger: dict[str, Any], observed_value: float | str | None = None, observed_state: str | None = None) -> bool:
    comparison = trigger["comparison"]
    threshold_kind = trigger["threshold_kind"]
    threshold_value = trigger["threshold_value"]

    if comparison == "state_change":
        return observed_state == threshold_value

    actual = _parse_numeric(observed_value)
    expected = _parse_numeric(threshold_value)
    if actual is None or expected is None:
        return False

    operations = {
        "<": lambda left, right: left < right,
        "<=": lambda left, right: left <= right,
        ">": lambda left, right: left > right,
        ">=": lambda left, right: left >= right,
        "eq": lambda left, right: left == right,
    }
    return operations[comparison](actual, expected)


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


def snooze_trigger(trigger: dict[str, Any], *, now: datetime | None = None, minutes: int = 60) -> dict[str, Any]:
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
