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
        REPO_ROOT / "evals" / "runtime-v1-microstructure-payload.json",
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


def test_skill_doc_links_microstructure_reference() -> None:
    skill_doc = (REPO_ROOT / "skills" / "prediction-market-analysis" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    microstructure_doc = (
        REPO_ROOT
        / "skills"
        / "prediction-market-analysis"
        / "references"
        / "microstructure-models.md"
    ).read_text(encoding="utf-8")

    assert "references/microstructure-models.md" in skill_doc
    assert "Price history is evidence, not verdict" in skill_doc
    assert "Markov / Transition-Matrix Gate" in microstructure_doc
    assert "maker_taker_tax_bps" in microstructure_doc


def test_eval_suite_covers_microstructure_failure_modes() -> None:
    eval_doc = json.loads((REPO_ROOT / "evals" / "evals.json").read_text(encoding="utf-8"))
    prompts = "\n".join(str(case["prompt"]) for case in eval_doc["evals"])
    referenced_files = {
        file_path for case in eval_doc["evals"] for file_path in case.get("files", [])
    }

    assert "longshot bias" in prompts
    assert "Markov transition matrix" in prompts
    assert "taker fee" in prompts
    assert "evals/runtime-v1-microstructure-payload.json" in referenced_files
