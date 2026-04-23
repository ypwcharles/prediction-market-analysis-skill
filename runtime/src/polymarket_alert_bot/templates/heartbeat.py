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


def _render_sleeve_counts(counts: Mapping[str, Any]) -> str:
    ordered = [
        "hot_board",
        "short_dated",
        "newly_listed",
        "family_inconsistency",
        "anchor_gap",
        "unassigned",
    ]
    parts: list[str] = []
    for sleeve in ordered:
        value = counts.get(sleeve)
        if value in (None, 0, "0"):
            continue
        parts.append(f"{sleeve}={value}")
    for sleeve, value in counts.items():
        if sleeve in ordered or value in (None, 0, "0"):
            continue
        parts.append(f"{sleeve}={value}")
    return " | ".join(parts) if parts else "-"


def render_heartbeat(payload: Mapping[str, Any]) -> str:
    archive_payload = _as_mapping(payload.get("archive_payload"))
    counts = _as_mapping(archive_payload.get("counts"))

    degraded = bool(payload.get("degraded") or archive_payload.get("degraded"))
    scan_run_id = _resolve(payload, archive_payload, "scan_run_id")
    monitor_run_id = _resolve(payload, archive_payload, "monitor_run_id")
    scanned_events = _resolve(payload, counts, "scanned_events")
    scanned_families = _resolve(payload, counts, "scanned_families")
    scanned_contracts = _resolve(payload, counts, "scanned_contracts")
    shortlisted_candidates = _resolve(payload, counts, "shortlisted_candidates")
    retrieved_shortlist_candidates = _resolve(payload, counts, "retrieved_shortlist_candidates")
    promoted_seed_count = _resolve(payload, counts, "promoted_seed_count")
    families_with_structural_flags = _resolve(payload, counts, "families_with_structural_flags")
    structurally_flagged_candidates = _resolve(payload, counts, "structurally_flagged_candidates")
    strict_count = _resolve(payload, counts, "strict_count")
    research_count = _resolve(payload, counts, "research_count")
    skipped_count = _resolve(payload, counts, "skipped_count")
    sleeve_input_counts = _as_mapping(
        _resolve(payload, counts, "sleeve_input_counts") or payload.get("sleeve_input_counts")
    )
    sleeve_shortlist_counts = _as_mapping(
        _resolve(payload, counts, "sleeve_shortlist_counts")
        or payload.get("sleeve_shortlist_counts")
    )
    sleeve_promoted_counts = _as_mapping(
        _resolve(payload, counts, "sleeve_promoted_counts") or payload.get("sleeve_promoted_counts")
    )
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
            "events/contracts/shortlist/retrieved/promoted: "
            f"{_as_text(scanned_events)}/{_as_text(scanned_contracts)}/"
            f"{_as_text(shortlisted_candidates)}/{_as_text(retrieved_shortlist_candidates)}/"
            f"{_as_text(promoted_seed_count)}",
            "families/flagged families/flagged candidates: "
            f"{_as_text(scanned_families)}/{_as_text(families_with_structural_flags)}/"
            f"{_as_text(structurally_flagged_candidates)}",
            f"strict/research/skipped: {_as_text(strict_count)}/{_as_text(research_count)}/{_as_text(skipped_count)}",
            f"sleeves input: {_render_sleeve_counts(sleeve_input_counts)}",
            f"sleeves shortlist: {_render_sleeve_counts(sleeve_shortlist_counts)}",
            f"sleeves promoted: {_render_sleeve_counts(sleeve_promoted_counts)}",
            f"reason: {_as_text(degraded_reason)}",
        ]
    )
