<!-- /autoplan restore point: /Users/peiwenyang/.gstack/projects/ypwcharles-prediction-market-analysis-skill/codex-polymarket-alert-runtime-autoplan-restore-20260421-195308.md -->
# Polymarket Runtime Hardening Plan

> **For agentic workers:** Run `/gstack-plan-eng-review` against this file before implementation. If you want the full review gauntlet with fewer back-and-forth decisions, run `/gstack-autoplan`.

**Goal:** Hard-stop the current drift between the human skill, the runtime contract, the runtime orchestration layer, and the repo health story, without changing the product wedge or rewriting the runtime.

**Why now:** The runtime is not failing today. `runtime/` tests are clean. The risk is slower and nastier: contract drift, orchestration bloat, and false-green health reporting. That is how a repo feels fine right up until every change gets expensive.

**Non-goals:**

- Do not change the core prediction-market judgment policy.
- Do not redesign Telegram delivery or the runtime deployment model.
- Do not do a big-bang rewrite of the runtime package.
- Do not add speculative infra.

---

## Problem Statement

The repo currently has four linked problems:

1. **The `runtime.v1` contract is duplicated.**
   The same field list and enum semantics live in the skill docs, runtime adapter, parser, eval fixtures, and design docs.
2. **`runtime_flow.py` is becoming the coordination sink.**
   Scan, monitor, callback, render handoff, trigger persistence, archive writing, and delivery are all routed through one file.
3. **Repo-level health reporting is misleading.**
   The real Python project lives in `runtime/`, but root-level autodetection misses it. Today that can produce a false-empty or underpowered health run.
4. **The top-level repo story is stale.**
   The repo is no longer "just a skill that returns TRADE / NO TRADE", but the root docs still read that way.

---

## Recommended Sequence

Do this in order. Do not start with the big file split.

```text
Phase 1: Contract SSOT
    |
    v
Phase 2: Flow Split
    |
    v
Phase 3: Health + CI
    |
    v
Phase 4: Docs + Routing Alignment
```

Why this order:

- If the contract is still duplicated, a flow split just spreads the duplication around.
- If the flow split lands before health tooling, review gets harder and regressions get cheaper.
- If docs are updated first, the repo tells a cleaner story than the code actually supports. Not great.

---

## Current Architecture Smell Map

```text
today

skill docs -----------+
                      |
runtime adapter ------+----> runtime.v1 semantics
                      |
parser ---------------+
                      |
eval fixtures --------+
                      |
design docs ----------+

scanner ----+
sources ----+--> runtime_flow.py --> delivery/archive/storage/service
monitor ----+
callback ---+
```

Target shape:

```text
shared contract/schema ----> skill docs
                         \-> adapter
                         \-> parser
                         \-> eval validation

flows/scan.py ----------+
flows/monitor.py -------+--> thin orchestration boundary --> delivery/archive/storage/service
flows/callback.py ------+
```

That is the whole game.

---

## Workstream 1: Contract Single Source Of Truth

**Objective:** Make one repo-local source of truth define the runtime judgment contract, then make every layer consume it or validate against it.

### Recommended approach

Use a boring Python-first source of truth inside `runtime/`, not another markdown-only contract.

Recommended shape:

- `runtime/src/polymarket_alert_bot/judgment/contract.py`
- Define:
  - allowed `alert_kind` values
  - allowed `cluster_action` values
  - required top-level fields
  - recommended top-level fields
  - a helper for producing the runtime request envelope
- Reuse that module from:
  - `judgment/skill_adapter.py`
  - `judgment/result_parser.py`
  - contract-focused tests

### Files to modify

- Modify: `runtime/src/polymarket_alert_bot/judgment/skill_adapter.py`
- Modify: `runtime/src/polymarket_alert_bot/judgment/result_parser.py`
- Modify: `runtime/tests/unit/test_result_parser.py`
- Modify: `runtime/tests/integration/test_runtime_flow.py`
- Modify: `skills/prediction-market-analysis/SKILL.md`
- Modify: `evals/evals.json`

### Files to create

- Create: `runtime/src/polymarket_alert_bot/judgment/contract.py`
- Create: `runtime/tests/unit/test_judgment_contract.py`

### Acceptance criteria

- One Python module is the contract source of truth for runtime fields and enums.
- `skill_adapter.py` imports required and recommended fields instead of hardcoding lists.
- `result_parser.py` imports enum values instead of defining a second copy.
- At least one test fails if a new enum is added in one place but not the others.
- The skill docs still explain runtime mode, but do not redefine the field table as an independent truth source.

### Validation commands

```bash
cd runtime && uv run pytest tests/unit/test_judgment_contract.py tests/unit/test_result_parser.py
cd runtime && uv run pytest tests/integration/test_runtime_flow.py
```

### Notes

- Keep the markdown reference doc if it helps humans, but make it derivative.
- Do not add a second JSON schema and a Python schema unless there is a hard runtime consumer that needs both.

---

## Workstream 2: Split `runtime_flow.py` Without Changing Behavior

**Objective:** Reduce blast radius by moving scan, monitor, and callback orchestration into separate modules while preserving the current CLI and service surfaces.

### Recommended approach

Refactor first. Behavior second.

Recommended target:

- `runtime/src/polymarket_alert_bot/flows/scan.py`
- `runtime/src/polymarket_alert_bot/flows/monitor.py`
- `runtime/src/polymarket_alert_bot/flows/callback.py`
- `runtime/src/polymarket_alert_bot/runtime_flow.py` becomes either:
  - a thin compatibility facade, or
  - deleted after imports are updated

### Ownership boundaries

```text
flows/scan.py
  - scan orchestration
  - seed judgment
  - research/strict/heartbeat branching

flows/monitor.py
  - fired actions
  - pending recheck judgment
  - monitor alert delivery

flows/callback.py
  - callback routing
  - feedback persistence
  - callback side effects
```

Leave these where they are unless a move is needed to make the split natural:

- `delivery/`
- `archive/`
- `storage/`
- `templates/`
- `service/`

### Files to modify

