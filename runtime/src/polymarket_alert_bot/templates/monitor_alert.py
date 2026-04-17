from __future__ import annotations

from typing import Any, Mapping


def _as_text(value: Any, *, default: str = "-") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _pick_value(*values: Any, default: str = "-") -> str:
    for value in values:
        text = _as_text(value, default="")
        if text:
            return text
    return default


def render_monitor_alert(payload: Mapping[str, Any]) -> str:
    trigger = _as_mapping(payload.get("trigger"))
    trigger_candidates = payload.get("triggers")
    if not trigger and isinstance(trigger_candidates, list):
        first_trigger = trigger_candidates[0] if trigger_candidates else {}
        trigger = _as_mapping(first_trigger)

    trigger_type = _pick_value(
        payload.get("trigger_type"),
        trigger.get("trigger_type"),
        trigger.get("kind"),
        trigger.get("type"),
    )
    trigger_state = _pick_value(
        payload.get("trigger_state"),
        trigger.get("trigger_state"),
        trigger.get("state"),
    )
    observation = _pick_value(
        payload.get("observation"),
        trigger.get("observation"),
        trigger.get("condition"),
    )
    suggested_action = _pick_value(
        payload.get("suggested_action"),
        trigger.get("suggested_action"),
        trigger.get("action_hint"),
    )

    trigger_ref = _pick_value(
        payload.get("trigger_id"),
        trigger.get("trigger_id"),
        default="",
    )
    fired_at = _pick_value(
        payload.get("trigger_fired_at"),
        trigger.get("fired_at"),
        default="",
    )

    lines = [
        "[MONITOR]",
        f"thesis: {_as_text(payload.get('thesis'))}",
        f"trigger: {trigger_type}",
        f"state: {trigger_state}",
        f"observation: {observation}",
        f"suggested action: {suggested_action}",
    ]
    market_link = _as_text(payload.get("market_link"), default="")
    if market_link:
        lines.append(f"market: {market_link}")
    if trigger_ref or fired_at:
        lines.append(f"trigger ref: id={_as_text(trigger_ref)} | fired_at={_as_text(fired_at)}")

    return "\n".join(
        lines
    )
