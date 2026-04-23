from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlparse

from polymarket_alert_bot.models.records import SourceRegistry

PRIMARY_TIERS = {"official", "platform", "news"}
SUPPLEMENTARY_TIERS = {"x"}
UNRESOLVED_CONFLICT_STATUSES = {"active", "conflicted", "unresolved"}
MIN_PRIMARY_SUPPORT_FOR_STRICT = 2
CLAIM_STOPWORDS = {
    "the",
    "and",
    "that",
    "this",
    "with",
    "from",
    "will",
    "into",
    "about",
    "still",
    "after",
    "before",
    "market",
    "markets",
    "reported",
    "reports",
    "report",
    "says",
    "said",
    "update",
    "updates",
}


@dataclass(slots=True)
class EvidenceItem:
    source_id: str
    source_kind: str
    fetched_at: str
    url: str
    claim_snippet: str
    tier: str
    conflict_status: str | None = None
    claim_slot: str | None = None
    claim_key: str | None = None
    independent_key: str | None = None


@dataclass(slots=True)
class EnrichedEvidence:
    items: list[EvidenceItem]
    primary_support_count: int
    supplementary_count: int
    unknown_count: int
    unresolved_primary_conflict: bool
    strict_allowed: bool
    strict_block_reason: str | None
    corroborated_primary_claim_count: int
    corroborated_primary_slots: tuple[str, ...]
    claim_slot_counts: dict[str, int]


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


def infer_claim_slot(*, claim_snippet: str, source_kind: str, url: str) -> str | None:
    text = _normalize_text(claim_snippet)
    host = urlparse(url).netloc.lower()
    if source_kind.lower() in {"platform"} or "kalshi" in host:
        return "external_anchor"
    if any(marker in text for marker in ("odds", "book", "price", "repricing", "implied")):
        return "external_anchor"
    if any(
        marker in text
        for marker in (
            "resolve",
            "resolution",
            "resolution criteria",
            "certified",
            "official result",
            "settlement",
            "winner is certified",
        )
    ):
        return "settlement_claim"
    if any(
        marker in text
        for marker in (
            "by ",
            "before ",
            "on ",
            "deadline",
            "schedule",
            "hearing",
            "meeting",
            "vote",
            "checkpoint",
        )
    ):
        return "timing_gate"
    if any(
        marker in text
        for marker in (
            "not",
            "no ",
            "denied",
            "without confirmation",
            "rumor",
            "unclear",
            "contradict",
        )
    ):
        return "counter_claim"
    if source_kind.lower() in {"official", "news"}:
        return "settlement_claim"
    return None


def normalize_claim_key(*, claim_snippet: str, claim_slot: str | None = None) -> str | None:
    normalized = _normalize_text(claim_snippet)
    tokens = [
        token
        for token in re.findall(r"[a-z0-9]+", normalized)
        if (len(token) >= 3 or token.isdigit()) and token not in CLAIM_STOPWORDS
    ]
    if not tokens:
        return None
    core = "-".join(tokens[:8])
    return f"{claim_slot or 'claim'}::{core}"


def infer_independent_key(*, source_id: str, source_kind: str, url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    if host:
        return host
    normalized_source = str(source_id).strip().lower()
    if source_kind.lower() == "x" and normalized_source:
        return normalized_source.removeprefix("@")
    return normalized_source or "unknown-source"


def evidence_claim_key(item: EvidenceItem) -> tuple[str, str]:
    claim_key = item.claim_key or normalize_claim_key(
        claim_snippet=item.claim_snippet,
        claim_slot=item.claim_slot,
    )
    independent_key = item.independent_key or infer_independent_key(
        source_id=item.source_id,
        source_kind=item.source_kind,
        url=item.url,
    )
    return claim_key or item.claim_snippet.strip(), independent_key


def enrich_evidence(
    evidence_items: Iterable[EvidenceItem | dict[str, object]],
    source_registry: SourceRegistry,
) -> EnrichedEvidence:
    normalized: list[EvidenceItem] = []
    primary_support_count = 0
    supplementary_count = 0
    unknown_count = 0
    unresolved_primary_conflict = False
    claim_slot_counts: dict[str, int] = {}
    primary_support_by_claim: dict[tuple[str, str], set[str]] = {}
    saw_claim_graph = False

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
                conflict_status=str(item["conflict_status"])
                if item.get("conflict_status")
                else None,
                claim_slot=str(item["claim_slot"]) if item.get("claim_slot") else None,
                claim_key=str(item["claim_key"]) if item.get("claim_key") else None,
                independent_key=str(item["independent_key"])
                if item.get("independent_key")
                else None,
            )

        inferred_tier = evidence.tier or infer_tier(
            source_kind=evidence.source_kind,
            url=evidence.url,
            source_registry=source_registry,
        )
        evidence.tier = inferred_tier
        evidence.claim_slot = evidence.claim_slot or infer_claim_slot(
            claim_snippet=evidence.claim_snippet,
            source_kind=evidence.source_kind,
            url=evidence.url,
        )
        evidence.claim_key = evidence.claim_key or normalize_claim_key(
            claim_snippet=evidence.claim_snippet,
            claim_slot=evidence.claim_slot,
        )
        evidence.independent_key = evidence.independent_key or infer_independent_key(
            source_id=evidence.source_id,
            source_kind=evidence.source_kind,
            url=evidence.url,
        )
        if evidence.claim_slot:
            claim_slot_counts[evidence.claim_slot] = (
                claim_slot_counts.get(evidence.claim_slot, 0) + 1
            )
        normalized.append(evidence)

        if inferred_tier == "primary":
            primary_support_count += 1
            if evidence.conflict_status in UNRESOLVED_CONFLICT_STATUSES:
                unresolved_primary_conflict = True
            if evidence.claim_slot and evidence.claim_key:
                saw_claim_graph = True
                primary_support_by_claim.setdefault(
                    (evidence.claim_slot, evidence.claim_key),
                    set(),
                ).add(evidence.independent_key or evidence.source_id)
        elif inferred_tier == "supplementary":
            supplementary_count += 1
        else:
            unknown_count += 1

    corroborated_claims = {
        key: independent_keys
        for key, independent_keys in primary_support_by_claim.items()
        if len(independent_keys) >= 2
    }
    corroborated_slots = tuple(sorted({slot for slot, _ in corroborated_claims}))

    strict_block_reason: str | None = None
    strict_allowed = True
    if primary_support_count < MIN_PRIMARY_SUPPORT_FOR_STRICT:
        strict_allowed = False
        strict_block_reason = "no_primary_support"
    elif unresolved_primary_conflict:
        strict_allowed = False
        strict_block_reason = "unresolved_primary_conflict"
    elif saw_claim_graph and not corroborated_claims and len(primary_support_by_claim) < 2:
        strict_allowed = False
        strict_block_reason = "uncorroborated_claim_graph"

    return EnrichedEvidence(
        items=normalized,
        primary_support_count=primary_support_count,
        supplementary_count=supplementary_count,
        unknown_count=unknown_count,
        unresolved_primary_conflict=unresolved_primary_conflict,
        strict_allowed=strict_allowed,
        strict_block_reason=strict_block_reason,
        corroborated_primary_claim_count=len(corroborated_claims),
        corroborated_primary_slots=corroborated_slots,
        claim_slot_counts=claim_slot_counts,
    )


def _normalize_text(text: object) -> str:
    return " ".join(str(text).replace("-", " ").replace("_", " ").lower().split())
