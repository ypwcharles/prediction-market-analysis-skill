from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from polymarket_alert_bot.config.source_registry import load_source_registry
from polymarket_alert_bot.judgment.result_parser import ParseError, parse_judgment_result
from polymarket_alert_bot.judgment.skill_adapter import SkillAdapter
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


def test_parse_judgment_result_supports_claim_aware_citation_and_rich_trigger_metadata() -> None:
    payload = {
        "alert_kind": "monitor",
        "cluster_action": "update",
        "ttl_hours": 3,
        "citations": [
            {
                "claim": "Primary desk says there is no confirmed strike order.",
                "source": {
                    "id": "reuters_002",
                    "name": "Reuters",
                    "url": "https://example.com/reuters-2",
                    "tier": "primary",
                    "fetched_at": "2026-04-17T11:00:00Z",
                },
            }
        ],
        "triggers": [
            {
                "trigger_type": "price_reprice",
                "trigger_state": "fired",
                "observation": "YES touched 0.61",
                "suggested_action": "Pause adds until thesis is rechecked.",
            }
        ],
        "archive_payload": {
            "summary": "monitor trigger fired",
            "message_refs": [{"chat_id": "-100123", "message_id": "45"}],
            "trigger_payload": {"condition": "yes>=0.61"},
        },
    }

    parsed = parse_judgment_result(payload)

    assert parsed.citations[0].source_id == "reuters_002"
    assert parsed.citations[0].url == "https://example.com/reuters-2"
    assert parsed.triggers[0].kind == "price_reprice"
    assert parsed.triggers[0].trigger_state == "fired"
    assert parsed.archive_payload["message_refs"][0]["message_id"] == "45"
    assert parsed.archive_payload["trigger_payload"]["condition"] == "yes>=0.61"


def test_skill_adapter_external_command_runner_success() -> None:
    command = [
        sys.executable,
        "-c",
        (
            "import json,sys;"
            "payload=json.load(sys.stdin);"
            "response={"
            "'alert_kind':'monitor',"
            "'cluster_action':'update',"
            "'ttl_hours':2,"
            "'citations':[{'source_id':'wire_1','url':'https://example.com','claim':'confirmed'}],"
            "'triggers':[{'kind':'price','condition':'yes>=0.61'}],"
            "'archive_payload':{'echo_contract':payload.get('contract_version')}};"
            "json.dump(response,sys.stdout)"
        ),
    ]
    adapter = SkillAdapter(external_command=command, timeout_seconds=2)

    parsed = adapter.judge({"candidate_facts": {"market_id": "m1"}})

    assert parsed.alert_kind == "monitor"
    assert parsed.cluster_action == "update"
    assert parsed.archive_payload["echo_contract"] == "runtime.v1"


def test_skill_adapter_degrades_when_no_runner_is_configured() -> None:
    adapter = SkillAdapter()

    parsed = adapter.judge({"candidate_facts": {"market_id": "m1"}})

    assert parsed.alert_kind == "degraded"
    assert parsed.archive_payload["reason"] == "runner_not_configured"


def test_parse_judgment_result_preserves_runtime_alert_fields() -> None:
    payload = {
        "alert_kind": "strict",
        "cluster_action": "create",
        "ttl_hours": 6,
        "thesis": "Diplomatic channel remains open, rumor premium should mean-revert.",
        "side": "NO",
        "theoretical_edge_cents": 14.2,
        "executable_edge_cents": 10.5,
        "max_entry_cents": 43.0,
        "suggested_size_usdc": 250.0,
        "why_now": "No official confirmation despite headline spike.",
        "kill_criteria_text": "Official confirmation or rule-scope shift.",
        "summary": "Desk summary",
        "watch_item": "Need second primary confirmation",
        "evidence_fresh_until": "2026-04-18T12:00:00Z",
        "recheck_required_at": "2026-04-18T06:00:00Z",
        "citations": [],
        "triggers": [],
        "archive_payload": {},
    }

    parsed = parse_judgment_result(payload)

    assert parsed.thesis == payload["thesis"]
    assert parsed.side == payload["side"]
    assert parsed.theoretical_edge_cents == payload["theoretical_edge_cents"]
    assert parsed.executable_edge_cents == payload["executable_edge_cents"]
    assert parsed.max_entry_cents == payload["max_entry_cents"]
    assert parsed.suggested_size_usdc == payload["suggested_size_usdc"]
    assert parsed.why_now == payload["why_now"]
    assert parsed.kill_criteria_text == payload["kill_criteria_text"]
    assert parsed.summary == payload["summary"]
    assert parsed.watch_item == payload["watch_item"]
    assert parsed.evidence_fresh_until == payload["evidence_fresh_until"]
    assert parsed.recheck_required_at == payload["recheck_required_at"]


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


def test_enricher_does_not_treat_unlisted_news_domain_as_primary() -> None:
    source_registry = load_source_registry("runtime/config/sources.toml")
    news_items = NewsClient().normalize_items(
        [
            {
                "source_id": "unknown_news_1",
                "url": "https://example-news.invalid/story",
                "claim_snippet": "Unlisted local outlet says deal is done.",
                "tier": "",
            }
        ]
    )

    enriched = enrich_evidence(news_items, source_registry)

    assert enriched.primary_support_count == 0
    assert enriched.unknown_count == 1
    assert enriched.strict_allowed is False
    assert enriched.strict_block_reason == "no_primary_evidence"
