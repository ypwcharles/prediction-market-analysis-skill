from __future__ import annotations

import json
from pathlib import Path
import sys

from polymarket_alert_bot.cli import main
from polymarket_alert_bot.config.settings import ensure_runtime_dirs, load_runtime_paths
from polymarket_alert_bot.monitor.position_sync import MonitorOutcome
from polymarket_alert_bot.runtime_flow import execute_monitor_flow
from polymarket_alert_bot.scanner.clob_client import BookSnapshot, degraded_snapshot
from polymarket_alert_bot.storage.db import connect_db
from polymarket_alert_bot.storage.migrations import apply_migrations


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
                    "rules_text=payload['context'].get('rules_text','');"
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
                    "'why_now':rules_text or 'No primary confirmation despite price spike.',"
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
        SELECT alert_kind, market_id, condition_id, status, archive_path, why_now
        FROM alerts
        ORDER BY market_id
        """
    ).fetchall()
    assert [(row["alert_kind"], row["market_id"], row["condition_id"], row["status"]) for row in alerts] == [
        ("strict_degraded", "mkt-live-degraded", "cond-live-b", "active"),
        ("strict", "mkt-live-tradable", "cond-live-a", "active"),
    ]
    assert all(Path(row["archive_path"]).exists() for row in alerts)
    why_now_by_market = {row["market_id"]: row["why_now"] for row in alerts}
    assert "Settlement uses certified election authority result." in why_now_by_market["mkt-live-tradable"]
    assert "Resolves YES only if Candidate A is certified as winner." in why_now_by_market["mkt-live-tradable"]
    assert "Settlement uses certified election authority result." in why_now_by_market["mkt-live-degraded"]
    assert "Resolves YES only if Candidate B is certified as winner." in why_now_by_market["mkt-live-degraded"]

    clusters = conn.execute(
        "SELECT canonical_name, status FROM thesis_clusters ORDER BY id"
    ).fetchall()
    assert len(clusters) == 2
    assert all(row["status"] == "open" for row in clusters)

    expression_rows = conn.execute(
        "SELECT condition_id, market_id, token_id, event_slug, market_slug FROM cluster_expressions ORDER BY market_id"
    ).fetchall()
    assert [
        (row["condition_id"], row["market_id"], row["token_id"], row["event_slug"], row["market_slug"])
        for row in expression_rows
    ] == [
        ("cond-live-b", "mkt-live-degraded", "token-live-degraded", "live-election-2026", "candidate-b-wins-live"),
        ("cond-live-a", "mkt-live-tradable", "token-live-tradable", "live-election-2026", "candidate-a-wins-live"),
    ]
    archive_text_by_market = {
        row["market_id"]: Path(row["archive_path"]).read_text(encoding="utf-8")
        for row in alerts
    }
    assert (
        "market: https://polymarket.com/event/live-election-2026/candidate-a-wins-live"
        in archive_text_by_market["mkt-live-tradable"]
    )
    assert (
        "market: https://polymarket.com/event/live-election-2026/candidate-b-wins-live"
        in archive_text_by_market["mkt-live-degraded"]
    )

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


def test_scan_command_loads_live_news_and_x_feeds_into_judgment_context(tmp_path, monkeypatch):
    data_dir = tmp_path / ".runtime-data"
    evidence_log = tmp_path / "evidence-log.jsonl"
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(data_dir))
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_ENABLE_SCAN", "1")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DISABLE_TELEGRAM", "1")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_TELEGRAM_CHAT_ID", "-100123456")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_NEWS_FEED_URL", str(FIXTURES / "news_samples.json"))
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_X_FEED_URL", str(FIXTURES / "x_samples.json"))
    monkeypatch.delenv("POLYMARKET_ALERT_BOT_NEWS_SAMPLES_PATH", raising=False)
    monkeypatch.delenv("POLYMARKET_ALERT_BOT_X_SAMPLES_PATH", raising=False)
    monkeypatch.setenv(
        "POLYMARKET_ALERT_BOT_JUDGMENT_RUNNER_CMD",
        " ".join(
            [
                sys.executable,
                "-c",
                (
                    "import json,sys,pathlib;"
                    "payload=json.load(sys.stdin);"
                    f"log_path=pathlib.Path({str(evidence_log)!r});"
                    "handle=log_path.open('a',encoding='utf-8');"
                    "handle.write(json.dumps(payload['context']['evidence'])+'\\n');"
                    "handle.close();"
                    "response={"
                    "'alert_kind':'research',"
                    "'cluster_action':'create',"
                    "'ttl_hours':6,"
                    "'summary':'feed evidence check',"
                    "'watch_item':'keep watching',"
                    "'citations':[],"
                    "'triggers':[],"
                    "'archive_payload':{'summary':'feed evidence check'}};"
                    "json.dump(response,sys.stdout)"
                ),
            ]
        ),
    )

    gamma_payload = _read_json("gamma_live_board.json")

    def _fake_fetch_book(token_id: str) -> BookSnapshot:
        return BookSnapshot(
            token_id=token_id,
            best_bid=0.49,
            best_ask=0.51,
            spread_bps=400.0,
            slippage_bps=200.0,
            is_degraded=False,
            degraded_reason=None,
        )

    monkeypatch.setattr("polymarket_alert_bot.scanner.board_scan.fetch_events", lambda: gamma_payload)
    monkeypatch.setattr("polymarket_alert_bot.scanner.board_scan.fetch_book", _fake_fetch_book)

    assert main(["scan"]) == 0

    evidence_rows = [
        json.loads(line)
        for line in evidence_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert evidence_rows
    source_ids = {item["source_id"] for item in evidence_rows[0]}
    assert {"reuters_001", "ap_002", "x_polymarket_001"} <= source_ids
    assert "x_reporter_002" not in source_ids


def test_scan_command_degrades_when_configured_evidence_feed_fails(tmp_path, monkeypatch):
    data_dir = tmp_path / ".runtime-data"
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(data_dir))
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_ENABLE_SCAN", "1")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DISABLE_TELEGRAM", "1")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_TELEGRAM_CHAT_ID", "-100123456")
    monkeypatch.setenv(
        "POLYMARKET_ALERT_BOT_NEWS_FEED_URL",
        str(tmp_path / "missing-news-feed.json"),
    )
    monkeypatch.delenv("POLYMARKET_ALERT_BOT_NEWS_SAMPLES_PATH", raising=False)
    monkeypatch.delenv("POLYMARKET_ALERT_BOT_X_FEED_URL", raising=False)
    monkeypatch.delenv("POLYMARKET_ALERT_BOT_X_SAMPLES_PATH", raising=False)
    monkeypatch.setenv(
        "POLYMARKET_ALERT_BOT_JUDGMENT_RUNNER_CMD",
        " ".join(
            [
                sys.executable,
                "-c",
                (
                    "import json,sys;"
                    "json.dump({"
                    "'alert_kind':'strict',"
                    "'cluster_action':'create',"
                    "'ttl_hours':6,"
                    "'thesis':'degraded evidence check',"
                    "'side':'NO',"
                    "'theoretical_edge_cents':15.0,"
                    "'executable_edge_cents':11.0,"
                    "'max_entry_cents':42.0,"
                    "'suggested_size_usdc':150.0,"
                    "'why_now':'strict candidate before evidence degradation handling',"
                    "'kill_criteria_text':'official confirmation',"
                    "'summary':'summary',"
                    "'watch_item':'watch',"
                    "'citations':[],"
                    "'triggers':[],"
                    "'archive_payload':{'summary':'archive'}"
                    "},sys.stdout)"
                ),
            ]
        ),
    )

    gamma_payload = _read_json("gamma_live_board.json")

    def _fake_fetch_book(token_id: str) -> BookSnapshot:
        return BookSnapshot(
            token_id=token_id,
            best_bid=0.49,
            best_ask=0.51,
            spread_bps=400.0,
            slippage_bps=200.0,
            is_degraded=False,
            degraded_reason=None,
        )

    monkeypatch.setattr("polymarket_alert_bot.scanner.board_scan.fetch_events", lambda: gamma_payload)
    monkeypatch.setattr("polymarket_alert_bot.scanner.board_scan.fetch_book", _fake_fetch_book)

    assert main(["scan"]) == 0

    conn = connect_db(data_dir / "sqlite" / "runtime.sqlite3")
    run_row = conn.execute(
        "SELECT id, status, degraded_reason FROM runs WHERE run_type = 'scan' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    assert run_row["status"] == "degraded"
    assert "news_feed_failed:FileNotFoundError" in run_row["degraded_reason"]

    alert_rows = conn.execute(
        "SELECT alert_kind FROM alerts WHERE run_id = ? ORDER BY market_id",
        [run_row["id"]],
    ).fetchall()
    assert alert_rows
    assert all(row["alert_kind"] != "strict" for row in alert_rows)
    assert any(row["alert_kind"] == "research" for row in alert_rows)


def _seed_monitor_source_alert(paths) -> None:
    conn = connect_db(paths.db_path)
    apply_migrations(conn)
    now_iso = "2026-04-18T00:00:00+00:00"
    conn.execute(
        """
        INSERT INTO runs (id, run_type, status, started_at, finished_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ["run-seed-monitor", "scan", "clean", now_iso, now_iso, now_iso],
    )
    conn.execute(
        """
        INSERT INTO thesis_clusters (id, canonical_name, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        ["cluster-source", "Source thesis", "open", now_iso, now_iso],
    )
    conn.execute(
        """
        INSERT INTO cluster_expressions (
            id, thesis_cluster_id, condition_id, event_id, market_id, token_id,
            event_slug, market_slug, expression_label, is_primary_expression, first_seen_at, last_seen_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            "expr-source",
            "cluster-source",
            "cond-source",
            "event-source",
            "market-source",
            "token-source",
            "source-event",
            "source-market",
            "source expression",
            1,
            now_iso,
            now_iso,
        ],
    )
    conn.execute(
        """
        INSERT INTO alerts (
            id, run_id, thesis_cluster_id, condition_id, event_id, market_id, token_id,
            alert_kind, delivery_mode, status, dedupe_key, why_now, kill_criteria_text, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            "alert-source",
            "run-seed-monitor",
            "cluster-source",
            "cond-source",
            "event-source",
            "market-source",
            "token-source",
            "strict",
            "immediate",
            "active",
            "dedupe-source",
            "Original narrative memo",
            "Resolve using official rule text only.",
            now_iso,
        ],
    )
    conn.commit()


def _seed_monitor_run(paths, run_id: str) -> None:
    conn = connect_db(paths.db_path)
    apply_migrations(conn)
    now_iso = "2026-04-18T01:00:00+00:00"
    conn.execute(
        """
        INSERT INTO runs (id, run_type, status, started_at, finished_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [run_id, "monitor", "clean", now_iso, now_iso, now_iso],
    )
    conn.commit()


def test_execute_monitor_flow_blocks_pending_recheck_without_llm_approval(monkeypatch, tmp_path):
    data_dir = tmp_path / ".runtime-data"
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(data_dir))
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DISABLE_TELEGRAM", "1")
    paths = load_runtime_paths()
    ensure_runtime_dirs(paths)
    _seed_monitor_source_alert(paths)

    recheck_log = tmp_path / "recheck-log.jsonl"
    script = (
        "import json,sys,pathlib;"
        "payload=json.load(sys.stdin);"
        f"log_path=pathlib.Path({str(recheck_log)!r});"
        "handle=log_path.open('a',encoding='utf-8');"
        "handle.write(json.dumps(payload)+'\\n');"
        "handle.close();"
        "response={"
        "'alert_kind':'research',"
        "'cluster_action':'hold',"
        "'ttl_hours':1,"
        "'citations':[],"
        "'triggers':[],"
        "'archive_payload':{'reason':'needs_more_confirmation'}"
        "};"
        "json.dump(response,sys.stdout)"
    )
    monkeypatch.setenv(
        "POLYMARKET_ALERT_BOT_JUDGMENT_RUNNER_CMD",
        " ".join([sys.executable, "-c", script]),
    )

    monitor_outcome = MonitorOutcome(
        run_id="run-monitor-test",
        stale_alert_ids=[],
        fired_actions=[],
        pending_recheck_actions=[
            {
                "trigger_id": "trigger-narrative",
                "alert_id": "alert-source",
                "thesis_cluster_id": "cluster-source",
                "trigger_type": "narrative_reassessment",
                "trigger_state": "armed",
                "suggested_action": "Reassess thesis",
                "observation": "Narrative moved without primary evidence",
                "requires_llm_recheck": True,
            }
        ],
        requires_llm_recheck_trigger_ids=["trigger-narrative"],
        reconciled_claim_ids=[],
        synced_official_positions=0,
    )
    _seed_monitor_run(paths, monitor_outcome.run_id)
    monkeypatch.setattr("polymarket_alert_bot.runtime_flow.run_monitor", lambda *args, **kwargs: monitor_outcome)

    delivered_messages: list[str] = []

    def _capture_deliver(*, text, **kwargs):
        delivered_messages.append(text)
        return None

    monkeypatch.setattr("polymarket_alert_bot.runtime_flow._deliver_message", _capture_deliver)

    summary = execute_monitor_flow(paths)

    assert summary.delivered_alert_ids == ()
    assert delivered_messages == []
    assert recheck_log.exists()
    payload_rows = [json.loads(line) for line in recheck_log.read_text(encoding="utf-8").splitlines()]
    assert len(payload_rows) == 1
    assert payload_rows[0]["context"]["candidate_facts"]["mode"] == "monitor_recheck"
    assert payload_rows[0]["context"]["candidate_facts"]["trigger_id"] == "trigger-narrative"


