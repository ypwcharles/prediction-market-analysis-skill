# Prediction Market Analysis Runtime Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align `skills/prediction-market-analysis/` with the runtime `runtime.v1` judgment contract while preserving the existing human-facing eight-section analysis workflow.

**Architecture:** Keep one judgment engine and add two explicit operating modes. `skills/prediction-market-analysis/SKILL.md` remains the entrypoint, but it will detect runtime payloads and switch from interactive markdown output to JSON-only Runtime Judgment Mode. A new runtime contract reference doc will hold the field semantics, and eval fixtures will lock the contract shape against drift.

**Tech Stack:** Markdown skill docs, JSON eval fixtures, repo-local validation with `python3`, existing runtime contract in `runtime/src/polymarket_alert_bot/judgment/`.

---

## File Structure

### Files to modify

- Modify: `skills/prediction-market-analysis/SKILL.md`
- Modify: `evals/evals.json`

### Files to create

- Create: `skills/prediction-market-analysis/references/runtime-judgment-contract.md`
- Create: `evals/runtime-v1-scan-payload.json`
- Create: `evals/runtime-v1-monitor-payload.json`

### Responsibility map

- `skills/prediction-market-analysis/SKILL.md`
  Continues to be the single skill entrypoint, but explicitly distinguishes Interactive Analysis Mode from Runtime Judgment Mode.
- `skills/prediction-market-analysis/references/runtime-judgment-contract.md`
  Defines the `runtime.v1` activation rule, required fields, recommended fields, enum values, and mapping semantics.
- `evals/runtime-v1-scan-payload.json`
  Provides a stable scan-style runtime input fixture built around the actual `context_builder.py` payload shape.
- `evals/runtime-v1-monitor-payload.json`
  Provides a stable monitor-style runtime input fixture that exercises prior-cluster and position-context paths.
- `evals/evals.json`
  Adds runtime-mode eval entries that assert JSON-only behavior and required-field coverage without breaking the existing interactive eval set.

## Task 1: Add the Runtime Contract Reference

**Files:**
- Create: `skills/prediction-market-analysis/references/runtime-judgment-contract.md`

- [ ] **Step 1: Verify the reference file does not already exist**

Run:
```bash
test -f skills/prediction-market-analysis/references/runtime-judgment-contract.md
```
Expected: command exits non-zero because the file does not exist yet.

- [ ] **Step 2: Create `runtime-judgment-contract.md`**

Write `skills/prediction-market-analysis/references/runtime-judgment-contract.md` with:
```markdown
# Runtime Judgment Contract

## Scope

Use this reference only when the caller provides a runtime payload with `contract_version: "runtime.v1"`.

## Activation Rule

Switch into Runtime Judgment Mode when the input includes:

- `contract_version: "runtime.v1"`
- `context`
- `response_schema`

In Runtime Judgment Mode:

- return one JSON object only
- do not emit markdown headings
- do not emit prose preambles
- do not wrap the JSON in a fenced code block

## Required Top-Level Fields

- `alert_kind`
- `cluster_action`
- `ttl_hours`
- `citations`
- `triggers`
- `archive_payload`

## Recommended Top-Level Fields

- `thesis`
- `side`
- `theoretical_edge_cents`
- `executable_edge_cents`
- `max_entry_cents`
- `suggested_size_usdc`
- `why_now`
- `kill_criteria_text`
- `summary`
- `watch_item`
- `evidence_fresh_until`
- `recheck_required_at`

## Allowed `alert_kind` Values

- `strict`
- `strict_degraded`
- `research`
- `reprice`
- `monitor`
- `heartbeat`
- `degraded`

## Allowed `cluster_action` Values

- `create`
- `update`
- `hold`
- `close`
- `none`

## Mapping Rules

- Use `strict` for clean, immediately actionable opportunities.
- Use `strict_degraded` when action remains valid but evidence or execution quality is degraded.
- Use `research` when the expression is worth surfacing but not ready for immediate action.
- Use `reprice` when the thesis survives but the live price changes the recommendation.
- Use `monitor` when the thesis should stay live operationally without becoming a fresh action alert.
- Use `degraded` when the runtime input or evidence path is too weak for a safe structured judgment.

## Citation Rules

Each citation should support a concrete claim and include:

- `source_id`
- `url`
- `claim`

Source metadata such as `source_name`, `source_tier`, `fetched_at`, and `confidence` should be included when available.

## Trigger Rules

Emit triggers only for real future checks, such as:

- price threshold rechecks
- evidence freshness expiry
- rule-change monitoring
- catalyst checkpoints

## Archive Payload Rules

`archive_payload` should preserve the durable judgment summary, including when available:

- `reason`
- `summary`
- `thesis`
- `thesis_cluster_id`
- `trigger_payload`
- `trigger_metadata`
```

