from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlparse

from polymarket_alert_bot.models.records import SourceRegistry

PRIMARY_TIERS = {"official", "platform", "news"}
SUPPLEMENTARY_TIERS = {"x"}
UNRESOLVED_CONFLICT_STATUSES = {"active", "conflicted", "unresolved"}
MIN_PRIMARY_SUPPORT_FOR_STRICT = 2


@dataclass(slots=True)
class EvidenceItem:
    source_id: str
    source_kind: str
    fetched_at: str
    url: str
    claim_snippet: str
    tier: str
    conflict_status: str | None = None


@dataclass(slots=True)
class EnrichedEvidence:
    items: list[EvidenceItem]
    primary_support_count: int
    supplementary_count: int
    unknown_count: int
    unresolved_primary_conflict: bool
    strict_allowed: bool
    strict_block_reason: str | None


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def infer_tier(*, source_kind: str, url: str, source_registry: SourceRegistry) -> str:
    normalized_kind = source_kind.lower()
    if normalized_kind in SUPPLEMENTARY_TIERS:
        return "supplementary"
    if normalized_kind in {"official", "platform"}:
        return "primary"

    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    if host in source_registry.primary_domains:
        return "primary"

    return "supplementary" if normalized_kind == "x" else "unknown"


def enrich_evidence(
    evidence_items: Iterable[EvidenceItem | dict[str, object]],
    source_registry: SourceRegistry,
) -> EnrichedEvidence:
    normalized: list[EvidenceItem] = []
    primary_support_count = 0
    supplementary_count = 0
    unknown_count = 0
    unresolved_primary_conflict = False

    for item in evidence_items:
        if isinstance(item, EvidenceItem):
            evidence = item
        else:
            evidence = EvidenceItem(
                source_id=str(item["source_id"]),
                source_kind=str(item["source_kind"]),
                fetched_at=str(item.get("fetched_at") or _now_iso()),
                url=str(item["url"]),
                claim_snippet=str(item["claim_snippet"]),
                tier=str(item.get("tier") or ""),
                conflict_status=str(item["conflict_status"]) if item.get("conflict_status") else None,
            )

        inferred_tier = evidence.tier or infer_tier(
            source_kind=evidence.source_kind,
            url=evidence.url,
            source_registry=source_registry,
        )
        evidence.tier = inferred_tier
        normalized.append(evidence)

        if inferred_tier == "primary":
            primary_support_count += 1
            if evidence.conflict_status in UNRESOLVED_CONFLICT_STATUSES:
                unresolved_primary_conflict = True
        elif inferred_tier == "supplementary":
            supplementary_count += 1
        else:
            unknown_count += 1

    strict_block_reason: str | None = None
    strict_allowed = True
    if primary_support_count < MIN_PRIMARY_SUPPORT_FOR_STRICT:
        strict_allowed = False
        strict_block_reason = "no_primary_support"
    elif unresolved_primary_conflict:
        strict_allowed = False
        strict_block_reason = "unresolved_primary_conflict"

    return EnrichedEvidence(
        items=normalized,
        primary_support_count=primary_support_count,
        supplementary_count=supplementary_count,
        unknown_count=unknown_count,
        unresolved_primary_conflict=unresolved_primary_conflict,
        strict_allowed=strict_allowed,
        strict_block_reason=strict_block_reason,
    )
