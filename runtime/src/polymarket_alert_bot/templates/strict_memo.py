from __future__ import annotations

from typing import Any, Mapping


def _as_text(value: Any, *, default: str = "-") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _format_price(value: Any) -> str:
    if value is None:
        return "-"
    return f"{float(value):.1f}c"


def _format_usdc(value: Any) -> str:
    if value is None:
        return "-"
    return f"{float(value):.0f} USDC"


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _citation_line(index: int, citation: Mapping[str, Any]) -> str:
    claim = _as_text(citation.get("claim"))
    source = citation.get("source", citation.get("source_ref", {}))
    if not isinstance(source, Mapping):
        source = {}
    source_name = _as_text(
        source.get(
            "name", citation.get("source_name", citation.get("source_id", source.get("id")))
        ),
        default="unknown",
    )
    tier = _as_text(source.get("tier", citation.get("source_tier")), default="unknown")
    url = _as_text(source.get("url", citation.get("url")))
    fetched_at = _as_text(source.get("fetched_at", citation.get("fetched_at")))
    detail = (
        f"{index}. {claim}\n   -> {source_name} ({tier})\n   -> {url}\n   -> fetched: {fetched_at}"
    )
    claim_id = _as_text(citation.get("claim_id"), default="")
    if claim_id:
        detail = f"{detail}\n   -> claim_id: {claim_id}"
    claim_scope = _as_text(citation.get("claim_scope"), default="")
    if claim_scope:
        detail = f"{detail}\n   -> claim_scope: {claim_scope}"
    return detail


def _render_claim_aware_citations(citations: list[Mapping[str, Any]]) -> str:
    if not citations:
        return "1. No claim-aware citation was provided."
    return "\n".join(
        _citation_line(index, citation) for index, citation in enumerate(citations, start=1)
    )


def _render_anchor_stack(anchor_stack: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            f"market price anchor: {_format_price(anchor_stack.get('market_price_anchor_cents'))}",
            f"external anchor: {_format_price(anchor_stack.get('external_anchor_cents'))}",
            f"rule-adjusted payout: {_format_price(anchor_stack.get('rule_adjusted_payout_cents'))}",
            "execution-adjusted fair entry: "
            f"{_format_price(anchor_stack.get('execution_adjusted_fair_entry_cents'))}",
            f"anchor gap: {_format_price(anchor_stack.get('anchor_gap_cents'))}",
            f"execution haircut: {_format_price(anchor_stack.get('execution_haircut_cents'))}",
        ]
    )


def _render_execution_overlay(overlay: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            f"alpha type: {_as_text(overlay.get('alpha_type'))}",
            f"execution style: {_as_text(overlay.get('execution_style'))}",
            f"primary sleeve: {_as_text(overlay.get('primary_scan_sleeve'))}",
            f"sleeves: {_as_text(', '.join(overlay.get('scan_sleeves', [])))}",
            f"fill probability score: {_as_text(overlay.get('fill_probability_score'))}",
            f"crowding penalty: {_as_text(overlay.get('crowding_penalty'))}",
            f"overlap penalty: {_as_text(overlay.get('overlap_penalty'))}",
            "category execution haircut: "
            f"{_format_price(overlay.get('category_execution_haircut_cents'))}",
            f"top factors: {_as_text(', '.join(overlay.get('top_positive_factors', [])))}",
            f"top penalties: {_as_text(', '.join(overlay.get('top_negative_factors', [])))}",
        ]
    )


def render_strict_memo(payload: Mapping[str, Any]) -> str:
    mode = _as_text(payload.get("mode"), default="STRICT").upper()
    citations = payload.get("citations", [])
    if not isinstance(citations, list):
        citations = []
    claim_citations = [item for item in citations if isinstance(item, Mapping)]
    anchor_stack = _as_mapping(payload.get("anchor_stack"))
    execution_overlay = _as_mapping(payload.get("execution_overlay"))

    lines = [
        f"[{mode}]",
        f"thesis: {_as_text(payload.get('thesis'))}",
        f"cluster: {_as_text(payload.get('thesis_cluster_id'))}",
        f"expression: {_as_text(payload.get('expression'))}",
    ]
    market_link = _as_text(payload.get("market_link"), default="")
    if market_link:
        lines.append(f"market: {market_link}")
    lines.extend(
        [
            (
                "action: "
                f"{_as_text(payload.get('side'))} <= {_format_price(payload.get('max_entry_cents'))} "
                f"| size {_format_usdc(payload.get('suggested_size_usdc'))} "
                f"| edge {_format_price(payload.get('executable_edge_cents'))}"
            ),
            f"why now: {_as_text(payload.get('why_now'))}",
            f"kill criteria: {_as_text(payload.get('kill_criteria_text'))}",
            (
                "timers: "
                f"fresh_until={_as_text(payload.get('evidence_fresh_until'))} "
                f"| recheck={_as_text(payload.get('recheck_required_at'))}"
            ),
            "anchor stack:",
            _render_anchor_stack(anchor_stack),
            "execution overlay:",
            _render_execution_overlay(execution_overlay),
            "citations (claim-aware):",
            _render_claim_aware_citations(claim_citations),
        ]
    )
    return "\n".join(lines)
