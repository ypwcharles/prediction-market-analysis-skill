from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from typing import Any, Iterable
from uuid import NAMESPACE_URL, uuid4, uuid5

from polymarket_alert_bot.archive.writer import write_archive_artifact
from polymarket_alert_bot.config.settings import RuntimeConfig, RuntimePaths, load_runtime_config
from polymarket_alert_bot.config.source_registry import load_source_registry
from polymarket_alert_bot.delivery.callback_router import build_feedback_keyboard
from polymarket_alert_bot.delivery.telegram_client import TelegramClient, TelegramMessageRef
from polymarket_alert_bot.judgment.context_builder import build_judgment_context
from polymarket_alert_bot.judgment.result_parser import ParsedJudgment, Trigger
from polymarket_alert_bot.judgment.skill_adapter import SkillAdapter
from polymarket_alert_bot.monitor.position_sync import run_monitor
from polymarket_alert_bot.scanner.board_scan import AlertSeed, run_scan
from polymarket_alert_bot.sources.evidence_enricher import EvidenceItem, enrich_evidence
from polymarket_alert_bot.sources.news_client import NewsClient
from polymarket_alert_bot.sources.x_client import XClient
from polymarket_alert_bot.storage.db import connect_db
from polymarket_alert_bot.storage.migrations import apply_migrations
from polymarket_alert_bot.storage.repositories import RuntimeRepository
from polymarket_alert_bot.templates.heartbeat import render_heartbeat
from polymarket_alert_bot.templates.monitor_alert import render_monitor_alert
from polymarket_alert_bot.templates.research_digest import render_research_digest
from polymarket_alert_bot.templates.strict_memo import render_strict_memo


@dataclass(frozen=True)
class ScanFlowSummary:
    run_id: str
    strict_alert_ids: tuple[str, ...]
    research_alert_ids: tuple[str, ...]
    heartbeat_alert_id: str | None


@dataclass(frozen=True)
class MonitorFlowSummary:
    run_id: str
    delivered_alert_ids: tuple[str, ...]
    stale_alert_ids: tuple[str, ...]


