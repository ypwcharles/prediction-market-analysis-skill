from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from polymarket_alert_bot.archive.writer import write_archive_artifact
from polymarket_alert_bot.config.settings import RuntimeConfig, RuntimePaths, load_runtime_config
from polymarket_alert_bot.config.source_registry import load_source_registry
from polymarket_alert_bot.flows.shared import (
    _build_render_payload,
    _combine_degraded_reason,
    _deliver_message,
    _delivery_mode_for_alert_kind,
    _finalize_alert_kind,
    _load_configured_evidence,
    _lookup_position_context,
    _merge_evidence,
    _message_ref_from_alert,
    _now_iso,
    _persist_claim_mappings,
    _replace_triggers,
    _resolve_timers,
    _seed_candidate_facts,
    _seed_executable_fields,
    _stable_cluster_id,
    _sync_source_registry,
    _upsert_cluster_state,
)
from polymarket_alert_bot.judgment.context_builder import build_judgment_context
from polymarket_alert_bot.judgment.result_parser import ParsedJudgment
from polymarket_alert_bot.judgment.skill_adapter import SkillAdapter
from polymarket_alert_bot.scanner.board_scan import AlertSeed, run_scan
from polymarket_alert_bot.sources.evidence_enricher import EvidenceItem, enrich_evidence
from polymarket_alert_bot.sources.shortlist_retrieval import retrieve_shortlist_evidence
from polymarket_alert_bot.storage.db import connect_db
from polymarket_alert_bot.storage.migrations import apply_migrations
from polymarket_alert_bot.storage.repositories import RuntimeRepository
from polymarket_alert_bot.templates.heartbeat import render_heartbeat
from polymarket_alert_bot.templates.research_digest import render_research_digest
from polymarket_alert_bot.templates.strict_memo import render_strict_memo


@dataclass(frozen=True)
class ScanFlowSummary:
    run_id: str
    strict_alert_ids: tuple[str, ...]
    research_alert_ids: tuple[str, ...]
    heartbeat_alert_id: str | None


def execute_scan_flow(
    paths: RuntimePaths, *, runtime_config: RuntimeConfig | None = None
) -> ScanFlowSummary:
    config = runtime_config or load_runtime_config()
    scan_result = run_scan(paths, max_judgment_candidates=config.scan_max_judgment_candidates)
    conn = connect_db(paths.db_path)
    apply_migrations(conn)
    repository = RuntimeRepository(conn)
    registry = load_source_registry(paths.sources_path)
    now_iso = _now_iso()
    _sync_source_registry(repository, registry, now_iso=now_iso)
    evidence_result = _load_configured_evidence(config, registry=registry)
    configured_evidence = evidence_result.items
    evidence_degraded = bool(evidence_result.degraded_reasons)
    degraded_reasons: list[str] = []
    if scan_result.degraded_reason:
        degraded_reasons.append(scan_result.degraded_reason)
    degraded_reasons.extend(evidence_result.degraded_reasons)

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
        existing_alert = repository.get_alert(seed.id)
        retrieval_result = retrieve_shortlist_evidence(seed, config, registry=registry)
        degraded_reasons.extend(retrieval_result.degraded_reasons)
        seed_evidence_degraded = evidence_degraded or bool(retrieval_result.degraded_reasons)
        parsed = _judge_seed(
            skill=skill,
            conn=conn,
            seed=seed,
            configured_evidence=configured_evidence,
            retrieved_evidence=retrieval_result.items,
            registry=registry,
        )
        final_kind = _finalize_alert_kind(
            parsed,
            seed,
            strict_allowed=_is_strict_allowed(
                seed,
                configured_evidence,
                registry,
                retrieved_evidence=retrieval_result.items,
            ),
            evidence_degraded=seed_evidence_degraded,
        )
        cluster_id = _stable_cluster_id(seed, parsed)
        fresh_until, recheck_at = _resolve_timers(parsed, seed_now)
        render_payload = _build_render_payload(
            seed, parsed, final_kind, fresh_until, recheck_at, cluster_id
        )

        _upsert_cluster_state(
            repository,
            seed=seed,
            cluster_id=cluster_id,
            canonical_name=render_payload["thesis"],
            now_iso=seed_now,
        )
        _persist_claim_mappings(
            conn,
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
        message_ref = None
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
                message_ref=_message_ref_from_alert(existing_alert),
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

    combined_degraded_reason = _combine_degraded_reason(*degraded_reasons)

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
                "degraded": scan_result.status == "degraded" or evidence_degraded,
                "degraded_reason": combined_degraded_reason,
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
            combined_degraded_reason,
            "degraded"
            if scan_result.status == "degraded" or evidence_degraded
            else scan_result.status,
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


def _judge_seed(
    *,
    skill: SkillAdapter,
    conn,
    seed: AlertSeed,
    configured_evidence: Iterable[EvidenceItem],
    retrieved_evidence: Iterable[EvidenceItem],
    registry,
) -> ParsedJudgment:
    evidence_items = _merge_evidence(seed, configured_evidence, retrieved_items=retrieved_evidence)
    enriched = enrich_evidence(evidence_items, registry)
    context = build_judgment_context(
        candidate_facts=_seed_candidate_facts(seed),
        rules_text=seed.rules_text,
        executable_fields=_seed_executable_fields(seed),
        enriched_evidence=enriched,
        prior_cluster_state=None,
        position_context=_lookup_position_context(conn, seed.token_id),
    )
    if seed.judgment_seed:
        context["judgment_seed"] = seed.judgment_seed
    return skill.judge(context)


def _is_strict_allowed(
    seed: AlertSeed,
    configured_evidence: Iterable[EvidenceItem],
    registry,
    *,
    retrieved_evidence: Iterable[EvidenceItem],
) -> bool:
    evidence_items = _merge_evidence(seed, configured_evidence, retrieved_items=retrieved_evidence)
    return enrich_evidence(evidence_items, registry).strict_allowed