- [ ] **Step 3: Verify the reference covers the runtime contract terms**

Run:
```bash
rg -n "runtime\\.v1|alert_kind|cluster_action|ttl_hours|archive_payload|strict_degraded|reprice|monitor" skills/prediction-market-analysis/references/runtime-judgment-contract.md -S
```
Expected: matches for the activation rule, required fields, and enum values.

- [ ] **Step 4: Commit the reference-doc task**

Run:
```bash
git add skills/prediction-market-analysis/references/runtime-judgment-contract.md
git commit -m "docs: add runtime judgment contract reference"
```
Expected: one commit containing only the new contract reference.

## Task 2: Update `SKILL.md` for Dual-Mode Operation

**Files:**
- Modify: `skills/prediction-market-analysis/SKILL.md`
- Create: `skills/prediction-market-analysis/references/runtime-judgment-contract.md`

- [ ] **Step 1: Write a failing mode-detection check**

Run:
```bash
python3 - <<'PY'
from pathlib import Path

text = Path("skills/prediction-market-analysis/SKILL.md").read_text()
required = [
    "## Operating Modes",
    "### Interactive Analysis Mode",
    "### Runtime Judgment Mode",
    'contract_version: "runtime.v1"',
    "references/runtime-judgment-contract.md",
]
for item in required:
    assert item in text, item
PY
```
Expected: `AssertionError` because the current skill does not yet document runtime mode.

- [ ] **Step 2: Add the operating-modes section near the top of `SKILL.md`**

Insert the following block after `## Core Principles`:
```markdown
## Operating Modes

### Interactive Analysis Mode

This is the default mode for normal user prompts.

In Interactive Analysis Mode:

- use the full risk-committee workflow below
- use the eight numbered output sections
- return a final verdict of `TRADE` or `NO TRADE` for the asked expression

### Runtime Judgment Mode

Switch into Runtime Judgment Mode only when the input includes:

- `contract_version: "runtime.v1"`
- `context`
- `response_schema`

In Runtime Judgment Mode:

- return one JSON object only
- do not emit markdown headings or prose summaries
- satisfy the required fields from `references/runtime-judgment-contract.md`
- use the same conservative judgment logic as Interactive Analysis Mode
```

- [ ] **Step 3: Replace the current verdict/output section with an explicit dual-mode contract**

Replace the existing `### 12. Return a binary verdict` and `## Output Format` introduction with:
```markdown
### 12. Return the mode-appropriate decision

In Interactive Analysis Mode:

- Final verdict must be one of `TRADE` or `NO TRADE`
- if the asked contract is inferior but a nearby expression is materially better, the verdict may still be `NO TRADE` for the asked market while recommending the cleaner expression

In Runtime Judgment Mode:

- do not emit `TRADE` / `NO TRADE` headings
- return only the JSON object required by `references/runtime-judgment-contract.md`
- choose the appropriate `alert_kind` and `cluster_action` instead of falling back to prose

## Output Format

### Interactive Analysis Mode

ALWAYS use this exact structure:
```

Then append the following block immediately after the interactive eight-section template:
```markdown
### Runtime Judgment Mode

When activated by a runtime payload, return one JSON object only.

Required top-level fields:

- `alert_kind`
- `cluster_action`
- `ttl_hours`
- `citations`
- `triggers`
- `archive_payload`

Recommended top-level fields:

- `thesis`
- `side`
- `theoretical_edge_cents`
- `executable_edge_cents`
- `max_entry_cents`
- `suggested_size_usdc`
- `why_now`
- `kill_criteria_text`
- `summary`
- `watch_item`
- `evidence_fresh_until`
- `recheck_required_at`

Use only the enum values and mapping rules defined in `references/runtime-judgment-contract.md`.
```

- [ ] **Step 4: Re-run the mode checks and preserve the interactive contract**

Run:
```bash
python3 - <<'PY'
from pathlib import Path

text = Path("skills/prediction-market-analysis/SKILL.md").read_text()
required = [
    "## Operating Modes",
    "### Interactive Analysis Mode",
    "### Runtime Judgment Mode",
    'contract_version: "runtime.v1"',
    "references/runtime-judgment-contract.md",
    "ALWAYS use this exact structure:",
    "Final verdict must be one of",
]
for item in required:
    assert item in text, item
print("skill dual-mode contract present")
PY
```
Expected: `skill dual-mode contract present`.

