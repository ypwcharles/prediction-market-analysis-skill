# Prediction Market Analysis Runtime Alignment Design

**Date:** 2026-04-20
**Status:** Draft for review
**Scope:** Align `skills/prediction-market-analysis/` with the Polymarket alert-bot runtime contract without replacing the existing human-facing analysis workflow.

## Goal

Preserve the current `prediction-market-analysis` skill as the single judgment core while making it explicitly usable by the runtime as a structured decision engine.

This design exists to solve one concrete mismatch:

- the repo skill currently enforces a human-facing eight-section `TRADE` / `NO TRADE` report
- the runtime already expects a machine-readable `runtime.v1` judgment payload

The result should be a single skill with two explicit operating modes rather than two drifting skills.

## Decision Summary

The skill will adopt a **dual-mode contract**:

1. **Interactive Analysis Mode**
   Default mode for normal user prompts. The skill keeps the existing conservative risk-committee workflow and the human-readable eight-section output.
2. **Runtime Judgment Mode**
   Activated only when the caller provides a runtime payload with `contract_version=runtime.v1`. In this mode the skill returns only structured JSON that satisfies the runtime contract.

This design intentionally keeps the analysis logic unified while separating output shape by caller intent.

## Why This Approach

### Recommended Option: One Skill, Two Modes

Pros:

- preserves the existing public skill behavior and evaluation surface
- avoids maintaining two separate judgment prompts that can drift on rule interpretation
- keeps the runtime contract close to the same decision principles the user already approved
- makes future Hermes/OpenClaw/operator integration simpler because every caller still points at one judgment engine

Cons:

- `SKILL.md` becomes more explicit about mode detection and output rules
- the skill must guard carefully against accidentally mixing prose output into runtime mode

### Rejected Option: Separate Runtime Skill

This would create a cleaner mechanical boundary, but it duplicates the most sensitive logic in the system:

- contract-selection heuristics
- reject-first tradeability standards
- rule-scope and timing decomposition
- conservative sizing logic

For this project, logic drift is more dangerous than a slightly heavier `SKILL.md`.

## Existing Constraints

The design must remain consistent with the current repository state:

- `skills/prediction-market-analysis/SKILL.md` is already the approved human-facing judgment workflow
- `runtime/src/polymarket_alert_bot/judgment/skill_adapter.py` already emits `contract_version: "runtime.v1"`
- `runtime/src/polymarket_alert_bot/judgment/result_parser.py` already validates the required top-level runtime fields
- the runtime plan says `skills/prediction-market-analysis/` stays the pure judgment engine while `runtime/` is the long-running operational shell

This means the skill should not absorb scheduler, delivery, persistence, callback, or service-shell responsibilities.

## Mode Model

### 1. Interactive Analysis Mode

This mode remains the default when the input is a normal user request or a thematic/single-market analysis prompt.

Behavior:

- keep the current trade archetypes
- keep the reject-first posture
- keep direction-vs-timing decomposition
- keep the eight numbered sections
- keep the final verdict semantics for the asked expression

No runtime-only fields should be required in this mode.

### 2. Runtime Judgment Mode

This mode activates only when the input is explicitly structured as a runtime judgment request.

Activation rule:

- input contains `contract_version: "runtime.v1"`
- input contains `context`
- input contains `response_schema`

Behavior:

- return a single JSON object only
- do not emit markdown, prose preamble, or fenced code blocks
- satisfy all required runtime fields
- use recommended runtime fields when the information is available from the judgment
- keep the same conservative logic standards used in interactive mode

## Runtime Contract

### Required Top-Level Fields

Runtime Judgment Mode must always return:

- `alert_kind`
- `cluster_action`
- `ttl_hours`
- `citations`
- `triggers`
- `archive_payload`

### Recommended Top-Level Fields

When the judgment supports them, Runtime Judgment Mode should also return:

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

### Alert Kind Semantics

The skill should treat `alert_kind` as an operational rendering of the same analysis outcome, not as a separate reasoning system.

Expected meanings:

- `strict`
  Clean, high-conviction, immediately actionable setup with adequate evidence and execution quality.
- `strict_degraded`
  Actionable setup, but some dimension is degraded: evidence freshness, source depth, liquidity quality, or execution certainty.
- `research`
  Worth surfacing, but not yet strong enough for immediate action.
- `reprice`
  Existing thesis survives, but current price/execution moved enough to justify an updated action recommendation.
- `monitor`
  Narrative or stateful development that should stay alive operationally rather than become a fresh trade alert.
- `heartbeat`
  Reporting/status output rather than thesis judgment. This remains primarily runtime-owned, not a general skill output.
- `degraded`
  Skill or evidence path could not produce a safe judgment.

### Cluster Action Semantics

