from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path


@contextmanager
def file_lock(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if lock_path.exists():
        raise RuntimeError(f"lock already held: {lock_path}")
    lock_path.write_text("locked\n", encoding="utf-8")
    try:
        yield
    finally:
        if lock_path.exists():
            lock_path.unlink()

