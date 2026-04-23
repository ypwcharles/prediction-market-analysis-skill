from __future__ import annotations

from datetime import UTC, datetime, timedelta
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
    now_dt = datetime.now(UTC)
    now = now_dt.isoformat()

    _seed_clusters(conn, now=now, cluster_ids=["cluster-1", "cluster-2"])
    _seed_scan_run(conn, now=now, run_id="seed-run", status="degraded")
    alert_1_created_at = (now_dt - timedelta(days=1)).isoformat()
    alert_2_created_at = (now_dt - timedelta(days=8)).isoformat()
    _seed_alert(
        conn,
        alert_id="alert-1",
        run_id="seed-run",
        cluster_id="cluster-1",
        alert_kind="strict",
        created_at=alert_1_created_at,
    )
    _seed_alert(
        conn,
        alert_id="alert-2",
        run_id="seed-run",
        cluster_id="cluster-1",
        alert_kind="reprice",
        created_at=alert_2_created_at,
    )
    _seed_alert(
        conn,
        alert_id="alert-3",
        run_id="seed-run",
        cluster_id="cluster-2",
        alert_kind="strict_degraded",
        created_at=(now_dt - timedelta(days=20)).isoformat(),
        status="stale",
    )
    _seed_feedback(
        conn,
        feedback_id="feedback-1",
        alert_id="alert-1",
        cluster_id="cluster-1",
        feedback_type="claimed_buy",
        created_at=(datetime.fromisoformat(alert_1_created_at) + timedelta(hours=1)).isoformat(),
    )
    _seed_feedback(
        conn,
        feedback_id="feedback-2",
        alert_id="alert-2",
        cluster_id="cluster-1",
        feedback_type="disagree",
        created_at=(datetime.fromisoformat(alert_2_created_at) + timedelta(hours=5)).isoformat(),
    )
    conn.commit()

    run_id = run_report(paths)

    run_row = conn.execute(
        """
        SELECT run_type, status
        FROM runs
        WHERE id = ?
        """,
        [run_id],
    ).fetchone()
    assert dict(run_row) == {"run_type": "report", "status": "clean"}

    report_row = conn.execute(
        """
        SELECT status, total_high_priority_alerts, distinct_clusters, repeated_cluster_discount, report_path
        FROM calibration_reports
        ORDER BY created_at DESC
        LIMIT 1
        """
    ).fetchone()
    assert dict(report_row) == {
        "status": "ready_for_limited_trial",
        "total_high_priority_alerts": 3,
        "distinct_clusters": 2,
        "repeated_cluster_discount": 1,
        "report_path": report_row["report_path"],
    }
    report_path = Path(report_row["report_path"])
    assert report_path.exists()
    report_text = report_path.read_text(encoding="utf-8")
    assert "# Calibration Report" in report_text
    assert "## Current Quality Scorecard" in report_text
    assert "- High-priority alerts: 3" in report_text
    assert "- Distinct thesis clusters: 2" in report_text
    assert "- Repeated-cluster discount: 1" in report_text
    assert "## Ex-post Review Buckets" in report_text
    assert "- Short-window (<=3d): 1" in report_text
    assert "- Medium-window (4-14d): 1" in report_text
    assert "- Long-window (>14d): 1" in report_text
    assert "## Discovery Health" in report_text
    assert "- Scan runs: 1" in report_text
    assert "- Degraded scan runs: 1 (100.0%)" in report_text
    assert "- Latest scan events/contracts/shortlist/promoted: 8/20/6/3" in report_text
    assert "- Sleeve inputs: hot_board=12 | short_dated=5 | anchor_gap=1" in report_text
    assert "- Sleeve promoted: anchor_gap=1 | hot_board=1" in report_text
    assert "## Operator Trust Signals" in report_text
    assert "- Stale alerts: 1" in report_text
    assert "- Feedback events: 2" in report_text
    assert "- Claimed-buy feedback: 1" in report_text
    assert "- Disagree feedback (false-positive proxy): 1 (50.0%)" in report_text
    assert "- Avg feedback latency hours: 3.0" in report_text


