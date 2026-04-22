from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from polymarket_alert_bot.config.settings import ensure_runtime_dirs, load_runtime_paths
from polymarket_alert_bot.monitor import position_sync
from polymarket_alert_bot.monitor.position_sync import run_monitor
from polymarket_alert_bot.scanner.clob_client import BookSnapshot
from polymarket_alert_bot.storage.db import connect_db
from polymarket_alert_bot.storage.migrations import apply_migrations

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_run_monitor_writes_clean_run(monkeypatch, tmp_path):
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(tmp_path / ".runtime-data"))
    paths = load_runtime_paths()
    ensure_runtime_dirs(paths)

    outcome = run_monitor(paths)

    conn = connect_db(paths.db_path)
    row = conn.execute(
        "SELECT run_type, status FROM runs WHERE id = ?",
        [outcome.run_id],
    ).fetchone()
    assert (row["run_type"], row["status"]) == ("monitor", "clean")
    assert outcome.fired_actions == []
    assert outcome.stale_alert_ids == []


def test_run_monitor_evaluates_triggers_and_reconciles_claims(monkeypatch, tmp_path):
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(tmp_path / ".runtime-data"))
    paths = load_runtime_paths()
    ensure_runtime_dirs(paths)
    conn = connect_db(paths.db_path)
    apply_migrations(conn)
    now = datetime(2026, 4, 17, 9, 0, tzinfo=UTC)
    now_iso = now.isoformat()
    stale_at = (now - timedelta(minutes=5)).isoformat()
    future_recheck = (now + timedelta(hours=2)).isoformat()

    conn.execute(
        """
        INSERT INTO runs (
            id, run_type, status, started_at, finished_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        ["run-seed", "scan", "clean", now_iso, now_iso, now_iso],
    )
    conn.executemany(
        """
        INSERT INTO thesis_clusters (
            id, canonical_name, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        [
            ["cluster-live", "Live thesis", "open", now_iso, now_iso],
            ["cluster-stale", "Stale thesis", "open", now_iso, now_iso],
        ],
    )
    conn.executemany(
        """
        INSERT INTO alerts (
            id, run_id, thesis_cluster_id, market_id, token_id,
            alert_kind, delivery_mode, status, dedupe_key, recheck_required_at,
            executable_edge_cents, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            [
                "alert-live",
                "run-seed",
                "cluster-live",
                "market-1",
                "token-1",
                "monitor",
                "immediate",
                "active",
                "dedupe-live",
                future_recheck,
                15.0,
                now_iso,
            ],
            [
                "alert-stale",
                "run-seed",
                "cluster-stale",
                "market-2",
                "token-2",
                "monitor",
                "immediate",
                "active",
                "dedupe-stale",
                stale_at,
                3.0,
                now_iso,
            ],
        ],
    )
    conn.executemany(
        """
        INSERT INTO triggers (
            id, thesis_cluster_id, alert_id, trigger_type, threshold_kind,
            comparison, threshold_value, suggested_action, requires_llm_recheck,
            state, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            [
                "trg-size",
                "cluster-live",
                "alert-live",
                "position_size",
                "position_size_shares",
                ">=",
                "10",
                "Scale-in review",
                0,
                "armed",
                now_iso,
                now_iso,
            ],
            [
                "trg-narrative",
                "cluster-live",
                "alert-live",
                "narrative_reassessment",
                "narrative",
                "eq",
                "escalation",
                "LLM recheck required",
                1,
                "armed",
                now_iso,
                now_iso,
            ],
        ],
    )
    conn.execute(
        """
        INSERT INTO positions (
            id, condition_id, token_id, market_id, side, size_shares, status,
            truth_source, snapshot_as_of, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            "pos-claim-1",
            "cond-1",
            "token-1",
            "market-1",
            "YES",
            10.0,
            "claimed_only",
            "telegram_claim",
            now_iso,
            now_iso,
        ],
    )
    conn.commit()

    official_payload = _load_fixture("monitor_official_positions_raw.json")
    outcome = run_monitor(paths, official_positions_payload=official_payload, now=now)

    run_row = conn.execute(
        "SELECT run_type, status FROM runs WHERE id = ?",
        [outcome.run_id],
    ).fetchone()
    assert (run_row["run_type"], run_row["status"]) == ("monitor", "clean")
    assert len(outcome.fired_actions) == 1
    assert outcome.fired_actions[0]["trigger_id"] == "trg-size"
    assert set(outcome.stale_alert_ids) == {"alert-stale"}
    assert set(outcome.requires_llm_recheck_trigger_ids) == {"trg-narrative"}
    assert outcome.reconciled_claim_ids == ["pos-claim-1"]

    trigger_states = {
        row["id"]: row["state"] for row in conn.execute("SELECT id, state FROM triggers").fetchall()
    }
    assert trigger_states == {
        "trg-size": "fired",
        "trg-narrative": "fired",
    }

    alert_status = conn.execute("SELECT status FROM alerts WHERE id = 'alert-stale'").fetchone()[
        "status"
    ]
    cluster_status = conn.execute(
        "SELECT status FROM thesis_clusters WHERE id = 'cluster-stale'"
    ).fetchone()["status"]
    claim_row = conn.execute(
        "SELECT status, truth_source FROM positions WHERE id = 'pos-claim-1'"
    ).fetchone()
    assert alert_status == "stale"
    assert cluster_status == "pending_recheck"
    assert (claim_row["status"], claim_row["truth_source"]) == ("open", "official_api")

    second_outcome = run_monitor(paths, official_positions_payload=official_payload, now=now)
    assert second_outcome.fired_actions == []
    assert second_outcome.pending_recheck_actions == []
    assert second_outcome.requires_llm_recheck_trigger_ids == []


def test_run_monitor_uses_live_orderbook_for_price_triggers(monkeypatch, tmp_path):
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(tmp_path / ".runtime-data"))
    paths = load_runtime_paths()
    ensure_runtime_dirs(paths)
    conn = connect_db(paths.db_path)
    apply_migrations(conn)
    now = datetime(2026, 4, 17, 9, 0, tzinfo=UTC)
    now_iso = now.isoformat()

    conn.execute(
        """
        INSERT INTO runs (
            id, run_type, status, started_at, finished_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        ["run-seed", "scan", "clean", now_iso, now_iso, now_iso],
    )
    conn.execute(
        """
        INSERT INTO thesis_clusters (
            id, canonical_name, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        ["cluster-live", "Live thesis", "open", now_iso, now_iso],
    )
    conn.execute(
        """
        INSERT INTO alerts (
            id, run_id, thesis_cluster_id, market_id, token_id,
            alert_kind, delivery_mode, status, dedupe_key, recheck_required_at,
            max_entry_cents, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            "alert-live",
            "run-seed",
            "cluster-live",
            "market-1",
            "token-1",
            "monitor",
            "immediate",
            "active",
            "dedupe-live",
            (now + timedelta(hours=2)).isoformat(),
            39.0,
            now_iso,
        ],
    )
    conn.execute(
        """
        INSERT INTO triggers (
            id, thesis_cluster_id, alert_id, trigger_type, threshold_kind,
            comparison, threshold_value, suggested_action, requires_llm_recheck,
            state, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            "trg-price",
            "cluster-live",
            "alert-live",
            "price_reprice",
            "price",
            "<=",
            "40",
            "Reprice review",
            0,
            "armed",
            now_iso,
            now_iso,
        ],
    )
    conn.commit()

    observed_book_calls: list[str] = []

    def _fake_fetch_book(token_id: str, *, url: str = "") -> BookSnapshot:
        observed_book_calls.append(token_id)
        return BookSnapshot(
            token_id=token_id,
            best_bid=0.39,
            best_ask=0.40,
            spread_bps=200.0,
            slippage_bps=100.0,
            is_degraded=False,
            degraded_reason=None,
        )

    monkeypatch.setattr(position_sync, "fetch_book", _fake_fetch_book)

    outcome = run_monitor(paths, now=now)

    assert observed_book_calls == ["token-1"]
    assert len(outcome.fired_actions) == 1
    assert outcome.fired_actions[0]["trigger_id"] == "trg-price"


def test_run_monitor_uses_live_orderbook_for_execution_cost_triggers(monkeypatch, tmp_path):
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(tmp_path / ".runtime-data"))
    paths = load_runtime_paths()
    ensure_runtime_dirs(paths)
    conn = connect_db(paths.db_path)
    apply_migrations(conn)
    now = datetime(2026, 4, 17, 9, 0, tzinfo=UTC)
    now_iso = now.isoformat()

    conn.execute(
        """
        INSERT INTO runs (
            id, run_type, status, started_at, finished_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        ["run-seed", "scan", "clean", now_iso, now_iso, now_iso],
    )
    conn.execute(
        """
        INSERT INTO thesis_clusters (
            id, canonical_name, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        ["cluster-live", "Live thesis", "open", now_iso, now_iso],
    )
    conn.execute(
        """
        INSERT INTO alerts (
            id, run_id, thesis_cluster_id, market_id, token_id,
            alert_kind, delivery_mode, status, dedupe_key, recheck_required_at,
            spread_bps, slippage_bps, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            "alert-live",
            "run-seed",
            "cluster-live",
            "market-1",
            "token-1",
            "monitor",
            "immediate",
            "active",
            "dedupe-live",
            (now + timedelta(hours=2)).isoformat(),
            800.0,
            400.0,
            now_iso,
        ],
    )
    conn.execute(
        """
        INSERT INTO triggers (
            id, thesis_cluster_id, alert_id, trigger_type, threshold_kind,
            comparison, threshold_value, suggested_action, requires_llm_recheck,
            state, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            "trg-cost",
            "cluster-live",
            "alert-live",
            "price_threshold",
            "execution_cost",
            "<=",
            "200",
            "Review",
            1,
            "armed",
            now_iso,
            now_iso,
        ],
    )
    conn.commit()

    observed_book_calls: list[str] = []

    def _fake_fetch_book(token_id: str, *, url: str = "") -> BookSnapshot:
        observed_book_calls.append(token_id)
        return BookSnapshot(
            token_id=token_id,
            best_bid=0.39,
            best_ask=0.40,
            spread_bps=120.0,
            slippage_bps=60.0,
            is_degraded=False,
            degraded_reason=None,
        )

    monkeypatch.setattr(position_sync, "fetch_book", _fake_fetch_book)

    outcome = run_monitor(paths, now=now)

    assert observed_book_calls == ["token-1"]
    assert outcome.fired_actions == []
    assert len(outcome.pending_recheck_actions) == 1
    assert outcome.pending_recheck_actions[0]["trigger_id"] == "trg-cost"
    assert outcome.pending_recheck_actions[0]["observation"] == 180.0

    trigger_row = conn.execute(
        "SELECT state, last_fired_at FROM triggers WHERE id = ?",
        ["trg-cost"],
    ).fetchone()
    assert trigger_row["state"] == "fired"
    assert trigger_row["last_fired_at"] == now_iso


def test_run_monitor_does_not_fire_execution_cost_trigger_on_degraded_live_book(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(tmp_path / ".runtime-data"))
    paths = load_runtime_paths()
    ensure_runtime_dirs(paths)
    conn = connect_db(paths.db_path)
    apply_migrations(conn)
    now = datetime(2026, 4, 17, 9, 0, tzinfo=UTC)
    now_iso = now.isoformat()

    conn.execute(
        """
        INSERT INTO runs (
            id, run_type, status, started_at, finished_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        ["run-seed", "scan", "clean", now_iso, now_iso, now_iso],
    )
    conn.execute(
        """
        INSERT INTO thesis_clusters (
            id, canonical_name, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        ["cluster-live", "Live thesis", "open", now_iso, now_iso],
    )
    conn.execute(
        """
        INSERT INTO alerts (
            id, run_id, thesis_cluster_id, market_id, token_id,
            alert_kind, delivery_mode, status, dedupe_key, recheck_required_at,
            spread_bps, slippage_bps, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            "alert-live",
            "run-seed",
            "cluster-live",
            "market-1",
            "token-1",
            "monitor",
            "immediate",
            "active",
            "dedupe-live",
            (now + timedelta(hours=2)).isoformat(),
            800.0,
            400.0,
            now_iso,
        ],
    )
    conn.execute(
        """
        INSERT INTO triggers (
            id, thesis_cluster_id, alert_id, trigger_type, threshold_kind,
            comparison, threshold_value, suggested_action, requires_llm_recheck,
            state, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            "trg-cost",
            "cluster-live",
            "alert-live",
            "price_threshold",
            "execution_cost",
            "<=",
            "200",
            "Review",
            1,
            "armed",
            now_iso,
            now_iso,
        ],
    )
    conn.commit()

    observed_book_calls: list[str] = []

    def _fake_fetch_book(token_id: str, *, url: str = "") -> BookSnapshot:
        observed_book_calls.append(token_id)
        return position_sync.degraded_snapshot(token_id, "book_fetch_error")

    monkeypatch.setattr(position_sync, "fetch_book", _fake_fetch_book)

    outcome = run_monitor(paths, now=now)

    assert observed_book_calls == ["token-1"]
    assert outcome.fired_actions == []
    assert outcome.pending_recheck_actions == []

    trigger_row = conn.execute(
        "SELECT state, last_fired_at FROM triggers WHERE id = ?",
        ["trg-cost"],
    ).fetchone()
    assert trigger_row["state"] == "armed"
    assert trigger_row["last_fired_at"] is None


def test_run_monitor_rearms_snoozed_triggers_after_cooldown(monkeypatch, tmp_path):
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(tmp_path / ".runtime-data"))
    paths = load_runtime_paths()
    ensure_runtime_dirs(paths)
    conn = connect_db(paths.db_path)
    apply_migrations(conn)
    now = datetime(2026, 4, 17, 9, 0, tzinfo=UTC)
    now_iso = now.isoformat()

    conn.execute(
        """
        INSERT INTO runs (
            id, run_type, status, started_at, finished_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        ["run-seed", "scan", "clean", now_iso, now_iso, now_iso],
    )
    conn.execute(
        """
        INSERT INTO thesis_clusters (
            id, canonical_name, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        ["cluster-live", "Live thesis", "open", now_iso, now_iso],
    )
    conn.execute(
        """
        INSERT INTO alerts (
            id, run_id, thesis_cluster_id, market_id, token_id,
            alert_kind, delivery_mode, status, dedupe_key, recheck_required_at,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            "alert-live",
            "run-seed",
            "cluster-live",
            "market-1",
            "token-1",
            "monitor",
            "immediate",
            "active",
            "dedupe-live",
            (now + timedelta(hours=2)).isoformat(),
            now_iso,
        ],
    )
    conn.execute(
        """
        INSERT INTO triggers (
            id, thesis_cluster_id, alert_id, trigger_type, threshold_kind,
            comparison, threshold_value, suggested_action, requires_llm_recheck,
            state, cooldown_until, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            "trg-snoozed",
            "cluster-live",
            "alert-live",
            "position_size",
            "position_size_shares",
            ">=",
            "10",
            "Scale-in review",
            0,
            "snoozed",
            (now - timedelta(minutes=30)).isoformat(),
            now_iso,
            now_iso,
        ],
    )
    conn.commit()

    outcome = run_monitor(paths, now=now)

    assert outcome.fired_actions == []
    row = conn.execute(
        "SELECT state FROM triggers WHERE id = ?",
        ["trg-snoozed"],
    ).fetchone()
    assert row["state"] == "rearmed"
