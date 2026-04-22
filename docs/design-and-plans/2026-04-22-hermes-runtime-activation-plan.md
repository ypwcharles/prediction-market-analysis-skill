# Hermes Runtime Activation Plan

> **For agentic workers:** Run `/gstack-autoplan` against this file before implementation. If you only want the engineering gauntlet, run `/gstack-plan-eng-review`.

**Goal:** Make the repo usable with a real Hermes judgment runner, then graduate from local runtime validation to automated Polymarket opportunity discovery.

**Why now:** We already proved the runtime shell is real. The remaining gap is not whether `runtime/` exists, but whether real Hermes output can survive the runtime contract, latency budget, trigger persistence, and live discovery loop without degrading into `skill_timeout`, `malformed_skill_output`, or human-only trigger prose.

**Primary blockers already filed:**
- `#2` Real Hermes judgment path exceeds current runtime timeout budget
- `#3` Runtime parser and real Hermes Runtime Judgment output are still contract-drifted
- `#4` Runtime trigger contract is still too human-shaped for monitor storage/execution

**North star:** A real Hermes-backed `scan -> monitor -> report` pass runs cleanly, consumes real Polymarket board inputs, stores machine-usable alerts/triggers, and surfaces actionable opportunities instead of just proving the shell boots.

---

## Success definition

This work is done only when all of the following are true:

1. **Real Hermes runtime judgment is operational**
   - `runtime/` can call Hermes through `POLYMARKET_ALERT_BOT_JUDGMENT_RUNNER_CMD`
   - no canonical local E2E run degrades to `skill_timeout`
   - no canonical local E2E run degrades to `malformed_skill_output`

2. **Runtime contract is hard enough for real model output**
   - parser accepts the documented runtime output shape
   - skill docs and parser agree on field semantics
   - contract drift is caught by tests, not discovered by live runs

3. **Triggers are machine-operational**
   - persisted triggers encode actual runtime semantics, not prose stuffed into fallback fields
   - narrative recheck paths reliably set `requires_llm_recheck`
   - monitor behavior is intentional, not accidental fallback behavior

4. **Real-Hermes E2E validation is green**
   - local mock-upstream + real Hermes + real FastAPI runtime pass `scan`, `monitor`, and `report`
   - SQLite side effects match the intended lifecycle

5. **Opportunity discovery actually becomes usable**
   - runtime can scan live Polymarket board inputs without collapsing into degraded-only noise
   - output distinguishes:
     - research-only monitors
     - reprice / strict candidates
     - no-op board clutter
   - at least one repeatable board-scan workflow exists for finding candidate opportunities automatically

---

## Execution order

Do this in order. Do not jump straight to live-market scanning.

```text
Phase 1: Runtime contract lock
    |
    v
Phase 2: Real Hermes runner compatibility
    |
    v
Phase 3: Trigger schema hardening
    |
    v
Phase 4: Real-Hermes local E2E goes green
    |
    v
Phase 5: Live upstream integration
    |
    v
Phase 6: Automated opportunity discovery loop
```

Why this order:
- If the contract is loose, real Hermes output will keep degrading even when the model is right.
- If Hermes latency is unmanaged, live scanning just times out at scale.
- If triggers remain human-shaped, monitor behavior will stay half-fake.
- If local E2E is not green, live upstream work only adds noise.

---

## Phase 1: Runtime contract lock

**Objective:** Make `runtime.v1` a real runtime contract, not a vague agreement between docs and parser.

### Scope
- close issue `#3`
- define one parser-accepted, skill-documented JSON shape for:
  - citations
  - triggers
  - archive payload
  - confidence fields

### Required outcomes
- decide whether `citations[].confidence` is numeric, enum-string, or removed
- decide whether `archive_payload.trigger_payload` is dict-only, list-only, or split into separate fields
- add fixtures from actual Hermes output, not only hand-authored ideal payloads
- make `parse_judgment_result()` resilient only where the contract explicitly allows it

### Acceptance criteria
- real captured Hermes output from probe fixtures parses cleanly
- parser failures become explicit contract violations, not accidental schema mismatches
- issue `#3` can be closed with reproducible evidence

---

## Phase 2: Real Hermes runner compatibility

**Objective:** Make the runtime capable of using Hermes as a real runner, not just a mocked subprocess.

### Scope
- close issue `#2`
- formalize the Hermes runner wrapper path
- set realistic timeout budgets
- document runner modes

### Required outcomes
- define supported runner modes:
  - fast fake/script runner
  - real Hermes runner