The skill will use the runtime cluster actions as follows:

- `create`
  New thesis cluster or materially new opportunity.
- `update`
  Existing cluster should be refreshed with new judgment or reprice information.
- `hold`
  Keep the cluster alive without changing active recommendation.
- `close`
  Thesis or expression should be retired.
- `none`
  No clustering side effect is appropriate.

## Interactive-To-Runtime Mapping

The human-facing `TRADE` / `NO TRADE` output is not removed. Instead, runtime mode translates the same internal judgment into richer operational categories.

### Mapping Principles

- `TRADE` does not always mean `strict`; it may become `strict_degraded` or `reprice` depending on evidence and context.
- `NO TRADE` does not always mean `degraded`; it may become `research`, `monitor`, `hold`, or `close`.
- runtime mode must evaluate the asked expression and the preferred expression separately when necessary

### Practical Mapping

- clear `TRADE`, clean execution, immediate action -> `alert_kind="strict"`
- `TRADE`, but execution/evidence degraded -> `alert_kind="strict_degraded"`
- thesis alive, price moved beyond prior entry logic -> `alert_kind="reprice"`
- asked expression rejected, but adjacent expression worth watching/researching -> `alert_kind="research"`
- thesis update requires continued observation or recheck rather than immediate action -> `alert_kind="monitor"`
- unable to produce safe structured result -> `alert_kind="degraded"`

## Citation and Trigger Expectations

### Citations

Runtime mode citations must remain evidence-bearing, not decorative.

Each citation should support a concrete claim and include:

- source identity
- URL
- claim text
- freshness metadata when available

The skill should prefer fewer decisive citations over many weak citations.

### Triggers

Runtime mode may return trigger objects when the judgment identifies future recheck conditions or operational monitoring hooks.

The skill should only emit triggers that correspond to real future observations, such as:

- price threshold rechecks
- rule-change or resolution-source changes
- catalyst or deadline checkpoints
- evidence freshness expiry

It should not invent generic triggers merely to satisfy a shape requirement.

## Archive Payload Expectations

`archive_payload` should be the structured handoff that lets runtime persist a durable explanation of the judgment.

It should be suitable for archive writing, operator review, and follow-up monitoring. The payload should include, when available:

- short reason/summary
- normalized thesis
- thesis cluster identifier when derivable
- trigger metadata that explains what to watch
- lightweight delivery metadata if runtime supplied or enriched it later

The skill should not attempt to own archive formatting templates; it should provide judgment content only.

## Confidence and Probability Handling

The current skill places heavy weight on intervals and conservative boundaries. That remains correct.

However, runtime mode should not require a top-level `confidence` field unless runtime begins parsing one explicitly. For this round:

- keep confidence interval reasoning inside the underlying pricing/sizing logic
- preserve any per-citation confidence when useful
- encode the actionable conclusion through `summary`, edge fields, and `why_now`

If runtime later wants first-class interval fields, that should be a separate contract revision rather than an implicit addition here.

## Documentation Changes

The following documentation updates are required:

1. Update `skills/prediction-market-analysis/SKILL.md`
   Add explicit mode detection, dual-mode behavior, and Runtime Judgment Mode output rules.
2. Add `skills/prediction-market-analysis/references/runtime-judgment-contract.md`
   Define the `runtime.v1` contract, field meanings, and mapping rules in one stable reference file.
3. Keep existing reference docs intact unless they need small clarifying notes
   The analysis engine should not be rewritten merely to mention runtime.

## Validation Plan

The alignment work is complete only if all of the following are true:

1. The skill still supports the approved human-facing eight-section output in normal usage.
2. The skill docs explicitly define Runtime Judgment Mode and `runtime.v1`.
3. The runtime-required fields in the docs match the parser and adapter expectations already in `runtime/`.
4. A repo-local validation artifact exists for runtime mode.

Acceptable validation artifacts for this round:

- `evals/evals.json` cases that assert runtime-mode output shape, or
- a dedicated runtime judgment fixture/spec used by tests or future eval harnesses

## Out of Scope

This design does not cover:

- moving scheduling into the skill
- moving Telegram delivery into the skill
- adding direct service endpoints to the skill
- rewriting runtime parser types
- introducing a new `runtime.v2` contract
- proving a live end-to-end runner invocation path in this document alone

Those belong to runtime implementation and integration follow-up.

## Implementation Readiness

This design is ready for a focused implementation plan covering:

- `SKILL.md` dual-mode edits
- new runtime contract reference doc
- small reference-file clarifications if needed
- validation/eval updates that lock the contract shape

The intended end state is:

- one judgment engine
- one human mode
- one runtime mode
- one explicit contract
- zero ambiguity about which output shape the caller should receive
