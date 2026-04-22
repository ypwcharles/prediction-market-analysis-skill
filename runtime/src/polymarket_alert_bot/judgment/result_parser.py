from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from polymarket_alert_bot.judgment.contract import (
    ALERT_KINDS,
    CLUSTER_ACTIONS,
    is_valid_alert_kind,
    is_valid_cluster_action,
)


class ParseError(ValueError):
    pass


class SourceRef(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    name: str | None = None
    url: str | None = None
    tier: str | None = None
    fetched_at: str | None = None


class Citation(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_id: str = Field(min_length=1)
    url: str = Field(min_length=1)
    claim: str = Field(min_length=1)
    source: SourceRef | None = None
    source_name: str | None = None
    source_tier: str | None = None
    fetched_at: str | None = None
    claim_id: str | None = None
    claim_scope: str | None = None
    confidence: float | str | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_citation(cls, raw: Any) -> Any:
        if not isinstance(raw, dict):
            return raw
        payload = dict(raw)
        source = payload.get("source")
        if isinstance(source, dict):
            payload.setdefault("source_id", source.get("id") or source.get("source_id"))
            payload.setdefault("url", source.get("url"))
            payload.setdefault("source_name", source.get("name"))
            payload.setdefault("source_tier", source.get("tier"))
            payload.setdefault("fetched_at", source.get("fetched_at"))
        confidence = payload.get("confidence")
        if isinstance(confidence, str):
            trimmed = confidence.strip()
            if trimmed:
                try:
                    payload["confidence"] = float(trimmed)
                except ValueError:
                    payload["confidence"] = trimmed
            else:
                payload["confidence"] = None
        payload.setdefault("source_id", "unknown_source")
        payload.setdefault("url", "about:blank")
        return payload


class Trigger(BaseModel):
    model_config = ConfigDict(extra="allow")

    kind: str = Field(min_length=1)
    condition: str = Field(min_length=1)
    trigger_id: str | None = None
    trigger_type: str | None = None
    trigger_state: str | None = None
    observation: str | None = None
    suggested_action: str | None = None
    threshold: str | float | int | None = None
    observed_value: str | float | int | None = None
    fired_at: str | None = None
    next_check_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _normalize_trigger(cls, raw: Any) -> Any:
        if not isinstance(raw, dict):
            return raw
        payload = dict(raw)
        derived_kind = (
            payload.get("kind")
            or payload.get("trigger_type")
            or payload.get("type")
            or payload.get("trigger_kind")
            or "generic"
        )
        payload.setdefault("kind", str(derived_kind))
        derived_condition = (
            payload.get("condition")
            or payload.get("condition_text")
            or payload.get("rule")
            or payload.get("expression")
            or payload.get("threshold")
            or "unspecified"
        )
        payload.setdefault("condition", str(derived_condition))
        payload.setdefault("trigger_type", payload.get("trigger_type") or payload.get("kind"))
        return payload


class ArchivePayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    reason: str | None = None
    summary: str | None = None
    thesis: str | None = None
    thesis_cluster_id: str | None = None
    alert_id: str | None = None
    message_refs: list[dict[str, Any]] = Field(default_factory=list)
    trigger_payload: dict[str, Any] | list[dict[str, Any]] = Field(default_factory=dict)
    trigger_metadata: dict[str, Any] = Field(default_factory=dict)
    delivery: dict[str, Any] = Field(default_factory=dict)


class ParsedJudgment(BaseModel):
    alert_kind: str
    cluster_action: str
    ttl_hours: int = Field(ge=0, default=0)
    thesis: str | None = None
    side: str | None = None
    theoretical_edge_cents: float | None = None
    executable_edge_cents: float | None = None
    max_entry_cents: float | None = None
    suggested_size_usdc: float | None = None
    why_now: str | None = None
    kill_criteria_text: str | None = None
    summary: str | None = None
    watch_item: str | None = None
    evidence_fresh_until: str | None = None
    recheck_required_at: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    triggers: list[Trigger] = Field(default_factory=list)
    archive_payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _normalize_archive_payload(cls, raw: Any) -> Any:
        if not isinstance(raw, dict):
            return raw
        payload = dict(raw)
        archive_payload = payload.get("archive_payload")
        if archive_payload is None:
            payload["archive_payload"] = {}
            return payload
        if not isinstance(archive_payload, dict):
            payload["archive_payload"] = {}
            return payload
        parsed_archive = ArchivePayload.model_validate(archive_payload)
        payload["archive_payload"] = parsed_archive.model_dump(exclude_none=True)
        return payload

    @model_validator(mode="after")
    def _validate_runtime_enums(self) -> "ParsedJudgment":
        if not is_valid_alert_kind(self.alert_kind):
            allowed = ", ".join(ALERT_KINDS)
            raise ValueError(f"alert_kind must be one of: {allowed}")
        if not is_valid_cluster_action(self.cluster_action):
            allowed = ", ".join(CLUSTER_ACTIONS)
            raise ValueError(f"cluster_action must be one of: {allowed}")
        return self

    @classmethod
    def degraded(cls, reason: str) -> "ParsedJudgment":
        return cls(
            alert_kind="degraded",
            cluster_action="hold",
            ttl_hours=1,
            summary=reason,
            citations=[],
            triggers=[],
            archive_payload={"reason": reason},
        )


def parse_judgment_result(payload: dict[str, Any] | str) -> ParsedJudgment:
    try:
        loaded_payload: Any
        if isinstance(payload, str):
            loaded_payload = json.loads(payload)
        else:
            loaded_payload = payload
        if not isinstance(loaded_payload, dict):
            raise ParseError("judgment payload must be an object")
        return ParsedJudgment.model_validate(loaded_payload)
    except json.JSONDecodeError as exc:
        raise ParseError("judgment payload is not valid JSON") from exc
    except ValidationError as exc:
        raise ParseError(f"judgment payload failed validation: {exc}") from exc
