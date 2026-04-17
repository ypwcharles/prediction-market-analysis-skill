from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from polymarket_alert_bot.monitor.position_sync import (
    fetch_official_positions,
    reconcile_claimed_position,
    sync_official_positions,
)
from polymarket_alert_bot.storage.db import connect_db
from polymarket_alert_bot.storage.migrations import apply_migrations

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


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


def test_fetch_official_positions_normalizes_and_syncs(tmp_path):
    conn = connect_db(tmp_path / "runtime.sqlite3")
    apply_migrations(conn)
    now = datetime(2026, 4, 17, 0, 0, tzinfo=UTC)
    rows = fetch_official_positions(
        payload=_load_fixture("monitor_official_positions_raw.json"),
        now=now,
    )
    sync_official_positions(conn, rows)

    assert rows == [
        {
            "id": "official-cond-1-token-1",
            "condition_id": "cond-1",
            "token_id": "token-1",
            "market_id": "market-1",
            "thesis_cluster_id": None,
            "side": "YES",
            "size_shares": 12.0,
            "avg_entry_cents": 41.5,
            "status": "open",
            "truth_source": "official_api",
            "snapshot_as_of": "2026-04-17T00:00:00+00:00",
            "updated_at": "2026-04-17T00:00:00+00:00",
        }
    ]

    row = conn.execute(
        """
        SELECT condition_id, token_id, side, size_shares, truth_source
        FROM positions
        """
    ).fetchone()
    assert dict(row) == {
        "condition_id": "cond-1",
        "token_id": "token-1",
        "side": "YES",
        "size_shares": 12.0,
        "truth_source": "official_api",
    }
