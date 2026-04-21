from __future__ import annotations

from pydantic import BaseModel, Field


class SourceEntry(BaseModel):
    name: str
    kind: str
    domain_or_handle: str
    is_primary_allowed: bool = False


class SourceRegistry(BaseModel):
    version: str
    primary_domains: set[str] = Field(default_factory=set)
    x_handles: set[str] = Field(default_factory=set)
    sources: list[SourceEntry] = Field(default_factory=list)
    tier_metadata: dict[str, list[str]] = Field(default_factory=dict)
