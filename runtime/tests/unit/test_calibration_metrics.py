from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from polymarket_alert_bot.calibration.metrics import build_calibration_summary
from polymarket_alert_bot.storage.db import connect_db
from polymarket_alert_bot.storage.migrations import apply_migrations


def test_build_calibration_summary_includes_scorecard_and_review_buckets(tmp_path):
    conn = connect_db(tmp_path / "runtime.sqlite3")
    apply_migrations(conn)
    now = datetime.now(UTC).isoformat()
    _seed_base_context(conn, now=now, run_id="run-1", cluster_ids=["cluster-1", "cluster-2"])
    _seed_alert(
        conn,
        alert_id="alert-1",
        run_id="run-1",
        cluster_id="cluster-1",
        alert_kind="strict",
        created_at=(datetime.now(UTC) - timedelta(days=1)).isoformat(),
    )
    _seed_alert(
        conn,
        alert_id="alert-2",
        run_id="run-1",
        cluster_id="cluster-1",
        alert_kind="reprice",
        created_at=(datetime.now(UTC) - timedelta(days=7)).isoformat(),
    )
    _seed_alert(
        conn,
        alert_id="alert-3",
        run_id="run-1",
        cluster_id="cluster-2",
        alert_kind="strict_degraded",
        created_at=(datetime.now(UTC) - timedelta(days=21)).isoformat(),
    )
    conn.commit()

    summary = build_calibration_summary(conn)

    assert summary["status"] == "ready_for_limited_trial"
    assert summary["total_high_priority_alerts"] == 3
    assert summary["distinct_clusters"] == 2
    assert summary["repeated_cluster_discount"] == 1
    assert summary["quality_score"] == 67
    assert summary["cluster_coverage_ratio"] == pytest.approx(2 / 3, abs=0.01)
    assert summary["review_bucket_short"] == 1
    assert summary["review_bucket_medium"] == 1
    assert summary["review_bucket_long"] == 1


def test_build_calibration_summary_respects_production_override(monkeypatch, tmp_path):
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_ALLOW_PRODUCTION_REPORT", "1")
    conn = connect_db(tmp_path / "runtime.sqlite3")
    apply_migrations(conn)
    now = datetime.now(UTC).isoformat()
    _seed_base_context(conn, now=now, run_id="run-1", cluster_ids=["cluster-1", "cluster-2"])
    _seed_alert(
        conn,
        alert_id="alert-1",
        run_id="run-1",
        cluster_id="cluster-1",
        alert_kind="strict",
        created_at=now,
    )
    _seed_alert(
        conn,
        alert_id="alert-2",
        run_id="run-1",
        cluster_id="cluster-2",
        alert_kind="reprice",
        created_at=now,
    )
    conn.commit()

    summary = build_calibration_summary(conn)
    assert summary["status"] == "ready_for_production"


def test_build_calibration_summary_returns_not_ready_without_signal(tmp_path):
    conn = connect_db(tmp_path / "runtime.sqlite3")
    apply_migrations(conn)

    summary = build_calibration_summary(conn)

    assert summary["status"] == "not_ready"
    assert summary["total_high_priority_alerts"] == 0
    assert summary["distinct_clusters"] == 0
    assert summary["repeated_cluster_discount"] == 0
    assert summary["review_bucket_short"] == 0
    assert summary["review_bucket_medium"] == 0
    assert summary["review_bucket_long"] == 0


def _seed_base_context(conn, *, now: str, run_id: str, cluster_ids: list[str]) -> None:
    conn.execute(
        """
        INSERT INTO runs (
            id, run_type, status, started_at, created_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        [run_id, "scan", "clean", now, now],
    )
    for cluster_id in cluster_ids:
        conn.execute(
            """
            INSERT INTO thesis_clusters (
                id, canonical_name, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [cluster_id, cluster_id, "open", now, now],
        )


def _seed_alert(
    conn, *, alert_id: str, run_id: str, cluster_id: str, alert_kind: str, created_at: str
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
            "active",
            f"dedupe-{alert_id}",
            created_at,
        ],
    )