def test_run_report_marks_not_ready_without_high_priority_alerts(monkeypatch, tmp_path):
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(tmp_path / ".runtime-data"))
    paths = load_runtime_paths()
    ensure_runtime_dirs(paths)
    conn = connect_db(paths.db_path)
    apply_migrations(conn)

    run_report(paths)

    report_row = conn.execute(
        """
        SELECT status, total_high_priority_alerts, distinct_clusters, repeated_cluster_discount, report_path
        FROM calibration_reports
        ORDER BY created_at DESC
        LIMIT 1
        """
    ).fetchone()
    assert report_row["status"] == "not_ready"
    assert report_row["total_high_priority_alerts"] == 0
    assert report_row["distinct_clusters"] == 0
    assert report_row["repeated_cluster_discount"] == 0
    report_text = Path(report_row["report_path"]).read_text(encoding="utf-8")
    assert "- Status: not_ready" in report_text
    assert "- Short-window (<=3d): 0" in report_text
    assert "- Medium-window (4-14d): 0" in report_text
    assert "- Long-window (>14d): 0" in report_text
    assert "- Scan runs: 0" in report_text
    assert "- Sleeve inputs: -" in report_text
    assert "- Feedback events: 0" in report_text


def test_run_report_marks_production_ready_with_override(monkeypatch, tmp_path):
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(tmp_path / ".runtime-data"))
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_ALLOW_PRODUCTION_REPORT", "1")
    paths = load_runtime_paths()
    ensure_runtime_dirs(paths)
    conn = connect_db(paths.db_path)
    apply_migrations(conn)
    now = datetime.now(UTC).isoformat()

    _seed_clusters(conn, now=now, cluster_ids=["cluster-a", "cluster-b"])
    _seed_scan_run(conn, now=now, run_id="seed-run")
    _seed_alert(
        conn,
        alert_id="alert-a",
        run_id="seed-run",
        cluster_id="cluster-a",
        alert_kind="strict",
        created_at=now,
    )
    _seed_alert(
        conn,
        alert_id="alert-b",
        run_id="seed-run",
        cluster_id="cluster-b",
        alert_kind="reprice",
        created_at=now,
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
    assert report_row["status"] == "ready_for_production"
    assert "- Status: ready_for_production" in Path(report_row["report_path"]).read_text(
        encoding="utf-8"
    )


def _seed_clusters(conn, *, now: str, cluster_ids: list[str]) -> None:
    for cluster_id in cluster_ids:
        conn.execute(
            """
            INSERT INTO thesis_clusters (
                id, canonical_name, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [cluster_id, f"Test cluster {cluster_id}", "open", now, now],
        )


def _seed_scan_run(conn, *, now: str, run_id: str, status: str = "clean") -> None:
    conn.execute(
        """
        INSERT INTO runs (
            id,
            run_type,
            status,
            started_at,
            created_at,
            scanned_events,
            scanned_contracts,
            shortlisted_candidates,
            retrieved_shortlist_candidates,
            promoted_seed_count,
            families_with_structural_flags,
            structurally_flagged_candidates,
            sleeve_input_counts_json,
            sleeve_shortlist_counts_json,
            sleeve_promoted_counts_json,
            strict_count,
            research_count,
            skipped_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            run_id,
            "scan",
            status,
            now,
            now,
            8,
            20,
            6,
            4,
            3,
            2,
            5,
            '{"hot_board": 12, "short_dated": 5, "anchor_gap": 1}',
            '{"hot_board": 3, "anchor_gap": 1}',
            '{"hot_board": 1, "anchor_gap": 1}',
            1,
            2,
            14,
        ],
    )


def _seed_alert(
    conn,
    *,
    alert_id: str,
    run_id: str,
    cluster_id: str,
    alert_kind: str,
    created_at: str,
    status: str = "active",
) -> None:
    conn.execute(
        """
        INSERT INTO alerts (
            id, run_id, thesis_cluster_id, alert_kind, delivery_mode,
            status, dedupe_key, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            alert_id,
            run_id,
            cluster_id,
            alert_kind,
            "immediate",
            status,
            f"dedupe-{alert_id}",
            created_at,
        ],
    )


def _seed_feedback(
    conn,
    *,
    feedback_id: str,
    alert_id: str,
    cluster_id: str,
    feedback_type: str,
    created_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO feedback (
            id, alert_id, thesis_cluster_id, feedback_type, created_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        [feedback_id, alert_id, cluster_id, feedback_type, created_at],
    )
