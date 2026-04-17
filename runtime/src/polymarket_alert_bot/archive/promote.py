from __future__ import annotations

from pathlib import Path
import shutil


def promote_archive_artifact(archive_path: Path | str, destination_dir: Path | str) -> Path:
    source = Path(archive_path)
    destination = Path(destination_dir)
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / source.name
    shutil.copy2(source, target)
    return target

