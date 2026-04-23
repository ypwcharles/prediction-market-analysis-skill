from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from polymarket_alert_bot.calibration.metrics import build_calibration_summary
from polymarket_alert_bot.storage.db import connect_db
from polymarket_alert_bot.storage.migrations import apply_migrations


def test_build_calibration_summary_includes_scorecard_and_review_buckets(tmp_path):
    conn = connect_db(tmp_path / "runtime.sqlite3")
    apply_migrations(conn)
    now_dt = datetime.now(UTC)
    now = now_dt.isoformat()
    _seed_base_context(
        conn,
        now=now,
        run_id="run-1",
        cluster_ids=["cluster-1", "cluster-2"],
        run_status="degraded",
    )
    alert_1_created_at = (now_dt - timedelta(days=1)).isoformat()
    alert_2_created_at = (now_dt - timedelta(days=7)).isoformat()
    _seed_alert(
        conn,
        alert_id="alert-1",
        run_id="run-1",
        cluster_id="cluster-1",
        alert_kind="strict",
        created_at=alert_1_created_at,
    )
    _seed_alert(
        conn,
        alert_id="alert-2",
        run_id="run-1",
        cluster_id="cluster-1",
        alert_kind="reprice",
        created_at=alert_2_created_at,
    )
    _seed_alert(
        conn,
        alert_id="alert-3",
        run_id="run-1",
        cluster_id="cluster-2",
        alert_kind="strict_degraded",
        created_at=(now_dt - timedelta(days=21)).isoformat(),
        status="stale",
    )
    _seed_feedback(
        conn,
        feedback_id="feedback-1",
        alert_id="alert-1",
        cluster_id="cluster-1",
        feedback_type="claimed_buy",
        created_at=(datetime.fromisoformat(alert_1_created_at) + timedelta(hours=2)).isoformat(),
    )
    _seed_feedback(
        conn,
        feedback_id="feedback-2",
        alert_id="alert-2",
        cluster_id="cluster-1",
        feedback_type="disagree",
        created_at=(datetime.fromisoformat(alert_2_created_at) + timedelta(hours=6)).isoformat(),
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
    assert summary["scan_run_count"] == 1
    assert summary["degraded_scan_run_count"] == 1
    assert summary["scan_degraded_rate"] == 1.0
    assert summary["latest_scan_events"] == 8
    assert summary["latest_scan_contracts"] == 20
    assert summary["latest_scan_shortlisted"] == 6
    assert summary["latest_scan_promoted"] == 3
    assert summary["scanned_contracts_total"] == 20
    assert summary["shortlisted_candidates_total"] == 6
    assert summary["promoted_seed_count_total"] == 3
    assert summary["families_with_structural_flags_total"] == 2
    assert summary["structurally_flagged_candidates_total"] == 5
    assert summary["retrieved_shortlist_candidates_total"] == 4
    assert summary["strict_count_total"] == 1
    assert summary["research_count_total"] == 2
    assert summary["skipped_count_total"] == 14
    assert summary["sleeve_input_totals"] == "hot_board=12 | short_dated=5 | anchor_gap=1"
    assert summary["sleeve_shortlist_totals"] == "hot_board=3 | anchor_gap=1"
    assert summary["sleeve_promoted_totals"] == "anchor_gap=1 | hot_board=1"
    assert summary["stale_alert_count"] == 1
    assert summary["feedback_event_count"] == 2
    assert summary["claimed_buy_feedback_count"] == 1
    assert summary["disagree_feedback_count"] == 1
    assert summary["close_thesis_feedback_count"] == 0
    assert summary["disagree_feedback_rate"] == 0.5
    assert summary["avg_feedback_latency_hours"] == pytest.approx(4.0, abs=0.01)


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
    assert summary["scan_run_count"] == 0
    assert summary["degraded_scan_run_count"] == 0
    assert summary["stale_alert_count"] == 0
    assert summary["feedback_event_count"] == 0
    assert summary["sleeve_input_totals"] == "-"


def _seed_base_context(
    conn, *, now: str, run_id: str, cluster_ids: list[str], run_status: str = "clean"
) -> None:
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
            run_status,
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
