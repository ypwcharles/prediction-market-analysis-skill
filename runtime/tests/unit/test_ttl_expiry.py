from __future__ import annotations

from datetime import UTC, datetime, timedelta

from polymarket_alert_bot.storage.db import connect_db
from polymarket_alert_bot.storage.migrations import apply_migrations
from polymarket_alert_bot.monitor.staleness import mark_stale_alerts


def test_mark_stale_alerts_updates_alert_and_cluster(tmp_path):
    conn = connect_db(tmp_path / "runtime.sqlite3")
    apply_migrations(conn)
    now = datetime.now(UTC)
    stale_at = (now - timedelta(minutes=1)).isoformat()
    conn.execute(
        """
        INSERT INTO thesis_clusters (
            id, canonical_name, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        ["cluster-1", "Test cluster", "open", now.isoformat(), now.isoformat()],
    )
    conn.execute(
        """
        INSERT INTO runs (
            id, run_type, status, started_at, created_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        ["run-1", "scan", "clean", now.isoformat(), now.isoformat()],
    )
    conn.execute(
        """
        INSERT INTO alerts (
            id, run_id, thesis_cluster_id, alert_kind, delivery_mode,
            status, dedupe_key, recheck_required_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            "alert-1",
            "run-1",
            "cluster-1",
            "strict",
            "immediate",
            "active",
            "dedupe-1",
            stale_at,
            now.isoformat(),
        ],
    )
    conn.commit()

    stale_ids = mark_stale_alerts(conn, now=now)
    assert stale_ids == ["alert-1"]
    alert_status = conn.execute(
        "SELECT status FROM alerts WHERE id = 'alert-1'"
    ).fetchone()[0]
    cluster_status = conn.execute(
        "SELECT status FROM thesis_clusters WHERE id = 'cluster-1'"
    ).fetchone()[0]
    assert alert_status == "stale"
    assert cluster_status == "pending_recheck"
