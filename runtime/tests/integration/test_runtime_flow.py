from __future__ import annotations

import json
from pathlib import Path
import sys

from polymarket_alert_bot.cli import main
from polymarket_alert_bot.scanner.clob_client import BookSnapshot, degraded_snapshot
from polymarket_alert_bot.storage.db import connect_db


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _read_json(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_scan_command_persists_final_alerts_clusters_and_archives(tmp_path, monkeypatch):
    data_dir = tmp_path / ".runtime-data"
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(data_dir))
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_ENABLE_SCAN", "1")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DISABLE_TELEGRAM", "1")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_TELEGRAM_CHAT_ID", "-100123456")
    monkeypatch.setenv(
        "POLYMARKET_ALERT_BOT_NEWS_SAMPLES_PATH",
        str(FIXTURES / "news_samples.json"),
    )
    monkeypatch.setenv(
        "POLYMARKET_ALERT_BOT_X_SAMPLES_PATH",
        str(FIXTURES / "x_samples.json"),
    )
    monkeypatch.setenv(
        "POLYMARKET_ALERT_BOT_JUDGMENT_RUNNER_CMD",
        " ".join(
            [
                sys.executable,
                "-c",
                (
                    "import json,sys;"
                    "payload=json.load(sys.stdin);"
                    "condition_id=payload['context']['candidate_facts'].get('condition_id');"
                    "alert_kind='strict' if condition_id=='cond-live-a' else 'strict';"
                    "response={"
                    "'alert_kind':alert_kind,"
                    "'cluster_action':'create',"
                    "'ttl_hours':6,"
                    "'thesis':'Rumor premium should mean-revert',"
                    "'side':'NO',"
                    "'theoretical_edge_cents':14.2,"
                    "'executable_edge_cents':10.5,"
                    "'max_entry_cents':43.0,"
                    "'suggested_size_usdc':250.0,"
                    "'why_now':'No primary confirmation despite price spike.',"
                    "'kill_criteria_text':'Primary confirmation or rule change.',"
                    "'summary':'research summary',"
                    "'watch_item':'Need updated official statement',"
                    "'evidence_fresh_until':'2026-04-18T12:00:00Z',"
                    "'recheck_required_at':'2026-04-18T06:00:00Z',"
                    "'citations':[{'claim':'Reuters reports no confirmation yet.','source':{'id':'reuters','name':'Reuters','url':'https://www.reuters.com/test','tier':'primary','fetched_at':'2026-04-17T12:00:00Z'}}],"
                    "'triggers':[{'trigger_type':'price_reprice','threshold_kind':'price','comparison':'<=','threshold_value':'43','suggested_action':'Add on repricing','condition':'YES <= 43'}],"
                    "'archive_payload':{'summary':'archive summary'}};"
                    "json.dump(response,sys.stdout)"
                ),
            ]
        ),
    )

    gamma_payload = _read_json("gamma_live_board.json")

    def _fake_fetch_book(token_id: str) -> BookSnapshot:
        if token_id == "token-live-tradable":
            return BookSnapshot(
                token_id=token_id,
                best_bid=0.49,
                best_ask=0.51,
                spread_bps=400.0,
                slippage_bps=200.0,
                is_degraded=False,
                degraded_reason=None,
            )
        return degraded_snapshot(token_id, "book_missing")

    monkeypatch.setattr("polymarket_alert_bot.scanner.board_scan.fetch_events", lambda: gamma_payload)
    monkeypatch.setattr("polymarket_alert_bot.scanner.board_scan.fetch_book", _fake_fetch_book)

    assert main(["scan"]) == 0

    conn = connect_db(data_dir / "sqlite" / "runtime.sqlite3")
    alerts = conn.execute(
        """
        SELECT alert_kind, market_id, condition_id, status, archive_path
        FROM alerts
        ORDER BY market_id
        """
    ).fetchall()
    assert [(row["alert_kind"], row["market_id"], row["condition_id"], row["status"]) for row in alerts] == [
        ("strict_degraded", "mkt-live-degraded", "cond-live-b", "active"),
        ("strict", "mkt-live-tradable", "cond-live-a", "active"),
    ]
    assert all(Path(row["archive_path"]).exists() for row in alerts)

    clusters = conn.execute(
        "SELECT canonical_name, status FROM thesis_clusters ORDER BY id"
    ).fetchall()
    assert len(clusters) == 2
    assert all(row["status"] == "open" for row in clusters)

    expression_rows = conn.execute(
        "SELECT condition_id, market_id, token_id FROM cluster_expressions ORDER BY market_id"
    ).fetchall()
    assert [(row["condition_id"], row["market_id"], row["token_id"]) for row in expression_rows] == [
        ("cond-live-b", "mkt-live-degraded", "token-live-degraded"),
        ("cond-live-a", "mkt-live-tradable", "token-live-tradable"),
    ]

    claim_mappings = conn.execute(
        "SELECT claim_type, source_id FROM claim_source_mappings ORDER BY id"
    ).fetchall()
    assert len(claim_mappings) == 2
    assert all(row["source_id"] == "reuters" for row in claim_mappings)

    triggers = conn.execute(
        "SELECT trigger_type, state, suggested_action FROM triggers ORDER BY id"
    ).fetchall()
    assert len(triggers) == 2
    assert all(row["trigger_type"] == "price_reprice" for row in triggers)
    assert all(row["state"] == "armed" for row in triggers)
