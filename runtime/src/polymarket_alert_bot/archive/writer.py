from __future__ import annotations

from pathlib import Path

from polymarket_alert_bot.config.settings import RuntimePaths

ARCHIVEABLE_ALERT_KINDS = {"strict", "reprice", "heartbeat"}
ALERT_KIND_ALIASES = {
    "strict_degraded": "strict",
}


def write_archive_artifact(
    paths: RuntimePaths,
    *,
    alert_id: str,
    alert_kind: str,
    content: str,
    high_value: bool = False,
) -> Path | None:
    normalized_kind = _normalize_alert_kind(alert_kind)
    if normalized_kind not in ARCHIVEABLE_ALERT_KINDS:
        return None
    if normalized_kind == "reprice" and not high_value:
        return None
    archive_path = paths.data_dir / "archives" / f"{normalized_kind}-{alert_id}.md"
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.write_text(content, encoding="utf-8")
    return archive_path


def _normalize_alert_kind(alert_kind: str) -> str:
    key = alert_kind.strip().lower()
    return ALERT_KIND_ALIASES.get(key, key)