- Modify: `runtime/src/polymarket_alert_bot/runtime_flow.py`
- Modify: `runtime/src/polymarket_alert_bot/cli.py`
- Modify: `runtime/src/polymarket_alert_bot/service/app.py`
- Modify: `runtime/tests/integration/test_runtime_flow.py`
- Modify: `runtime/tests/integration/test_service_endpoints.py`

### Files to create

- Create: `runtime/src/polymarket_alert_bot/flows/__init__.py`
- Create: `runtime/src/polymarket_alert_bot/flows/scan.py`
- Create: `runtime/src/polymarket_alert_bot/flows/monitor.py`
- Create: `runtime/src/polymarket_alert_bot/flows/callback.py`

### Acceptance criteria

- `runtime_flow.py` is no longer the primary implementation home for all three flows.
- Public entrypoints keep working:
  - `execute_scan_flow(...)`
  - `execute_monitor_flow(...)`
  - `execute_callback_flow(...)`
- CLI commands remain unchanged.
- FastAPI endpoints remain unchanged.
- Existing integration tests still pass with minimal fixture churn.

### Validation commands

```bash
cd runtime && uv run pytest tests/integration/test_runtime_flow.py
cd runtime && uv run pytest tests/integration/test_service_endpoints.py tests/integration/test_cli_dry_run.py
cd runtime && uv run pytest
```

### Guardrails

- No behavioral edits mixed into the file move unless they are required to keep tests green.
- No new abstraction layer unless it deletes obvious repetition.
- If a helper is only used once after the split, inline it.

---

## Workstream 3: Health And CI Hardening

**Objective:** Make repo health checks tell the truth about this repo instead of accidentally grading the wrong surface.

### Recommended approach

Define health explicitly. Do not rely on repo-root autodetection here.

Recommended minimum stack:

- `ruff check`
- `ruff format --check`
- `mypy`
- `pytest`

Recommended implementation:

- Add a root `CLAUDE.md` with:
  - `## Skill routing`
  - `## Health Stack`
- Add Python tooling to `runtime/pyproject.toml`
- Add one repo-root helper script or make target only if it simplifies repeated use

### Files to modify

- Modify: `runtime/pyproject.toml`
- Modify: `.gitignore`
- Create or modify: `CLAUDE.md`
- Optionally modify: `.github/workflows/runtime-image.yml`

### Optional files to create

- Optional: `scripts/runtime-health.sh`

### Acceptance criteria

- Running the chosen health entrypoint from repo root actually checks `runtime/`.
- Lint, format, type check, and tests are all first-class health categories.
- The repo has one obvious command for local health.
- CI runs the same or a near-identical command.
- The health story no longer depends on a human remembering to `cd runtime`.

### Validation commands

```bash
cd runtime && uv run ruff check .
cd runtime && uv run ruff format --check .
cd runtime && uv run mypy src
cd runtime && uv run pytest
```

### Notes

- Prefer `ruff + mypy` here. Boring, fast, good enough.
- If `mypy` becomes noisy, fix the config. Do not silently drop type checking.

---

## Workstream 4: Docs And Routing Alignment

**Objective:** Make the repo tell the truth about what it is now.

### Recommended approach

Update the root docs after the code-level contract and flow boundaries are stable enough to describe accurately.

### Files to modify

- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `runtime/README.md`
- Create or modify: `CLAUDE.md`

### Required doc changes

- Root README must describe the repo as:
  - prediction-market analysis skill
  - runtime shell
  - eval fixtures
  - design and ops docs
- Remove the misleading root claim that the repo only returns `TRADE` / `NO TRADE`.
- Explain where the true runtime project lives.
- Document the health command at repo root.
- Add gstack routing rules so future work hits the right specialized path.

### Acceptance criteria

- A new reader can understand the repo shape in under 2 minutes.
- README language matches the current dual-mode skill and runtime reality.
- `CLAUDE.md` exists and includes both routing and health stack instructions.

---

## Commit Strategy

Keep this incremental. No monster diff.

```text
Commit 1
  contract SSOT + contract tests

Commit 2
  flow split only

Commit 3
  health tooling + CI updates

Commit 4
  README/docs/CLAUDE alignment
```

If Commit 2 starts dragging behavior changes in, stop and split again.

---

## Test Plan

### Required regression coverage

```text
contract layer
  - enum/value parity
  - required field parity
  - adapter/parser agreement

scan flow
  - strict path
  - research path
  - heartbeat path
  - degraded evidence downgrade path

monitor flow
  - direct fired action delivery
  - narrative recheck blocked
  - narrative recheck approved

callback flow
  - claimed buy
  - close thesis
  - seen
  - snooze

service layer
  - /healthz
  - /status
  - /internal/scan
  - /internal/monitor
  - /internal/report
  - /telegram/webhook
```

### Required smoke commands

```bash
cd runtime && uv run polymarket-alert-bot scan
cd runtime && uv run polymarket-alert-bot monitor
cd runtime && uv run polymarket-alert-bot report
```

Use fixture-backed or dry-run-safe inputs if live credentials are not present.

---

## Risks And Mitigations

### Risk 1: Contract cleanup still leaves two truths

Mitigation:

- Treat `contract.py` as canonical.
- Keep human docs descriptive, not normative.
- Add tests that compare adapter/parser constants against the canonical source.

### Risk 2: Flow split changes behavior while moving code

Mitigation:

- Move code first.
- Keep function names stable.
- Run integration tests after each moved slice, not at the very end.

### Risk 3: Health hardening becomes tool churn

Mitigation:

- Stop at `ruff`, `mypy`, `pytest`.
- Reuse `runtime/pyproject.toml`.
- Avoid introducing a second task runner unless the repo already has one.

### Risk 4: Docs get updated before reality

Mitigation:

- Land docs last.
- Tie README updates to the same PR that lands the health entrypoint and contract cleanup.

---

## Definition Of Done

This plan is done when all of the following are true:

- The runtime contract has one code-level source of truth.
- `runtime_flow.py` is no longer the coordination sink for the entire runtime.
- Repo-root health checks target the real Python project and include lint, format, type check, and tests.
- Root docs describe the current repo accurately.
- A reviewer can trace every change through tests and one obvious health command.

