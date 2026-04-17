from __future__ import annotations

from typing import Any, Mapping


def _as_text(value: Any, *, default: str = "-") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _citation_brief(index: int, citation: Mapping[str, Any]) -> str:
    source = citation.get("source", {})
    if not isinstance(source, Mapping):
        source = {}
    claim = _as_text(citation.get("claim"))
    source_name = _as_text(source.get("name"), default="unknown")
    return f"{index}. {claim} [{source_name}]"


def render_research_digest(payload: Mapping[str, Any]) -> str:
    citations = payload.get("citations", [])
    if not isinstance(citations, list):
        citations = []
    claim_citations = [item for item in citations if isinstance(item, Mapping)]
    citation_lines = (
        "\n".join(_citation_brief(index, citation) for index, citation in enumerate(claim_citations, start=1))
        if claim_citations
        else "1. No claim-aware citation was provided."
    )
    return "\n".join(
        [
            "[RESEARCH]",
            f"thesis: {_as_text(payload.get('thesis'))}",
            f"summary: {_as_text(payload.get('summary'))}",
            f"watch: {_as_text(payload.get('watch_item'))}",
            "citations (claim-aware):",
            citation_lines,
        ]
    )