def execute_scan_flow(paths: RuntimePaths, *, runtime_config: RuntimeConfig | None = None) -> ScanFlowSummary:
    config = runtime_config or load_runtime_config()
    scan_result = run_scan(paths)
    conn = connect_db(paths.db_path)
    apply_migrations(conn)
    repository = RuntimeRepository(conn)
    registry = load_source_registry(paths.sources_path)
    now_iso = _now_iso()
    _sync_source_registry(repository, registry, now_iso=now_iso)
    configured_evidence = _load_configured_evidence(config)

    skill = SkillAdapter(
        timeout_seconds=config.judgment_timeout_seconds,
        external_command=list(config.judgment_command) or None,
    )
    strict_alert_ids: list[str] = []
    research_alert_ids: list[str] = []
    research_renderings: list[str] = []
    heartbeat_alert_id: str | None = None

    for seed in scan_result.alert_seeds:
        seed_now = _now_iso()
        parsed = _judge_seed(
            skill=skill,
            conn=conn,
            seed=seed,
            configured_evidence=configured_evidence,
            registry=registry,
        )
        final_kind = _finalize_alert_kind(
            parsed,
            seed,
            strict_allowed=_is_strict_allowed(seed, configured_evidence, registry),
        )
        cluster_id = _stable_cluster_id(seed, parsed)
        fresh_until, recheck_at = _resolve_timers(parsed, seed_now)
        render_payload = _build_render_payload(seed, parsed, final_kind, fresh_until, recheck_at, cluster_id)

        _upsert_cluster_state(
            repository,
            seed=seed,
            cluster_id=cluster_id,
            canonical_name=render_payload["thesis"],
            now_iso=seed_now,
        )
        _persist_claim_mappings(
            repository,
            registry,
            alert_id=seed.id,
            thesis_cluster_id=cluster_id,
            citations=parsed.citations,
            now_iso=seed_now,
        )
        _replace_triggers(
            conn,
            repository,
            alert_id=seed.id,
            thesis_cluster_id=cluster_id,
            parsed_triggers=parsed.triggers,
            now_iso=seed_now,
        )

        archive_path: Path | None = None
        message_ref: TelegramMessageRef | None = None
        if final_kind in {"strict", "strict_degraded", "reprice"}:
            rendered = render_strict_memo(render_payload)
            archive_path = write_archive_artifact(
                paths,
                alert_id=seed.id,
                alert_kind="strict" if final_kind != "reprice" else "reprice",
                content=rendered,
                high_value=True,
            )
            message_ref = _deliver_message(
                config=config,
                text=rendered,
                alert_id=seed.id,
                thesis_cluster_id=cluster_id,
            )
            strict_alert_ids.append(seed.id)
        else:
            rendered = render_research_digest(render_payload)
            research_renderings.append(rendered)
            research_alert_ids.append(seed.id)

        repository.update_alert(
            alert_id=seed.id,
            payload={
                "thesis_cluster_id": cluster_id,
                "alert_kind": final_kind,
                "delivery_mode": _delivery_mode_for_alert_kind(final_kind),
                "side": parsed.side,
                "theoretical_edge_cents": parsed.theoretical_edge_cents,
                "executable_edge_cents": parsed.executable_edge_cents,
                "spread_bps": seed.spread_bps,
                "slippage_bps": seed.slippage_bps,
                "max_entry_cents": parsed.max_entry_cents,
                "suggested_size_usdc": parsed.suggested_size_usdc,
                "why_now": render_payload["why_now"],
                "kill_criteria_text": render_payload["kill_criteria_text"],
                "evidence_fresh_until": fresh_until,
                "recheck_required_at": recheck_at,
                "status": "active",
                "archive_path": str(archive_path) if archive_path else None,
                "telegram_chat_id": message_ref.chat_id if message_ref else None,
                "telegram_message_id": message_ref.message_id if message_ref else None,
            },
        )

    if research_renderings:
        _deliver_message(
            config=config,
            text="\n\n".join(research_renderings),
            alert_id=f"research-digest::{scan_result.run_id}",
            thesis_cluster_id="research",
        )

    if not strict_alert_ids:
        heartbeat_alert_id = str(uuid4())
        heartbeat_text = render_heartbeat(
            {
                "scan_run_id": scan_result.run_id,
                "monitor_run_id": "-",
                "strict_count": len(strict_alert_ids),
                "research_count": len(research_alert_ids),
                "skipped_count": scan_result.outcome.coverage.skipped,
                "degraded": scan_result.status == "degraded",
                "degraded_reason": scan_result.degraded_reason,
            }
        )
        archive_path = write_archive_artifact(
            paths,
            alert_id=heartbeat_alert_id,
            alert_kind="heartbeat",
            content=heartbeat_text,
            high_value=True,
        )
        message_ref = _deliver_message(
            config=config,
            text=heartbeat_text,
            alert_id=heartbeat_alert_id,
            thesis_cluster_id="heartbeat",
        )
        repository.insert_alert(
            {
                "id": heartbeat_alert_id,
                "run_id": scan_result.run_id,
                "thesis_cluster_id": None,
                "condition_id": None,
                "event_id": None,
                "market_id": None,
                "token_id": None,
                "alert_kind": "heartbeat",
                "delivery_mode": "system",
                "status": "active",
                "telegram_chat_id": message_ref.chat_id if message_ref else None,
                "telegram_message_id": message_ref.message_id if message_ref else None,
                "archive_path": str(archive_path) if archive_path else None,
                "dedupe_key": f"heartbeat::{scan_result.run_id}",
                "created_at": _now_iso(),
            }
        )

    conn.execute(
        """
        UPDATE runs
        SET strict_count = ?,
            research_count = ?,
            skipped_count = ?,
            heartbeat_sent = ?,
            finished_at = ?,
            degraded_reason = ?,
            status = ?
        WHERE id = ?
        """,
        [
            len(strict_alert_ids),
            len(research_alert_ids),
            scan_result.outcome.coverage.skipped,
            1 if heartbeat_alert_id else 0,
            _now_iso(),
            scan_result.degraded_reason,
            scan_result.status,
            scan_result.run_id,
        ],
    )
    conn.commit()

    return ScanFlowSummary(
        run_id=scan_result.run_id,
        strict_alert_ids=tuple(strict_alert_ids),
        research_alert_ids=tuple(research_alert_ids),
        heartbeat_alert_id=heartbeat_alert_id,
    )