If any one of those is still false, the repo is improved but not hardened.

---

## First Implementation Step

Start with Workstream 1.

Concrete first move:

```bash
cd /Users/peiwenyang/Development/polymarket-research/runtime
rg -n "alert_kind|cluster_action|archive_payload|ttl_hours" src tests
```

Then create `src/polymarket_alert_bot/judgment/contract.py` and move the shared constants there before touching anything else.

---

## Autoplan Phase 1 Review

### 0A. Premise Challenge

| Premise | Status | Evidence | Adjustment required |
|---|---|---|---|
| Runtime hardening is the right bottleneck right now. | Partially accepted. | `runtime/src/polymarket_alert_bot/runtime_flow.py` is 1019 lines and currently acts as the coordination sink. Root CI only builds the runtime image, and the root README still presents the repo as a skill-first package. | Keep the hardening work, but tie it to operator trust. The plan should explicitly improve alert trust, not just file layout. |
| A Python `contract.py` can be the single source of truth. | Accepted with a condition. | `runtime/src/polymarket_alert_bot/judgment/skill_adapter.py` hardcodes required/recommended fields, while `runtime/src/polymarket_alert_bot/judgment/result_parser.py` separately hardcodes enums. | Make `skills/prediction-market-analysis/SKILL.md` and `evals/evals.json` derivative or validated against the canonical contract. Otherwise `contract.py` becomes a third truth, not the first. |
| Splitting `runtime_flow.py` now is worth the churn. | Accepted with guardrails. | The file owns scan orchestration, monitor delivery, callback persistence, archive writing, and Telegram handoff. That is enough surface area to justify extraction. | Only do behavior-preserving extraction after contract parity tests land. Do not combine the split with behavior changes. |
| Health + CI fixes are mainly a tooling problem. | Partially accepted. | `.github/workflows/runtime-image.yml` only builds a Docker image. `runtime/pyproject.toml` only declares pytest dev deps today. | Add one deterministic repo-root health entrypoint that points at `runtime/`, plus CI that actually runs lint, type check, and tests. |
| No product-scope change is needed. | Partially accepted. | The user still wants a discovery-first Telegram runtime, not a dashboard or trading engine. But false positives, parse failures, and degraded evidence handling are product behavior, not just code hygiene. | Keep the wedge unchanged, but add operator-trust acceptance criteria to the plan: degraded visibility, contract parity checks, and one obvious smoke path. |

### 0B. Existing Code Leverage Map

| Sub-problem | What already exists | Reuse decision | Plan impact |
|---|---|---|---|
| Runtime orchestration | `runtime/src/polymarket_alert_bot/runtime_flow.py` already exposes `execute_scan_flow(...)`, `execute_monitor_flow(...)`, and `execute_callback_flow(...)`. | Reuse the public entrypoints. | Refactor behind the existing API, not around it. |
| Contract parsing | `runtime/src/polymarket_alert_bot/judgment/result_parser.py` already validates the runtime payload with Pydantic. | Reuse validation, centralize constants. | Move enums/field lists to canonical contract helpers and import them here. |
| Judgment invocation | `runtime/src/polymarket_alert_bot/judgment/skill_adapter.py` already builds payloads and degrades on runner failures. | Reuse the adapter shell. | Remove duplicated contract literals and add parity tests. |
| Evidence degradation | `_load_configured_evidence(...)` already rescues feed failures into degraded reasons. | Reuse the rescue behavior. | Promote degraded-mode visibility into explicit acceptance criteria and reporting. |
| Runtime verification | `runtime/tests/unit/` and `runtime/tests/integration/` already cover parser, scan, monitor, callback, service, and rendering paths. | Reuse the existing test base. | Add contract-parity tests and a repo-root health smoke target instead of rebuilding the suite. |
| Service auth surface | `runtime/tests/integration/test_service_endpoints.py` already verifies `/healthz`, `/status`, internal endpoints, and webhook auth. | Reuse the endpoint/test contract. | Keep Phase 3 focused on health truthfulness, not a service redesign. |
| Repo docs | `README.md` and `docs/README.md` already exist. | Reuse and realign. | Update the root story after code and CI truth land, not before. |

### 0C. Dream State Diagram

```text
CURRENT
  skill-first root story
  + duplicated runtime.v1 literals
  + 1019-line runtime_flow.py
  + runtime-only CI truth

THIS PLAN, after Phase 1 adjustments
  canonical runtime contract
  + derivative/validated skill + eval references
  + thinner flow boundaries behind stable entrypoints
  + one truthful repo-root health command
  + root docs aligned to the real product surface

12-MONTH IDEAL
  self-measuring alert runtime
  + contract generation or parity enforcement
  + quality scorecards for false positives / degraded runs / operator trust
  + cleaner packaging boundary between judgment skill and operational runtime
  + routine shipping with CI that proves the whole operator path
```

### 0C-bis. Implementation Alternatives

| Approach | Pros | Cons | Effort | Verdict |
|---|---|---|---|---|
| A. Keep the four workstreams, add operator-trust guardrails. | Smallest blast radius. Reuses the current runtime, tests, and CLI/service entrypoints. | Does not create a moat by itself. Still a hardening plan, not a product leap. | Medium | Selected. This is the right near-term path. |
| B. Put a golden end-to-end contract/eval harness ahead of all refactors. | Strongest drift protection. Forces agreement across runtime, skill docs, and evals before file motion. | Leaves `runtime_flow.py`, root CI, and stale repo story untouched longer. | Medium | Partially adopted as an added acceptance criterion inside Workstream 1, not as a full reorder. |
| C. Split the runtime into a separate repo or service now. | Cleanest long-term boundary between judgment core and operational shell. | High migration cost, no immediate user value, easy to burn a week on packaging instead of trust. | Large | Rejected for this cycle. Revisit only after the runtime is self-consistent and measured. |

### 0D. Mode Selection, `SELECTIVE EXPANSION`

