from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable
from uuid import NAMESPACE_URL, uuid4, uuid5

from polymarket_alert_bot.config.settings import RuntimeConfig
from polymarket_alert_bot.delivery.callback_router import build_feedback_keyboard
from polymarket_alert_bot.delivery.telegram_client import TelegramClient, TelegramMessageRef
from polymarket_alert_bot.judgment.result_parser import ParsedJudgment, Trigger
from polymarket_alert_bot.scanner.board_scan import AlertSeed
from polymarket_alert_bot.scanner.market_link import build_polymarket_market_url
from polymarket_alert_bot.sources.evidence_enricher import EvidenceItem
from polymarket_alert_bot.sources.news_client import NewsClient
from polymarket_alert_bot.sources.x_client import XClient
from polymarket_alert_bot.storage.repositories import RuntimeRepository


@dataclass(frozen=True)
class EvidenceLoadResult:
    items: tuple[EvidenceItem, ...]
    degraded_reasons: tuple[str, ...]


def _load_configured_evidence(config: RuntimeConfig, *, registry) -> EvidenceLoadResult:
    evidence: list[EvidenceItem] = []
    degraded_reasons: list[str] = []
    news_source = config.news_feed_url or config.news_samples_path
    if news_source:
        try:
            evidence.extend(NewsClient().fetch_items(news_source))
        except Exception as exc:
            degraded_reasons.append(f"news_feed_failed:{exc.__class__.__name__}")
    x_source = config.x_feed_url or config.x_samples_path
    if x_source:
        try:
            evidence.extend(XClient().fetch_items(x_source, allowed_handles=registry.x_handles))
        except Exception as exc:
            degraded_reasons.append(f"x_feed_failed:{exc.__class__.__name__}")
    return EvidenceLoadResult(items=tuple(evidence), degraded_reasons=tuple(degraded_reasons))


def _merge_evidence(
    seed: AlertSeed,
    configured_items: Iterable[EvidenceItem],
    *,
    retrieved_items: Iterable[EvidenceItem] = (),
) -> list[EvidenceItem]:
    merged: list[EvidenceItem] = []
    seen: set[tuple[str, str, str]] = set()
    base_items = (*configured_items, *retrieved_items)
    for item in base_items:
        key = (item.source_id, item.url, item.claim_snippet)
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    for raw in seed.evidence_seeds:
        if "source_kind" not in raw:
            continue
        item = EvidenceItem(
            source_id=str(raw.get("source_id") or raw.get("source") or "seed"),
            source_kind=str(raw.get("source_kind") or raw.get("source") or "unknown"),
            fetched_at=str(raw.get("fetched_at") or _now_iso()),
            url=str(raw.get("url") or "about:blank"),
            claim_snippet=str(raw.get("claim_snippet") or raw.get("claim") or "seed evidence"),
            tier=str(raw.get("tier") or ""),
            conflict_status=str(raw["conflict_status"]) if raw.get("conflict_status") else None,
        )
        key = (item.source_id, item.url, item.claim_snippet)
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def _finalize_alert_kind(
    parsed: ParsedJudgment,
    seed: AlertSeed,
    *,
    strict_allowed: bool,
    evidence_degraded: bool = False,
) -> str:
    desired = parsed.alert_kind
    if desired in {"strict", "strict_degraded"}:
        if not strict_allowed:
            return "research"
        if seed.is_degraded or evidence_degraded:
            return "strict_degraded"
    if desired == "reprice":
        return "reprice"
    return desired


