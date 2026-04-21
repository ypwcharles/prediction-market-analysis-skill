from __future__ import annotations

import json
from pathlib import Path

from polymarket_alert_bot.judgment.contract import (
    ALERT_KINDS,
    CLUSTER_ACTIONS,
    RECOMMENDED_TOP_LEVEL_FIELDS,
    REQUIRED_TOP_LEVEL_FIELDS,
    runtime_response_schema,
)
from polymarket_alert_bot.judgment.skill_adapter import SkillAdapter

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_skill_adapter_uses_canonical_runtime_schema() -> None:
    adapter = SkillAdapter()

    payload = adapter.build_payload({"candidate_facts": {"market_id": "m1"}})

    assert payload["response_schema"] == runtime_response_schema()


def test_eval_runtime_payloads_match_canonical_runtime_schema() -> None:
    expected_schema = runtime_response_schema()
    fixture_paths = (
        REPO_ROOT / "evals" / "runtime-v1-scan-payload.json",
        REPO_ROOT / "evals" / "runtime-v1-monitor-payload.json",
    )

    for fixture_path in fixture_paths:
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        assert payload["response_schema"] == expected_schema, fixture_path.name


def test_runtime_contract_reference_tracks_canonical_fields_and_enums() -> None:
    contract_doc = (
        REPO_ROOT
        / "skills"
        / "prediction-market-analysis"
        / "references"
        / "runtime-judgment-contract.md"
    ).read_text(encoding="utf-8")

    assert "runtime/src/polymarket_alert_bot/judgment/contract.py" in contract_doc
    for field_name in REQUIRED_TOP_LEVEL_FIELDS:
        assert f"`{field_name}`" in contract_doc
    for field_name in RECOMMENDED_TOP_LEVEL_FIELDS:
        assert f"`{field_name}`" in contract_doc
    for alert_kind in ALERT_KINDS:
        assert f"`{alert_kind}`" in contract_doc
    for cluster_action in CLUSTER_ACTIONS:
        assert f"`{cluster_action}`" in contract_doc


def test_skill_doc_marks_runtime_contract_reference_as_canonical() -> None:
    skill_doc = (REPO_ROOT / "skills" / "prediction-market-analysis" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    assert "references/runtime-judgment-contract.md" in skill_doc
    assert "Do not treat this skill file as a second schema definition." in skill_doc