def execute_monitor_flow(paths: RuntimePaths, *, runtime_config: RuntimeConfig | None = None) -> MonitorFlowSummary:
    config = runtime_config or load_runtime_config()
    outcome = run_monitor(paths, runtime_config=config)
    conn = connect_db(paths.db_path)
    apply_migrations(conn)
    repository = RuntimeRepository(conn)
    delivered_alert_ids: list[str] = []
    now_iso = _now_iso()

    for payload in outcome.fired_actions + outcome.pending_recheck_actions:
        source_alert = repository.get_alert(str(payload["alert_id"]))
        if source_alert is None:
            continue
        monitor_alert_id = str(uuid4())
        message = render_monitor_alert(
            {
                "thesis": source_alert["why_now"] or source_alert["thesis_cluster_id"] or "-",
                "trigger": payload,
                "suggested_action": payload["suggested_action"],
            }
        )
        message_ref = _deliver_message(
            config=config,
            text=message,
            alert_id=monitor_alert_id,
            thesis_cluster_id=str(payload["thesis_cluster_id"]),
        )
        repository.insert_alert(
            {
                "id": monitor_alert_id,
                "run_id": outcome.run_id,
                "thesis_cluster_id": payload["thesis_cluster_id"],
                "condition_id": source_alert["condition_id"],
                "event_id": source_alert["event_id"],
                "market_id": source_alert["market_id"],
                "token_id": source_alert["token_id"],
                "alert_kind": "monitor",
                "delivery_mode": "immediate",
                "why_now": message,
                "status": "active",
                "telegram_chat_id": message_ref.chat_id if message_ref else None,
                "telegram_message_id": message_ref.message_id if message_ref else None,
                "dedupe_key": f"monitor::{payload['trigger_id']}::{now_iso}",
                "created_at": now_iso,
            }
        )
        delivered_alert_ids.append(monitor_alert_id)

    return MonitorFlowSummary(
        run_id=outcome.run_id,
        delivered_alert_ids=tuple(delivered_alert_ids),
        stale_alert_ids=tuple(outcome.stale_alert_ids),
    )


def _judge_seed(
    *,
    skill: SkillAdapter,
    conn,
    seed: AlertSeed,
    configured_evidence: Iterable[EvidenceItem],
    registry,
) -> ParsedJudgment:
    evidence_items = _merge_evidence(seed, configured_evidence)
    enriched = enrich_evidence(evidence_items, registry)
    context = build_judgment_context(
        candidate_facts=_seed_candidate_facts(seed),
        rules_text=None,
        executable_fields=_seed_executable_fields(seed),
        enriched_evidence=enriched,
        prior_cluster_state=None,
        position_context=_lookup_position_context(conn, seed.token_id),
    )
    if seed.judgment_seed:
        context["judgment_seed"] = seed.judgment_seed
    return skill.judge(context)


def _is_strict_allowed(seed: AlertSeed, configured_evidence: Iterable[EvidenceItem], registry) -> bool:
    evidence_items = _merge_evidence(seed, configured_evidence)
    return enrich_evidence(evidence_items, registry).strict_allowed


def _load_configured_evidence(config: RuntimeConfig) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []
    if config.news_samples_path:
        evidence.extend(NewsClient().normalize_items(_load_json_rows(config.news_samples_path)))
    if config.x_samples_path:
        evidence.extend(XClient().normalize_items(_load_json_rows(config.x_samples_path)))
    return evidence


