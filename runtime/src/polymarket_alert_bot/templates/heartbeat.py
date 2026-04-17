from __future__ import annotations

from typing import Any, Mapping


def _as_text(value: Any, *, default: str = "-") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def render_heartbeat(payload: Mapping[str, Any]) -> str:
    mode = "DEGRADED" if payload.get("degraded") else "HEARTBEAT"
    return "\n".join(
        [
            f"[{mode}]",
            f"scan run: {_as_text(payload.get('scan_run_id'))}",
            f"monitor run: {_as_text(payload.get('monitor_run_id'))}",
            f"strict/research/skipped: {_as_text(payload.get('strict_count'))}/{_as_text(payload.get('research_count'))}/{_as_text(payload.get('skipped_count'))}",
            f"reason: {_as_text(payload.get('degraded_reason'))}",
        ]
    )
