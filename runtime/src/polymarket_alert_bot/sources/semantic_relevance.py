from __future__ import annotations

import json
import os
import shlex
import subprocess
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from polymarket_alert_bot.scanner.board_scan import AlertSeed
from polymarket_alert_bot.sources.evidence_enricher import EvidenceItem

DEFAULT_EXTERNAL_RUNNER_ENV = "POLYMARKET_ALERT_BOT_SEMANTIC_RELEVANCE_RUNNER_CMD"
SEMANTIC_RELEVANCE_CONTRACT_VERSION = "semantic_relevance.v1"

SemanticRunner = Callable[[dict[str, Any], int], dict[str, Any] | str]
ExternalCommandRunner = Callable[[list[str], str, int], dict[str, Any] | str]


class ParseError(ValueError):
    pass


class SemanticEvidenceDecision(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_id: str | None = None
    url: str | None = None
    claim_snippet: str | None = None
    keep: bool | None = None
    conflict_status: str | None = None
    reason: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_decision(cls, raw: Any) -> Any:
        if not isinstance(raw, dict):
            return raw
        payload = dict(raw)
        source = payload.get("source")
        if isinstance(source, dict):
            payload.setdefault("source_id", source.get("id") or source.get("source_id"))
            payload.setdefault("url", source.get("url"))
        raw_keep = payload.get("keep")
        if raw_keep is None:
            verdict = (
                payload.get("verdict")
                or payload.get("relevance")
                or payload.get("label")
                or payload.get("classification")
            )
            if isinstance(verdict, str):
                normalized_verdict = _normalize_label(verdict)
                payload["keep"] = normalized_verdict not in {
                    "drop",
                    "exclude",
                    "irrelevant",
                    "settlement_irrelevant",
                    "not_relevant",
                }
        elif isinstance(raw_keep, str):
            payload["keep"] = raw_keep.strip().lower() in {"1", "true", "yes", "on", "keep"}

        if payload.get("conflict_status") is None:
            stance = payload.get("stance") or payload.get("support_status")
            if isinstance(stance, str):
                payload["conflict_status"] = _normalize_conflict_status(stance)
        elif isinstance(payload.get("conflict_status"), str):
            payload["conflict_status"] = _normalize_conflict_status(payload["conflict_status"])
        return payload


class ParsedSemanticRelevance(BaseModel):
    model_config = ConfigDict(extra="allow")

    decisions: list[SemanticEvidenceDecision] = Field(default_factory=list)
    kept_source_ids: list[str] = Field(default_factory=list)
    dropped_source_ids: list[str] = Field(default_factory=list)
    conflicting_source_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_payload(cls, raw: Any) -> Any:
        if not isinstance(raw, dict):
            return raw
        payload = dict(raw)
        for alias in ("items", "evidence"):
            if "decisions" not in payload and isinstance(payload.get(alias), list):
                payload["decisions"] = payload.get(alias)
        return payload


@dataclass(frozen=True)
class SemanticRelevanceResult:
    items: tuple[EvidenceItem, ...]
    degraded_reason: str | None = None


class SemanticRelevanceAdapter:
    def __init__(
        self,
        *,
        enabled: bool,
        timeout_seconds: int,
        max_items: int,
        runner: SemanticRunner | None = None,
        external_command: list[str] | str | None = None,
        external_runner: ExternalCommandRunner | None = None,
    ) -> None:
        self.enabled = enabled
        self.timeout_seconds = timeout_seconds
        self.max_items = max(max_items, 1)
        self._runner = runner
        self._external_command = self._normalize_command(external_command)
        self._external_runner = external_runner or self._run_external_command

    def filter_evidence(
        self,
        *,
        seed: AlertSeed,
        evidence_items: Iterable[EvidenceItem],
    ) -> SemanticRelevanceResult:
        lexical_items = tuple(evidence_items)
        if not lexical_items or not self.enabled:
            return SemanticRelevanceResult(items=lexical_items)
        if self._runner is None and not self._external_command:
            return SemanticRelevanceResult(
                items=lexical_items,
                degraded_reason="semantic_relevance_runner_not_configured",
            )

        limited_items = lexical_items[: self.max_items]
        payload = self.build_payload(seed=seed, evidence_items=limited_items)

        raw: dict[str, Any] | str
        try:
            if self._runner is not None:
                raw = self._runner(payload, self.timeout_seconds)
            else:
                raw = self._external_runner(
                    self._external_command,
                    json.dumps(payload, ensure_ascii=False),
                    self.timeout_seconds,
                )
        except TimeoutError:
            return SemanticRelevanceResult(
                items=lexical_items,
                degraded_reason="semantic_relevance_timeout",
            )
        except Exception:
            return SemanticRelevanceResult(
                items=lexical_items,
                degraded_reason="semantic_relevance_runner_failed",
            )

        try:
            parsed = parse_semantic_relevance_result(raw)
        except ParseError:
            return SemanticRelevanceResult(
                items=lexical_items,
                degraded_reason="semantic_relevance_malformed_output",
            )

        filtered_items = _apply_decisions(limited_items, parsed)
        return SemanticRelevanceResult(items=filtered_items)

    def build_payload(
        self, *, seed: AlertSeed, evidence_items: Iterable[EvidenceItem]
    ) -> dict[str, Any]:
        return {
            "contract_version": SEMANTIC_RELEVANCE_CONTRACT_VERSION,
            "context": {
                "candidate": {
                    "event_id": seed.event_id,
                    "event_title": seed.event_title,
                    "event_category": seed.event_category,
                    "event_end_time": seed.event_end_time,
                    "condition_id": seed.condition_id,
                    "market_id": seed.market_id,
                    "token_id": seed.token_id,
                    "event_slug": seed.event_slug,
                    "market_slug": seed.market_slug,
                    "question": seed.question,
                    "outcome_name": seed.outcome_name,
                    "expression_summary": seed.expression_summary,
                    "family_summary": {
                        "event_title": seed.family_summary.event_title,
                        "sibling_count": seed.family_summary.sibling_count,
                        "sibling_markets": [
                            {
                                "market_id": sibling.market_id,
                                "market_slug": sibling.market_slug,
                                "question": sibling.question,
                                "outcome_name": sibling.outcome_name,
                            }
                            for sibling in seed.family_summary.sibling_markets[:2]
                        ],
                    },
                    "ranking_summary": seed.ranking_summary,
                },
                "rules_text": seed.rules_text,
                "evidence": [
                    {
                        "source_id": item.source_id,
                        "source_kind": item.source_kind,
                        "fetched_at": item.fetched_at,
                        "url": item.url,
                        "claim_snippet": item.claim_snippet,
                        "tier": item.tier,
                        "conflict_status": item.conflict_status,
                    }
                    for item in evidence_items
                ],
            },
        }

    @staticmethod
    def _normalize_command(command: list[str] | str | None) -> list[str]:
        if command is None:
            env_command = os.environ.get(DEFAULT_EXTERNAL_RUNNER_ENV, "").strip()
            if not env_command:
                return []
            return SemanticRelevanceAdapter._split_command_text(env_command)
        if isinstance(command, str):
            text = command.strip()
            return SemanticRelevanceAdapter._split_command_text(text) if text else []
        return SemanticRelevanceAdapter._coalesce_inline_script(
            [str(part).strip() for part in command if str(part).strip()]
        )

    @staticmethod
    def _coalesce_inline_script(parts: list[str]) -> list[str]:
        if "-c" not in parts:
            return parts
        script_index = parts.index("-c")
        if script_index == len(parts) - 1:
            return parts
        return [*parts[: script_index + 1], " ".join(parts[script_index + 1 :])]

    @staticmethod
    def _split_command_text(text: str) -> list[str]:
        marker = " -c "
        if marker not in text:
            return SemanticRelevanceAdapter._coalesce_inline_script(shlex.split(text))
        prefix, inline_script = text.split(marker, maxsplit=1)
        prefix_parts = shlex.split(prefix)
        if not prefix_parts:
            return []
        return [*prefix_parts, "-c", inline_script]

    @staticmethod
    def _run_external_command(command: list[str], payload_json: str, timeout_seconds: int) -> str:
        try:
            completed = subprocess.run(
                command,
                input=payload_json,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError("external semantic runner timed out") from exc

        if completed.returncode != 0:
            stderr_text = (completed.stderr or "").strip()
            raise RuntimeError(
                f"external semantic runner exited with code {completed.returncode}: {stderr_text}"
            )

        stdout_text = (completed.stdout or "").strip()
        if not stdout_text:
            raise RuntimeError("external semantic runner returned empty stdout")
        return stdout_text


def parse_semantic_relevance_result(payload: dict[str, Any] | str) -> ParsedSemanticRelevance:
    try:
        loaded_payload: Any
        if isinstance(payload, str):
            loaded_payload = json.loads(payload)
        else:
            loaded_payload = payload
        if not isinstance(loaded_payload, dict):
            raise ParseError("semantic relevance payload must be an object")
        return ParsedSemanticRelevance.model_validate(loaded_payload)
    except json.JSONDecodeError as exc:
        raise ParseError("semantic relevance payload is not valid JSON") from exc
    except ValidationError as exc:
        raise ParseError(f"semantic relevance payload failed validation: {exc}") from exc


def _apply_decisions(
    evidence_items: tuple[EvidenceItem, ...],
    parsed: ParsedSemanticRelevance,
) -> tuple[EvidenceItem, ...]:
    decisions_by_key: dict[tuple[str | None, str | None, str | None], SemanticEvidenceDecision] = {}
    decisions_by_url_claim: dict[tuple[str, str], SemanticEvidenceDecision] = {}
    decisions_by_url: dict[str, SemanticEvidenceDecision] = {}
    decisions_by_source_id: dict[str, SemanticEvidenceDecision] = {}
    for parsed_decision in parsed.decisions:
        key = (parsed_decision.source_id, parsed_decision.url, parsed_decision.claim_snippet)
        decisions_by_key[key] = parsed_decision
        if parsed_decision.url and parsed_decision.claim_snippet:
            decisions_by_url_claim.setdefault(
                (parsed_decision.url, parsed_decision.claim_snippet),
                parsed_decision,
            )
        if parsed_decision.url:
            decisions_by_url.setdefault(parsed_decision.url, parsed_decision)
        if parsed_decision.source_id:
            decisions_by_source_id.setdefault(parsed_decision.source_id, parsed_decision)

    kept_source_ids = {source_id for source_id in parsed.kept_source_ids if source_id}
    dropped_source_ids = {source_id for source_id in parsed.dropped_source_ids if source_id}
    conflicting_source_ids = {source_id for source_id in parsed.conflicting_source_ids if source_id}

    filtered: list[EvidenceItem] = []
    for item in evidence_items:
        decision = _match_decision(
            item,
            decisions_by_key=decisions_by_key,
            decisions_by_url_claim=decisions_by_url_claim,
            decisions_by_url=decisions_by_url,
            decisions_by_source_id=decisions_by_source_id,
        )

        keep = True
        if kept_source_ids:
            keep = item.source_id in kept_source_ids
        elif dropped_source_ids:
            keep = item.source_id not in dropped_source_ids
        elif decision is not None and decision.keep is not None:
            keep = decision.keep

        if not keep:
            continue

        conflict_status = item.conflict_status
        if item.source_id in conflicting_source_ids:
            conflict_status = "active"
        if decision is not None and decision.conflict_status is not None:
            conflict_status = decision.conflict_status
        if conflict_status == item.conflict_status:
            filtered.append(item)
            continue
        filtered.append(
            EvidenceItem(
                source_id=item.source_id,
                source_kind=item.source_kind,
                fetched_at=item.fetched_at,
                url=item.url,
                claim_snippet=item.claim_snippet,
                tier=item.tier,
                conflict_status=conflict_status,
            )
        )
    return tuple(filtered)


def _match_decision(
    item: EvidenceItem,
    *,
    decisions_by_key: dict[tuple[str | None, str | None, str | None], SemanticEvidenceDecision],
    decisions_by_url_claim: dict[tuple[str, str], SemanticEvidenceDecision],
    decisions_by_url: dict[str, SemanticEvidenceDecision],
    decisions_by_source_id: dict[str, SemanticEvidenceDecision],
) -> SemanticEvidenceDecision | None:
    exact_match = decisions_by_key.get((item.source_id, item.url, item.claim_snippet))
    if exact_match is not None:
        return exact_match

    if item.url and item.claim_snippet:
        url_claim_match = decisions_by_url_claim.get((item.url, item.claim_snippet))
        if url_claim_match is not None:
            return url_claim_match

    source_id_match = decisions_by_source_id.get(item.source_id)
    if source_id_match is not None:
        return source_id_match

    if item.url:
        return decisions_by_url.get(item.url)
    return None


def _normalize_label(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _normalize_conflict_status(value: str) -> str | None:
    normalized = _normalize_label(value)
    if normalized in {"support", "supports", "supported", "neutral", "keep"}:
        return None
    if normalized in {"conflict", "conflicts", "contradict", "contradicts", "against"}:
        return "active"
    if normalized in {"active", "conflicted", "unresolved", "resolved"}:
        return normalized
    return None
