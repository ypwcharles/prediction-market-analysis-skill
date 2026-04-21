from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "runtime.v1"

ALERT_KINDS: tuple[str, ...] = (
    "strict",
    "strict_degraded",
    "research",
    "reprice",
    "monitor",
    "heartbeat",
    "degraded",
)

CLUSTER_ACTIONS: tuple[str, ...] = (
    "create",
    "update",
    "hold",
    "close",
    "none",
)

REQUIRED_TOP_LEVEL_FIELDS: tuple[str, ...] = (
    "alert_kind",
    "cluster_action",
    "ttl_hours",
    "citations",
    "triggers",
    "archive_payload",
)

RECOMMENDED_TOP_LEVEL_FIELDS: tuple[str, ...] = (
    "thesis",
    "side",
    "theoretical_edge_cents",
    "executable_edge_cents",
    "max_entry_cents",
    "suggested_size_usdc",
    "why_now",
    "kill_criteria_text",
    "summary",
    "watch_item",
    "evidence_fresh_until",
    "recheck_required_at",
)


def runtime_response_schema() -> dict[str, list[str]]:
    return {
        "required": list(REQUIRED_TOP_LEVEL_FIELDS),
        "recommended": list(RECOMMENDED_TOP_LEVEL_FIELDS),
        "alert_kind_enum": list(ALERT_KINDS),
    }


def runtime_request_envelope(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "context": context,
        "response_schema": runtime_response_schema(),
    }


def is_valid_alert_kind(value: str) -> bool:
    return value in ALERT_KINDS


def is_valid_cluster_action(value: str) -> bool:
    return value in CLUSTER_ACTIONS
