from __future__ import annotations

import json
from pathlib import Path

from polymarket_alert_bot.config.settings import ensure_runtime_dirs, load_runtime_paths
from polymarket_alert_bot.scanner.board_scan import run_scan, scan_board
from polymarket_alert_bot.scanner.clob_client import BookSnapshot, degraded_snapshot
from polymarket_alert_bot.storage.db import connect_db

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _read_json(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_scan_pipeline_prefilters_and_coverage_accounting():
    gamma_payload = _read_json("gamma_board.json")
    clob_payload = _read_json("clob_books.json")

    outcome = scan_board(gamma_payload, clob_payload)

    assert outcome.coverage.total_events == 2
    assert outcome.coverage.total_markets == 4
    assert outcome.coverage.total_candidates == 4
    assert outcome.coverage.tradable_candidates == 1
    assert outcome.coverage.rejected_low_liquidity == 1
    assert outcome.coverage.rejected_duplicate == 1
    assert outcome.coverage.degraded_books == 1
    assert outcome.coverage.skipped == 3

    assert [candidate.market_id for candidate in outcome.tradable] == ["mkt-tradable"]
    assert [candidate.market_id for candidate in outcome.degraded] == ["mkt-degraded"]
    assert outcome.tradable[0].condition_id == "cond-election-a"
    assert outcome.degraded[0].condition_id == "cond-fed-may"
    assert (
        outcome.tradable[0].expression_key
        == "event-election::will candidate a win the 2026 election?"
    )

    rejected_reasons = {candidate.market_id: reason for candidate, reason in outcome.rejected}
    assert rejected_reasons == {
        "mkt-low-liq": "low_liquidity",
        "mkt-duplicate": "duplicate_expression",
    }


def test_run_scan_live_orchestration_persists_seed_alerts(monkeypatch, tmp_path):
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(tmp_path / ".runtime-data"))
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_ENABLE_SCAN", "1")
    paths = load_runtime_paths()
    ensure_runtime_dirs(paths)

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

    result = run_scan(
        paths,
        judgment_seed_inputs={
            "cond-live-a": {"thesis": "candidate-a-momentum"},
        },
        evidence_seed_inputs={
            "cond-live-a": [{"source": "x", "url": "https://example.com/x"}],
            "cond-live-b": [{"source": "news", "url": "https://example.com/news"}],
        },
    )

    assert result.outcome.coverage.total_events == 1
    assert result.outcome.coverage.total_markets == 2
    assert result.outcome.coverage.total_candidates == 2
    assert [seed.market_id for seed in result.alert_seeds] == [
        "mkt-live-tradable",
        "mkt-live-degraded",
    ]
    assert [seed.event_slug for seed in result.alert_seeds] == [
        "live-election-2026",
        "live-election-2026",
    ]
    assert [seed.market_slug for seed in result.alert_seeds] == [
        "candidate-a-wins-live",
        "candidate-b-wins-live",
    ]
    assert [seed.market_link for seed in result.alert_seeds] == [
        "https://polymarket.com/event/live-election-2026/candidate-a-wins-live",
        "https://polymarket.com/event/live-election-2026/candidate-b-wins-live",
    ]
    assert result.alert_seeds[0].judgment_seed == {"thesis": "candidate-a-momentum"}
    assert result.alert_seeds[1].judgment_seed is None
    assert result.alert_seeds[1].evidence_seeds == (
        {"source": "news", "url": "https://example.com/news"},
    )

    conn = connect_db(paths.db_path)
    rows = conn.execute(
        """
        SELECT alert_kind, market_id, condition_id, status, dedupe_key
        FROM alerts
        ORDER BY market_id
        """
    ).fetchall()
    assert [
        (row["alert_kind"], row["market_id"], row["condition_id"], row["status"]) for row in rows
    ] == [
        ("scanner_seed_degraded", "mkt-live-degraded", "cond-live-b", "seeded"),
        ("scanner_seed", "mkt-live-tradable", "cond-live-a", "seeded"),
    ]
    assert rows[0]["dedupe_key"].startswith("scanner-seed::")
    run_row = conn.execute(
        "SELECT scanned_events, scanned_contracts FROM runs WHERE id = ?",
        [result.run_id],
    ).fetchone()
    assert dict(run_row) == {
        "scanned_events": result.outcome.coverage.total_markets,
        "scanned_contracts": result.outcome.coverage.total_candidates,
    }


