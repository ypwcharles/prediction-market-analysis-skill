from __future__ import annotations

from pathlib import Path

import pytest

from polymarket_alert_bot.archive.promote import promote_archive_artifact
from polymarket_alert_bot.archive.writer import write_archive_artifact
from polymarket_alert_bot.config.settings import ensure_runtime_dirs, load_runtime_paths


def test_write_archive_artifact_normalizes_kind_and_writes_markdown(monkeypatch, tmp_path):
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(tmp_path / ".runtime-data"))
    paths = load_runtime_paths()
    ensure_runtime_dirs(paths)

    archive_path = write_archive_artifact(
        paths,
        alert_id="alert-1",
        alert_kind="STRICT_DEGRADED",
        content="# strict memo\n",
    )

    assert archive_path is not None
    assert archive_path.name == "strict-alert-1.md"
    assert archive_path.read_text(encoding="utf-8") == "# strict memo\n"


def test_write_archive_artifact_skips_low_value_reprice(monkeypatch, tmp_path):
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(tmp_path / ".runtime-data"))
    paths = load_runtime_paths()
    ensure_runtime_dirs(paths)

    archive_path = write_archive_artifact(
        paths,
        alert_id="alert-2",
        alert_kind="reprice",
        content="# reprice memo\n",
        high_value=False,
    )

    assert archive_path is None


def test_promote_archive_artifact_copies_markdown(tmp_path):
    source = tmp_path / "strict-alert-1.md"
    source.write_text("# strict memo\n", encoding="utf-8")
    destination = tmp_path / "docs" / "market-analysis"

    promoted = promote_archive_artifact(source, destination)

    assert promoted == destination / source.name
    assert promoted.read_text(encoding="utf-8") == "# strict memo\n"


def test_promote_archive_artifact_rejects_non_markdown(tmp_path):
    source = tmp_path / "strict-alert-1.txt"
    source.write_text("not markdown", encoding="utf-8")
    destination = tmp_path / "docs" / "market-analysis"

    with pytest.raises(ValueError, match=r"\.md"):
        promote_archive_artifact(source, destination)


def test_promote_archive_artifact_raises_for_missing_source(tmp_path):
    source = tmp_path / "missing.md"
    destination = tmp_path / "docs" / "market-analysis"

    with pytest.raises(FileNotFoundError):
        promote_archive_artifact(source, destination)


def test_promote_archive_artifact_is_noop_when_target_is_same_file(tmp_path):
    source = tmp_path / "strict-alert-1.md"
    source.write_text("# strict memo\n", encoding="utf-8")

    promoted = promote_archive_artifact(source, source.parent)

    assert promoted == Path(source)
    assert promoted.read_text(encoding="utf-8") == "# strict memo\n"