Baseline scope stays intact. A few adjacent expansions are worth pulling in because they make the hardening work actually change user trust.

Accepted into scope:

- Add operator-trust acceptance criteria: degraded visibility, parse-failure visibility, and one obvious repo-root smoke path.
- Add a canonical-to-derivative rule for skill docs and eval fixtures so `contract.py` cannot become a third truth.
- Add a repo-root health/CI entrypoint that points at `runtime/`, not just a note in the docs.

Deferred to later or `TODOS.md`:

- Quality scorecards for false positives, stale alerts, and operator time-to-triage.
- A packaging split between the standalone skill and the operational runtime.
- Rich observability beyond counters and run outcomes.

Explicitly skipped in this plan:

- Changing the core judgment policy.
- One-click order execution or portfolio automation.
- A new dashboard or UI shell.

### 0E. Temporal Interrogation

| Window | What improves | What still hurts |
|---|---|---|
| Hour 1 | Contract duplication becomes visible and locally actionable. | Nothing user-facing changes yet. |
| First PR | Parser/adapter drift gets harder to introduce, and the repo has a more truthful health path. | Alert-quality measurement is still mostly manual. |
| 1-2 weeks | Refactoring `runtime_flow.py` becomes less dangerous because contract and CI guardrails exist. | Telegram delivery and callback failure handling still need sharper rescue/logging. |
| 6 months | The repo is easier to evolve without fear. | If we stop here, competitors still win on signal quality, freshness, and operator confidence. |

### 0F. Mode Confirmation

`SELECTIVE EXPANSION` remains the right mode. The user wants this hardening work done, but the complete version needs three adjacent guardrails so the plan improves real operator trust instead of just internal cleanliness.

### CODEX SAYS (CEO, strategy challenge)

- The current plan risks optimizing for repo hygiene while under-specifying the real bottleneck: alert economics and operator trust.
- A Python-only source of truth does not help if the independently consumed skill docs and eval fixtures stay hand-maintained.
- The mixed skill/runtime repo boundary is still fuzzy. Golden contract tests are a better near-term boundary than a repo split.
- CI blind spots matter more than tidy docs. Right now the only root workflow builds a Docker image; it does not prove the runtime actually works.

### CLAUDE SUBAGENT (CEO, strategic independence)

- High: The plan hardens internals but does not state product metrics for alert quality, stale alerts, or operator time-to-decision.
- High: The health-story premise is asserted but not reproed in the plan. Add the failing baseline command or explicitly mark it as prior evidence that still needs confirmation.
- High: `contract.py` becomes dangerous if skill docs and evals remain freehand copies.
- Medium: Splitting `runtime_flow.py` is plausible, but the plan should justify it as a risk reducer, not architecture theater.
- High: Competitive risk is underplayed. A cleaner runtime is irrelevant if alert quality does not improve.

### CEO Dual Voices, Consensus Table

| Dimension | Claude subagent | Codex | Consensus |
|---|---|---|---|
| Premises valid? | Partial | Partial | Partial accept. Premises are directionally right but missing explicit operator-trust framing. |
| Right problem to solve? | Partial | Partial | Necessary but incomplete. Hardening is worth doing if it strengthens alert trust, not if it stops at code hygiene. |
| Scope calibration correct? | Partial | Partial | Keep the core scope. Pull in three guardrails, do not widen into product redesign. |
| Alternatives sufficiently explored? | No | No | Add the alternatives table and record why repo split / metrics-first reorder were not selected. |
| Competitive / market risks covered? | No | No | Missing. The plan should explicitly say this does not improve the moat unless quality measurements follow. |
| 6-month trajectory sound? | Partial | Partial | Sound only if contract parity, CI truth, and repo-story alignment all land together. |

### Section 1. Architecture And Product Fit

This is the right technical cleanup, but it was undersold as a product-trust problem. The biggest code smell is real, `runtime_flow.py` owns too many responsibilities, and the contract literals are duplicated. The missing piece is that the plan must say why users benefit: fewer false-green runs, fewer silent contract mismatches, and a safer path to improve alert quality later.

Auto-decision: keep the four-workstream order, but raise the bar for Workstream 1 and Workstream 3. Workstream 1 now includes derivative/validated docs and evals. Workstream 3 now includes a repo-root health command and CI runner, not just local tooling advice.

### Section 2. Errors And Rescue

The runtime already rescues some important failures. Skill runner failures degrade instead of crashing, and configured evidence load failures degrade instead of pretending the run was clean. That is good.

The gaps are sharper than the plan stated. Telegram delivery still looks fail-stop, callback validation failures are unrescued `RuntimeError`s, and the repo-root health story can still silently grade the wrong surface if nobody adds an explicit root command.

### Section 3. Security

Examined the current runtime service surface and tests. Existing coverage already checks bearer auth on `/status` and internal endpoints plus secret validation on `/telegram/webhook`, so this hardening plan does not need a security-driven scope expansion.

No new high-severity security issue was flagged in Phase 1. The right call is to reuse the current auth shape and keep this plan focused on trust and maintainability.

### Section 4. Data Truth And Operator UX

The operator problem is not just "does the code run?" It is "can I trust the alert that showed up in Telegram, and can I tell when the system degraded?" The current plan needed to say that explicitly.

Two operator-facing truth gaps remain central: the root repo still tells a skill-first story, and degraded/parse-failure conditions are not yet elevated into top-level success criteria.

### Section 5. Quality

The runtime test surface is already decent. There are parser tests, scan/monitor/callback integration tests, rendering snapshots, and service endpoint tests.

The quality gap is cross-surface parity, not raw test count. There is still no single failing proof that contract drift between adapter, parser, skill docs, and eval fixtures cannot ship.

### Section 6. Tests

The plan already had the right instinct to put contract work before file splitting. The review adds one requirement: prove parity at the contract boundary, not just within Python.

Test coverage sketch:

```text
runtime contract literals
  adapter payload builder      -> unit tests exist, parity test missing
  parser enums / validation    -> unit tests exist
  skill docs / eval fixtures   -> no automated parity proof yet

runtime flows
  scan                         -> integration tests exist
  monitor                      -> integration tests exist
  callback                     -> integration tests exist
  service endpoints            -> integration tests exist

repo-root truth
  root health command / CI     -> missing
```