- [ ] **Step 5: Commit the dual-mode skill update**

Run:
```bash
git add skills/prediction-market-analysis/SKILL.md skills/prediction-market-analysis/references/runtime-judgment-contract.md
git commit -m "feat: add runtime judgment mode to skill"
```
Expected: one commit containing the dual-mode skill docs and contract reference.

## Task 3: Add Runtime Eval Fixtures and Validation Coverage

**Files:**
- Create: `evals/runtime-v1-scan-payload.json`
- Create: `evals/runtime-v1-monitor-payload.json`
- Modify: `evals/evals.json`

- [ ] **Step 1: Write a failing fixture-wiring check**

Run:
```bash
python3 - <<'PY'
import json
from pathlib import Path

data = json.loads(Path("evals/evals.json").read_text())
files = {path for item in data["evals"] for path in item.get("files", [])}
assert "evals/runtime-v1-scan-payload.json" in files
assert "evals/runtime-v1-monitor-payload.json" in files
PY
```
Expected: `AssertionError` because runtime fixtures are not wired into the eval set yet.

- [ ] **Step 2: Create the scan-style runtime fixture**

Create `evals/runtime-v1-scan-payload.json` with:
```json
{
  "contract_version": "runtime.v1",
  "context": {
    "candidate_facts": {
      "market_id": "pm_scan_boj_april_no_change",
      "market_slug": "bank-of-japan-decision-in-april",
      "market_question": "Bank of Japan Decision in April?",
      "market_url": "https://polymarket.com/event/bank-of-japan-decision-in-april",
      "platform": "Polymarket",
      "trade_archetype_hint": "time-bucket trade",
      "side": "YES",
      "outcome_name": "No change"
    },
    "rules_text": "This market resolves to 'No change' if the Bank of Japan leaves policy rates unchanged at its April decision meeting.",
    "executable_fields": {
      "best_bid_cents": 34.0,
      "best_ask_cents": 35.0,
      "mid_cents": 34.5,
      "max_entry_cents": 35.0,
      "suggested_bankroll_usdc": 10000.0
    },
    "evidence": [
      {
        "source_id": "boj-summary-2026-03",
        "source_kind": "official_release",
        "fetched_at": "2026-04-20T08:00:00Z",
        "url": "https://www.boj.or.jp/en/",
        "claim_snippet": "Board members preferred waiting for more wage and inflation data before the next move.",
        "tier": "primary",
        "conflict_status": "supportive"
      },
      {
        "source_id": "boj-governor-briefing-2026-04",
        "source_kind": "official_release",
        "fetched_at": "2026-04-20T08:15:00Z",
        "url": "https://www.boj.or.jp/en/announcements/press/kaiken_2026/kk260420a.htm",
        "claim_snippet": "Governor comments reinforced patience and no near-term policy move.",
        "tier": "primary",
        "conflict_status": "supportive"
      }
    ],
    "source_tier_state": {
      "strict_allowed": true,
      "strict_block_reason": "",
      "primary_support_count": 2,
      "supplementary_count": 0,
      "unknown_count": 0,
      "unresolved_primary_conflict": false
    },
    "prior_cluster_state": {},
    "position_context": {
      "bankroll_usdc": 10000.0,
      "open_positions": []
    }
  },
  "response_schema": {
    "required": [
      "alert_kind",
      "cluster_action",
      "ttl_hours",
      "citations",
      "triggers",
      "archive_payload"
    ],
    "recommended": [
      "thesis",
      "side",
      "theoretical_edge_cents",
      "executable_edge_cents",
      "max_entry_cents",
      "suggested_size_usdc",
      "why_now",
      "kill_criteria_text",
      "summary",
      "watch_item",
      "evidence_fresh_until",
      "recheck_required_at"
    ],
    "alert_kind_enum": [
      "strict",
      "strict_degraded",
      "research",
      "reprice",
      "monitor",
      "heartbeat",
      "degraded"
    ]
  }
}
```

- [ ] **Step 3: Create the monitor-style runtime fixture**

