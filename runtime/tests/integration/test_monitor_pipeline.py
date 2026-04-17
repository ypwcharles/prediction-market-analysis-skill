from __future__ import annotations

from polymarket_alert_bot.config.settings import ensure_runtime_dirs, load_runtime_paths
from polymarket_alert_bot.monitor.position_sync import run_monitor
from polymarket_alert_bot.storage.db import connect_db


def test_run_monitor_writes_clean_run(monkeypatch, tmp_path):
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(tmp_path / ".runtime-data"))
    paths = load_runtime_paths()
    ensure_runtime_dirs(paths)

    run_id = run_monitor(paths)

    conn = connect_db(paths.db_path)
    row = conn.execute(
        "SELECT run_type, status FROM runs WHERE id = ?",
        [run_id],
    ).fetchone()
    assert (row["run_type"], row["status"]) == ("monitor", "clean")