### Section 7. Performance And Cost

No acute runtime-performance issue was exposed by this review. The immediate risk is not latency, it is shipping bad internal complexity that slows future changes.

The main performance guardrail is social: do not turn Phase 3 into tool churn. Add only the checks that support one obvious health command and one CI path.

### Section 8. Observability

The repo already has useful operational artifacts, `.runtime-data/sqlite/`, `.runtime-data/reports/`, and `.runtime-data/archives/` give the runtime a place to persist truth. That is enough base to build on.

What is missing is summary visibility: degraded feed load counts, malformed judgment counts, and Telegram delivery failures should become visible outcomes, not hidden implementation details.

### Section 9. Deploy And Rollback

The current plan is right to stage the work into separate commits. Keep that.

The deployment gap is that CI currently proves image buildability, not runtime truth. Rollback stays straightforward only if the refactor is behavior-preserving and lands behind the same public entrypoints.

### Section 10. Future Reversibility

The chosen path is reversible as long as the boundary changes stay local. A canonical contract module, flow extraction behind stable function names, and a root health entrypoint are all easy to unwind.

What would not be reversible at low cost is a premature repo or service split. That is why it stays out of scope for this cycle.

### Section 11. Design

Skipped. No UI scope was detected in the plan or the current repo surface.

## NOT In Scope

- Judgment-policy redesign: this plan is about runtime consistency, not changing the trading brain.
- Execution plumbing: order placement, wallet automation, and one-click trading stay out.
- Dashboard or UI shell: the product surface remains scheduled runs plus Telegram push.
- Repo/service split between skill and runtime: useful later, premature now.
- Rich observability stack: beyond counters and run outcomes, defer until the runtime is internally consistent.

## What Already Exists

| Need | Existing artifact | Reuse plan |
|---|---|---|
| Stable runtime entrypoints | `execute_scan_flow(...)`, `execute_monitor_flow(...)`, `execute_callback_flow(...)` in `runtime_flow.py` | Keep as compatibility boundary during refactor. |
| Runtime parser validation | `runtime/src/polymarket_alert_bot/judgment/result_parser.py` | Reuse model validation, centralize constants. |
| Graceful judgment degradation | `SkillAdapter.judge(...)` degraded returns for timeout, runner failure, malformed output | Keep rescue behavior, make it more measurable. |
| Evidence degradation | `_load_configured_evidence(...)` | Keep degraded-mode fallback, surface it in acceptance criteria. |
| Flow tests | `runtime/tests/integration/test_runtime_flow.py`, `test_scan_pipeline.py`, `test_monitor_pipeline.py`, `test_callback_reconciliation.py` | Extend, do not replace. |
| Service auth tests | `runtime/tests/integration/test_service_endpoints.py` | Reuse for Phase 3 CI truth. |
| Runtime packaging | `runtime/pyproject.toml` and the `polymarket-alert-bot` script | Extend with lint/type tooling instead of adding a new task runner. |
| Repo docs | `README.md`, `docs/README.md` | Update last, after code and CI truth land. |

## Dream State Delta

If this plan lands with the Phase 1 adjustments, the repo becomes truthful and easier to change. It does not become a self-measuring alert product.

What still remains after this plan:

- No automated quality scorecard for false positives, stale alerts, or operator trust.
- No hard packaging boundary between the reusable judgment skill and the operational runtime.
- No richer observability for Telegram delivery or degraded-path trends beyond basic run artifacts.

## Error & Rescue Registry

| Codepath | Failure / exception | Rescued? | Rescue action | Test coverage | User impact |
|---|---|---|---|---|---|
| `SkillAdapter.judge(...)` | no runner configured | Yes | returns `ParsedJudgment.degraded("runner_not_configured")` | `runtime/tests/unit/test_result_parser.py` | alert downgrades instead of crashing |
| `SkillAdapter.judge(...)` | timeout, runner exception, malformed output | Yes | returns degraded judgment | `runtime/tests/unit/test_result_parser.py` | alert may downgrade to degraded / research path |
| `_load_configured_evidence(...)` | news feed load failure | Yes | appends `news_feed_failed:*`, continues run | `runtime/tests/integration/test_runtime_flow.py` | run continues in degraded mode |
| `_load_configured_evidence(...)` | X feed load failure | Yes | appends `x_feed_failed:*`, continues run | `runtime/tests/integration/test_runtime_flow.py` | run continues in degraded mode |
| `_deliver_message(...)` / `TelegramClient.upsert_message(...)` | Telegram API/network failure | No | none | telegram client unit coverage exists, no flow-level rescue | scan / monitor can fail after successful judgment, alert may be missed |
| `execute_callback_flow(...)` | unsupported callback payload | No | raises `RuntimeError` | auth / happy-path callback tests exist, no invalid-payload rescue | webhook or CLI call fails outright |
| `execute_callback_flow(...)` | unknown alert id / missing thesis cluster id | No | raises `RuntimeError` | callback happy-path tests exist | operator action can fail hard after a real alert |
| `connect_db(...)` / `apply_migrations(...)` in flow entrypoints | SQLite open or migration failure | No | none | schema tests exist, no runtime rescue | whole flow exits before doing work |

## Failure Modes Registry

| Codepath | Failure mode | Rescued? | Test? | User sees? | Logged? |
|---|---|---|---|---|---|
| adapter/parser/skill-doc/eval contract surfaces | contract drift ships without one canonical parity proof | No | Partial | degraded alerts or inconsistent behavior | No |
| repo-root health path | builder runs health at repo root and gets a false-green or incomplete picture | No | No | Silent | No |
| Telegram delivery path | judgment succeeds but alert delivery fails | No | Partial | missing or stale Telegram alert | Unknown |
| configured evidence feeds | remote/local feed load fails | Yes | Yes | degraded run / downgraded strictness | Partial |
| skill runner output | runner times out or returns malformed JSON | Yes | Yes | degraded judgment path | Partial |
| callback payload handling | Telegram callback payload is unsupported or points to unknown alert state | No | Partial | explicit request failure | Partial |