- set non-naive timeout defaults or per-runner budgets
- make timeout failures observable as configuration mismatch, not mysterious runtime degradation
- capture real latency baselines for:
  - scan seed
  - monitor recheck

### Acceptance criteria
- real Hermes no longer times out in the canonical local E2E harness
- README/runtime docs explain how to run the real Hermes path
- issue `#2` can be closed with measured before/after evidence

---

## Phase 3: Trigger schema hardening

**Objective:** Make model-emitted triggers machine-usable by `monitor/`, storage, and future automation.

### Scope
- close issue `#4`
- replace fallback-heavy trigger persistence with explicit trigger classes

### Required outcomes
- define supported runtime trigger classes and required machine fields
- map runtime-mode trigger JSON into storage rows intentionally
- stop defaulting unrelated triggers onto `threshold_kind=price` / `comparison=<=`
- ensure narrative recheck triggers map onto monitor semantics predictably

### Acceptance criteria
- persisted trigger rows are interpretable without reading the original prose blob
- monitor engine behavior matches trigger intent
- issue `#4` can be closed with real stored-row evidence from E2E runs

---

## Phase 4: Real-Hermes local E2E goes green

**Objective:** Re-run the local harness with real Hermes and get a clean operational result.

### Scope
- use the existing runtime validation workflow
- keep upstream APIs mocked
- keep Telegram disabled

### Required outcomes
- clean `scan`
- clean `monitor`
- clean `report`
- real `runtime.v1` payloads logged for both:
  - scan seed
  - monitor recheck
- SQLite artifacts prove the lifecycle is real

### Acceptance criteria
- no runtime degradation caused by contract drift or timeout drift
- `alerts`, `triggers`, `positions`, and `calibration_reports` all show intentional state
- local validation doc can be updated with a genuine green real-Hermes path

---

## Phase 5: Live upstream integration

**Objective:** Replace mock board inputs with live Polymarket inputs without regressing runtime stability.

### Scope
- live Gamma/CLOB/positions inputs
- no Telegram/Cloudflare requirement yet

### Required outcomes
- classify live-run failures cleanly:
  - upstream fetch failure
  - malformed upstream payload
  - judgment degradation
  - empty-opportunity board state
- keep evidence and rule-reading discipline intact
- preserve deterministic operator logs

### Acceptance criteria
- live scan completes against real upstream APIs
- runtime produces a meaningful mix of `research`, `monitor`, `reprice`, or `strict` instead of collapsing into universal degradation

---

## Phase 6: Automated opportunity discovery loop

**Objective:** Turn the runtime from “it runs” into “it finds things worth looking at.”

### Scope
- board scanning and filtering
- candidate triage
- quality instrumentation

### Required outcomes
- define what counts as an “opportunity” for automated discovery:
  - rules-clean
  - executable
  - non-noisy
  - evidence-backed
- add operator-trust instrumentation from `TODOS.md`
- separate:
  - board coverage
  - actionable candidates
  - degraded/noisy candidates
- create a repeatable operator workflow for reviewing surfaced candidates inside Hermes

### Acceptance criteria
- runtime can run a board scan and surface a small, interpretable set of candidates
- output quality can be measured, not guessed
- the system is useful for actual opportunity discovery, not just runtime demos

---

## Proposed issue workflow

### Active execution stack
1. `#3` contract drift
2. `#2` real Hermes timeout budget
3. `#4` trigger schema hardening
4. umbrella execution issue for the full activation path

### Branching recommendation
- active hardening branch 1: `fix/runtime-contract-drift`
- active hardening branch 2: `fix/hermes-runtime-stability`
- keep timeout and trigger-schema fixes on the active hardening stack unless someone explicitly restacks the open PRs
- reserve `feat/live-opportunity-discovery` for after the hardening stack lands

Keep the current hardening work on the existing stack. Do not create parallel timeout or trigger-schema branches from this plan unless the stack is intentionally re-cut first.

---

## Risks

1. **Fixing the parser too permissively**
   - risk: we normalize garbage instead of enforcing a clean contract

2. **Using Hermes online everywhere**
   - risk: live scan latency and cost blow up before the pipeline is selective enough

3. **Pretending discovery quality without measurement**
   - risk: the bot “finds opportunities” but actually just creates operator noise

4. **Mixing hardening and product expansion in one PR**
   - risk: impossible review surface, fake progress

---

## Immediate next step

Start with `#3`.

That is the root blocker. Until the runtime contract and parser agree on real Hermes output, every other stage remains partly fake.
