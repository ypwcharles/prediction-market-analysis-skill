from __future__ import annotations

from polymarket_alert_bot.cli import main
from polymarket_alert_bot.storage.db import connect_db


def test_scan_monitor_and_report_write_run_rows(tmp_path, monkeypatch):
    data_dir = tmp_path / ".runtime-data"
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(data_dir))

    assert main(["scan"]) == 0
    assert main(["monitor"]) == 0
    assert main(["report"]) == 0

    conn = connect_db(data_dir / "sqlite" / "runtime.sqlite3")
    rows = conn.execute("select run_type, status from runs order by created_at").fetchall()
    assert [(row["run_type"], row["status"]) for row in rows] == [
        ("scan", "clean"),
        ("monitor", "clean"),
        ("report", "clean"),
    ]