Critical gaps:

- `contract drift ships without one canonical parity proof` is a critical gap because the user can receive a degraded or semantically wrong runtime path without any top-level proof that the contract stayed aligned.
- `repo-root health path false-green` is a critical gap because it is silent and encourages trust in the wrong surface.
- `Telegram delivery succeeds only on the happy path` is a critical gap because the judgment engine can do the right thing and the operator still sees nothing.

### Phase 1 Transition Summary

Phase 1 complete for CEO review content. Codex surfaced 4 strategic concerns. Claude subagent surfaced 5 issues. Consensus: both voices agree the plan is worth doing, but only if it is reframed as operator-trust hardening rather than repo hygiene alone.

### Completion Summary

```text
  +====================================================================+
  |            MEGA PLAN REVIEW - COMPLETION SUMMARY                   |
  +====================================================================+
  | Mode selected        | SELECTIVE EXPANSION                         |
  | System Audit         | 1019-line flow sink, duplicated contract,   |
  |                      | root story / CI lag runtime reality         |
  | Step 0               | 3 guardrails accepted, no product rewrite   |
  | Section 1  (Arch)    | 4 issues found                              |
  | Section 2  (Errors)  | 8 error paths mapped, 3 critical gaps       |
  | Section 3  (Security)| 0 high-severity issues, reuse current auth  |
  | Section 4  (Data/UX) | 2 operator-truth issues                     |
  | Section 5  (Quality) | 2 issues found                              |
  | Section 6  (Tests)   | diagram produced, 2 gaps                    |
  | Section 7  (Perf)    | 1 tooling-discipline issue                  |
  | Section 8  (Observ)  | 3 visibility gaps                           |
  | Section 9  (Deploy)  | 2 risks flagged                             |
  | Section 10 (Future)  | Reversibility: 4/5, debt items: 3           |
  | Section 11 (Design)  | SKIPPED (no UI scope)                       |
  +--------------------------------------------------------------------+
  | NOT in scope         | written (5 items)                           |
  | What already exists  | written                                     |
  | Dream state delta    | written                                     |
  | Error/rescue registry| 8 methods, 3 critical gaps                 |
  | Failure modes        | 6 total, 3 critical gaps                   |
  | TODOS.md updates     | deferred to later phases                    |
  | Scope proposals      | 3 proposed, 3 accepted                      |
  | CEO plan             | written                                     |
  | Outside voice        | ran (codex + claude subagent)               |
  | Lake Score           | 3/3 complete-option picks                    |
  | Diagrams produced    | 2 (dream state, test coverage sketch)       |
  | Stale diagrams found | 0 new contradictions found                  |
  | Unresolved decisions | 1 (premise gate)                            |
  +====================================================================+
```

## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|-------|----------|----------------|-----------|-----------|----------|
| 1 | CEO | Keep `SELECTIVE EXPANSION` as the review mode | auto-decided | P2 + P5 | This is an iteration on an existing runtime, so the complete move is to preserve scope and pull in only the adjacent guardrails that materially improve trust. | Full expansion, hold-scope without guardrails |
| 2 | CEO | Accept operator-trust acceptance criteria into scope | expansion accepted | P1 + P2 | Hardening that does not change alert trust is incomplete work. These additions stay within the current runtime blast radius. | Pure code-shape hardening |
| 3 | CEO | Require canonical-to-derivative contract validation | auto-decided | P1 + P4 | A new `contract.py` only helps if the other contract surfaces stop being independent truths. | Manual sync between docs, evals, and code |
| 4 | CEO | Keep flow split after contract work, not before | auto-decided | P5 | The simplest safe sequence is to lock the contract first, then move code behind stable entrypoints. | Split-first refactor |
| 5 | CEO | Skip design review phase for this plan | auto-decided | P4 | No UI scope was detected in the plan or repo surface. Running a design phase here would be ceremony without signal. | Forced Phase 2 design review |
| 6 | Eng | Add explicit delivery/callback/startup failure handling to the plan | auto-decided | P1 + P2 | Both engineering voices flagged fail-stop Friday-night paths, and they sit inside the current runtime blast radius. | Deferring failures to a later reliability pass |
| 7 | Eng | Require a one-way module graph before splitting `runtime_flow.py` | auto-decided | P5 | The safest refactor is explicit dependency direction with shared utilities/context only where multiple flows truly need them. | Ad hoc extraction with helper drift |
| 8 | Eng | Expand test scope to parity, negative, root-health, and concurrency cases | auto-decided | P1 | Existing tests are good but not sufficient for the specific risks this plan claims to address. | Happy-path-only regression coverage |
| 9 | Eng | Add repo-root health truth, not just repo-root lint wiring | auto-decided | P1 + P5 | `/healthz` and current CI are too weak to signal operator trust; the root path must prove runtime readiness, not just process liveness. | Keeping image-build CI as the only repo-level signal |
| 10 | Eng | Defer product analytics, packaging split, and richer eval harness into `TODOS.md` | auto-decided | P3 + P4 | These are valuable but outside the smallest complete hardening slice. Capturing them preserves context without expanding the current implementation beyond control. | Silent deferral or expanding this plan into a platform rewrite |

## Phase 2 Status

Skipped. No UI scope was detected in the plan or the current repo surface.

## Autoplan Phase 3 Review

### Step 0. Scope Challenge, Actual Code Analysis

Actual code reviewed:

- `runtime/src/polymarket_alert_bot/runtime_flow.py`
- `runtime/src/polymarket_alert_bot/judgment/skill_adapter.py`
- `runtime/src/polymarket_alert_bot/judgment/result_parser.py`
- `runtime/src/polymarket_alert_bot/service/app.py`
- `runtime/src/polymarket_alert_bot/cli.py`
- `runtime/src/polymarket_alert_bot/delivery/telegram_client.py`
- `runtime/tests/integration/test_runtime_flow.py`
- `runtime/tests/integration/test_service_endpoints.py`
- `runtime/tests/unit/test_result_parser.py`
- `.github/workflows/runtime-image.yml`
- `runtime/pyproject.toml`

