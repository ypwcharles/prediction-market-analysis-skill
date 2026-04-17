from __future__ import annotations

from datetime import UTC, datetime
import sqlite3
from uuid import uuid4

from polymarket_alert_bot.config.settings import RuntimePaths
from polymarket_alert_bot.models.enums import RunStatus, RunType
from polymarket_alert_bot.storage.db import connect_db
from polymarket_alert_bot.storage.migrations import apply_migrations
from polymarket_alert_bot.storage.repositories import RuntimeRepository


def sync_official_positions(conn: sqlite3.Connection, rows: list[dict[str, object]]) -> None:
    RuntimeRepository(conn).replace_positions(rows)


def reconcile_claimed_position(
    conn: sqlite3.Connection,
    *,
    condition_id: str,
    token_id: str,
    snapshot_as_of: str,
) -> None:
    conn.execute(
        """
        UPDATE positions
        SET status = 'open',
            truth_source = 'official_api',
            snapshot_as_of = ?,
            updated_at = ?
        WHERE condition_id = ?
          AND token_id = ?
          AND truth_source = 'telegram_claim'
        """,
        [snapshot_as_of, snapshot_as_of, condition_id, token_id],
    )
    conn.commit()


def run_monitor(paths: RuntimePaths) -> str:
    timestamp = datetime.now(UTC).isoformat()
    run_id = str(uuid4())
    conn = connect_db(paths.db_path)
    apply_migrations(conn)
    RuntimeRepository(conn).upsert_run(
        {
            "id": run_id,
            "run_type": RunType.MONITOR.value,
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
    return run_id