def _stable_cluster_id(seed: AlertSeed, parsed: ParsedJudgment) -> str:
    raw_key = (
        parsed.archive_payload.get("thesis_cluster_id") or seed.condition_id or seed.expression_key
    )
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
    market_link = seed.market_link or build_polymarket_market_url(
        event_slug=seed.event_slug,
        market_slug=seed.market_slug,
    )
    return {
        "mode": "STRICT-DEGRADED"
        if final_kind == "strict_degraded"
        else final_kind.upper().replace("_", "-"),
        "thesis": parsed.thesis or seed.expression_summary,
        "thesis_cluster_id": cluster_id,
        "expression": seed.expression_summary,
        "event_slug": seed.event_slug,
        "market_slug": seed.market_slug,
        "market_link": market_link,
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
        "watch_item": parsed.watch_item
        or parsed.kill_criteria_text
        or "Monitor evidence freshness.",
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
            "event_slug": seed.event_slug,
            "market_slug": seed.market_slug,
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
    conn,
    repository: RuntimeRepository,
    registry,
    *,
    alert_id: str,
    thesis_cluster_id: str,
    citations,
    now_iso: str,
) -> None:
    conn.execute("DELETE FROM claim_source_mappings WHERE alert_id = ?", [alert_id])
    conn.commit()
    for citation in citations:
        source_id = citation.source_id
        source_name = (
            citation.source_name
            or (citation.source.name if citation.source else None)
            or citation.source_id
        )
        source_tier = (
            citation.source_tier or (citation.source.tier if citation.source else None) or "unknown"
        )
        fetched_at = (
            citation.fetched_at
            or (citation.source.fetched_at if citation.source else None)
            or now_iso
        )
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


def _persisted_trigger_defaults(trigger: Trigger) -> dict[str, object]:
    trigger_type = str(trigger.trigger_type or trigger.kind or "").strip().lower()
    defaults: dict[str, dict[str, object]] = {
        "price_reprice": {
            "threshold_kind": "price",
            "comparison": "<=",
            "requires_llm_recheck": False,
        },
        "price_threshold": {
            "threshold_kind": "execution_cost",
            "comparison": "<=",
            "requires_llm_recheck": True,
        },
        "evidence_freshness_expiry": {
            "threshold_kind": "time",
            "comparison": "<=",
            "requires_llm_recheck": True,
        },
        "evidence_freshness": {
            "threshold_kind": "time",
            "comparison": ">=",
            "requires_llm_recheck": True,
        },
        "rule_change": {
            "threshold_kind": "narrative",
            "comparison": "eq",
            "requires_llm_recheck": True,
        },
        "rule_change_monitor": {
            "threshold_kind": "narrative",
            "comparison": "eq",
            "requires_llm_recheck": True,
        },
        "catalyst_checkpoint": {
            "threshold_kind": "narrative",
            "comparison": "eq",
            "requires_llm_recheck": True,
        },
        "market_data_recheck": {
            "threshold_kind": "book_state",
            "comparison": "state_change",
            "requires_llm_recheck": False,
        },
        "narrative_reassessment": {
            "threshold_kind": "narrative",
            "comparison": "eq",
            "requires_llm_recheck": True,
        },
        "narrative_recheck": {
            "threshold_kind": "narrative",
            "comparison": "eq",
            "requires_llm_recheck": True,
        },
    }
    return defaults.get(
        trigger_type,
        {
            "threshold_kind": "price",
            "comparison": "<=",
            "requires_llm_recheck": False,
        },
    )


def _persisted_trigger_threshold_value(trigger: Trigger) -> str:
    if trigger.threshold_value not in (None, ""):
        return str(trigger.threshold_value)
    if trigger.threshold not in (None, ""):
        return str(trigger.threshold)
    if trigger.metadata.get("threshold_value") not in (None, ""):
        return str(trigger.metadata["threshold_value"])
    trigger_type = str(trigger.trigger_type or trigger.kind or "").strip().lower()
    if trigger_type == "market_data_recheck":
        return "quotes_available"
    return str(trigger.condition)


def _persisted_trigger_threshold_kind(trigger: Trigger) -> str:
    if trigger.threshold_kind not in (None, ""):
        return str(trigger.threshold_kind)
    if trigger.metadata.get("threshold_kind") not in (None, ""):
        return str(trigger.metadata["threshold_kind"])
    return str(_persisted_trigger_defaults(trigger)["threshold_kind"])


def _persisted_trigger_comparison(trigger: Trigger) -> str:
    if trigger.comparison not in (None, ""):
        return str(trigger.comparison)
    if trigger.metadata.get("comparison") not in (None, ""):
        return str(trigger.metadata["comparison"])
    return str(_persisted_trigger_defaults(trigger)["comparison"])