Create `evals/runtime-v1-monitor-payload.json` with:
```json
{
  "contract_version": "runtime.v1",
  "context": {
    "candidate_facts": {
      "market_id": "pm_monitor_conflict_end_apr15",
      "market_slug": "iran-israel-us-conflict-ends-by-apr-15",
      "market_question": "Iran x Israel/US conflict ends by April 15?",
      "market_url": "https://polymarket.com/event/iran-x-israel-us-conflict-ends-by-apr-15",
      "platform": "Polymarket",
      "trade_archetype_hint": "cross-bucket structure",
      "side": "NO",
      "outcome_name": "Yes"
    },
    "rules_text": "This market resolves Yes if credible public reporting confirms that direct conflict between Iran and Israel or the United States has ended by April 15 under the market rules.",
    "executable_fields": {
      "best_bid_cents": 60.0,
      "best_ask_cents": 62.0,
      "mid_cents": 61.0,
      "max_entry_cents": 58.0,
      "suggested_bankroll_usdc": 10000.0
    },
    "evidence": [
      {
        "source_id": "regional-diplomacy-roundup-1",
        "source_kind": "quality_press",
        "fetched_at": "2026-04-20T08:00:00Z",
        "url": "https://example.com/deescalation-roundup",
        "claim_snippet": "Officials discussed de-escalation, but no verified ceasefire terms or resolution mechanism have been announced.",
        "tier": "secondary",
        "conflict_status": "mixed"
      }
    ],
    "source_tier_state": {
      "strict_allowed": false,
      "strict_block_reason": "no_primary_support",
      "primary_support_count": 0,
      "supplementary_count": 1,
      "unknown_count": 0,
      "unresolved_primary_conflict": false
    },
    "prior_cluster_state": {
      "thesis_cluster_id": "iran-deescalation-april",
      "current_alert_kind": "monitor",
      "last_summary": "Narrative drift toward de-escalation remains unconfirmed."
    },
    "position_context": {
      "bankroll_usdc": 10000.0,
      "open_positions": [
        {
          "market_id": "pm_monitor_conflict_end_apr15",
          "side": "NO",
          "size_usdc": 250.0,
          "avg_entry_cents": 57.0
        }
      ]
    }
  },
  "response_schema": {
    "required": [
      "alert_kind",
      "cluster_action",
      "ttl_hours",
      "citations",
      "triggers",
      "archive_payload"
    ],
    "recommended": [
      "thesis",
      "side",
      "theoretical_edge_cents",
      "executable_edge_cents",
      "max_entry_cents",
      "suggested_size_usdc",
      "why_now",
      "kill_criteria_text",
      "summary",
      "watch_item",
      "evidence_fresh_until",
      "recheck_required_at"
    ],
    "alert_kind_enum": [
      "strict",
      "strict_degraded",
      "research",
      "reprice",
      "monitor",
      "heartbeat",
      "degraded"
    ]
  }
}
```

- [ ] **Step 4: Append runtime-mode eval cases to `evals/evals.json`**

Add the following objects to the `evals` array in `evals/evals.json`:
```json
{
  "id": 8,
  "prompt": "Use only the runtime payload in `evals/runtime-v1-scan-payload.json`. Because the payload declares `contract_version: \"runtime.v1\"`, switch into Runtime Judgment Mode and return one JSON object only.",
  "expected_output": "A JSON object that satisfies the runtime.v1 contract, preserves the skill's conservative analysis logic, and does not emit the interactive eight-section report.",
  "files": [
    "evals/runtime-v1-scan-payload.json"
  ],
  "expectations": [
    "The output is a single JSON object, not markdown.",
    "The output contains alert_kind, cluster_action, ttl_hours, citations, triggers, and archive_payload.",
    "The output does not include the literal interactive header '1. Verdict'.",
    "The output uses a runtime alert kind instead of the literal verdict TRADE or NO TRADE."
  ]
},
{
  "id": 9,
  "prompt": "Use only the runtime payload in `evals/runtime-v1-monitor-payload.json`. Stay in Runtime Judgment Mode and return one JSON object only. If the evidence is not clean enough for immediate action, use the appropriate non-strict runtime alert kind rather than falling back to prose.",
  "expected_output": "A JSON object that preserves runtime mode, uses the existing cluster and position context, and can choose monitor/research/degraded behavior without emitting the interactive report.",
  "files": [
    "evals/runtime-v1-monitor-payload.json"
  ],
  "expectations": [
    "The output is a single JSON object, not markdown.",
    "The output contains the required runtime.v1 top-level fields.",
    "The output can keep an existing thesis alive with monitor/research/hold semantics instead of forcing a fresh TRADE verdict.",
    "The output does not include numbered interactive sections."
  ]
}
```

- [ ] **Step 5: Validate the fixture files and eval wiring**

Run:
```bash
python3 - <<'PY'
import json
from pathlib import Path

