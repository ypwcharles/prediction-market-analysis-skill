from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shlex


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class RuntimePaths:
    repo_root: Path
    data_dir: Path
    db_path: Path
    sources_path: Path
    scan_lock: Path
    monitor_lock: Path


@dataclass(frozen=True)
class RuntimeConfig:
    gamma_events_url: str
    gamma_limit: int
    clob_book_url: str
    positions_url: str
    positions_user: str | None
    telegram_chat_id: str | None
    judgment_command: tuple[str, ...]
    judgment_timeout_seconds: int
    news_feed_url: str | None
    x_feed_url: str | None
    news_samples_path: Path | None
    x_samples_path: Path | None


def load_runtime_paths() -> RuntimePaths:
    repo_root = _repo_root()
    data_dir = Path(
        os.environ.get(
            "POLYMARKET_ALERT_BOT_DATA_DIR",
            repo_root / ".runtime-data",
        )
    )
    db_path = Path(
        os.environ.get(
            "POLYMARKET_ALERT_BOT_DB_PATH",
            data_dir / "sqlite" / "runtime.sqlite3",
        )
    )
    sources_path = Path(
        os.environ.get(
            "POLYMARKET_ALERT_BOT_SOURCES_PATH",
            repo_root / "runtime" / "config" / "sources.toml",
        )
    )
    return RuntimePaths(
        repo_root=repo_root,
        data_dir=data_dir,
        db_path=db_path,
        sources_path=sources_path,
        scan_lock=data_dir / "locks" / "scan.lock",
        monitor_lock=data_dir / "locks" / "monitor.lock",
    )


def load_runtime_config() -> RuntimeConfig:
    judgment_command_text = (
        _optional_env("POLYMARKET_ALERT_BOT_JUDGMENT_COMMAND")
        or _optional_env("POLYMARKET_ALERT_BOT_JUDGMENT_RUNNER_CMD")
    )
    judgment_command = tuple(_split_command_text(judgment_command_text)) if judgment_command_text else ()

    return RuntimeConfig(
        gamma_events_url=os.environ.get(
            "POLYMARKET_ALERT_BOT_GAMMA_EVENTS_URL",
            "https://gamma-api.polymarket.com/events",
        ),
        gamma_limit=int(os.environ.get("POLYMARKET_ALERT_BOT_GAMMA_LIMIT", "200")),
        clob_book_url=os.environ.get(
            "POLYMARKET_ALERT_BOT_CLOB_BOOK_URL",
            "https://clob.polymarket.com/book",
        ),
        positions_url=os.environ.get(
            "POLYMARKET_ALERT_BOT_POSITIONS_URL",
            "https://data-api.polymarket.com/positions",
        ),
        positions_user=_optional_env("POLYMARKET_ALERT_BOT_POSITIONS_USER"),
        telegram_chat_id=_optional_env("POLYMARKET_ALERT_BOT_TELEGRAM_CHAT_ID"),
        judgment_command=judgment_command,
        judgment_timeout_seconds=int(
            os.environ.get("POLYMARKET_ALERT_BOT_JUDGMENT_TIMEOUT_SECONDS", "90")
        ),
        news_feed_url=_optional_env("POLYMARKET_ALERT_BOT_NEWS_FEED_URL"),
        x_feed_url=_optional_env("POLYMARKET_ALERT_BOT_X_FEED_URL"),
        news_samples_path=_optional_path("POLYMARKET_ALERT_BOT_NEWS_SAMPLES_PATH"),
        x_samples_path=_optional_path("POLYMARKET_ALERT_BOT_X_SAMPLES_PATH"),
    )


def ensure_runtime_dirs(paths: RuntimePaths) -> None:
    for directory in (
        paths.data_dir,
        paths.db_path.parent,
        paths.data_dir / "archives",
        paths.data_dir / "reports",
        paths.data_dir / "locks",
    ):
        directory.mkdir(parents=True, exist_ok=True)


def _optional_env(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return None
    text = value.strip()
    return text or None


def _optional_path(name: str) -> Path | None:
    value = _optional_env(name)
    return Path(value) if value else None


def _split_command_text(text: str) -> list[str]:
    marker = " -c "
    if marker not in text:
        return shlex.split(text)
    prefix, inline_script = text.split(marker, maxsplit=1)
    prefix_parts = shlex.split(prefix)
    if not prefix_parts:
        return []
    return [*prefix_parts, "-c", inline_script]
