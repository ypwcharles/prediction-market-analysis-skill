from __future__ import annotations

import json
from pathlib import Path

from polymarket_alert_bot.scanner.board_scan import scan_board


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

    rejected_reasons = {candidate.market_id: reason for candidate, reason in outcome.rejected}
    assert rejected_reasons == {
        "mkt-low-liq": "low_liquidity",
        "mkt-duplicate": "duplicate_expression",
    }
