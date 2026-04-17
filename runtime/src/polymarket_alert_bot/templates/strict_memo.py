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


def _citation_line(index: int, citation: Mapping[str, Any]) -> str:
    claim = _as_text(citation.get("claim"))
    source = citation.get("source", {})
    if not isinstance(source, Mapping):
        source = {}
    source_name = _as_text(
        source.get("name", citation.get("source_name", citation.get("source_id"))),
        default="unknown",
    )
    tier = _as_text(source.get("tier", citation.get("source_tier")), default="unknown")
    url = _as_text(source.get("url", citation.get("url")))
    fetched_at = _as_text(source.get("fetched_at", citation.get("fetched_at")))
    return (
        f"{index}. {claim}\n"
        f"   -> {source_name} ({tier})\n"
        f"   -> {url}\n"
        f"   -> fetched: {fetched_at}"
    )


def _render_claim_aware_citations(citations: list[Mapping[str, Any]]) -> str:
    if not citations:
        return "1. No claim-aware citation was provided."
    return "\n".join(_citation_line(index, citation) for index, citation in enumerate(citations, start=1))


def render_strict_memo(payload: Mapping[str, Any]) -> str:
    mode = _as_text(payload.get("mode"), default="STRICT").upper()
    citations = payload.get("citations", [])
    if not isinstance(citations, list):
        citations = []
    claim_citations = [item for item in citations if isinstance(item, Mapping)]

    return "\n".join(
        [
            f"[{mode}]",
            f"thesis: {_as_text(payload.get('thesis'))}",
            f"cluster: {_as_text(payload.get('thesis_cluster_id'))}",
            f"expression: {_as_text(payload.get('expression'))}",
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
            "citations (claim-aware):",
            _render_claim_aware_citations(claim_citations),
        ]
    )
