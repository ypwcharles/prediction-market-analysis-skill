from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

import httpx

from polymarket_alert_bot.sources.evidence_enricher import EvidenceItem
from polymarket_alert_bot.sources.feed_loader import load_feed_rows


class NewsClient:
    """Normalize news source rows into evidence items."""

    source_kind = "news"

    def fetch_items(
        self,
        feed_source: str | Path,
        *,
        fetched_at: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> list[EvidenceItem]:
        return self.normalize_items(
            load_feed_rows(feed_source, http_client=http_client),
            fetched_at=fetched_at,
        )

    def normalize_items(
        self,
        rows: Iterable[dict[str, object]],
        *,
        fetched_at: str | None = None,
    ) -> list[EvidenceItem]:
        effective_fetched_at = fetched_at or datetime.now(UTC).isoformat()
        normalized: list[EvidenceItem] = []
        for row in rows:
            row_fetched_at = str(row.get("fetched_at") or effective_fetched_at)
            normalized.append(
                EvidenceItem(
                    source_id=str(row["source_id"]),
                    source_kind=self.source_kind,
                    fetched_at=row_fetched_at,
                    url=str(row["url"]),
                    claim_snippet=str(row["claim_snippet"]),
                    tier=str(row.get("tier") or ""),
                    conflict_status=str(row["conflict_status"]) if row.get("conflict_status") else None,
                )
            )
        return normalized