def test_run_scan_live_uses_runtime_config_urls_and_limit(monkeypatch, tmp_path):
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(tmp_path / ".runtime-data"))
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_ENABLE_SCAN", "1")
    monkeypatch.setenv(
        "POLYMARKET_ALERT_BOT_GAMMA_EVENTS_URL", "https://gamma.example.test/markets"
    )
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_GAMMA_LIMIT", "77")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_CLOB_BOOK_URL", "https://clob.example.test/book")
    paths = load_runtime_paths()
    ensure_runtime_dirs(paths)

    gamma_payload = _read_json("gamma_live_board.json")
    observed_gamma_url: str | None = None
    observed_gamma_limit: int | None = None
    observed_book_calls: list[tuple[str, str]] = []

    def _fake_fetch_events(*, url: str, limit: int, active: bool = True, closed: bool = False):
        nonlocal observed_gamma_url, observed_gamma_limit
        observed_gamma_url = url
        observed_gamma_limit = limit
        assert active is True
        assert closed is False
        return gamma_payload

    def _fake_fetch_book(token_id: str, *, url: str) -> BookSnapshot:
        observed_book_calls.append((token_id, url))
        return degraded_snapshot(token_id, "book_fetch_error")

    monkeypatch.setattr("polymarket_alert_bot.scanner.board_scan.fetch_events", _fake_fetch_events)
    monkeypatch.setattr("polymarket_alert_bot.scanner.board_scan.fetch_book", _fake_fetch_book)

    result = run_scan(paths)

    assert observed_gamma_url == "https://gamma.example.test/markets"
    assert observed_gamma_limit == 77
    assert observed_book_calls == [
        ("token-live-tradable", "https://clob.example.test/book"),
        ("token-live-degraded", "https://clob.example.test/book"),
    ]
    assert result.status == "degraded"
    assert result.degraded_reason == "executable_checks_partial"
    assert result.outcome.coverage.degraded_books == 2


def test_run_scan_caps_judgment_candidates_by_priority(monkeypatch, tmp_path):
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(tmp_path / ".runtime-data"))
    paths = load_runtime_paths()
    ensure_runtime_dirs(paths)

    gamma_payload = [
        {
            "id": "event-1",
            "slug": "event-one",
            "description": "Event one",
            "markets": [
                {
                    "id": "market-low",
                    "slug": "market-low",
                    "question": "New celebrity album before GTA VI?",
                    "status": "open",
                    "active": True,
                    "conditionId": "cond-low",
                    "liquidity": 15000,
                    "token_id": "token-low",
                },
                {
                    "id": "market-high",
                    "slug": "market-high",
                    "question": "Will bitcoin hit $1m before GTA VI?",
                    "status": "open",
                    "active": True,
                    "conditionId": "cond-high",
                    "liquidity": 9000,
                    "token_id": "token-high",
                },
            ],
        }
    ]
    clob_payload = {
        "books": [
            {
                "token_id": "token-low",
                "bids": [{"price": "0.40"}],
                "asks": [{"price": "0.42"}],
            },
            {
                "token_id": "token-high",
                "bids": [{"price": "0.40"}],
                "asks": [{"price": "0.41"}],
            },
        ]
    }

    result = run_scan(
        paths,
        gamma_payload=gamma_payload,
        clob_payload=clob_payload,
        max_judgment_candidates=1,
    )

    assert len(result.alert_seeds) == 1
    assert result.alert_seeds[0].market_id == "market-high"

    assert result.alert_seeds[0].market_id == "market-high"
