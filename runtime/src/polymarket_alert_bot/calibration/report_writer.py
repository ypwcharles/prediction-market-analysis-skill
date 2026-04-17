from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from polymarket_alert_bot.config.settings import RuntimePaths
from polymarket_alert_bot.calibration.metrics import build_calibration_summary
from polymarket_alert_bot.models.enums import RunStatus, RunType
from polymarket_alert_bot.storage.db import connect_db
from polymarket_alert_bot.storage.migrations import apply_migrations
from polymarket_alert_bot.storage.repositories import RuntimeRepository


def _write_markdown_report(report_path: Path, summary: dict[str, int | str], created_at: str) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        "\n".join(
            [
                "# Calibration Report",
                "",
                f"- Generated at: {created_at}",
                f"- Status: {summary['status']}",
                f"- High-priority alerts: {summary['total_high_priority_alerts']}",
                f"- Distinct thesis clusters: {summary['distinct_clusters']}",
                f"- Repeated-cluster discount: {summary['repeated_cluster_discount']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def run_report(paths: RuntimePaths) -> str:
    timestamp = datetime.now(UTC).isoformat()
    run_id = str(uuid4())
    conn = connect_db(paths.db_path)
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
    return run_id
