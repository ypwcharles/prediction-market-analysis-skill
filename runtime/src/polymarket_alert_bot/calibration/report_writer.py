from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from polymarket_alert_bot.calibration.metrics import build_calibration_summary
from polymarket_alert_bot.config.settings import RuntimePaths
from polymarket_alert_bot.models.enums import RunStatus, RunType
from polymarket_alert_bot.storage.db import connect_db
from polymarket_alert_bot.storage.migrations import apply_migrations
from polymarket_alert_bot.storage.repositories import RuntimeRepository


def _write_markdown_report(
    report_path: Path, summary: dict[str, int | float | str], created_at: str
) -> None:
    coverage_pct = f"{float(summary['cluster_coverage_ratio']) * 100:.1f}%"
    degraded_rate_pct = f"{float(summary['scan_degraded_rate']) * 100:.1f}%"
    disagree_rate_pct = f"{float(summary['disagree_feedback_rate']) * 100:.1f}%"
    latest_scan_summary = (
        f"{summary['latest_scan_events']}/"
        f"{summary['latest_scan_contracts']}/"
        f"{summary['latest_scan_shortlisted']}/"
        f"{summary['latest_scan_promoted']}"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        "\n".join(
            [
                "# Calibration Report",
                "",
                f"- Generated at: {created_at}",
                f"- Status: {summary['status']}",
                "",
                "## Current Quality Scorecard",
                f"- High-priority alerts: {summary['total_high_priority_alerts']}",
                f"- Distinct thesis clusters: {summary['distinct_clusters']}",
                f"- Cluster coverage: {coverage_pct}",
                f"- Repeated-cluster discount: {summary['repeated_cluster_discount']}",
                f"- Quality score (0-100): {summary['quality_score']}",
                "",
                "## Ex-post Review Buckets",
                f"- Short-window (<=3d): {summary['review_bucket_short']}",
                f"- Medium-window (4-14d): {summary['review_bucket_medium']}",
                f"- Long-window (>14d): {summary['review_bucket_long']}",
                "",
                "## Discovery Health",
                f"- Scan runs: {summary['scan_run_count']}",
                (
                    "- Degraded scan runs: "
                    f"{summary['degraded_scan_run_count']} ({degraded_rate_pct})"
                ),
                f"- Latest scan events/contracts/shortlist/promoted: {latest_scan_summary}",
                f"- Total scanned contracts: {summary['scanned_contracts_total']}",
                f"- Total shortlisted candidates: {summary['shortlisted_candidates_total']}",
                f"- Total promoted seeds: {summary['promoted_seed_count_total']}",
                (
                    "- Structural-flag families/candidates: "
                    f"{summary['families_with_structural_flags_total']}/"
                    f"{summary['structurally_flagged_candidates_total']}"
                ),
                (
                    "- Strict/research/skipped totals: "
                    f"{summary['strict_count_total']}/"
                    f"{summary['research_count_total']}/"
                    f"{summary['skipped_count_total']}"
                ),
                f"- Retrieved shortlist candidates: {summary['retrieved_shortlist_candidates_total']}",
                f"- Sleeve inputs: {summary['sleeve_input_totals']}",
                f"- Sleeve shortlist: {summary['sleeve_shortlist_totals']}",
                f"- Sleeve promoted: {summary['sleeve_promoted_totals']}",
                "",
                "## Operator Trust Signals",
                f"- Stale alerts: {summary['stale_alert_count']}",
                f"- Feedback events: {summary['feedback_event_count']}",
                f"- Claimed-buy feedback: {summary['claimed_buy_feedback_count']}",
                (
                    "- Disagree feedback (false-positive proxy): "
                    f"{summary['disagree_feedback_count']} ({disagree_rate_pct})"
                ),
                f"- Close-thesis feedback: {summary['close_thesis_feedback_count']}",
                f"- Avg feedback latency hours: {summary['avg_feedback_latency_hours']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def run_report(paths: RuntimePaths) -> str:
    timestamp = datetime.now(UTC).isoformat()
    run_id = str(uuid4())
    conn = connect_db(paths.db_path)
    try:
        apply_migrations(conn)
        RuntimeRepository(conn).upsert_run(
            {
                "id": run_id,
                "run_type": RunType.REPORT.value,
                "status": RunStatus.CLEAN.value,
                "started_at": timestamp,
                "finished_at": timestamp,
                "degraded_reason": None,
                "scanned_events": 0,
                "scanned_contracts": 0,
                "strict_count": 0,
                "research_count": 0,
                "skipped_count": 0,
                "heartbeat_sent": 0,
                "created_at": timestamp,
            }
        )
        summary = build_calibration_summary(conn)
        report_id = str(uuid4())
        report_path = paths.data_dir / "reports" / f"calibration-{report_id}.md"
        _write_markdown_report(report_path, summary, timestamp)
        conn.execute(
            """
            INSERT INTO calibration_reports (
                id,
                run_id,
                status,
                total_high_priority_alerts,
                distinct_clusters,
                repeated_cluster_discount,
                report_path,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                report_id,
                run_id,
                summary["status"],
                summary["total_high_priority_alerts"],
                summary["distinct_clusters"],
                summary["repeated_cluster_discount"],
                str(report_path),
                timestamp,
            ],
        )
        conn.commit()
    finally:
        conn.close()
    return run_id
