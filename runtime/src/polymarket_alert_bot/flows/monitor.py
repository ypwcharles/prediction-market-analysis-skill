from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable
from uuid import uuid4

from polymarket_alert_bot.config.settings import RuntimeConfig, RuntimePaths, load_runtime_config
from polymarket_alert_bot.config.source_registry import load_source_registry
from polymarket_alert_bot.flows.shared import (
    _deliver_message,
    _load_configured_evidence,
    _lookup_position_context,
    _now_iso,
    _resolve_alert_market_link,
)
from polymarket_alert_bot.judgment.context_builder import build_judgment_context
from polymarket_alert_bot.judgment.result_parser import ParsedJudgment
from polymarket_alert_bot.judgment.skill_adapter import SkillAdapter
from polymarket_alert_bot.monitor.position_sync import run_monitor
from polymarket_alert_bot.sources.evidence_enricher import EvidenceItem, enrich_evidence
from polymarket_alert_bot.storage.db import connect_db
from polymarket_alert_bot.storage.migrations import apply_migrations
from polymarket_alert_bot.storage.repositories import RuntimeRepository
from polymarket_alert_bot.templates.monitor_alert import render_monitor_alert


@dataclass(frozen=True)
class MonitorFlowSummary:
    run_id: str
    delivered_alert_ids: tuple[str, ...]
    stale_alert_ids: tuple[str, ...]


def execute_monitor_flow(
    paths: RuntimePaths, *, runtime_config: RuntimeConfig | None = None
) -> MonitorFlowSummary:
    config = runtime_config or load_runtime_config()
    outcome = run_monitor(paths, runtime_config=config)
    conn = connect_db(paths.db_path)
    apply_migrations(conn)
    repository = RuntimeRepository(conn)
    registry = load_source_registry(paths.sources_path)
    evidence_result = _load_configured_evidence(config, registry=registry)
    configured_evidence = evidence_result.items
    skill = SkillAdapter(
        timeout_seconds=config.judgment_timeout_seconds,
        external_command=list(config.judgment_command) or None,
    )
    delivered_alert_ids: list[str] = []
    now_iso = _now_iso()
    delivery_groups: dict[str, dict[str, Any]] = {}

    def _append_delivery_candidate(
        payload: dict[str, object], *, parsed: ParsedJudgment | None = None
    ) -> None:
        source_alert = repository.get_alert(str(payload["alert_id"]))
        if source_alert is None:
            return
        group = delivery_groups.setdefault(
            str(payload["alert_id"]),
            {
                "source_alert": source_alert,
                "market_link": _resolve_alert_market_link(conn, source_alert),
                "payloads": [],
                "parsed_results": [],
            },
        )
        group["payloads"].append(dict(payload))
        if parsed is not None:
            group["parsed_results"].append(parsed)

    for payload in outcome.fired_actions:
        _append_delivery_candidate(payload)

    for payload in outcome.pending_recheck_actions:
        source_alert = repository.get_alert(str(payload["alert_id"]))
        if source_alert is None:
            continue
        parsed = _judge_monitor_recheck(
            skill=skill,
            conn=conn,
            source_alert=source_alert,
            payload=payload,
            configured_evidence=configured_evidence,
            registry=registry,
        )
        if not _monitor_recheck_allows_delivery(parsed):
            continue
        _append_delivery_candidate(payload, parsed=parsed)

    for group in delivery_groups.values():
        monitor_alert_id = _deliver_monitor_action(
            repository=repository,
            config=config,
            run_id=outcome.run_id,
            source_alert=group["source_alert"],
            payloads=group["payloads"],
            parsed_results=group["parsed_results"],
            now_iso=now_iso,
            market_link=group["market_link"],
        )
        delivered_alert_ids.append(monitor_alert_id)

    return MonitorFlowSummary(
        run_id=outcome.run_id,
        delivered_alert_ids=tuple(delivered_alert_ids),
        stale_alert_ids=tuple(outcome.stale_alert_ids),
    )


