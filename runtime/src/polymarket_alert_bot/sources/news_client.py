from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from polymarket_alert_bot.sources.evidence_enricher import EvidenceItem


class NewsClient:
    """Normalize news source rows into evidence items."""

    source_kind = "news"

    def normalize_items(
        self,
        rows: Iterable[dict[str, object]],
        *,
        fetched_at: str | None = None,
    ) -> list[EvidenceItem]:
        effective_fetched_at = fetched_at or datetime.now(UTC).isoformat()
        normalized: list[EvidenceItem] = []
        for row in rows:
            normalized.append(
                EvidenceItem(
                    source_id=str(row["source_id"]),
                    source_kind=self.source_kind,
                    fetched_at=effective_fetched_at,
                    url=str(row["url"]),
                    claim_snippet=str(row["claim_snippet"]),
                    tier=str(row.get("tier") or "primary"),
                    conflict_status=str(row["conflict_status"]) if row.get("conflict_status") else None,
                )
            )
        return normalized
