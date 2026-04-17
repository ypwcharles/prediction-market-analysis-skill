from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from polymarket_alert_bot.calibration.report_writer import run_report
from polymarket_alert_bot.config.settings import ensure_runtime_dirs, load_runtime_paths
from polymarket_alert_bot.storage.db import connect_db
from polymarket_alert_bot.storage.migrations import apply_migrations


def test_run_report_writes_markdown_and_sqlite_summary(monkeypatch, tmp_path):
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(tmp_path / ".runtime-data"))
    paths = load_runtime_paths()
    ensure_runtime_dirs(paths)
    conn = connect_db(paths.db_path)
    apply_migrations(conn)
    now = datetime.now(UTC).isoformat()

    conn.execute(
        """
        INSERT INTO thesis_clusters (
            id, canonical_name, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        ["cluster-1", "Test cluster", "open", now, now],
    )
    conn.execute(
        """
        INSERT INTO runs (
            id, run_type, status, started_at, created_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        ["seed-run", "scan", "clean", now, now],
    )
    conn.execute(
        """
        INSERT INTO alerts (
            id, run_id, thesis_cluster_id, alert_kind, delivery_mode,
            status, dedupe_key, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ["alert-1", "seed-run", "cluster-1", "strict", "immediate", "active", "dedupe-1", now],
    )
    conn.commit()

    run_report(paths)

    report_row = conn.execute(
        """
        SELECT status, report_path
        FROM calibration_reports
        ORDER BY created_at DESC
        LIMIT 1
        """
    ).fetchone()
    assert report_row["status"] in {
        "not_ready",
        "ready_for_limited_trial",
        "ready_for_production",
    }
    assert Path(report_row["report_path"]).exists()
