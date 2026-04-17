from __future__ import annotations

from typing import Any, Mapping


def _as_text(value: Any, *, default: str = "-") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def render_monitor_alert(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "[MONITOR]",
            f"thesis: {_as_text(payload.get('thesis'))}",
            f"trigger: {_as_text(payload.get('trigger_type'))}",
            f"state: {_as_text(payload.get('trigger_state'))}",
            f"observation: {_as_text(payload.get('observation'))}",
            f"suggested action: {_as_text(payload.get('suggested_action'))}",
        ]
    )
