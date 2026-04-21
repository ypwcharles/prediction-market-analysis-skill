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


def _resolve(payload: Mapping[str, Any], archive_payload: Mapping[str, Any], key: str) -> Any:
    if key in payload:
        return payload.get(key)
    return archive_payload.get(key)


def render_heartbeat(payload: Mapping[str, Any]) -> str:
    archive_payload = _as_mapping(payload.get("archive_payload"))
    counts = _as_mapping(archive_payload.get("counts"))

    degraded = bool(payload.get("degraded") or archive_payload.get("degraded"))
    scan_run_id = _resolve(payload, archive_payload, "scan_run_id")
    monitor_run_id = _resolve(payload, archive_payload, "monitor_run_id")
    strict_count = _resolve(payload, counts, "strict_count")
    research_count = _resolve(payload, counts, "research_count")
    skipped_count = _resolve(payload, counts, "skipped_count")
    degraded_reason = (
        payload.get("degraded_reason")
        or archive_payload.get("degraded_reason")
        or archive_payload.get("reason")
    )

    mode = "DEGRADED" if degraded else "HEARTBEAT"
    return "\n".join(
        [
            f"[{mode}]",
            f"scan run: {_as_text(scan_run_id)}",
            f"monitor run: {_as_text(monitor_run_id)}",
            f"strict/research/skipped: {_as_text(strict_count)}/{_as_text(research_count)}/{_as_text(skipped_count)}",
            f"reason: {_as_text(degraded_reason)}",
        ]
    )
