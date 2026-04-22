from __future__ import annotations

import json
import sys
from pathlib import Path

from polymarket_alert_bot.cli import main
from polymarket_alert_bot.config.settings import ensure_runtime_dirs, load_runtime_paths
from polymarket_alert_bot.monitor.position_sync import MonitorOutcome
from polymarket_alert_bot.runtime_flow import execute_monitor_flow
from polymarket_alert_bot.scanner.board_scan import run_scan as board_run_scan
from polymarket_alert_bot.scanner.clob_client import BookSnapshot, degraded_snapshot
from polymarket_alert_bot.sources.evidence_enricher import EvidenceItem
from polymarket_alert_bot.sources.shortlist_retrieval import ShortlistRetrievalResult
from polymarket_alert_bot.storage.db import connect_db
from polymarket_alert_bot.storage.migrations import apply_migrations

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _read_json(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _write_live_election_candidate_feeds(tmp_path: Path) -> tuple[Path, Path]:
    news_feed = tmp_path / "candidate-news-feed.json"
    x_feed = tmp_path / "candidate-x-feed.json"
    news_feed.write_text(
        json.dumps(
            [
                {
                    "source_id": "news-live-1",
                    "url": "https://news.example.test/live-1",
                    "claim_snippet": (
                        "2026 Live Election update: Candidate A and Candidate B still await "
                        "a certified result."
                    ),
                    "tier": "primary",
                },
                {
                    "source_id": "news-live-2",
                    "url": "https://news.example.test/live-2",
                    "claim_snippet": (
                        "Live election board remains uncertified as officials review "
                        "Candidate A versus Candidate B."
                    ),
                    "tier": "primary",
                },
            ]
        ),
        encoding="utf-8",
    )
    x_feed.write_text(
        json.dumps(
            [
                {
                    "source_id": "x-live-1",
                    "handle": "@polymarket",
                    "url": "https://x.com/polymarket/status/1",
                    "claim_snippet": (
                        "Polymarket update: Candidate A and Candidate B live election market "
                        "still awaits certification."
                    ),
                }
            ]
        ),
        encoding="utf-8",
    )
    return news_feed, x_feed


def test_scan_command_persists_final_alerts_clusters_and_archives(tmp_path, monkeypatch):
    data_dir = tmp_path / ".runtime-data"
    news_feed, x_feed = _write_live_election_candidate_feeds(tmp_path)
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(data_dir))
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_ENABLE_SCAN", "1")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DISABLE_TELEGRAM", "1")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_TELEGRAM_CHAT_ID", "-100123456")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_NEWS_FEED_URL", str(news_feed))
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_X_FEED_URL", str(x_feed))
    monkeypatch.delenv("POLYMARKET_ALERT_BOT_NEWS_SAMPLES_PATH", raising=False)
    monkeypatch.delenv("POLYMARKET_ALERT_BOT_X_SAMPLES_PATH", raising=False)
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

    monkeypatch.setattr(
        "polymarket_alert_bot.scanner.board_scan.fetch_events", lambda: gamma_payload
    )
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
    assert [
        (row["alert_kind"], row["market_id"], row["condition_id"], row["status"]) for row in alerts
    ] == [
        ("strict_degraded", "mkt-live-degraded", "cond-live-b", "active"),
        ("strict", "mkt-live-tradable", "cond-live-a", "active"),
    ]
    assert all(Path(row["archive_path"]).exists() for row in alerts)
    why_now_by_market = {row["market_id"]: row["why_now"] for row in alerts}
    assert (
        "Settlement uses certified election authority result."
        in why_now_by_market["mkt-live-tradable"]
    )
    assert (
        "Resolves YES only if Candidate A is certified as winner."
        in why_now_by_market["mkt-live-tradable"]
    )
    assert (
        "Settlement uses certified election authority result."
        in why_now_by_market["mkt-live-degraded"]
    )
    assert (
        "Resolves YES only if Candidate B is certified as winner."
        in why_now_by_market["mkt-live-degraded"]
    )

    clusters = conn.execute(
        "SELECT canonical_name, status FROM thesis_clusters ORDER BY id"
    ).fetchall()
    assert len(clusters) == 2
    assert all(row["status"] == "open" for row in clusters)

    expression_rows = conn.execute(
        "SELECT condition_id, market_id, token_id, event_slug, market_slug FROM cluster_expressions ORDER BY market_id"
    ).fetchall()
    assert [
        (
            row["condition_id"],
            row["market_id"],
            row["token_id"],
            row["event_slug"],
            row["market_slug"],
        )
        for row in expression_rows
    ] == [
        (
            "cond-live-b",
            "mkt-live-degraded",
            "token-live-degraded",
            "live-election-2026",
            "candidate-b-wins-live",
        ),
        (
            "cond-live-a",
            "mkt-live-tradable",
            "token-live-tradable",
            "live-election-2026",
            "candidate-a-wins-live",
        ),
    ]
    archive_text_by_market = {
        row["market_id"]: Path(row["archive_path"]).read_text(encoding="utf-8") for row in alerts
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
        """
        SELECT trigger_type, threshold_kind, comparison, threshold_value, state, suggested_action
        FROM triggers
        ORDER BY id
        """
    ).fetchall()
    assert len(triggers) == 2
    assert all(row["trigger_type"] == "price_reprice" for row in triggers)
    assert all(row["threshold_kind"] == "price" for row in triggers)
    assert all(row["comparison"] == "<=" for row in triggers)
    assert all(row["threshold_value"] == "43" for row in triggers)
    assert all(row["state"] == "armed" for row in triggers)


