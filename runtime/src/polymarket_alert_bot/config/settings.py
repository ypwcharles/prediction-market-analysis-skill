from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


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


def ensure_runtime_dirs(paths: RuntimePaths) -> None:
    for directory in (
        paths.data_dir,
        paths.db_path.parent,
        paths.data_dir / "archives",
        paths.data_dir / "reports",
        paths.data_dir / "locks",
    ):
        directory.mkdir(parents=True, exist_ok=True)
