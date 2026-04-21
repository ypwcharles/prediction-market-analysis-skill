from __future__ import annotations

import shutil
from pathlib import Path


def promote_archive_artifact(archive_path: Path | str, destination_dir: Path | str) -> Path:
    source = Path(archive_path)
    if not source.exists():
        raise FileNotFoundError(f"archive artifact not found: {source}")
    if not source.is_file():
        raise IsADirectoryError(f"archive artifact must be a file: {source}")
    if source.suffix.lower() != ".md":
        raise ValueError(f"archive artifact must be markdown (.md): {source}")

    destination = Path(destination_dir)
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / source.name
    if source.resolve() == target.resolve():
        return target
    shutil.copy2(source, target)
    return target