json.loads(Path("evals/runtime-v1-scan-payload.json").read_text())
json.loads(Path("evals/runtime-v1-monitor-payload.json").read_text())

data = json.loads(Path("evals/evals.json").read_text())
ids = {item["id"] for item in data["evals"]}
assert 8 in ids and 9 in ids
files = {path for item in data["evals"] for path in item.get("files", [])}
assert "evals/runtime-v1-scan-payload.json" in files
assert "evals/runtime-v1-monitor-payload.json" in files
print("runtime eval fixtures wired")
PY
```
Expected: `runtime eval fixtures wired`.

- [ ] **Step 6: Commit the runtime eval coverage**

Run:
```bash
git add evals/evals.json evals/runtime-v1-scan-payload.json evals/runtime-v1-monitor-payload.json
git commit -m "test: add runtime eval fixtures for skill"
```
Expected: one commit containing only the new fixtures and eval updates.

## Task 4: Run the Alignment Verification Pass

**Files:**
- Modify: `skills/prediction-market-analysis/SKILL.md`
- Create: `skills/prediction-market-analysis/references/runtime-judgment-contract.md`
- Modify: `evals/evals.json`
- Create: `evals/runtime-v1-scan-payload.json`
- Create: `evals/runtime-v1-monitor-payload.json`

- [ ] **Step 1: Run a repo-local alignment check against the documented runtime contract**

Run:
```bash
python3 - <<'PY'
import json
from pathlib import Path

skill_text = Path("skills/prediction-market-analysis/SKILL.md").read_text()
contract_text = Path("skills/prediction-market-analysis/references/runtime-judgment-contract.md").read_text()
evals = json.loads(Path("evals/evals.json").read_text())

for marker in [
    "## Operating Modes",
    "### Runtime Judgment Mode",
    'contract_version: "runtime.v1"',
    "references/runtime-judgment-contract.md",
]:
    assert marker in skill_text, marker

for marker in [
    "## Required Top-Level Fields",
    "`alert_kind`",
    "`cluster_action`",
    "`ttl_hours`",
    "`archive_payload`",
]:
    assert marker in contract_text, marker

runtime_eval_ids = {item["id"] for item in evals["evals"] if item["id"] in {8, 9}}
assert runtime_eval_ids == {8, 9}, runtime_eval_ids
print("alignment verification passed")
PY
```
Expected: `alignment verification passed`.

- [ ] **Step 2: Inspect the diff to make sure the plan stayed in scope**

Run:
```bash
git diff -- skills/prediction-market-analysis/SKILL.md \
  skills/prediction-market-analysis/references/runtime-judgment-contract.md \
  evals/evals.json \
  evals/runtime-v1-scan-payload.json \
  evals/runtime-v1-monitor-payload.json
```
Expected: diff only touches the skill entrypoint, the new runtime contract reference, and runtime eval fixtures.

- [ ] **Step 3: Create the wrap-up commit**

Run:
```bash
git add skills/prediction-market-analysis/SKILL.md \
  skills/prediction-market-analysis/references/runtime-judgment-contract.md \
  evals/evals.json \
  evals/runtime-v1-scan-payload.json \
  evals/runtime-v1-monitor-payload.json
git commit -m "feat: align prediction market skill with runtime contract"
```
Expected: one final integration commit if the task was implemented as a single batch instead of task-by-task commits.

## Self-Review

### Spec coverage

- Dual-mode behavior is implemented in Task 2.
- `runtime.v1` field semantics are documented in Task 1.
- Validation artifacts are added in Task 3.
- Final alignment verification is covered in Task 4.

### Placeholder scan

This plan contains no unresolved placeholders or deferred "handle later" instructions. Each code step includes exact file paths, concrete content, and runnable commands.

### Type consistency

- The runtime fixture shape matches the current `context_builder.py` output keys:
  - `candidate_facts`
  - `rules_text`
  - `executable_fields`
  - `evidence`
  - `source_tier_state`
  - `prior_cluster_state`
  - `position_context`
- The required and recommended top-level fields match `runtime/src/polymarket_alert_bot/judgment/skill_adapter.py`.

## Execution Handoff

Plan complete and saved to `docs/design-and-plans/2026-04-20-prediction-market-analysis-runtime-alignment.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