Concrete findings from code, not just the plan:

- `runtime_flow.py` is not only large, it mixes scan, monitor, callback, Telegram delivery, archive persistence, trigger persistence, and degraded handling in one file.
- Contract literals are duplicated in both `skill_adapter.py` and `result_parser.py`.
- The scan path enriches evidence twice for the same seed: once in `_judge_seed(...)`, and again in `_is_strict_allowed(...)`.
- Trigger and claim persistence currently do per-alert `DELETE` plus `commit()` before reinsertion, which increases churn and makes partial-write reasoning harder.
- Delivery failure behavior is still fail-stop at the flow layer even though the lower Telegram client has some method-level rescue behavior.
- Service auth coverage is decent, but health truth and repo-root CI truth are still weaker than the plan claims to solve.

### Plan Deltas From Engineering Review

These deltas are now part of the plan:

- Workstream 1 must include parity validation between `contract.py`, `skills/prediction-market-analysis/SKILL.md`, and `evals/runtime-v1-*.json` / `evals/evals.json`.
- Workstream 2 must define a one-way module graph before moving code.
- Workstream 2 must keep shared orchestration logic in a small common layer rather than duplicating helpers across `flows/scan.py`, `flows/monitor.py`, and `flows/callback.py`.
- Workstream 2 and 3 must add explicit degraded or delivery-failed behavior for Telegram transport failure, invalid callback payloads, and startup DB/migration failure paths.
- Workstream 3 must add a truthful repo-root health command and CI workflow that runs lint, type check, and tests before or alongside image build.

### CODEX SAYS (eng, architecture challenge)

- High: Contract truth is still split across adapter/parser, so `contract.py` must be consumed and parity-tested instead of becoming a third truth.
- High: `runtime_flow.py` hides flow-specific failure semantics; split into dedicated flow modules with explicit shared utilities and explicit degraded/fatal outcomes.
- High: The scan path enriches evidence twice for the same seed, which risks drift and unnecessary work.
- High: Delivery and callback failures are not operator-safe; convert them into structured degraded or delivery-failed outcomes with durable surfacing.
- Medium: Health and CI signals are too weak; add degraded-aware readiness plus root lint/type/test gates.

### CLAUDE SUBAGENT (eng, independent review)

- High: Contract SSOT is only nominal without generation or CI parity checks for skill docs and evals.
- Medium: Flow split currently lacks a one-way dependency graph and explicit shared-state boundaries.
- Critical: Friday-night failure paths remain fail-stop, especially Telegram delivery, malformed callbacks, and startup DB/migration failure.
- High: Test plan is too happy-path oriented and misses parity, negative, root-health, idempotency, and concurrency coverage.
- High: Security boundaries need explicit auth-negative tests to prove no unauthorized state writes happen.

### Eng Dual Voices, Consensus Table

| Dimension | Claude subagent | Codex | Consensus |
|---|---|---|---|
| Architecture sound? | Partial | Partial | Sound if the split gets an explicit one-way module graph and shared common layer first. |
| Test coverage sufficient? | No | No | No. Add parity, negative, root-health, and concurrency coverage. |
| Performance risks addressed? | Partial | Partial | Main risk is hidden duplicated work and transaction churn, not raw scale today. |
| Security threats covered? | Partial | Partial | Existing auth surface is decent, but negative tests still need to be explicit in scope. |
| Error paths handled? | No | No | No. Delivery, callback, and startup failures are still too fail-stop. |
| Deployment risk manageable? | Partial | Partial | Manageable if CI proves runtime truth before image-only success is trusted. |

### Section 1. Architecture

The architecture should stay layered and boring. `cli.py` and `service/app.py` should remain thin entrypoints. `runtime_flow.py` should become a compatibility facade only, not another bucket of helpers after the split.

Required module graph:

```text
cli.py / service.app
        |
        v
runtime_flow.py  (compatibility facade only)
        |
        +-----------------------+
        |                       |
        v                       v
flows/scan.py           flows/monitor.py         flows/callback.py
        |                       |                       |
        +-----------+-----------+-----------+-----------+
                    |                       |
                    v                       v
             judgment/                runtime_common/
       contract.py / adapter /        delivery, archive,
          result_parser               storage, timers, outcomes
                    |
                    v
        scanner/ sources/ monitor/ storage/
```

Architecture rule:

- `flows/*` may depend on `runtime_common/`, `judgment/`, and domain modules.
- `runtime_common/` may not depend on `flows/*`.
- `service/` and `cli.py` may only call public flow entrypoints or facade functions.

### Section 2. Code Quality

Main code-quality issues that the plan now must address:

- Contract literals duplicated across adapter and parser.
- Shared flow responsibilities are not yet named clearly enough to avoid helper copy-paste during the split.
- Scan strict-gating currently recomputes evidence enrichment after judgment.
- Persistence helpers commit at a more granular level than the operator-facing unit of work.

Auto-decisions:

- Keep names explicit over clever. `flows/scan.py`, `flows/monitor.py`, `flows/callback.py`, and `runtime_common/` are enough.
- Do not introduce a generic orchestration framework. Keep helpers domain-specific.
- If a helper is only reused by one flow after extraction, inline it there instead of centralizing prematurely.

### Section 3. Test Review

Test coverage diagram:

