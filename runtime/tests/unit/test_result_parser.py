from __future__ import annotations

import json
from pathlib import Path

import pytest

from polymarket_alert_bot.config.source_registry import load_source_registry
from polymarket_alert_bot.judgment.result_parser import ParseError, parse_judgment_result
from polymarket_alert_bot.sources.evidence_enricher import enrich_evidence
from polymarket_alert_bot.sources.news_client import NewsClient
from polymarket_alert_bot.sources.x_client import XClient


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def _load_fixture(name: str) -> list[dict[str, object]]:
    with (FIXTURES_DIR / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


@pytest.mark.parametrize("alert_kind", ["strict", "strict_degraded", "research"])
def test_parse_judgment_result_accepts_core_alert_kinds(alert_kind: str) -> None:
    payload = {
        "alert_kind": alert_kind,
        "cluster_action": "update",
        "ttl_hours": 6,
        "citations": [
            {
                "source_id": "reuters_001",
                "url": "https://www.reuters.com/world/example-news-1",
                "claim": "Talks resumed",
            }
        ],
        "triggers": [{"kind": "price", "condition": "yes<=0.42"}],
        "archive_payload": {"summary": "sample"},
    }

    parsed = parse_judgment_result(payload)

    assert parsed.alert_kind == alert_kind
    assert parsed.cluster_action == "update"
    assert parsed.ttl_hours == 6
    assert len(parsed.citations) == 1
    assert len(parsed.triggers) == 1


def test_parse_judgment_result_rejects_malformed_payload() -> None:
    malformed_payload = {
        "alert_kind": "invalid_kind",
        "cluster_action": "update",
        "ttl_hours": 1,
        "citations": [],
        "triggers": [],
        "archive_payload": {},
    }

    with pytest.raises(ParseError):
        parse_judgment_result(malformed_payload)


def test_enricher_blocks_strict_when_only_x_sources_present() -> None:
    source_registry = load_source_registry("runtime/config/sources.toml")
    x_items = XClient().normalize_items(_load_fixture("x_samples.json"))
    enriched = enrich_evidence(x_items, source_registry)

    assert enriched.primary_support_count == 0
    assert enriched.strict_allowed is False
    assert enriched.strict_block_reason == "no_primary_evidence"


def test_enricher_blocks_strict_when_primary_conflict_unresolved() -> None:
    source_registry = load_source_registry("runtime/config/sources.toml")
    news_items = NewsClient().normalize_items(_load_fixture("news_samples.json"))
    conflicted = []
    for item in news_items:
        conflicted.append(
            {
                "source_id": item.source_id,
                "source_kind": item.source_kind,
                "fetched_at": item.fetched_at,
                "url": item.url,
                "claim_snippet": item.claim_snippet,
                "tier": item.tier,
                "conflict_status": "conflicted",
            }
        )

    enriched = enrich_evidence(conflicted, source_registry)

    assert enriched.primary_support_count == 2
    assert enriched.unresolved_primary_conflict is True
    assert enriched.strict_allowed is False
    assert enriched.strict_block_reason == "unresolved_primary_conflict"