def _deliver_monitor_action(
    *,
    repository: RuntimeRepository,
    config: RuntimeConfig,
    run_id: str,
    source_alert,
    payloads: list[dict[str, object]],
    parsed_results: list[ParsedJudgment],
    now_iso: str,
    market_link: str | None,
) -> str:
    monitor_alert_id = str(uuid4())
    primary_parsed = _pick_primary_parsed(parsed_results)
    message = render_monitor_alert(
        {
            "thesis": (
                primary_parsed.thesis
                if primary_parsed and primary_parsed.thesis
                else source_alert["why_now"] or source_alert["thesis_cluster_id"] or "-"
            ),
            "summary": primary_parsed.summary if primary_parsed else None,
            "why_now": primary_parsed.why_now if primary_parsed else source_alert["why_now"],
            "watch_item": primary_parsed.watch_item if primary_parsed else None,
            "suggested_action": _joined_suggested_actions(payloads),
            "triggers": payloads,
            "market_link": market_link,
        }
    )
    message_ref = _deliver_message(
        config=config,
        text=message,
        alert_id=monitor_alert_id,
        thesis_cluster_id=str(payloads[0]["thesis_cluster_id"]),
    )
    repository.insert_alert(
        {
            "id": monitor_alert_id,
            "run_id": run_id,
            "thesis_cluster_id": payloads[0]["thesis_cluster_id"],
            "condition_id": source_alert["condition_id"],
            "event_id": source_alert["event_id"],
            "market_id": source_alert["market_id"],
            "token_id": source_alert["token_id"],
            "alert_kind": "monitor",
            "delivery_mode": "immediate",
            "side": primary_parsed.side if primary_parsed else source_alert["side"],
            "theoretical_edge_cents": (
                primary_parsed.theoretical_edge_cents
                if primary_parsed and primary_parsed.theoretical_edge_cents is not None
                else source_alert["theoretical_edge_cents"]
            ),
            "executable_edge_cents": (
                primary_parsed.executable_edge_cents
                if primary_parsed and primary_parsed.executable_edge_cents is not None
                else source_alert["executable_edge_cents"]
            ),
            "max_entry_cents": (
                primary_parsed.max_entry_cents
                if primary_parsed and primary_parsed.max_entry_cents is not None
                else source_alert["max_entry_cents"]
            ),
            "suggested_size_usdc": (
                primary_parsed.suggested_size_usdc
                if primary_parsed and primary_parsed.suggested_size_usdc is not None
                else source_alert["suggested_size_usdc"]
            ),
            "why_now": message,
            "kill_criteria_text": (
                primary_parsed.kill_criteria_text
                if primary_parsed
                else source_alert["kill_criteria_text"]
            ),
            "evidence_fresh_until": primary_parsed.evidence_fresh_until if primary_parsed else None,
            "recheck_required_at": primary_parsed.recheck_required_at if primary_parsed else None,
            "status": "active",
            "telegram_chat_id": message_ref.chat_id if message_ref else None,
            "telegram_message_id": message_ref.message_id if message_ref else None,
            "dedupe_key": f"monitor::{payloads[0]['alert_id']}::{run_id}",
            "created_at": now_iso,
        }
    )
    return monitor_alert_id


def _pick_primary_parsed(parsed_results: list[ParsedJudgment]) -> ParsedJudgment | None:
    if not parsed_results:
        return None

    def _score(parsed: ParsedJudgment) -> tuple[int, int]:
        text = " ".join(
            part
            for part in [parsed.summary, parsed.why_now, parsed.thesis, parsed.watch_item]
            if part
        )
        has_cjk = any("\u4e00" <= char <= "\u9fff" for char in text)
        return (1 if has_cjk else 0, len(text))

    return max(parsed_results, key=_score)


def _joined_suggested_actions(payloads: list[dict[str, object]]) -> str | None:
    actions: list[str] = []
    seen: set[str] = set()
    for payload in payloads:
        raw = payload.get("suggested_action")
        if raw is None:
            continue
        text = str(raw).strip()
        if not text or text in seen:
            continue
        actions.append(text)
        seen.add(text)
    if not actions:
        return None
    return " / ".join(actions)


def _judge_monitor_recheck(
    *,
    skill: SkillAdapter,
    conn,
    source_alert,
    payload: dict[str, object],
    configured_evidence: Iterable[EvidenceItem],
    registry,
) -> ParsedJudgment:
    evidence_items = list(configured_evidence)
    observation = payload.get("observation")
    if observation is not None:
        evidence_items.append(
            EvidenceItem(
                source_id=f"monitor-trigger-{payload['trigger_id']}",
                source_kind="monitor_trigger",
                fetched_at=_now_iso(),
                url=f"monitor://trigger/{payload['trigger_id']}",
                claim_snippet=f"Trigger observation: {observation}",
                tier="supplementary",
                conflict_status=None,
            )
        )
    enriched = enrich_evidence(evidence_items, registry)
    context = build_judgment_context(
        candidate_facts={
            "mode": "monitor_recheck",
            "alert_id": source_alert["id"],
            "thesis_cluster_id": source_alert["thesis_cluster_id"],
            "condition_id": source_alert["condition_id"],
            "event_id": source_alert["event_id"],
            "market_id": source_alert["market_id"],
            "token_id": source_alert["token_id"],
            "market_link": _resolve_alert_market_link(conn, source_alert),
            "trigger_id": payload["trigger_id"],
            "trigger_type": payload["trigger_type"],
            "trigger_state": payload.get("trigger_state"),
            "suggested_action": payload.get("suggested_action"),
            "observation": observation,
            "narrative": source_alert["why_now"],
        },
        rules_text=_build_monitor_recheck_rules_text(source_alert),
        executable_fields={
            "theoretical_edge_cents": source_alert["theoretical_edge_cents"],
            "executable_edge_cents": source_alert["executable_edge_cents"],
            "spread_bps": source_alert["spread_bps"],
            "slippage_bps": source_alert["slippage_bps"],
            "max_entry_cents": source_alert["max_entry_cents"],
        },
        enriched_evidence=enriched,
        prior_cluster_state=None,
        position_context=_lookup_position_context(conn, str(source_alert["token_id"] or "")),
    )
    return skill.judge(context)


def _build_monitor_recheck_rules_text(source_alert) -> str:
    parts = [source_alert["kill_criteria_text"], source_alert["why_now"]]
    lines: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if part is None:
            continue
        text = str(part).strip()
        if not text or text in seen:
            continue
        lines.append(text)
        seen.add(text)
    return "\n".join(lines)


def _monitor_recheck_allows_delivery(parsed: ParsedJudgment) -> bool:
    return parsed.alert_kind in {"strict", "strict_degraded", "reprice", "monitor"}