```text
CONTRACT / RUNTIME SURFACE
  contract enums + required fields
    current coverage: parser unit tests only
    missing: canonical parity test across contract.py, adapter, docs, eval fixtures

SCAN FLOW
  strict path
    current coverage: yes, integration
  degraded evidence path
    current coverage: yes, integration
  evidence feed ingestion
    current coverage: yes, integration
  Telegram transport failure
    current coverage: no flow-level test
  startup DB / migration failure
    current coverage: no
  root health smoke path
    current coverage: no

MONITOR FLOW
  fired trigger delivery
    current coverage: yes, integration
  narrative recheck blocked / approved
    current coverage: yes, integration
  concurrent overlap / file lock behavior
    current coverage: partial, scheduler overlap only
  delivery failure during monitor alert
    current coverage: no flow-level test

CALLBACK FLOW
  claimed buy / seen / close thesis
    current coverage: yes, CLI / integration
  unsupported payload
    current coverage: no direct negative test
  unknown alert / unresolved cluster
    current coverage: no direct negative test
  duplicate callback idempotency
    current coverage: no

SERVICE SURFACE
  auth-positive and malformed webhook JSON object
    current coverage: yes
  auth-negative should not mutate state
    current coverage: partial
  deeper readiness beyond process-ok
    current coverage: no
```

LLM / prompt surface implications:

- This plan touches `skills/prediction-market-analysis/SKILL.md` and `evals/evals.json`, so contract and prompt-facing regression checks cannot stop at `pytest`.
- The repo does not currently expose a native prompt-eval harness beyond fixture files and `evals/evals.json`, so this plan must at minimum add parity tests and JSON syntax validation, and leave richer prompt-harness work in `TODOS.md`.

Test plan artifact written to disk:

- `/Users/peiwenyang/.gstack/projects/ypwcharles-prediction-market-analysis-skill/peiwenyang-codex-polymarket-alert-runtime-test-plan-20260421-203344.md`

### Section 4. Performance

No acute scale bottleneck was found that should expand scope beyond hardening. The real performance risks are hidden complexity and duplicated work.

Specific performance / correctness risks:

- `execute_scan_flow(...)` currently enriches evidence twice per seed.
- `_persist_claim_mappings(...)` and `_replace_triggers(...)` each commit per alert, which increases transaction churn and complicates rollback reasoning.
- The current health surface can report "ok" while deeper runtime readiness is still broken.

### Section 5. Failure Modes Addendum

Additional failure modes from engineering review:

| Codepath | Failure mode | Rescued? | Test? | User sees? | Logged? |
|---|---|---|---|---|---|
| scan strict-gating | evidence snapshot differs between judgment and strict-allow evaluation | No | No | inconsistent strict vs research outcome | No |
| claim / trigger persistence | per-alert delete+commit leaves partial state after mid-loop failure | No | No | missing or half-updated trigger / claim mappings | Unknown |
| service health path | `/healthz` stays green while deeper runtime readiness is broken | No | No | false-green health | No |
| callback routing | unsupported or unresolved callback exits hard without structured degraded state | No | Partial | explicit 500 / CLI failure | Partial |

Engineering critical gaps:

- Contract parity across code, docs, and evals is still a critical gap until the canonical parity test exists.
- Delivery and callback failure handling remain critical gaps until they become structured runtime outcomes.
- Repo-root health truth remains a critical gap until a root command and CI workflow prove the real runtime surface.

### Worktree Parallelization Strategy

Dependency table:

| Step | Modules touched | Depends on |
|---|---|---|
| Contract SSOT + parity | `runtime/src/polymarket_alert_bot/judgment/`, `skills/prediction-market-analysis/`, `evals/`, `runtime/tests/unit/` | — |
| Flow split | `runtime/src/polymarket_alert_bot/flows/`, `runtime_flow.py`, `service/`, `cli.py`, `runtime/tests/integration/` | Contract SSOT + parity |
| Health + CI truth | `.github/workflows/`, `runtime/`, repo-root scripts/docs entrypoint | Contract SSOT + parity |
| Docs alignment | `README.md`, `docs/`, optional `CLAUDE.md` | Flow split, Health + CI truth |

Parallel lanes:

- Lane A: Contract SSOT + parity (sequential, foundational)
- Lane B: Flow split (starts after Lane A)
- Lane C: Health + CI truth (starts after Lane A, parallel to Lane B)
- Lane D: Docs alignment (starts after Lane B + C merge)

Execution order:

- Launch Lane A first.
- After Lane A lands, launch Lane B and Lane C in parallel worktrees.
- Merge both.
- Then run Lane D.

Conflict flags:

- Lane B and Lane C both likely touch `runtime/` and `runtime/tests/`, so they are parallelizable at the module level but need coordination on test files and root health commands.

### TODOS.md Updates

`TODOS.md` was created and populated for deferred items:

- Alert quality scorecard and operator-trust metrics
- Richer prompt / skill eval harness
- Future packaging boundary between skill and runtime

### Cross-Phase Themes

**Theme: operator trust** — flagged in Phase 1 and Phase 3. High-confidence signal. The plan is only worth doing if health, degradation, and delivery behavior become visible to the operator.

**Theme: one truth for the runtime contract** — flagged in Phase 1 and Phase 3. High-confidence signal. A canonical contract with hand-maintained mirrors is still contract drift.

**Theme: silent failure is the real risk** — flagged in Phase 1 and Phase 3. High-confidence signal. False-green health, delivery failure without runtime surfacing, and callback hard-fails are the main ways this system will betray an operator.

### Phase 3 Transition Summary

Phase 3 complete. Codex surfaced 5 engineering concerns. Claude subagent surfaced 5 issues. Consensus: the plan is structurally right, but it must absorb explicit failure-handling, parity-testing, and health-truth requirements before it is implementation-ready.

### Completion Summary

```text
  +====================================================================+
  |            MEGA PLAN REVIEW - COMPLETION SUMMARY                   |
  +====================================================================+
  | Step 0: Scope Challenge | scope accepted, engineering guardrails   |
  | Architecture Review     | 4 issues found                           |
  | Code Quality Review     | 4 issues found                           |
  | Test Review             | diagram produced, 6 gaps identified      |
  | Performance Review      | 3 issues found                           |
  | NOT in scope            | written                                  |
  | What already exists     | written                                  |
  | TODOS.md updates        | 3 items proposed and auto-written        |
  | Failure modes           | 3 critical gaps flagged                  |
  | Outside voice           | ran (codex + claude subagent)            |
  | Parallelization         | 4 lanes, 2 parallel / 2 sequential       |
  | Lake Score              | 4/4 recommendations chose complete opt   |
  +====================================================================+
```
