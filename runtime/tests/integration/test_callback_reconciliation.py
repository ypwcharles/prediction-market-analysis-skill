from __future__ import annotations

from datetime import UTC, datetime

from polymarket_alert_bot.monitor.position_sync import reconcile_claimed_position
from polymarket_alert_bot.storage.db import connect_db
from polymarket_alert_bot.storage.migrations import apply_migrations


def test_reconcile_claimed_position_promotes_claim_to_official(tmp_path):
    conn = connect_db(tmp_path / "runtime.sqlite3")
    apply_migrations(conn)
    now = datetime.now(UTC).isoformat()
    conn.execute(
        """
        INSERT INTO positions (
            id, condition_id, token_id, side, size_shares,
            status, truth_source, snapshot_as_of, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            "pos-1",
            "cond-1",
            "token-1",
            "YES",
            10.0,
            "claimed_only",
            "telegram_claim",
            now,
            now,
        ],
    )
    conn.commit()

    reconcile_claimed_position(
        conn,
        condition_id="cond-1",
        token_id="token-1",
        snapshot_as_of=now,
    )

    row = conn.execute(
        "SELECT status, truth_source FROM positions WHERE id = 'pos-1'"
    ).fetchone()
    assert (row["status"], row["truth_source"]) == ("open", "official_api")