def test_scan_command_loads_live_news_and_x_feeds_into_judgment_context(tmp_path, monkeypatch):
    data_dir = tmp_path / ".runtime-data"
    evidence_log = tmp_path / "evidence-log.jsonl"
    news_feed, x_feed = _write_live_election_candidate_feeds(tmp_path)
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(data_dir))
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_ENABLE_SCAN", "1")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DISABLE_TELEGRAM", "1")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_TELEGRAM_CHAT_ID", "-100123456")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_NEWS_FEED_URL", str(news_feed))
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_X_FEED_URL", str(x_feed))
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

    monkeypatch.setattr(
        "polymarket_alert_bot.scanner.board_scan.fetch_events", lambda: gamma_payload
    )
    monkeypatch.setattr("polymarket_alert_bot.scanner.board_scan.fetch_book", _fake_fetch_book)

    assert main(["scan"]) == 0

    evidence_rows = [
        json.loads(line)
        for line in evidence_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert evidence_rows
    source_ids = {item["source_id"] for item in evidence_rows[0]}
    assert {"news-live-1", "news-live-2", "x-live-1"} <= source_ids


def test_scan_command_prefers_shortlist_retrieval_and_passes_rich_snapshot(tmp_path, monkeypatch):
    data_dir = tmp_path / ".runtime-data"
    payload_log = tmp_path / "payload-log.jsonl"
    news_feed = tmp_path / "news-feed.json"
    x_feed = tmp_path / "x-feed.json"
    news_feed.write_text(
        json.dumps(
            [
                {
                    "source_id": "news-candidate-a-1",
                    "url": "https://news.example.test/candidate-a-1",
                    "claim_snippet": "2026 Live Election polling update puts Candidate A ahead.",
                    "tier": "primary",
                },
                {
                    "source_id": "news-candidate-a-2",
                    "url": "https://news.example.test/candidate-a-2",
                    "claim_snippet": "Candidate A gains momentum in the live election.",
                    "tier": "primary",
                },
                {
                    "source_id": "news-unrelated",
                    "url": "https://news.example.test/unrelated",
                    "claim_snippet": "Oil inventories rose overnight.",
                    "tier": "primary",
                },
            ]
        ),
        encoding="utf-8",
    )
    x_feed.write_text(
        json.dumps(
            [
                {
                    "source_id": "x-candidate-a",
                    "handle": "@polymarket",
                    "url": "https://x.com/polymarket/status/1",
                    "claim_snippet": "Candidate A market moving after live election update.",
                },
                {
                    "source_id": "x-unrelated",
                    "handle": "@polymarket",
                    "url": "https://x.com/polymarket/status/2",
                    "claim_snippet": "Completely unrelated sports headline.",
                },
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(data_dir))
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_ENABLE_SCAN", "1")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DISABLE_TELEGRAM", "1")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_TELEGRAM_CHAT_ID", "-100123456")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_SCAN_MAX_JUDGMENT_CANDIDATES", "1")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_NEWS_FEED_URL", str(news_feed))
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_X_FEED_URL", str(x_feed))
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
                    f"log_path=pathlib.Path({str(payload_log)!r});"
                    "handle=log_path.open('a',encoding='utf-8');"
                    "handle.write(json.dumps(payload)+'\\n');"
                    "handle.close();"
                    "json.dump({"
                    "'alert_kind':'research',"
                    "'cluster_action':'create',"
                    "'ttl_hours':6,"
                    "'summary':'shortlist retrieval check',"
                    "'watch_item':'keep watching',"
                    "'citations':[],"
                    "'triggers':[],"
                    "'archive_payload':{'summary':'shortlist retrieval check'}"
                    "},sys.stdout)"
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

    monkeypatch.setattr(
        "polymarket_alert_bot.scanner.board_scan.fetch_events", lambda: gamma_payload
    )
    monkeypatch.setattr("polymarket_alert_bot.scanner.board_scan.fetch_book", _fake_fetch_book)

    assert main(["scan"]) == 0

    payload_rows = [
        json.loads(line) for line in payload_log.read_text(encoding="utf-8").splitlines() if line
    ]
    assert len(payload_rows) == 1
    context = payload_rows[0]["context"]
    assert context["candidate_facts"]["event_title"] == "2026 Live Election"
    assert context["candidate_facts"]["event_category"] == "Politics"
    assert context["candidate_facts"]["event_end_time"] == "2026-11-04T05:00:00Z"
    assert (
        context["candidate_facts"]["market_question"] == "Will Candidate A win in the live board?"
    )
    assert context["candidate_facts"]["outcome_name"] == "Candidate A"
    assert context["candidate_facts"]["family_summary"]["sibling_count"] == 1
    assert context["candidate_facts"]["family_summary"]["sibling_markets"][0]["market_id"] == (
        "mkt-live-degraded"
    )
    assert context["candidate_facts"]["family_summary"]["structural_flag_count"] == 0
    assert context["executable_fields"]["best_bid_cents"] == 49.0
    assert context["executable_fields"]["best_ask_cents"] == 51.0
    assert context["executable_fields"]["mid_cents"] == 50.0
    assert context["executable_fields"]["last_price_cents"] == 50.5
    assert context["executable_fields"]["max_entry_cents"] == 51.0
    assert context["candidate_facts"]["ranking_summary"]["supported_runtime_domain"] is True
    assert context["candidate_facts"]["ranking_summary"]["family_sibling_count"] == 1
    assert context["candidate_facts"]["ranking_summary"]["family_structural_signal_score"] == 0
    evidence_ids = {item["source_id"] for item in context["evidence"]}
    assert {"news-candidate-a-1", "news-candidate-a-2", "x-candidate-a"} <= evidence_ids
    assert "news-unrelated" not in evidence_ids
    assert "x-unrelated" not in evidence_ids


def test_scan_command_applies_semantic_relevance_before_final_judgment(tmp_path, monkeypatch):
    data_dir = tmp_path / ".runtime-data"
    payload_log = tmp_path / "semantic-payload-log.jsonl"
    news_feed = tmp_path / "news-feed.json"
    x_feed = tmp_path / "x-feed.json"
    news_feed.write_text(
        json.dumps(
            [
                {
                    "source_id": "news-candidate-a-1",
                    "url": "https://news.example.test/candidate-a-1",
                    "claim_snippet": "Candidate A still has no certified result.",
                    "tier": "primary",
                },
                {
                    "source_id": "news-candidate-a-2",
                    "url": "https://news.example.test/candidate-a-2",
                    "claim_snippet": "Candidate A recount speculation continues.",
                    "tier": "primary",
                },
            ]
        ),
        encoding="utf-8",
    )
    x_feed.write_text(
        json.dumps(
            [
                {
                    "source_id": "x-candidate-a",
                    "handle": "@polymarket",
                    "url": "https://x.com/polymarket/status/1",
                    "claim_snippet": "Candidate A market repricing after election desk chatter.",
                }
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(data_dir))
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_ENABLE_SCAN", "1")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DISABLE_TELEGRAM", "1")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_TELEGRAM_CHAT_ID", "-100123456")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_SCAN_MAX_JUDGMENT_CANDIDATES", "1")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_NEWS_FEED_URL", str(news_feed))
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_X_FEED_URL", str(x_feed))
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_SEMANTIC_RELEVANCE_ENABLED", "1")
    monkeypatch.setenv(
        "POLYMARKET_ALERT_BOT_SEMANTIC_RELEVANCE_RUNNER_CMD",
        " ".join(
            [
                sys.executable,
                "-c",
                (
                    "import json,sys;"
                    "payload=json.load(sys.stdin);"
                    "json.dump({"
                    "'kept_source_ids':['news-candidate-a-1','x-candidate-a']"
                    "},sys.stdout)"
                ),
            ]
        ),
    )
    monkeypatch.setenv(
        "POLYMARKET_ALERT_BOT_JUDGMENT_RUNNER_CMD",
        " ".join(
            [
                sys.executable,
                "-c",
                (
                    "import json,sys,pathlib;"
                    "payload=json.load(sys.stdin);"
                    f"log_path=pathlib.Path({str(payload_log)!r});"
                    "handle=log_path.open('a',encoding='utf-8');"
                    "handle.write(json.dumps(payload['context']['evidence'])+'\\n');"
                    "handle.close();"
                    "json.dump({"
                    "'alert_kind':'research',"
                    "'cluster_action':'create',"
                    "'ttl_hours':6,"
                    "'summary':'semantic relevance check',"
                    "'watch_item':'keep watching',"
                    "'citations':[],"
                    "'triggers':[],"
                    "'archive_payload':{'summary':'semantic relevance check'}"
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

    monkeypatch.setattr(
        "polymarket_alert_bot.scanner.board_scan.fetch_events", lambda: gamma_payload
    )
    monkeypatch.setattr("polymarket_alert_bot.scanner.board_scan.fetch_book", _fake_fetch_book)

    assert main(["scan"]) == 0

    evidence_rows = [
        json.loads(line) for line in payload_log.read_text(encoding="utf-8").splitlines() if line
    ]
    assert len(evidence_rows) == 1
    assert {item["source_id"] for item in evidence_rows[0]} == {
        "news-candidate-a-1",
        "x-candidate-a",
    }
    assert "news-candidate-a-2" not in {item["source_id"] for item in evidence_rows[0]}


def test_scan_command_routes_strict_candidate_to_research_when_semantic_filter_removes_primary_support(
    tmp_path, monkeypatch
):
    data_dir = tmp_path / ".runtime-data"
    news_feed = tmp_path / "news-feed.json"
    x_feed = tmp_path / "x-feed.json"
    news_feed.write_text(
        json.dumps(
            [
                {
                    "source_id": "news-candidate-a-1",
                    "url": "https://news.example.test/candidate-a-1",
                    "claim_snippet": "Candidate A still has no certified result.",
                    "tier": "primary",
                },
                {
                    "source_id": "news-candidate-a-2",
                    "url": "https://news.example.test/candidate-a-2",
                    "claim_snippet": "Election desk says certification is still pending for Candidate A.",
                    "tier": "primary",
                },
            ]
        ),
        encoding="utf-8",
    )
    x_feed.write_text(
        json.dumps(
            [
                {
                    "source_id": "x-candidate-a",
                    "handle": "@polymarket",
                    "url": "https://x.com/polymarket/status/1",
                    "claim_snippet": "Candidate A market repricing after election desk chatter.",
                }
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(data_dir))
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_ENABLE_SCAN", "1")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DISABLE_TELEGRAM", "1")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_TELEGRAM_CHAT_ID", "-100123456")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_SCAN_MAX_JUDGMENT_CANDIDATES", "1")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_NEWS_FEED_URL", str(news_feed))
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_X_FEED_URL", str(x_feed))
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_SEMANTIC_RELEVANCE_ENABLED", "1")
    monkeypatch.setenv(
        "POLYMARKET_ALERT_BOT_SEMANTIC_RELEVANCE_RUNNER_CMD",
        " ".join(
            [
                sys.executable,
                "-c",
                (
                    "import json,sys;"
                    "payload=json.load(sys.stdin);"
                    "json.dump({"
                    "'kept_source_ids':['news-candidate-a-1'],"
                    "'items':["
                    "{'source_id':'news-candidate-a-1','relevance':'settlement relevant'},"
                    "{'source_id':'news-candidate-a-2','relevance':'settlement relevant'}"
                    "]"
                    "},sys.stdout)"
                ),
            ]
        ),
    )
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
                    "'thesis':'still strict absent semantic filter',"
                    "'side':'NO',"
                    "'theoretical_edge_cents':14.0,"
                    "'executable_edge_cents':10.0,"
                    "'max_entry_cents':43.0,"
                    "'suggested_size_usdc':200.0,"
                    "'why_now':'strict before deterministic gate',"
                    "'kill_criteria_text':'official certification',"
                    "'summary':'semantic strict gate check',"
                    "'watch_item':'watch certification',"
                    "'citations':[],"
                    "'triggers':[],"
                    "'archive_payload':{'summary':'semantic strict gate check'}"
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

    monkeypatch.setattr(
        "polymarket_alert_bot.scanner.board_scan.fetch_events", lambda: gamma_payload
    )
    monkeypatch.setattr("polymarket_alert_bot.scanner.board_scan.fetch_book", _fake_fetch_book)

    assert main(["scan"]) == 0

    conn = connect_db(data_dir / "sqlite" / "runtime.sqlite3")
    alert_row = conn.execute(
        """
        SELECT alert_kind
        FROM alerts
        WHERE run_id = (
            SELECT id FROM runs WHERE run_type = 'scan' ORDER BY created_at DESC LIMIT 1
        )
          AND market_id = 'mkt-live-tradable'
        """
    ).fetchone()
    assert alert_row["alert_kind"] == "research"

    run_row = conn.execute(
        """
        SELECT status, degraded_reason
        FROM runs
        WHERE run_type = 'scan'
        ORDER BY created_at DESC
        LIMIT 1
        """
    ).fetchone()
    assert run_row["status"] == "clean"
    assert run_row["degraded_reason"] is None


def test_scan_command_falls_back_to_lexical_bundle_when_semantic_relevance_fails(
    tmp_path, monkeypatch
):
    data_dir = tmp_path / ".runtime-data"
    payload_log = tmp_path / "semantic-fallback-log.jsonl"
    news_feed = tmp_path / "news-feed.json"
    x_feed = tmp_path / "x-feed.json"
    news_feed.write_text(
        json.dumps(
            [
                {
                    "source_id": "news-candidate-a-1",
                    "url": "https://news.example.test/candidate-a-1",
                    "claim_snippet": "Candidate A still has no certified result.",
                    "tier": "primary",
                },
                {
                    "source_id": "news-candidate-a-2",
                    "url": "https://news.example.test/candidate-a-2",
                    "claim_snippet": "Candidate A recount speculation continues.",
                    "tier": "primary",
                },
            ]
        ),
        encoding="utf-8",
    )
    x_feed.write_text(
        json.dumps(
            [
                {
                    "source_id": "x-candidate-a",
                    "handle": "@polymarket",
                    "url": "https://x.com/polymarket/status/1",
                    "claim_snippet": "Candidate A market repricing after election desk chatter.",
                }
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(data_dir))
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_ENABLE_SCAN", "1")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DISABLE_TELEGRAM", "1")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_TELEGRAM_CHAT_ID", "-100123456")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_SCAN_MAX_JUDGMENT_CANDIDATES", "1")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_NEWS_FEED_URL", str(news_feed))
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_X_FEED_URL", str(x_feed))
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_SEMANTIC_RELEVANCE_ENABLED", "1")
    monkeypatch.setenv(
        "POLYMARKET_ALERT_BOT_SEMANTIC_RELEVANCE_RUNNER_CMD",
        " ".join(
            [
                sys.executable,
                "-c",
                "import sys;sys.exit(1)",
            ]
        ),
    )
    monkeypatch.setenv(
        "POLYMARKET_ALERT_BOT_JUDGMENT_RUNNER_CMD",
        " ".join(
            [
                sys.executable,
                "-c",
                (
                    "import json,sys,pathlib;"
                    "payload=json.load(sys.stdin);"
                    f"log_path=pathlib.Path({str(payload_log)!r});"
                    "handle=log_path.open('a',encoding='utf-8');"
                    "handle.write(json.dumps(payload['context']['evidence'])+'\\n');"
                    "handle.close();"
                    "json.dump({"
                    "'alert_kind':'research',"
                    "'cluster_action':'create',"
                    "'ttl_hours':6,"
                    "'summary':'semantic fallback check',"
                    "'watch_item':'keep watching',"
                    "'citations':[],"
                    "'triggers':[],"
                    "'archive_payload':{'summary':'semantic fallback check'}"
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

    monkeypatch.setattr(
        "polymarket_alert_bot.scanner.board_scan.fetch_events", lambda: gamma_payload
    )
    monkeypatch.setattr("polymarket_alert_bot.scanner.board_scan.fetch_book", _fake_fetch_book)

    assert main(["scan"]) == 0

    evidence_rows = [
        json.loads(line) for line in payload_log.read_text(encoding="utf-8").splitlines() if line
    ]
    assert len(evidence_rows) == 1
    assert {item["source_id"] for item in evidence_rows[0]} == {
        "news-candidate-a-1",
        "news-candidate-a-2",
        "x-candidate-a",
    }

    conn = connect_db(data_dir / "sqlite" / "runtime.sqlite3")
    run_row = conn.execute(
        """
        SELECT status, degraded_reason
        FROM runs
        WHERE run_type = 'scan'
        ORDER BY created_at DESC
        LIMIT 1
        """
    ).fetchone()
    assert run_row["status"] == "degraded"
    assert "semantic_relevance_runner_failed" in run_row["degraded_reason"]


def test_scan_command_semantic_relevance_keeps_seeded_evidence_within_max_item_cap(
    tmp_path, monkeypatch
):
    data_dir = tmp_path / ".runtime-data"
    payload_log = tmp_path / "semantic-seeded-log.jsonl"
    news_feed = tmp_path / "seeded-news-feed.json"
    news_feed.write_text(
        json.dumps(
            [
                {
                    "source_id": "news-1",
                    "url": "https://news.example.test/1",
                    "claim_snippet": "Candidate A still has no certified result.",
                    "tier": "primary",
                },
                {
                    "source_id": "news-2",
                    "url": "https://news.example.test/2",
                    "claim_snippet": "Candidate A recount speculation continues.",
                    "tier": "primary",
                },
                {
                    "source_id": "news-3",
                    "url": "https://news.example.test/3",
                    "claim_snippet": "Election desk says certification is still pending for Candidate A.",
                    "tier": "primary",
                },
                {
                    "source_id": "news-4",
                    "url": "https://news.example.test/4",
                    "claim_snippet": "Candidate A legal challenge remains unresolved.",
                    "tier": "primary",
                },
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(data_dir))
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_ENABLE_SCAN", "1")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DISABLE_TELEGRAM", "1")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_TELEGRAM_CHAT_ID", "-100123456")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_SCAN_MAX_JUDGMENT_CANDIDATES", "1")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_NEWS_FEED_URL", str(news_feed))
    monkeypatch.delenv("POLYMARKET_ALERT_BOT_NEWS_SAMPLES_PATH", raising=False)
    monkeypatch.delenv("POLYMARKET_ALERT_BOT_X_FEED_URL", raising=False)
    monkeypatch.delenv("POLYMARKET_ALERT_BOT_X_SAMPLES_PATH", raising=False)
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_SEMANTIC_RELEVANCE_ENABLED", "1")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_SEMANTIC_RELEVANCE_MAX_ITEMS", "4")
    monkeypatch.setenv(
        "POLYMARKET_ALERT_BOT_SEMANTIC_RELEVANCE_RUNNER_CMD",
        " ".join(
            [
                sys.executable,
                "-c",
                (
                    "import json,sys;"
                    "payload=json.load(sys.stdin);"
                    "source_ids=[item['source_id'] for item in payload['context']['evidence']];"
                    "json.dump({'kept_source_ids':source_ids},sys.stdout)"
                ),
            ]
        ),
    )
    monkeypatch.setenv(
        "POLYMARKET_ALERT_BOT_JUDGMENT_RUNNER_CMD",
        " ".join(
            [
                sys.executable,
                "-c",
                (
                    "import json,sys,pathlib;"
                    "payload=json.load(sys.stdin);"
                    f"log_path=pathlib.Path({str(payload_log)!r});"
                    "handle=log_path.open('a',encoding='utf-8');"
                    "handle.write(json.dumps(payload['context']['evidence'])+'\\n');"
                    "handle.close();"
                    "json.dump({"
                    "'alert_kind':'research',"
                    "'cluster_action':'create',"
                    "'ttl_hours':6,"
                    "'summary':'semantic seeded evidence check',"
                    "'watch_item':'keep watching',"
                    "'citations':[],"
                    "'triggers':[],"
                    "'archive_payload':{'summary':'semantic seeded evidence check'}"
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

    def _run_scan_with_seeded_evidence(paths, *, max_judgment_candidates):
        return board_run_scan(
            paths,
            max_judgment_candidates=max_judgment_candidates,
            evidence_seed_inputs={
                "cond-live-a": [
                    {
                        "source_id": "seeded-evidence",
                        "source_kind": "news",
                        "url": "https://seed.example.test/1",
                        "claim_snippet": "Operator seeded Candidate A evidence.",
                        "tier": "primary",
                    }
                ]
            },
        )

    monkeypatch.setattr(
        "polymarket_alert_bot.scanner.board_scan.fetch_events", lambda: gamma_payload
    )
    monkeypatch.setattr("polymarket_alert_bot.scanner.board_scan.fetch_book", _fake_fetch_book)
    monkeypatch.setattr("polymarket_alert_bot.flows.scan.run_scan", _run_scan_with_seeded_evidence)
    monkeypatch.setattr(
        "polymarket_alert_bot.flows.scan.retrieve_shortlist_evidence",
        lambda seed, config, registry: ShortlistRetrievalResult(
            items=tuple(
                EvidenceItem(
                    source_id=f"retrieved-{index}",
                    source_kind="x",
                    fetched_at=f"2026-04-22T01:1{index}:00Z",
                    url=f"https://x.com/example/status/{index}",
                    claim_snippet=f"Candidate A market chatter update {index}.",
                    tier="supplementary",
                )
                for index in range(4)
            ),
            degraded_reasons=(),
        ),
    )

    assert main(["scan"]) == 0

    evidence_rows = [
        json.loads(line) for line in payload_log.read_text(encoding="utf-8").splitlines() if line
    ]
    assert len(evidence_rows) == 1
    assert "seeded-evidence" in {item["source_id"] for item in evidence_rows[0]}


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

    monkeypatch.setattr(
        "polymarket_alert_bot.scanner.board_scan.fetch_events", lambda: gamma_payload
    )
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


def test_scan_command_dedupes_repeated_runs_into_the_same_alert_rows(tmp_path, monkeypatch):
    data_dir = tmp_path / ".runtime-data"
    news_feed, x_feed = _write_live_election_candidate_feeds(tmp_path)
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(data_dir))
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_ENABLE_SCAN", "1")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DISABLE_TELEGRAM", "1")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_TELEGRAM_CHAT_ID", "-100123456")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_NEWS_FEED_URL", str(news_feed))
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_X_FEED_URL", str(x_feed))
    monkeypatch.delenv("POLYMARKET_ALERT_BOT_NEWS_SAMPLES_PATH", raising=False)
    monkeypatch.delenv("POLYMARKET_ALERT_BOT_X_SAMPLES_PATH", raising=False)
    monkeypatch.setenv(
        "POLYMARKET_ALERT_BOT_JUDGMENT_RUNNER_CMD",
        " ".join(
            [
                sys.executable,
                "-c",
                (
                    "import json,sys;"
                    "payload=json.load(sys.stdin);"
                    "rules_text=payload['context'].get('rules_text','');"
                    "response={"
                    "'alert_kind':'strict',"
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

    monkeypatch.setattr(
        "polymarket_alert_bot.scanner.board_scan.fetch_events", lambda: gamma_payload
    )
    monkeypatch.setattr("polymarket_alert_bot.scanner.board_scan.fetch_book", _fake_fetch_book)

    assert main(["scan"]) == 0
    assert main(["scan"]) == 0

    conn = connect_db(data_dir / "sqlite" / "runtime.sqlite3")
    alert_rows = conn.execute(
        """
        SELECT id, alert_kind, market_id, dedupe_key
        FROM alerts
        ORDER BY market_id
        """
    ).fetchall()
    assert len(alert_rows) == 2
    assert [(row["alert_kind"], row["market_id"]) for row in alert_rows] == [
        ("strict_degraded", "mkt-live-degraded"),
        ("strict", "mkt-live-tradable"),
    ]
    assert all(row["dedupe_key"].startswith("scanner-seed::") for row in alert_rows)

    claim_mapping_count = conn.execute("SELECT COUNT(*) FROM claim_source_mappings").fetchone()[0]
    trigger_count = conn.execute("SELECT COUNT(*) FROM triggers").fetchone()[0]
    run_count = conn.execute("SELECT COUNT(*) FROM runs WHERE run_type = 'scan'").fetchone()[0]
    assert claim_mapping_count == 2
    assert trigger_count == 2
    assert run_count == 2


def test_scan_command_marks_run_degraded_when_shortlist_retrieval_fails(tmp_path, monkeypatch):
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
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_SCAN_MAX_JUDGMENT_CANDIDATES", "1")
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
                    "'thesis':'shortlist degrade check',"
                    "'side':'NO',"
                    "'theoretical_edge_cents':12.0,"
                    "'executable_edge_cents':9.0,"
                    "'max_entry_cents':43.0,"
                    "'suggested_size_usdc':100.0,"
                    "'why_now':'shortlist retrieval degraded',"
                    "'kill_criteria_text':'official confirmation',"
                    "'summary':'summary',"
                    "'watch_item':'watch',"
                    "'citations':[{'claim':'Reuters confirms update.','source':{'id':'reuters','name':'Reuters','url':'https://www.reuters.com/test','tier':'primary','fetched_at':'2026-04-17T12:00:00Z'}},{'claim':'AP confirms update.','source':{'id':'ap','name':'AP','url':'https://apnews.com/test','tier':'primary','fetched_at':'2026-04-17T12:05:00Z'}}],"
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

    monkeypatch.setattr(
        "polymarket_alert_bot.scanner.board_scan.fetch_events", lambda: gamma_payload
    )
    monkeypatch.setattr("polymarket_alert_bot.scanner.board_scan.fetch_book", _fake_fetch_book)
    monkeypatch.setattr(
        "polymarket_alert_bot.flows.scan.retrieve_shortlist_evidence",
        lambda seed, config, registry: ShortlistRetrievalResult(
            items=(),
            degraded_reasons=("shortlist_x_failed:TimeoutError",),
        ),
    )

    assert main(["scan"]) == 0

    conn = connect_db(data_dir / "sqlite" / "runtime.sqlite3")
    run_row = conn.execute(
        """
        SELECT status, degraded_reason, retrieved_shortlist_candidates
        FROM runs
        WHERE run_type = 'scan'
        ORDER BY created_at DESC
        LIMIT 1
        """
    ).fetchone()
    assert dict(run_row) == {
        "status": "degraded",
        "degraded_reason": "shortlist_x_failed:TimeoutError",
        "retrieved_shortlist_candidates": 0,
    }
    alert_row = conn.execute(
        """
        SELECT alert_kind
        FROM alerts
        WHERE run_id = (
            SELECT id FROM runs WHERE run_type = 'scan' ORDER BY created_at DESC LIMIT 1
        )
          AND market_id = 'mkt-live-tradable'
        """
    ).fetchone()
    assert alert_row["alert_kind"] == "research"


def test_scan_command_does_not_let_unrelated_configured_evidence_unlock_strict_gate(
    tmp_path, monkeypatch
):
    data_dir = tmp_path / ".runtime-data"
    news_feed = tmp_path / "news-feed.json"
    payload_log = tmp_path / "unrelated-evidence-log.jsonl"
    news_feed.write_text(
        json.dumps(
            [
                {
                    "source_id": "news-unrelated-1",
                    "url": "https://news.example.test/unrelated-1",
                    "claim_snippet": "Oil inventories rose overnight.",
                    "tier": "primary",
                },
                {
                    "source_id": "news-unrelated-2",
                    "url": "https://news.example.test/unrelated-2",
                    "claim_snippet": "Snowstorm expected next week.",
                    "tier": "primary",
                },
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(data_dir))
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_ENABLE_SCAN", "1")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DISABLE_TELEGRAM", "1")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_TELEGRAM_CHAT_ID", "-100123456")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_SCAN_MAX_JUDGMENT_CANDIDATES", "1")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_NEWS_FEED_URL", str(news_feed))
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
                    "import json,sys,pathlib;"
                    "payload=json.load(sys.stdin);"
                    f"log_path=pathlib.Path({str(payload_log)!r});"
                    "handle=log_path.open('a',encoding='utf-8');"
                    "handle.write(json.dumps(payload['context']['evidence'])+'\\n');"
                    "handle.close();"
                    "json.dump({"
                    "'alert_kind':'strict',"
                    "'cluster_action':'create',"
                    "'ttl_hours':6,"
                    "'thesis':'should downgrade when no relevant support exists',"
                    "'side':'NO',"
                    "'theoretical_edge_cents':12.0,"
                    "'executable_edge_cents':9.0,"
                    "'max_entry_cents':43.0,"
                    "'suggested_size_usdc':100.0,"
                    "'why_now':'strict gate should block unrelated configured evidence',"
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

    monkeypatch.setattr(
        "polymarket_alert_bot.scanner.board_scan.fetch_events", lambda: gamma_payload
    )
    monkeypatch.setattr("polymarket_alert_bot.scanner.board_scan.fetch_book", _fake_fetch_book)
    monkeypatch.setattr(
        "polymarket_alert_bot.flows.scan.retrieve_shortlist_evidence",
        lambda seed, config, registry: ShortlistRetrievalResult(
            items=(),
            degraded_reasons=(),
        ),
    )

    assert main(["scan"]) == 0

    payload_rows = [
        json.loads(line) for line in payload_log.read_text(encoding="utf-8").splitlines() if line
    ]
    assert len(payload_rows) == 1
    assert payload_rows[0] == []

    conn = connect_db(data_dir / "sqlite" / "runtime.sqlite3")
    alert_row = conn.execute(
        """
        SELECT alert_kind
        FROM alerts
        WHERE run_id = (
            SELECT id FROM runs WHERE run_type = 'scan' ORDER BY created_at DESC LIMIT 1
        )
          AND market_id = 'mkt-live-tradable'
        """
    ).fetchone()
    assert alert_row["alert_kind"] == "research"


def test_scan_command_marks_heartbeat_degraded_when_shortlist_retrieval_fails(
    tmp_path, monkeypatch
):
    data_dir = tmp_path / ".runtime-data"
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(data_dir))
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_ENABLE_SCAN", "1")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DISABLE_TELEGRAM", "1")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_TELEGRAM_CHAT_ID", "-100123456")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_SCAN_MAX_JUDGMENT_CANDIDATES", "1")
    monkeypatch.setenv(
        "POLYMARKET_ALERT_BOT_JUDGMENT_RUNNER_CMD",
        " ".join(
            [
                sys.executable,
                "-c",
                (
                    "import json,sys;"
                    "json.dump({"
                    "'alert_kind':'research',"
                    "'cluster_action':'create',"
                    "'ttl_hours':6,"
                    "'summary':'heartbeat degrade check',"
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

    monkeypatch.setattr(
        "polymarket_alert_bot.scanner.board_scan.fetch_events", lambda: gamma_payload
    )
    monkeypatch.setattr("polymarket_alert_bot.scanner.board_scan.fetch_book", _fake_fetch_book)
    monkeypatch.setattr(
        "polymarket_alert_bot.flows.scan.retrieve_shortlist_evidence",
        lambda seed, config, registry: ShortlistRetrievalResult(
            items=(),
            degraded_reasons=("shortlist_x_failed:TimeoutError",),
        ),
    )

    assert main(["scan"]) == 0

    conn = connect_db(data_dir / "sqlite" / "runtime.sqlite3")
    run_id = conn.execute(
        "SELECT id FROM runs WHERE run_type = 'scan' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()["id"]
    heartbeat_row = conn.execute(
        """
        SELECT archive_path
        FROM alerts
        WHERE run_id = ? AND alert_kind = 'heartbeat'
        """,
        [run_id],
    ).fetchone()
    assert heartbeat_row is not None
    heartbeat_text = Path(heartbeat_row["archive_path"]).read_text(encoding="utf-8")
    assert heartbeat_text.startswith("[DEGRADED]")
    assert "events/contracts/shortlist/retrieved/promoted: 1/2/2/0/1" in heartbeat_text
    assert "families/flagged families/flagged candidates: 1/0/0" in heartbeat_text
    assert "shortlist_x_failed:TimeoutError" in heartbeat_text


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
    monkeypatch.setattr(
        "polymarket_alert_bot.flows.monitor.run_monitor", lambda *args, **kwargs: monitor_outcome
    )

    delivered_messages: list[str] = []

    def _capture_deliver(*, text, **kwargs):
        delivered_messages.append(text)
        return None

    monkeypatch.setattr("polymarket_alert_bot.flows.monitor._deliver_message", _capture_deliver)

    summary = execute_monitor_flow(paths)

    assert summary.delivered_alert_ids == ()
    assert delivered_messages == []
    assert recheck_log.exists()
    payload_rows = [
        json.loads(line) for line in recheck_log.read_text(encoding="utf-8").splitlines()
    ]
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
    monkeypatch.setattr(
        "polymarket_alert_bot.flows.monitor.run_monitor", lambda *args, **kwargs: monitor_outcome
    )

    delivered_messages: list[str] = []

    def _capture_deliver(*, text, **kwargs):
        delivered_messages.append(text)
        return None

    monkeypatch.setattr("polymarket_alert_bot.flows.monitor._deliver_message", _capture_deliver)

    summary = execute_monitor_flow(paths)

    assert len(summary.delivered_alert_ids) == 1
    assert len(delivered_messages) == 1
    assert (
        "market: https://polymarket.com/event/source-event/source-market" in delivered_messages[0]
    )
    assert recheck_log.exists()
    payload_rows = [
        json.loads(line) for line in recheck_log.read_text(encoding="utf-8").splitlines()
    ]
    assert len(payload_rows) == 1
    assert (
        payload_rows[0]["context"]["candidate_facts"]["trigger_id"] == "trigger-narrative-approved"
    )

    conn = connect_db(paths.db_path)
    monitor_alert_rows = conn.execute(
        "SELECT alert_kind, delivery_mode, market_id FROM alerts WHERE run_id = ?",
        ["run-monitor-test-approve"],
    ).fetchall()
    assert [
        (row["alert_kind"], row["delivery_mode"], row["market_id"]) for row in monitor_alert_rows
    ] == [("monitor", "immediate", "market-source")]
