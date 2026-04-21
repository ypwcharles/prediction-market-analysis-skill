from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path


@contextmanager
def file_lock(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError(f"lock already held: {lock_path}") from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write("locked\n")
        yield
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass
