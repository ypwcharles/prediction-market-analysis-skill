from __future__ import annotations

import sqlite3
from datetime import UTC, datetime


def mark_stale_alerts(conn: sqlite3.Connection, *, now: datetime | None = None) -> list[str]:
    now = now or datetime.now(UTC)
    now_iso = now.isoformat()
    rows = conn.execute(
        """
        SELECT id
        FROM alerts
        WHERE status = 'active'
          AND recheck_required_at IS NOT NULL
          AND recheck_required_at <= ?
        """,
        [now_iso],
    ).fetchall()
    stale_ids = [row["id"] for row in rows]
    if stale_ids:
        conn.executemany(
            """
            UPDATE alerts
            SET status = 'stale'
            WHERE id = ?
            """,
            [(alert_id,) for alert_id in stale_ids],
        )
        conn.execute(
            """
            UPDATE thesis_clusters
            SET status = 'pending_recheck', updated_at = ?
            WHERE id IN (
                SELECT DISTINCT thesis_cluster_id
                FROM alerts
                WHERE id IN ({})
            )
            """.format(", ".join("?" for _ in stale_ids)),
            [now_iso, *stale_ids],
        )
        conn.commit()
    return stale_ids
