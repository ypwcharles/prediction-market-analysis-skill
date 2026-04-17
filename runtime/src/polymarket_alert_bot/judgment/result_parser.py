from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

AllowedAlertKind = Literal[
    "strict",
    "strict_degraded",
    "research",
    "reprice",
    "monitor",
    "heartbeat",
    "degraded",
]
AllowedClusterAction = Literal["create", "update", "hold", "close", "none"]


class ParseError(ValueError):
    pass


class Citation(BaseModel):
    source_id: str
    url: str
    claim: str = Field(min_length=1)
    source_name: str | None = None
    source_tier: str | None = None
    fetched_at: str | None = None


class Trigger(BaseModel):
    kind: str = Field(min_length=1)
    condition: str = Field(min_length=1)


class ParsedJudgment(BaseModel):
    alert_kind: AllowedAlertKind
    cluster_action: AllowedClusterAction
    ttl_hours: int = Field(ge=0, default=0)
    citations: list[Citation] = Field(default_factory=list)
    triggers: list[Trigger] = Field(default_factory=list)
    archive_payload: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def degraded(cls, reason: str) -> "ParsedJudgment":
        return cls(
            alert_kind="degraded",
            cluster_action="hold",
            ttl_hours=1,
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
