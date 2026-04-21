from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

import httpx


def load_feed_rows(
    feed_source: str | Path,
    *,
    http_client: httpx.Client | None = None,
    timeout_seconds: float = 10.0,
) -> list[dict[str, object]]:
    raw_source = str(feed_source).strip()
    if not raw_source:
        return []
    payload = _load_payload(raw_source, http_client=http_client, timeout_seconds=timeout_seconds)
    if not isinstance(payload, list):
        return []
    normalized_rows: list[dict[str, object]] = []
    for item in payload:
        if isinstance(item, Mapping):
            normalized_rows.append(dict(item))
    return normalized_rows


def _load_payload(
    feed_source: str,
    *,
    http_client: httpx.Client | None,
    timeout_seconds: float,
) -> Any:
    parsed = urlparse(feed_source)
    if parsed.scheme in {"http", "https"}:
        return _load_remote_payload(
            feed_source, http_client=http_client, timeout_seconds=timeout_seconds
        )
    local_path = _resolve_local_path(feed_source, parsed=parsed)
    return json.loads(local_path.read_text(encoding="utf-8"))


def _resolve_local_path(feed_source: str, *, parsed) -> Path:
    if parsed.scheme == "file":
        return Path(parsed.path).expanduser()
    return Path(feed_source).expanduser()


def _load_remote_payload(
    feed_source: str,
    *,
    http_client: httpx.Client | None,
    timeout_seconds: float,
) -> Any:
    if http_client is not None:
        response = http_client.get(feed_source)
        response.raise_for_status()
        return response.json()
    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.get(feed_source)
        response.raise_for_status()
        return response.json()
