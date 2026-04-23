from __future__ import annotations

from typing import Any

from polymarket_alert_bot.sources.evidence_enricher import EnrichedEvidence


def build_judgment_context(
    *,
    candidate_facts: dict[str, Any],
    rules_text: str | None,
    executable_fields: dict[str, Any],
    enriched_evidence: EnrichedEvidence,
    prior_cluster_state: dict[str, Any] | None = None,
    position_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "candidate_facts": candidate_facts,
        "rules_text": rules_text or "",
        "executable_fields": executable_fields,
        "evidence": [
            {
                "source_id": item.source_id,
                "source_kind": item.source_kind,
                "fetched_at": item.fetched_at,
                "url": item.url,
                "claim_snippet": item.claim_snippet,
                "tier": item.tier,
                "conflict_status": item.conflict_status,
                "claim_slot": item.claim_slot,
                "claim_key": item.claim_key,
                "independent_key": item.independent_key,
            }
            for item in enriched_evidence.items
        ],
        "source_tier_state": {
            "strict_allowed": enriched_evidence.strict_allowed,
            "strict_block_reason": enriched_evidence.strict_block_reason,
            "primary_support_count": enriched_evidence.primary_support_count,
            "supplementary_count": enriched_evidence.supplementary_count,
            "unknown_count": enriched_evidence.unknown_count,
            "unresolved_primary_conflict": enriched_evidence.unresolved_primary_conflict,
            "corroborated_primary_claim_count": enriched_evidence.corroborated_primary_claim_count,
            "corroborated_primary_slots": list(enriched_evidence.corroborated_primary_slots),
            "claim_slot_counts": enriched_evidence.claim_slot_counts,
        },
        "prior_cluster_state": prior_cluster_state or {},
        "position_context": position_context or {},
    }
