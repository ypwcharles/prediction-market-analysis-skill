from __future__ import annotations

from typing import Any, Mapping


def _as_text(value: Any, *, default: str = "-") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _citation_brief(index: int, citation: Mapping[str, Any]) -> str:
    source = citation.get("source", citation.get("source_ref", {}))
    if not isinstance(source, Mapping):
        source = {}
    claim = _as_text(citation.get("claim"))
    source_name = _as_text(source.get("name", citation.get("source_name")), default="unknown")
    return f"{index}. {claim} [{source_name}]"


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _microstructure_line(diagnostics: Mapping[str, Any]) -> str:
    if not diagnostics:
        return ""
    return " | ".join(f"{key}: {_as_text(value)}" for key, value in sorted(diagnostics.items()))


def render_research_digest(payload: Mapping[str, Any]) -> str:
    citations = payload.get("citations", [])
    if not isinstance(citations, list):
        citations = []
    claim_citations = [item for item in citations if isinstance(item, Mapping)]
    citation_lines = (
        "\n".join(
            _citation_brief(index, citation)
            for index, citation in enumerate(claim_citations, start=1)
        )
        if claim_citations
        else "1. No claim-aware citation was provided."
    )
    lines = [
        "[RESEARCH]",
        f"thesis: {_as_text(payload.get('thesis'))}",
        f"summary: {_as_text(payload.get('summary'))}",
        f"watch: {_as_text(payload.get('watch_item'))}",
    ]
    microstructure = _microstructure_line(_as_mapping(payload.get("microstructure_diagnostics")))
    if microstructure:
        lines.append(f"microstructure: {microstructure}")
    market_link = _as_text(payload.get("market_link"), default="")
    if market_link:
        lines.append(f"market: {market_link}")
    lines.extend(
        [
            "citations (claim-aware):",
            citation_lines,
        ]
    )
    return "\n".join(lines)
