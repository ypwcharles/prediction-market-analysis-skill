from __future__ import annotations

import os
import sqlite3


def build_calibration_summary(conn: sqlite3.Connection) -> dict[str, int | str]:
    total_high_priority_alerts = conn.execute(
        """
        SELECT COUNT(*)
        FROM alerts
        WHERE alert_kind IN ('strict', 'strict_degraded', 'reprice')
        """
    ).fetchone()[0]
    distinct_clusters = conn.execute(
        """
        SELECT COUNT(DISTINCT thesis_cluster_id)
        FROM alerts
        WHERE thesis_cluster_id IS NOT NULL
          AND alert_kind IN ('strict', 'strict_degraded', 'reprice')
        """
    ).fetchone()[0]
    repeated_cluster_discount = max(total_high_priority_alerts - distinct_clusters, 0)

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
    }
