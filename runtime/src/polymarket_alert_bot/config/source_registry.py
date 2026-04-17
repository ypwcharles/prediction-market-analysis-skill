from __future__ import annotations

from pathlib import Path
import tomllib

from polymarket_alert_bot.models.records import SourceEntry, SourceRegistry


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _resolve_registry_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.exists():
        return candidate

    repo_relative = _repo_root() / candidate
    if repo_relative.exists():
        return repo_relative

    raise FileNotFoundError(f"source registry not found: {path}")


def load_source_registry(path: str | Path) -> SourceRegistry:
    registry_path = _resolve_registry_path(path)
    with registry_path.open("rb") as handle:
        payload = tomllib.load(handle)

    sources = [SourceEntry(**source) for source in payload.get("sources", [])]
    primary_domains = {
        source.domain_or_handle
        for source in sources
        if source.is_primary_allowed and not source.domain_or_handle.startswith("@")
    }
    x_handles = {
        source.domain_or_handle
        for source in sources
        if source.kind == "x"
    }

    return SourceRegistry(
        version=payload["version"],
        primary_domains=primary_domains,
        x_handles=x_handles,
        sources=sources,
        tier_metadata=payload.get("tiers", {}),
    )