def _load_json_rows(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else []


def _merge_evidence(seed: AlertSeed, configured_items: Iterable[EvidenceItem]) -> list[EvidenceItem]:
    merged = list(configured_items)
    for raw in seed.evidence_seeds:
        if "source_kind" not in raw:
            continue
        merged.append(
            EvidenceItem(
                source_id=str(raw.get("source_id") or raw.get("source") or "seed"),
                source_kind=str(raw.get("source_kind") or raw.get("source") or "unknown"),
                fetched_at=str(raw.get("fetched_at") or _now_iso()),
                url=str(raw.get("url") or "about:blank"),
                claim_snippet=str(raw.get("claim_snippet") or raw.get("claim") or "seed evidence"),
                tier=str(raw.get("tier") or ""),
                conflict_status=str(raw["conflict_status"]) if raw.get("conflict_status") else None,
            )
        )
    return merged


def _finalize_alert_kind(parsed: ParsedJudgment, seed: AlertSeed, *, strict_allowed: bool) -> str:
    desired = parsed.alert_kind
    if desired in {"strict", "strict_degraded", "reprice"}:
        if not strict_allowed:
            return "research"
        if seed.is_degraded:
            return "strict_degraded"
    return desired


def _stable_cluster_id(seed: AlertSeed, parsed: ParsedJudgment) -> str:
    raw_key = parsed.archive_payload.get("thesis_cluster_id") or seed.condition_id or seed.expression_key
    return f"cluster-{uuid5(NAMESPACE_URL, str(raw_key))}"


def _resolve_timers(parsed: ParsedJudgment, now_iso: str) -> tuple[str | None, str | None]:
    if parsed.evidence_fresh_until and parsed.recheck_required_at:
        return parsed.evidence_fresh_until, parsed.recheck_required_at
    now = datetime.fromisoformat(now_iso)
    ttl = max(parsed.ttl_hours, 1)
    fresh_until = parsed.evidence_fresh_until or (now + timedelta(hours=ttl)).isoformat()
    recheck_at = parsed.recheck_required_at or (now + timedelta(hours=max(ttl // 2, 1))).isoformat()
    return fresh_until, recheck_at


def _build_render_payload(
    seed: AlertSeed,
    parsed: ParsedJudgment,
    final_kind: str,
    fresh_until: str | None,
    recheck_at: str | None,
    cluster_id: str,
) -> dict[str, Any]:
    return {
        "mode": "STRICT-DEGRADED" if final_kind == "strict_degraded" else final_kind.upper().replace("_", "-"),
        "thesis": parsed.thesis or seed.expression_summary,
        "thesis_cluster_id": cluster_id,
        "expression": seed.expression_summary,
        "side": parsed.side or "NO",
        "theoretical_edge_cents": parsed.theoretical_edge_cents,
        "executable_edge_cents": parsed.executable_edge_cents,
        "max_entry_cents": parsed.max_entry_cents,
        "suggested_size_usdc": parsed.suggested_size_usdc,
        "why_now": parsed.why_now or parsed.summary or seed.expression_summary,
        "kill_criteria_text": parsed.kill_criteria_text or "See updated evidence set.",
        "evidence_fresh_until": fresh_until,
        "recheck_required_at": recheck_at,
        "summary": parsed.summary or parsed.why_now or seed.expression_summary,
        "watch_item": parsed.watch_item or parsed.kill_criteria_text or "Monitor evidence freshness.",
        "citations": [citation.model_dump(exclude_none=True) for citation in parsed.citations],
        "triggers": [trigger.model_dump(exclude_none=True) for trigger in parsed.triggers],
        "archive_payload": parsed.archive_payload,
    }


def _upsert_cluster_state(
    repository: RuntimeRepository,
    *,
    seed: AlertSeed,
    cluster_id: str,
    canonical_name: str,
    now_iso: str,
) -> None:
    repository.upsert_thesis_cluster(
        {
            "id": cluster_id,
            "canonical_name": canonical_name,
            "status": "open",
            "cluster_version": 1,
            "cluster_reason": seed.expression_key,
            "closed_reason": None,
            "closed_at": None,
            "reopen_reason": None,
            "last_alert_id": seed.id,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
    )
    repository.upsert_cluster_expression(
        {
            "id": str(uuid5(NAMESPACE_URL, f"expr::{seed.market_id}")),
            "thesis_cluster_id": cluster_id,
            "condition_id": seed.condition_id,
            "event_id": seed.event_id,
            "market_id": seed.market_id,
            "token_id": seed.token_id,
            "event_slug": None,
            "market_slug": None,
            "expression_label": seed.expression_summary,
            "is_primary_expression": 1,
            "first_seen_at": now_iso,
            "last_seen_at": now_iso,
        }
    )


def _sync_source_registry(repository: RuntimeRepository, registry, *, now_iso: str) -> None:
    tier_map: dict[str, str] = {}
    for tier_name, members in registry.tier_metadata.items():
        for member in members:
            tier_map[member] = tier_name
    for entry in registry.sources:
        repository.upsert_source(
            {
                "id": _source_id(entry.domain_or_handle),
                "source_name": entry.name,
                "source_kind": entry.kind,
                "source_tier": tier_map.get(
                    entry.domain_or_handle,
                    "primary" if entry.is_primary_allowed else "supplementary",
                ),
                "domain_or_handle": entry.domain_or_handle,
                "is_primary_allowed": 1 if entry.is_primary_allowed else 0,
                "is_active": 1,
                "config_version": registry.version,
                "created_at": now_iso,
                "updated_at": now_iso,
            }
        )


def _persist_claim_mappings(
    repository: RuntimeRepository,
    registry,
    *,
    alert_id: str,
    thesis_cluster_id: str,
    citations,
    now_iso: str,
) -> None:
    for citation in citations:
        source_id = citation.source_id
        source_name = citation.source_name or (citation.source.name if citation.source else None) or citation.source_id
        source_tier = citation.source_tier or (citation.source.tier if citation.source else None) or "unknown"
        fetched_at = citation.fetched_at or (citation.source.fetched_at if citation.source else None) or now_iso
        repository.upsert_source(
            {
                "id": source_id,
                "source_name": source_name,
                "source_kind": "news",
                "source_tier": source_tier,
                "domain_or_handle": citation.url,
                "is_primary_allowed": 1 if source_tier == "primary" else 0,
                "is_active": 1,
                "config_version": registry.version,
                "created_at": now_iso,
                "updated_at": now_iso,
            }
        )
        repository.insert_claim_mapping(
            {
                "id": str(uuid4()),
                "alert_id": alert_id,
                "thesis_cluster_id": thesis_cluster_id,
                "claim_type": citation.claim_scope or "evidence",
                "claim_text": citation.claim,
                "source_id": source_id,
                "url": citation.url,
                "fetched_at": fetched_at,
                "conflict_status": "active",
                "superseded_by_mapping_id": None,
            }
        )


def _replace_triggers(
    conn,
    repository: RuntimeRepository,
    *,
    alert_id: str,
    thesis_cluster_id: str,
    parsed_triggers: list[Trigger],
    now_iso: str,
) -> None:
    conn.execute("DELETE FROM triggers WHERE alert_id = ?", [alert_id])
    conn.commit()
    repository.insert_triggers(
        [
            {
                "id": trigger.trigger_id or str(uuid4()),
                "thesis_cluster_id": thesis_cluster_id,
                "alert_id": alert_id,
                "trigger_type": trigger.trigger_type or trigger.kind,
                "threshold_kind": trigger.metadata.get("threshold_kind") or "price",
                "comparison": trigger.metadata.get("comparison") or "<=",
                "threshold_value": str(trigger.threshold or trigger.condition),
                "suggested_action": trigger.suggested_action or "Review",
                "requires_llm_recheck": 1
                if trigger.metadata.get("requires_llm_recheck") or trigger.trigger_type == "narrative_reassessment"
                else 0,
                "human_note": trigger.condition,
                "state": trigger.trigger_state or "armed",
                "cooldown_until": None,
                "last_fired_at": trigger.fired_at,
                "created_at": now_iso,
                "updated_at": now_iso,
            }
            for trigger in parsed_triggers
        ]
    )


def _seed_candidate_facts(seed: AlertSeed) -> dict[str, Any]:
    return {
        "event_id": seed.event_id,
        "market_id": seed.market_id,
        "token_id": seed.token_id,
        "condition_id": seed.condition_id,
        "expression_summary": seed.expression_summary,
        "expression_key": seed.expression_key,
        "degraded_reason": seed.degraded_reason,
    }


def _seed_executable_fields(seed: AlertSeed) -> dict[str, Any]:
    return {
        "spread_bps": seed.spread_bps,
        "slippage_bps": seed.slippage_bps,
        "is_degraded": seed.is_degraded,
        "degraded_reason": seed.degraded_reason,
    }


def _lookup_position_context(conn, token_id: str) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT SUM(size_shares) AS size_shares, MAX(avg_entry_cents) AS avg_entry_cents
        FROM positions
        WHERE token_id = ?
        """,
        [token_id],
    ).fetchone()
    if row is None:
        return {}
    return {"size_shares": row["size_shares"], "avg_entry_cents": row["avg_entry_cents"]}


def _delivery_mode_for_alert_kind(alert_kind: str) -> str:
    if alert_kind in {"strict", "strict_degraded", "reprice"}:
        return "immediate"
    if alert_kind == "research":
        return "digest"
    if alert_kind == "monitor":
        return "immediate"
    return "system"


def _deliver_message(
    *,
    config: RuntimeConfig,
    text: str,
    alert_id: str,
    thesis_cluster_id: str,
) -> TelegramMessageRef | None:
    if not config.telegram_chat_id:
        return None
    keyboard = (
        build_feedback_keyboard(alert_id=alert_id, thesis_cluster_id=thesis_cluster_id)
        if thesis_cluster_id not in {"research", "heartbeat"}
        else None
    )
    with TelegramClient() as telegram:
        return telegram.send_message(chat_id=config.telegram_chat_id, text=text, inline_keyboard=keyboard)


def _source_id(domain_or_handle: str) -> str:
    slug = domain_or_handle.strip().lower().replace("https://", "").replace("http://", "")
    slug = slug.replace("/", "-").replace("@", "at-").replace(".", "-")
    return slug or f"source-{uuid4()}"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
