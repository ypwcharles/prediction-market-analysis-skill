from __future__ import annotations

import os
import sqlite3

HIGH_PRIORITY_ALERT_KINDS = ("strict", "strict_degraded", "reprice")
SHORT_REVIEW_DAYS = 3
MEDIUM_REVIEW_DAYS = 14


def build_calibration_summary(conn: sqlite3.Connection) -> dict[str, int | float | str]:
    total_high_priority_alerts = conn.execute(
        """
        SELECT COUNT(*)
        FROM alerts
        WHERE alert_kind IN (?, ?, ?)
        """,
        HIGH_PRIORITY_ALERT_KINDS,
    ).fetchone()[0]
    distinct_clusters = conn.execute(
        """
        SELECT COUNT(DISTINCT thesis_cluster_id)
        FROM alerts
        WHERE thesis_cluster_id IS NOT NULL
          AND alert_kind IN (?, ?, ?)
        """,
        HIGH_PRIORITY_ALERT_KINDS,
    ).fetchone()[0]
    repeated_cluster_discount = max(total_high_priority_alerts - distinct_clusters, 0)
    coverage_ratio = _ratio(distinct_clusters, total_high_priority_alerts)
    repetition_ratio = _ratio(repeated_cluster_discount, total_high_priority_alerts)
    score = max(0.0, min(1.0, (0.7 * coverage_ratio) + (0.3 * (1 - repetition_ratio))))
    quality_score = int(round(score * 100))
    review_buckets = _load_review_buckets(conn)

    production_override = os.environ.get("POLYMARKET_ALERT_BOT_ALLOW_PRODUCTION_REPORT") == "1"

    if total_high_priority_alerts == 0 or distinct_clusters == 0:
        status = "not_ready"
    elif production_override and repeated_cluster_discount == 0:
        status = "ready_for_production"
    else:
        status = "ready_for_limited_trial"

    return {
        "status": status,
        "total_high_priority_alerts": total_high_priority_alerts,
        "distinct_clusters": distinct_clusters,
        "repeated_cluster_discount": repeated_cluster_discount,
        "quality_score": quality_score,
        "cluster_coverage_ratio": coverage_ratio,
        "review_bucket_short": review_buckets["short"],
        "review_bucket_medium": review_buckets["medium"],
        "review_bucket_long": review_buckets["long"],
    }


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _load_review_buckets(conn: sqlite3.Connection) -> dict[str, int]:
    row = conn.execute(
        """
        SELECT
            COALESCE(SUM(CASE WHEN age_days <= ? THEN 1 ELSE 0 END), 0) AS short_bucket,
            COALESCE(SUM(CASE WHEN age_days > ? AND age_days <= ? THEN 1 ELSE 0 END), 0) AS medium_bucket,
            COALESCE(SUM(CASE WHEN age_days > ? THEN 1 ELSE 0 END), 0) AS long_bucket
        FROM (
            SELECT (julianday('now') - julianday(created_at)) AS age_days
            FROM alerts
            WHERE alert_kind IN (?, ?, ?)
              AND created_at IS NOT NULL
        )
        """,
        [
            SHORT_REVIEW_DAYS,
            SHORT_REVIEW_DAYS,
            MEDIUM_REVIEW_DAYS,
            MEDIUM_REVIEW_DAYS,
            *HIGH_PRIORITY_ALERT_KINDS,
        ],
    ).fetchone()
    return {
        "short": int(row["short_bucket"]),
        "medium": int(row["medium_bucket"]),
        "long": int(row["long_bucket"]),
    }
