from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

from polymarket_alert_bot.sources.evidence_enricher import EvidenceItem
from polymarket_alert_bot.sources.feed_loader import load_feed_rows


class XClient:
    """Normalize X source rows into evidence items."""

    source_kind = "x"

    def fetch_items(
        self,
        feed_source: str | Path,
        *,
        fetched_at: str | None = None,
        allowed_handles: set[str] | None = None,
        http_client: httpx.Client | None = None,
    ) -> list[EvidenceItem]:
        rows = load_feed_rows(feed_source, http_client=http_client)
        filtered_rows = self.filter_rows(rows, allowed_handles=allowed_handles)
        return self.normalize_items(filtered_rows, fetched_at=fetched_at)

    def filter_rows(
        self,
        rows: Iterable[dict[str, object]],
        *,
        allowed_handles: set[str] | None = None,
    ) -> list[dict[str, object]]:
        normalized_allowlist = {self._normalize_handle(handle) for handle in (allowed_handles or set()) if handle}
        if not normalized_allowlist:
            return [dict(row) for row in rows]

        filtered: list[dict[str, object]] = []
        for row in rows:
            row_dict = dict(row)
            handle = self.extract_handle(row_dict)
            if handle and handle in normalized_allowlist:
                filtered.append(row_dict)
        return filtered

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
                    tier=str(row.get("tier") or "supplementary"),
                    conflict_status=str(row["conflict_status"]) if row.get("conflict_status") else None,
                )
            )
        return normalized

    @classmethod
    def extract_handle(cls, row: dict[str, object]) -> str | None:
        candidates = (
            row.get("handle"),
            row.get("author_handle"),
            row.get("username"),
            row.get("screen_name"),
        )
        for candidate in candidates:
            normalized = cls._normalize_handle(candidate)
            if normalized:
                return normalized

        url = row.get("url")
        if isinstance(url, str):
            parsed = urlparse(url)
            path_bits = [part for part in parsed.path.split("/") if part]
            if path_bits:
                normalized = cls._normalize_handle(path_bits[0])
                if normalized:
                    return normalized

        source_id = row.get("source_id")
        normalized = cls._normalize_handle(source_id)
        if normalized:
            return normalized
        return None

    @staticmethod
    def _normalize_handle(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        if text.startswith("https://") or text.startswith("http://"):
            return None
        text = text.removeprefix("@")
        if not text:
            return None
        return f"@{text.lower()}"