def _persisted_trigger_requires_recheck(trigger: Trigger) -> bool:
    if trigger.requires_llm_recheck is not None:
        return bool(trigger.requires_llm_recheck)
    if "requires_llm_recheck" in trigger.metadata:
        return bool(trigger.metadata["requires_llm_recheck"])
    return bool(_persisted_trigger_defaults(trigger)["requires_llm_recheck"])


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
                "threshold_kind": _persisted_trigger_threshold_kind(trigger),
                "comparison": _persisted_trigger_comparison(trigger),
                "threshold_value": _persisted_trigger_threshold_value(trigger),
                "suggested_action": trigger.suggested_action or "Review",
                "requires_llm_recheck": 1 if _persisted_trigger_requires_recheck(trigger) else 0,
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
        "platform": "Polymarket",
        "event_id": seed.event_id,
        "event_title": seed.event_title,
        "event_category": seed.event_category,
        "event_end_time": seed.event_end_time,
        "market_id": seed.market_id,
        "market_question": seed.question,
        "outcome_name": seed.outcome_name,
        "token_id": seed.token_id,
        "condition_id": seed.condition_id,
        "event_slug": seed.event_slug,
        "market_slug": seed.market_slug,
        "market_link": seed.market_link,
        "market_url": seed.market_link,
        "expression_summary": seed.expression_summary,
        "expression_key": seed.expression_key,
        "family_summary": seed.family_summary.as_dict(),
        "ranking_summary": seed.ranking_summary,
        "rules_text": seed.rules_text or "",
        "degraded_reason": seed.degraded_reason,
    }


def _seed_executable_fields(seed: AlertSeed) -> dict[str, Any]:
    return {
        "best_bid_cents": seed.best_bid_cents,
        "best_ask_cents": seed.best_ask_cents,
        "mid_cents": seed.mid_cents,
        "last_price_cents": seed.last_price_cents,
        "max_entry_cents": seed.best_ask_cents,
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
    message_ref: TelegramMessageRef | None = None,
) -> TelegramMessageRef | None:
    if not config.telegram_chat_id:
        return message_ref
    keyboard = (
        build_feedback_keyboard(alert_id=alert_id, thesis_cluster_id=thesis_cluster_id)
        if thesis_cluster_id not in {"research", "heartbeat"}
        else None
    )
    with TelegramClient() as telegram:
        return telegram.upsert_message(
            chat_id=config.telegram_chat_id,
            text=text,
            message_ref=message_ref,
            inline_keyboard=keyboard,
            message_thread_id=config.telegram_message_thread_id,
        )


def _message_ref_from_alert(alert_row) -> TelegramMessageRef | None:
    if alert_row is None:
        return None
    chat_id = alert_row["telegram_chat_id"]
    message_id = alert_row["telegram_message_id"]
    if not chat_id or not message_id:
        return None
    return TelegramMessageRef(chat_id=str(chat_id), message_id=str(message_id))


def _source_id(domain_or_handle: str) -> str:
    slug = domain_or_handle.strip().lower().replace("https://", "").replace("http://", "")
    slug = slug.replace("/", "-").replace("@", "at-").replace(".", "-")
    return slug or f"source-{uuid4()}"


def _combine_degraded_reason(*parts: str | None) -> str | None:
    normalized: list[str] = []
    for part in parts:
        if part is None:
            continue
        text = str(part).strip()
        if text and text not in normalized:
            normalized.append(text)
    return ";".join(normalized) if normalized else None


def _resolve_alert_market_link(conn, alert_row) -> str | None:
    row_keys = set(alert_row.keys())
    if "event_slug" in row_keys or "market_slug" in row_keys:
        direct_link = build_polymarket_market_url(
            event_slug=alert_row["event_slug"] if "event_slug" in row_keys else None,
            market_slug=alert_row["market_slug"] if "market_slug" in row_keys else None,
        )
        if direct_link:
            return direct_link

    row = conn.execute(
        """
        SELECT event_slug, market_slug
        FROM cluster_expressions
        WHERE market_id = ?
           OR (thesis_cluster_id = ? AND condition_id = ?)
        ORDER BY is_primary_expression DESC, last_seen_at DESC
        LIMIT 1
        """,
        [alert_row["market_id"], alert_row["thesis_cluster_id"], alert_row["condition_id"]],
    ).fetchone()
    if row is None:
        return None
    return build_polymarket_market_url(
        event_slug=row["event_slug"],
        market_slug=row["market_slug"],
    )


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