def test_execute_monitor_flow_delivers_pending_recheck_after_llm_approval(monkeypatch, tmp_path):
    data_dir = tmp_path / ".runtime-data"
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(data_dir))
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DISABLE_TELEGRAM", "1")
    paths = load_runtime_paths()
    ensure_runtime_dirs(paths)
    _seed_monitor_source_alert(paths)

    recheck_log = tmp_path / "recheck-log-approved.jsonl"
    script = (
        "import json,sys,pathlib;"
        "payload=json.load(sys.stdin);"
        f"log_path=pathlib.Path({str(recheck_log)!r});"
        "handle=log_path.open('a',encoding='utf-8');"
        "handle.write(json.dumps(payload)+'\\n');"
        "handle.close();"
        "response={"
        "'alert_kind':'monitor',"
        "'cluster_action':'update',"
        "'ttl_hours':2,"
        "'citations':[],"
        "'triggers':[],"
        "'archive_payload':{'reason':'approved'}"
        "};"
        "json.dump(response,sys.stdout)"
    )
    monkeypatch.setenv(
        "POLYMARKET_ALERT_BOT_JUDGMENT_RUNNER_CMD",
        " ".join([sys.executable, "-c", script]),
    )

    monitor_outcome = MonitorOutcome(
        run_id="run-monitor-test-approve",
        stale_alert_ids=[],
        fired_actions=[],
        pending_recheck_actions=[
            {
                "trigger_id": "trigger-narrative-approved",
                "alert_id": "alert-source",
                "thesis_cluster_id": "cluster-source",
                "trigger_type": "narrative_reassessment",
                "trigger_state": "armed",
                "suggested_action": "Approve and alert",
                "observation": "Primary evidence now supports narrative shift",
                "requires_llm_recheck": True,
            }
        ],
        requires_llm_recheck_trigger_ids=["trigger-narrative-approved"],
        reconciled_claim_ids=[],
        synced_official_positions=0,
    )
    _seed_monitor_run(paths, monitor_outcome.run_id)
    monkeypatch.setattr("polymarket_alert_bot.runtime_flow.run_monitor", lambda *args, **kwargs: monitor_outcome)

    delivered_messages: list[str] = []

    def _capture_deliver(*, text, **kwargs):
        delivered_messages.append(text)
        return None

    monkeypatch.setattr("polymarket_alert_bot.runtime_flow._deliver_message", _capture_deliver)

    summary = execute_monitor_flow(paths)

    assert len(summary.delivered_alert_ids) == 1
    assert len(delivered_messages) == 1
    assert "market: https://polymarket.com/event/source-event/source-market" in delivered_messages[0]
    assert recheck_log.exists()
    payload_rows = [json.loads(line) for line in recheck_log.read_text(encoding="utf-8").splitlines()]
    assert len(payload_rows) == 1
    assert payload_rows[0]["context"]["candidate_facts"]["trigger_id"] == "trigger-narrative-approved"

    conn = connect_db(paths.db_path)
    monitor_alert_rows = conn.execute(
        "SELECT alert_kind, delivery_mode, market_id FROM alerts WHERE run_id = ?",
        ["run-monitor-test-approve"],
    ).fetchall()
    assert [(row["alert_kind"], row["delivery_mode"], row["market_id"]) for row in monitor_alert_rows] == [
        ("monitor", "immediate", "market-source")
    ]
