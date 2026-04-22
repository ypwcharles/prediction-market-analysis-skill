<!-- /autoplan restore point: /Users/peiwenyang/.gstack/projects/ypwcharles-prediction-market-analysis-skill/main-autoplan-restore-20260422-122442.md -->
# Polymarket Scan Discovery Foundation Plan

> **For agentic workers:** Run `/gstack-autoplan` against this file before implementation. This plan is intentionally scoped as a first shipping slice, not the full end-state discovery system.

**Goal:** Upgrade the scan pipeline from `thin filter + sample judgment` to a richer discovery foundation that preserves executable context, exposes nearby expressions, ranks candidates before spending judgment budget, and adds shallow candidate-targeted retrieval for the top-ranked shortlist.

**Why now:** The current runtime is operational, but the discovery layer is still too lossy. It drops key execution fields before judgment, passes single-market context instead of expression families, and defaults to a tiny judgment budget over a coarse priority key. That means it can run cleanly while still missing the best opportunities.

**Primary input:** [2026-04-22-polymarket-scan-logic-review.md](2026-04-22-polymarket-scan-logic-review.md)

## Non-goals

- Do not change the core `prediction-market-analysis` judgment policy.
- Do not redesign Telegram delivery, monitor flow, or callback flow.
- Do not build broad candidate-targeted retrieval across the full board in this slice.
- Do not build a full evidence relevance engine, claim graph, or retrieval platform in this slice.
- Do not attempt a full discovery-system rewrite.
- Do not introduce a graph database, vector store, or speculative infra.

---

## Problem Statement

The current scan stack has five linked weaknesses:

1. **Candidate context is too thin.**
   Runtime fetches orderbook data, but only passes `spread_bps` / `slippage_bps` into the judgment path. It does not preserve the executable price context that the eval fixtures already assume.
2. **The scan is still sample-heavy.**
   Universe pull is biased toward top `volume24hr` markets, and the ranking key is mostly `supported domain + liquidity + spread`. The default judgment budget of `2` candidates is too low for broad opportunity discovery.
3. **Expression selection is underpowered.**
   The skill expects adjacent buckets and rule-scope variants, but runtime sends mostly single-market context. This weakens the system exactly where contract expression should be a wedge.
4. **Evidence routing is too global.**
   Configured feeds are merged into every candidate. The runtime does not yet do enough shortlist-targeted evidence narrowing before judgment.
5. **Coverage accounting is not discovery-aware enough.**
   The runtime can report run counts, but it does not yet tell us enough about ranking, family coverage, or why promising-looking candidates were not promoted.

---

## Recommended Sequence

```text
Phase 1A: Rich candidate snapshot
    |
    v
Phase 1B: Expression family summary
    |
    v
Phase 1C: Pre-LLM ranking layer
    |
    v
Phase 1D: Shortlist-targeted retrieval
    |
    v
Phase 1E: Coverage + calibration corrections
```

Why this order:

- If candidate snapshots are still thin, ranking becomes fake sophistication.
- If family context is missing, the system still cannot reliably find cleaner expressions.
- If retrieval lands before ranking, the system spends evidence budget on the wrong contracts.
- If coverage lands after ranking and retrieval, we will not know whether either of them actually improved discovery.

---

## Decision Summary

### Decision 1: Keep the judgment engine, enrich the judgment inputs

Recommended approach:

- Leave `skills/prediction-market-analysis/` untouched in policy terms.
- Improve what runtime sends into judgment.

Pros:

- Keeps the approved risk-committee logic stable.
- Fixes the highest-leverage bottleneck without retraining the decision layer.

Cons:

- More payload shape to maintain across scanner and tests.

### Decision 2: Add a Python-first pre-LLM ranking layer

Recommended approach:

- Compute a structured candidate score before judgment.
- Spend judgment budget on ranked candidates, not raw liquidity leaders.

Pros:

- Better use of runtime cost budget.
- Makes discovery behavior inspectable and testable.

Cons:

- Ranking heuristics can drift or overfit if they are not kept simple.

### Decision 3: Represent nearby expressions as lightweight family summaries

Recommended approach:

- Add family-aware context without building a heavy graph system.
- Start with same-event siblings plus simple adjacent-expression heuristics.

Pros:

- Captures the main expression-selection value cheaply.
- Good enough for phase 1.

Cons:

- Not a full market ontology.
- Cross-event equivalents will still be incomplete in this slice.

### Decision 4: Add shallow candidate-targeted retrieval only after shortlist selection

Recommended approach:

- Retrieve additional evidence only for the ranked shortlist.
- Reuse existing feed clients and source registry where possible.
- Keep retrieval shallow, bounded, and operationally cheap.

Pros:

- Starts fixing evidence relevance in the same slice as shortlist quality.
- Avoids spending retrieval cost on the full board.
- Better aligns runtime behavior with the skill's evidence expectations.

Cons:

- Expands phase 1 scope and failure surface.
- Introduces a second new decision layer, not just richer ranking.

---

## Target Architecture

```text
Gamma/CLOB pull
  -> normalized market snapshot
  -> expression family builder
  -> structural ranking
  -> shortlist
  -> shortlist-targeted retrieval
  -> judgment context with executable fields + family summary + targeted evidence
  -> judgment engine
  -> alert / research / heartbeat
  -> coverage + calibration artifacts
```

Phase 1 adds **shallow shortlist-targeted retrieval**, not a full retrieval platform. The point is to narrow evidence for promoted candidates, not to crawl the entire board or rebuild the evidence engine from scratch.

---

## File Structure

### Modify

- `runtime/src/polymarket_alert_bot/scanner/normalizer.py`
- `runtime/src/polymarket_alert_bot/scanner/board_scan.py`
- `runtime/src/polymarket_alert_bot/scanner/gamma_client.py`
- `runtime/src/polymarket_alert_bot/flows/shared.py`
- `runtime/src/polymarket_alert_bot/flows/scan.py`
- `runtime/src/polymarket_alert_bot/config/settings.py`
- `runtime/tests/integration/test_scan_pipeline.py`
- `runtime/tests/integration/test_runtime_flow.py`
- `runtime/tests/unit/test_source_feed_loading.py`
- `runtime/tests/unit/test_settings.py`

### Create

- `runtime/src/polymarket_alert_bot/scanner/ranking.py`
- `runtime/src/polymarket_alert_bot/sources/shortlist_retrieval.py`
- `runtime/tests/unit/test_scan_ranking.py`
- `runtime/tests/unit/test_shortlist_retrieval.py`

### Optional if needed during implementation

- `runtime/src/polymarket_alert_bot/scanner/family.py`
- `runtime/tests/unit/test_scan_family.py`

Do not create extra files unless the implementation becomes clearly cleaner.

---

## Workstream 1: Rich Candidate Snapshot

**Objective:** Preserve enough market state for real executable judgment and shortlist ranking.

### Scope

- [ ] Extend the candidate model to keep:
  - best bid
  - best ask
  - mid
  - optional last price if available
  - event title
  - outcome label when derivable
  - category / tag summary when derivable from Gamma payload
  - close time / deadline if available
- [ ] Extend seed payloads so these fields survive through `AlertSeed`.
- [ ] Pass these fields into `candidate_facts` and `executable_fields`.

### Acceptance criteria

- Judgment context includes real executable price fields, not only spread/slippage.
- The runtime scan path is closer to parity with `evals/runtime-v1-scan-payload.json`.
- Integration tests prove the fields survive scan -> seed -> context.

### Validation

```bash
cd runtime && uv run pytest tests/integration/test_scan_pipeline.py tests/integration/test_runtime_flow.py
```

---

## Workstream 2: Expression Family Summary

**Objective:** Give judgment enough local context to pick cleaner expressions.

### Scope

- [ ] Group same-event markets into a lightweight `expression family`.
- [ ] Build a family summary with:
  - primary expression
  - sibling expressions
  - simple adjacent-expression hints
  - family size / family ids
- [ ] Attach the family summary to `candidate_facts`.
- [ ] Keep this same-event only in phase 1 unless there is a very cheap extension.

### Acceptance criteria

- Judgment sees more than one expression when same-event siblings exist.
- The context is enough to support nearby-bucket or cleaner-expression reasoning.
- Payload size remains operationally reasonable.

### Validation

```bash
cd runtime && uv run pytest tests/integration/test_scan_pipeline.py tests/integration/test_runtime_flow.py
```

---

## Workstream 3: Pre-LLM Ranking Layer

**Objective:** Rank discovery candidates structurally before spending judgment budget.

### Scope

- [ ] Move ranking logic into a dedicated Python module.
- [ ] Replace the current coarse priority key with a score composed from:
  - execution quality
  - liquidity
  - family richness
  - deadline proximity when available
  - domain support heuristics
  - degraded penalties
- [ ] Make judgment candidate count configurable with a more realistic default.
- [ ] Keep the score explainable. Every rank component should be testable and inspectable.

### Decision guardrail

- Do not try to estimate true edge in ranking.
- Ranking should decide what deserves judgment, not replace judgment.

### Acceptance criteria

- Ranking is no longer a thin proxy for `liquidity + spread`.
- The shortlist can include structurally better candidates even when they are not the hottest contracts by raw volume.
- Unit tests cover scoring behavior deterministically.

### Validation

```bash
cd runtime && uv run pytest tests/unit/test_scan_ranking.py tests/integration/test_scan_pipeline.py
```

---

## Workstream 4: Shortlist-Targeted Retrieval

**Objective:** Improve evidence relevance for promoted candidates without building a full retrieval platform.

### Scope

- [ ] Add a shallow retrieval layer that runs only for the ranked shortlist.
- [ ] Reuse existing news / X feed clients where possible instead of introducing a broad new source system.
- [ ] Build candidate-aware retrieval inputs from:
  - primary expression
  - family summary
  - event title
  - outcome / deadline metadata when available
- [ ] Merge shortlist-targeted evidence ahead of judgment while preserving the configured-feed fallback path.
- [ ] Cap retrieval volume and attach explicit degraded reasons when targeted retrieval fails or returns nothing useful.
- [ ] Keep this bounded and explainable, not a full relevance engine.

### Acceptance criteria

- Judgment sees a candidate-specific evidence bundle for promoted shortlist entries.
- The retrieval layer does not fan out to the full board.
- Integration tests prove targeted evidence is added without breaking strict/research downgrade behavior.

### Validation

```bash
cd runtime && uv run pytest tests/unit/test_shortlist_retrieval.py tests/integration/test_runtime_flow.py
```

---

## Workstream 5: Coverage And Calibration Corrections

**Objective:** Make discovery behavior auditable after ranking and shortlist-targeted retrieval land.

### Scope

- [ ] Correct any misleading scan counters.
- [ ] Record family-aware coverage, shortlist counts, and promoted seed counts.
- [ ] Record missing-field counts for ranking and retrieval inputs.
- [ ] Preserve enough rejection reasons to explain why candidates were skipped.
- [ ] Make the accounting recall-first, not just ops-first.
- [ ] Keep this operational, not analytics-heavy.

### Acceptance criteria

- Run summaries distinguish universe size, shortlist size, retrieved shortlist size, and promoted seed count.
- Coverage accounting better matches what the user actually cares about: what was checked, what was skipped, what was retrieved, and why.

### Validation

```bash
cd runtime && uv run pytest tests/integration/test_scan_pipeline.py tests/integration/test_calibration_report.py
```

---

## Verification

### Automated

- [ ] `cd runtime && uv run pytest tests/unit/test_scan_ranking.py`
- [ ] `cd runtime && uv run pytest tests/unit/test_shortlist_retrieval.py`
- [ ] `cd runtime && uv run pytest tests/integration/test_scan_pipeline.py tests/integration/test_runtime_flow.py`
- [ ] `bash scripts/runtime-health.sh`

### Manual

- [ ] Run one fixture-backed scan and confirm the shortlist includes richer candidate fields.
- [ ] Inspect one archived strict or research payload and confirm executable fields, family summary, and targeted evidence are present.
- [ ] Confirm no monitor/callback behavior changed unintentionally.

---

## Risks And Mitigations

### Risk 1: Ranking becomes too clever and brittle

Mitigation:

- Keep the ranking score simple and additive.
- Test the components directly.
- Do not let ranking estimate fair value.

### Risk 2: Context payloads get bloated

Mitigation:

- Use family summaries, not raw full-board dumps.
- Cap sibling lists if needed.

### Risk 3: Gamma data is inconsistent across market types

Mitigation:

- Treat optional fields as optional.
- Gracefully degrade when tags, deadlines, or labels are missing.

### Risk 4: Shortlist-targeted retrieval becomes a stealth second system

Mitigation:

- Keep retrieval limited to promoted shortlist entries only.
- Reuse existing feed clients and registry plumbing.
- Add explicit caps, degraded reasons, and fallback semantics.

### Risk 5: Coverage work turns into analytics sprawl

Mitigation:

- Keep coverage focused on recall, ranking, retrieval, and rejection explanations.
- Do not add a separate analytics subsystem in phase 1.

---

## Deferred To Phase 2

- Claim-level evidence dedupe before judgment
- Settlement-direct evidence scoring in runtime
- Broader universe construction beyond the current single `volume24hr` intake path
- Cross-event equivalent-expression discovery
- Discovery-quality postmortem metrics for missed opportunities

---

## Success Criteria

- The runtime still behaves like the same product, but discovery is less lossy.
- Judgment gets the executable and family context it was previously missing.
- The shortlist is no longer just the top few liquid markets that survived a thin filter.
- Promoted candidates enter judgment with more candidate-specific evidence than the raw global feed.
- Coverage accounting is good enough to explain what the system looked at, what it retrieved, and why it chose what it chose.

---

## CEO Review (Phase 1 / Autoplan)

**Review status:** `DONE_WITH_CONCERNS`

This plan is directionally right. It attacks the most obvious information-loss bug between scan and judgment.

It is not yet the full discovery answer.

The biggest strategic risk is that the plan currently improves shortlist fidelity without fully addressing recall. In other words, it could become a cleaner version of the same conservative scanner if we do not explicitly handle `what got missed, why it got missed, and whether the current intake was broad enough`.

### Step 0A. Premise Challenge

#### Premise 1

`Richer candidate snapshot + better ranking` is the highest-leverage first fix.

**Verdict:** `ACCEPTED`

Why:

- Current scan-to-judgment handoff is materially lossy. `ScanCandidate` only preserves thin market state in `runtime/src/polymarket_alert_bot/scanner/normalizer.py`, while `_seed_candidate_facts()` and `_seed_executable_fields()` in `runtime/src/polymarket_alert_bot/flows/shared.py` pass only ids, `spread_bps`, and `slippage_bps`.
- The eval fixture already assumes `best_bid_cents`, `best_ask_cents`, and `mid_cents`, but the real scan path does not preserve them.

#### Premise 2

Same-event family summaries are the cheapest way to restore cleaner-expression reasoning.

**Verdict:** `ACCEPTED WITH LIMIT`

Why:

- The skill explicitly expects adjacent buckets, mutually exclusive outcomes, rule-scope variants, and named-actor variants before final trade judgment.
- A same-event family summary is the cheapest runtime approximation.
- It will not cover the full expression graph. Cross-event equivalents still remain deferred.

#### Premise 3

Candidate-targeted retrieval can safely wait for phase 2.

**Verdict:** `USER OVERRIDE: ACCEPTED IN PHASE 1`

Why:

- The current evidence path still loads global feeds in `_load_configured_evidence()` and appends them to every seed in `_merge_evidence()`.
- `strict_allowed` in `runtime/src/polymarket_alert_bot/sources/evidence_enricher.py` is still essentially `>= 2 primary` plus `no unresolved primary conflict`.
- That means a better shortlist could still enter judgment with noisy, non-candidate-specific evidence.

#### Premise 4

This phase materially improves discovery even if universe construction stays as-is.

**Verdict:** `CHALLENGED`

Why:

- `fetch_events()` in `runtime/src/polymarket_alert_bot/scanner/gamma_client.py` still fetches `order=volume24hr` only.
- Ranking on top of the same intake does not equal broader discovery. It mostly reorders a biased universe.

#### Premise 5

Coverage can stay operational and avoid becoming an analytics project.

**Verdict:** `ACCEPTED WITH AMENDMENT`

Why:

- We do not need a separate analytics system.
- We do need recall-aware counters, family coverage, missing-field counts, and rejection reasons, otherwise the scanner cannot learn from false negatives.

#### Premise Verdict

The plan should proceed, with two important clarifications:

- Phase 1 is a `discovery foundation`, not a full discovery engine.
- Phase 1 now includes shallow shortlist-targeted retrieval, but it must remain tightly bounded to promoted candidates only.
- Workstream 5 must stay recall-first so the system can explain misses instead of just producing a better-looking shortlist.

### Step 0B. Existing Code Leverage Map

| Sub-problem | Existing code | Reuse posture | Gap |
| --- | --- | --- | --- |
| Universe pull | `scanner/gamma_client.py`, `board_scan._run_live_scan()` | Reuse existing Gamma pull path | Still single-lane and volume-sorted |
| Executable market quality | `scanner/clob_client.py`, `normalizer.py` | Reuse existing book fetch + spread/slippage derivation | Rich price fields are not preserved past normalization |
| Prefiltering and seed creation | `board_scan.py` | Reuse prefilter, dedupe, seed plumbing | Current priority key is too coarse |
| Judgment context construction | `flows/shared.py`, `flows/scan.py` | Reuse alert seed and context builder pipeline | Context is too thin for executable and expression-aware judgment |
| Evidence loading and gating | `flows/shared.py`, `sources/evidence_enricher.py` | Reuse feed loaders and tier inference | Relevance scoring and candidate-specific retrieval are missing |
| Runtime verification | `runtime/tests/integration/*`, `evals/runtime-v1-scan-payload.json` | Reuse fixture and integration coverage | Need ranking and family-specific assertions |

**Conclusion:** This is a refactor-and-enrich plan, not a rewrite. Existing runtime boundaries are usable. The main requirement is to preserve and expose more structure through the current path instead of building parallel systems.

### Step 0C. Dream State Mapping

```text
CURRENT STATE
Top-volume board sample
  -> thin candidate snapshot
  -> coarse filter and priority key
  -> tiny judgment budget
  -> global evidence merged into every seed
  -> hard to explain misses

THIS PLAN
Same scanner and judgment engine
  -> richer candidate snapshot
  -> same-event family summary
  -> explicit structural ranking
  -> larger and inspectable shortlist
  -> shallow shortlist-targeted retrieval
  -> coverage and rejection accounting

12-MONTH IDEAL
Multi-entry universe construction
  -> recall-first discovery ranking
  -> candidate-targeted retrieval
  -> cross-bucket and cross-event expression graph
  -> miss-review loop that learns from false negatives
  -> trade-ready alerts with auditable evidence quality
```

### Step 0C-bis. Implementation Alternatives

#### Approach A: Schema Parity Patch

Summary:

- Only preserve richer executable fields and pass them through to judgment.
- Keep ranking and family logic mostly where they are today.

Effort: `S-M`
Risk: `Low`

Pros:

- Smallest diff.
- Quickly closes the eval-fixture parity gap.
- Lowest rollout risk.

Cons:

- Does not materially improve opportunity selection.
- Leaves discovery behavior mostly sample-driven.
- Misses the expression-selection wedge.

Reuses:

- Existing `board_scan.py`, `shared.py`, `scan.py` pipeline as-is.

#### Approach B: Discovery Foundation With Recall Instrumentation

Summary:

- Preserve rich candidate state, add same-event family summaries, move ranking into a dedicated module, and make coverage accounting recall-aware.
- Keep candidate-targeted retrieval deferred.

Effort: `M`
Risk: `Low-Med`

Pros:

- Fixes the most obvious runtime information bottlenecks.
- Produces an inspectable shortlist layer.
- Adds the minimum learning loop needed to understand misses.

Cons:

- Universe construction is still biased.
- Evidence relevance remains weak.
- Still not the final discovery engine.

Reuses:

- Existing scan pipeline, seed plumbing, judgment engine, and test harness.

#### Approach C: Discovery Foundation Plus Shortlist-Targeted Retrieval

Summary:

- Do everything in Approach B, then add shallow candidate-specific retrieval for the top-ranked shortlist before judgment.

Effort: `M-L`
Risk: `Med`

Pros:

- Starts fixing both shortlist selection and evidence relevance in the same slice.
- More likely to change actual judgment quality than schema work alone.
- Better long-term trajectory.

Cons:

- Enlarges failure surface immediately.
- Makes phase 1 less cleanly scoped.
- Introduces more source, timeout, and relevance-handling work before the foundation is verified.

Reuses:

- Existing feed clients and evidence pipeline, but with a new shortlist-specific retrieval layer on top.

**Recommendation before premise gate:** Choose **Approach B** as the baseline because it fixes the highest-confidence bottleneck first and creates an inspectable discovery layer without mixing in a second reliability problem.

**Premise gate outcome:** The user explicitly selected the broader premise, so phase 1 proceeds with **Approach C**.

### Step 0D. Mode-Specific Analysis

**Auto-selected mode:** `SELECTIVE EXPANSION`

Reason:

- This is an iteration on an existing runtime, not a greenfield system.
- The baseline scope is directionally correct.
- There are a few high-leverage expansions worth cherry-picking, but not enough to justify turning this into a full scope-expansion cycle.

#### Complexity check

The plan currently modifies at least 10 existing files and creates at least 3 new files, with an optional family module on top.

That is already near the upper bound for a "clean phase 1" slice.

Implication:

- Keep `ranking.py` and `shortlist_retrieval.py` as the only clearly justified new modules.
- Only create `family.py` if it materially reduces coupling inside `board_scan.py`.
- The user has explicitly chosen the broader path, so shallow retrieval is now in scope, but broader universe expansion and cross-event graphing still stay out.

#### Minimum set that achieves the stated goal

Must ship together:

- rich candidate snapshot
- shortlist ranking module
- same-event family summary
- shallow shortlist-targeted retrieval
- coverage and rejection accounting
- integration and unit coverage for the new path

Can be deferred without invalidating phase 1:

- cross-event equivalent-expression discovery
- graph/ontology style expression mapping
- broader universe construction

#### Expansion scan

**Accepted scope expansion**

1. Upgrade Workstream 4 from generic coverage fixes to explicit `recall-first discovery accounting`.
2. Pull shallow candidate-targeted retrieval for the top-ranked shortlist into phase 1.

Why accepted:

- It is inside the current blast radius.
- It does not require new infrastructure.
- It closes the most important product blind spot, `what got skipped, why, and how often`.

What this means in practice:

- record missing-field counts
- record family coverage counts
- record shortlist and promoted-seed counts separately
- record rejection reasons in a way that supports miss review

Why the retrieval expansion was accepted at the premise gate:

- evidence relevance is already a bottleneck
- a better shortlist with the same noisy evidence layer may underperform
- retrieval is now constrained to promoted shortlist entries, not the full board

**Deferred expansions**

1. Universe diversification beyond the single `volume24hr` intake path.
2. Cross-event equivalent-expression discovery.

Why deferred:

- They are strategically attractive, but they widen the slice materially.
- They should be pulled into phase 1 only if you want the broader premise, not silently auto-included.

### Step 0E. Temporal Interrogation

#### Hour 1

- One fixture-backed scan should show that executable price fields survive into judgment context.
- One archived payload should show family summary, richer executable fields, and candidate-targeted evidence.

#### Hour 6

- Ranked shortlist reasons should be visible and testable.
- Targeted retrieval should be visible and testable only for promoted shortlist entries.
- Coverage output should distinguish universe size, shortlist size, retrieved shortlist size, promoted seeds, and skipped reasons.

#### Day 1

- We should be able to answer "why did this run not alert anything?" without manually spelunking the database.
- We should be able to compare promoted candidates against skipped candidates structurally.

#### Still not solved after this phase

- whether the intake was broad enough
- whether evidence relevance is high enough in a settlement-direct sense
- whether the system is learning from real missed trades yet

### Step 0F. Mode Selection Confirmation

Mode remains `SELECTIVE EXPANSION`.

Selected approach is now `Approach C`, with two accepted expansions:

- strengthen Workstream 5 into recall-first discovery accounting
- pull shallow shortlist-targeted retrieval into phase 1

Explicitly deferred for now:

- broader universe construction
- cross-event expression graph

Premise gate has been passed and phase 1 scope is now fixed.

---

## Review Sections

### Section 1: Architecture Review

**Issues found:** `3`

#### Architecture diagram

```text
CURRENT
Gamma (top volume only) + CLOB books
  -> normalize_candidates
  -> prefilter
  -> coarse priority key
  -> top K seeds
  -> global evidence merge
  -> judgment

THIS PLAN
Gamma + CLOB books
  -> rich candidate snapshot
  -> same-event family summary
  -> ranking.py structural score
  -> ranked shortlist
  -> shortlist_retrieval.py
  -> judgment context with executable fields + family summary + targeted evidence
  -> judgment
  -> recall-aware coverage artifact
```

Findings:

1. The architecture still has a single-lane intake. `ranking.py` improves selection after fetch, but the plan does not yet broaden what gets fetched in the first place.
2. Family-building must remain a pure data-prep step. If cleaner-expression judgments leak into family construction, the architecture will duplicate skill logic in Python.
3. The new retrieval layer must remain post-shortlist and low-fanout. If it starts behaving like a board-wide search system, phase 1 will sprawl.

### Section 2: Error & Rescue Map

**Error paths mapped:** `7`
**Critical gaps:** `4`

| Method / codepath | What can go wrong | Exception / failure class | Rescued? | Rescue action | User sees |
| --- | --- | --- | --- | --- | --- |
| `gamma_client.fetch_events()` | HTTP timeout / bad JSON | `httpx.HTTPError`, `ValueError` | Yes | return empty list | heartbeat or zero-coverage scan |
| `board_scan._fetch_live_book()` | book fetch fails | generic external fetch failure | Yes | degraded snapshot | degraded or research outcome |
| `_load_configured_evidence()` | feed fetch fails | client exception | Yes | degraded reason recorded | evidence degraded, strict may downgrade |
| `ranking.py score builder` | missing deadline/category/family fields | missing metadata / partial snapshot | **No, plan unspecified** | should degrade to partial score and log reason | currently risks silent mis-ranking |
| family summary builder | malformed or huge sibling set | malformed market metadata / payload bloat | **No, plan unspecified** | should cap, truncate, and emit partial family summary | currently risks silent prompt bloat or missing context |
| `shortlist_retrieval.py` | no targeted hits / feed parse failure / over-broad query | retrieval failure / empty result | **No, plan unspecified** | should fall back to configured evidence path and log degraded reason | otherwise retrieval silently changes evidence quality |
| judgment on richer context | empty / malformed / refusal output | model output failure | **Plan does not spell this out** | should downgrade to research or degraded with explicit reason | otherwise failure semantics are ambiguous |

Review note:

- The plan is good on data enrichment, but weak on failure semantics for the new ranking, retrieval, and family layers.
- Those rescue paths need to be explicitly added before implementation starts.

### Section 3: Security & Threat Model

**Issues found:** `2`
**High severity:** `0`

Findings:

1. This slice does not add a large new write surface, which is good. Security risk is mostly about untrusted external content flowing into ranking, family summaries, and prompts.
2. Payload growth itself is a risk. Richer candidate and family data should be size-bounded before entering archive artifacts or LLM context to avoid prompt bloat and accidental prompt-injection amplification.

### Section 4: Data Flow & Interaction Edge Cases

**Edge cases mapped:** `8`
**Unhandled or under-specified:** `3`

#### Data flow

```text
INPUT
Gamma market payload + CLOB book
  -> VALIDATION
     missing ids? missing token? malformed numeric fields?
  -> TRANSFORM
     normalize rich snapshot + family summary + ranking inputs + retrieval inputs
  -> PERSIST
     run + alert seeds + archive artifacts
  -> OUTPUT
     shortlist + targeted evidence + judgment context + heartbeat/strict/research render

SHADOW PATHS
- missing deadline/category -> partial snapshot, not drop
- empty sibling set -> family summary with zero siblings, not error
- ranking metadata absent -> lower confidence score, logged
- targeted retrieval returns no good hits -> fall back to configured evidence, logged
- degraded books -> still visible as degraded candidates
```

Findings:

1. The plan needs explicit behavior for missing optional fields such as deadline, category, or outcome label. Missing metadata should degrade score confidence, not silently remove candidates.
2. Family summaries need hard caps. An event with many sibling markets cannot be dumped raw into prompt context.
3. Coverage accounting must distinguish `not fetched`, `fetched but rejected`, `retrieved but weak`, and `promoted but judged no-trade`. Right now only the middle bucket is clearly represented.

### Section 5: Code Quality Review

**Issues found:** `3`

Findings:

1. Do not let ranking logic remain half in `board_scan.py` and half in the new ranking module. One module should own scoring and explanation.
2. Avoid untyped dict soup for family summaries. A small typed structure is better than ad hoc nested dictionaries spread across scanner and flow layers.
3. `gamma_client.py` and `normalizer.py` should have a single source of truth for event-level metadata extraction. Do not parse title/tag/close-time separately in multiple places.

### Section 6: Test Review

**Diagram produced:** `Yes`
**Gaps:** `6`

#### New things introduced

```text
NEW DATA FLOWS
- market snapshot preservation from scan -> seed -> judgment context
- family summary assembly
- structural ranking and shortlist ordering
- shortlist-targeted retrieval and fallback merge
- recall-aware coverage and rejection accounting

NEW CODEPATHS
- ranking score calculation
- family summary attachment
- retrieval query/input construction
- targeted evidence merge and fallback handling
- richer executable field propagation
- coverage detail reporting

NEW EXTERNAL DEPENDENCIES
- none beyond existing Gamma/CLOB/feed clients

NEW ERROR/RESCUE PATHS
- ranking on partial metadata
- family summary truncation/degradation
- targeted retrieval miss / parse failure / fallback
- larger shortlist with missing optional fields
```

Required tests that are missing or under-specified in the current plan:

1. A comparative shortlist test, proving the new score changes candidate ordering in a deterministic and inspectable way.
2. A degraded-metadata test, proving missing deadline/category/family inputs do not silently discard a candidate.
3. A retrieval-input test, proving promoted candidates generate bounded retrieval inputs from expression/event metadata.
4. A retrieval-fallback test, proving no-hit or failed retrieval degrades cleanly to the configured evidence path.
5. A payload-size test, proving family summary caps and targeted evidence caps protect the judgment context from prompt bloat.
6. A scan accounting test, proving universe size, shortlisted count, retrieved shortlist size, and promoted seed count cannot drift again.

### Section 7: Performance Review

**Issues found:** `2`

Findings:

1. This phase is computationally cheap at current scale, but any later increase to `gamma_limit` will multiply CLOB book fetches linearly. The plan should keep room for future batching or staged fetch strategies.
2. The real p99 risk in phase 1 is not Python scoring cost. It is prompt-size and feed-processing growth from family summaries, targeted evidence, plus a larger judgment budget.

### Section 8: Observability & Debuggability Review

**Gaps found:** `5`

Required observability additions:

1. Log ranking components for every promoted candidate.
2. Record missing-field counts by run, for deadline/category/outcome/family inputs.
3. Record retrieval attempt counts, retrieval-hit counts, and retrieval fallback counts.
4. Record `tradable`, `degraded`, `shortlisted`, `retrieved`, and `promoted` as separate counters.
5. Preserve rejection reasons in a form that supports post-run miss review.

This section is the difference between "the scanner feels smarter" and "we can prove what it actually looked at."

### Section 9: Deployment & Rollout Review

**Risks flagged:** `4`

Findings:

1. New ranking defaults should be rollout-safe through config. If the shortlist quality regresses, rollback should be possible by reverting the new score path or lowering judgment candidate count without changing the judgment engine.
2. Post-deploy smoke tests must inspect one real scan artifact, not just passing tests.
3. If targeted retrieval is enabled, rollout should verify one promoted candidate actually receives bounded targeted evidence and one fallback case degrades cleanly.
4. If richer payloads are archived, rollout should verify archive size and render correctness immediately after deployment.

### Section 10: Long-Term Trajectory Review

**Reversibility:** `4/5`
**Debt items:** `3`

Findings:

1. This plan moves toward the right architecture. It creates a proper shortlist layer instead of pretending the LLM can discover structure from thin inputs.
2. The biggest remaining debt after phase 1 will be `biased intake`, `incomplete settlement-direct evidence scoring`, and `incomplete miss learning`.
3. If those become phase-2 work immediately after shipping this slice, the trajectory is sound. If they drift indefinitely, this will become a nice plumbing refactor with limited product impact.

### Section 11: Design & UX Review

`SKIPPED`

Reason:

- This plan has no meaningful UI scope.
- Any UI detection here would be a false positive from product-language keywords rather than actual interface work.

---

## NOT in Scope

- broad candidate-targeted retrieval across the full board
- a standalone retrieval platform or evidence scoring engine
- broader universe construction beyond the current single `volume24hr` intake path
- cross-event equivalent-expression discovery
- graph or vector infra for expression matching
- delivery, monitor, callback, or trading UX redesign

## What Already Exists

- live Gamma pull and CLOB book fetch path
- tradable/degraded/rejected prefilter path
- alert seed creation and judgment handoff
- feed-based evidence loading and strict/research downgrade flow
- source clients and registry plumbing that can support shallow shortlist retrieval
- archive rendering, Telegram delivery, heartbeat generation
- integration-test scaffolding and scan payload fixture

## Dream State Delta

If implemented as recommended, this plan leaves the runtime in a materially better place:

- not yet a true discovery engine
- but finally a real shortlist engine
- with richer executable context
- enough family structure to compare nearby expressions inside an event
- enough targeted retrieval to narrow evidence for promoted candidates
- enough accounting to understand misses and scanner behavior

It does **not** yet get us to:

- broad recall confidence
- fully settlement-direct evidence relevance confidence
- self-learning from missed opportunities

That is phase 2 and beyond.

## Error & Rescue Registry

| Codepath | Failure mode | Rescued? | Rescue action | User impact | Critical gap? |
| --- | --- | --- | --- | --- | --- |
| Gamma fetch | HTTP / JSON failure | Yes | empty scan result, heartbeat path | no alerts, degraded understanding | No |
| CLOB fetch | orderbook unavailable | Yes | degraded snapshot | degraded candidate quality | No |
| Feed load | feed source failure | Yes | degraded evidence reason | strict may downgrade | No |
| Ranking build | partial metadata | **No, plan unspecified** | should partial-score + log | silent ordering distortion | **Yes** |
| Family builder | malformed or oversized sibling data | **No, plan unspecified** | should truncate + log | silent context distortion | **Yes** |
| Shortlist retrieval | no hits / feed parse failure / over-broad retrieval | **No, plan unspecified** | should fall back + log degraded reason | silent evidence-quality drift | **Yes** |
| Judgment on richer context | malformed / empty model output | **No, plan unspecified** | should downgrade with explicit reason | ambiguous failure semantics | **Yes** |

## Failure Modes Registry

| Codepath | Failure mode | Rescued? | Test? | User sees? | Logged? |
| --- | --- | --- | --- | --- | --- |
| Gamma intake | upstream returns empty list | Yes | Partial | heartbeat / no opportunities | Partial |
| Rich snapshot normalization | optional fields missing | Partial | No | silent quality loss today | No |
| Family summary assembly | sibling set missing | Partial | No | weaker cleaner-expression analysis | No |
| Family summary assembly | sibling set too large | No | No | prompt bloat / truncation risk | No |
| Ranking | metadata absent or malformed | No | No | silent mis-ranking | No |
| Shortlist retrieval | no useful targeted hits | No | No | falls back unclearly or silently | No |
| Coverage accounting | misleading counters | No | Partial | false sense of coverage | Partial |
| Judgment | richer context causes malformed output | Partial | No | ambiguous downgrade or failure | Partial |
| Archive / render | payload shape drift | Partial | No | broken memo or heartbeat content | Partial |

Rows that remain `Rescued=No`, `Test=No`, and `Logged=No` are phase-1-critical planning gaps.

## Diagrams

### System Architecture

```text
Gamma + CLOB
  -> normalizer
  -> family summary
  -> ranking
  -> shortlist
  -> shortlist retrieval
  -> judgment context
  -> judgment engine
  -> render/archive/delivery
  -> coverage artifact
```

### Data Flow

```text
Market payload
  -> validate required ids
  -> normalize optional metadata
  -> enrich with book state
  -> attach family summary
  -> score and rank
  -> choose shortlist
  -> retrieve candidate-specific evidence
  -> build judgment context
  -> persist run/alert/archive outputs
```

### Error Flow

```text
Gamma/CLOB/feed/retrieval failure
  -> degrade snapshot or evidence
  -> continue scan
  -> mark run degraded
  -> heartbeat / research downgrade instead of silent failure
```

### Deployment Sequence

```text
add tests
  -> ship ranking + snapshot + family + retrieval changes behind config-safe defaults
  -> run fixture-backed scan
  -> inspect archive payload
  -> inspect coverage counters
  -> watch first live scan
```

### Rollback Flow

```text
shortlist or evidence quality regresses
  -> reduce judgment budget / disable retrieval / revert ranking path
  -> re-run smoke scan
  -> confirm alert artifacts return to prior shape
```

### Stale Diagram Audit

- No existing ASCII diagrams appear to require refresh in the touched plan area yet.

---

## CLAUDE SUBAGENT (CEO — strategic independence)

Status: `[subagent-only outside voice available]`

Independent findings:

1. The plan is solving an internal pipeline bottleneck, but the larger product question is still recall and learning from misses.
2. The plan assumes richer schema and ranking will improve discovery, but does not yet prove which signals actually change shortlist quality.
3. The strongest alternative, shortlist-targeted retrieval, was correctly surfaced because evidence relevance is already a known weakness.
4. Same-event family summaries help, but do not cover many of the best cross-bucket or cross-scope opportunities.
5. The moat is not richer plumbing alone. It is broader coverage, higher-relevance evidence, and a loop that learns from false negatives.

## CODEX SAYS (CEO — strategy challenge)

Status: `[unavailable]`

The external Codex strategy review was invoked, but the session lost its sampling stream before returning final findings. Treat this phase as `subagent-only` for cross-model consensus purposes.

## CEO DUAL VOICES — CONSENSUS TABLE

| Dimension | Claude subagent | Codex | Consensus |
| --- | --- | --- | --- |
| 1. Premises valid? | Partly assumed | N/A | N/A |
| 2. Right problem to solve? | Mostly yes, but recall framing is underpowered | N/A | N/A |
| 3. Scope calibration correct? | Baseline yes, but too conservative until retrieval was pulled in | N/A | N/A |
| 4. Alternatives sufficiently explored? | No, targeted retrieval and broader intake need clearer treatment | N/A | N/A |
| 5. Competitive / market risks covered? | Not enough | N/A | N/A |
| 6. 6-month trajectory sound? | Only if follow-up work is explicit | N/A | N/A |

Missing voice means `not confirmed`, not `accepted`.

Single-voice strategic concerns still matter and are surfaced at the premise gate below.

---

## Scope Expansion Decisions

Accepted:

- strengthen Workstream 5 into recall-first discovery accounting
- pull shallow shortlist-targeted retrieval into phase 1

Deferred:

- broader universe construction
- cross-event equivalent-expression discovery

Skipped:

- heavy graph / vector / infra expansion in phase 1

## CEO Completion Summary

```text
+====================================================================+
|            MEGA PLAN REVIEW — COMPLETION SUMMARY                   |
+====================================================================+
| Mode selected        | SELECTIVE EXPANSION                         |
| System Audit         | Discovery bottleneck is real, but recall    |
|                      | and evidence relevance remain partially open |
| Step 0               | Approach C selected, 2 expansions accepted,  |
|                      | premise gate passed                          |
| Section 1  (Arch)    | 3 issues found                              |
| Section 2  (Errors)  | 7 error paths mapped, 4 gaps                |
| Section 3  (Security)| 2 issues found, 0 High severity             |
| Section 4  (Data/UX) | 8 edge cases mapped, 3 under-specified      |
| Section 5  (Quality) | 3 issues found                              |
| Section 6  (Tests)   | Diagram produced, 6 gaps                    |
| Section 7  (Perf)    | 2 issues found                              |
| Section 8  (Observ)  | 5 gaps found                                |
| Section 9  (Deploy)  | 4 risks flagged                             |
| Section 10 (Future)  | Reversibility: 4/5, debt items: 3           |
| Section 11 (Design)  | SKIPPED (no UI scope)                       |
+--------------------------------------------------------------------+
| NOT in scope         | written (5 items)                           |
| What already exists  | written                                     |
| Dream state delta    | written                                     |
| Error/rescue registry| 7 methods, 4 critical gaps                 |
| Failure modes        | 9 total, 4 critical gaps                   |
| TODOS.md updates     | 0 items proposed in phase 1                |
| Scope proposals      | 3 proposed, 2 accepted                     |
| CEO plan             | written                                     |
| Outside voice        | ran (claude), codex unavailable            |
| Lake Score           | 2/2 major recommendations chose completeness|
| Diagrams produced    | 5 (system, data, error, deploy, rollback)  |
| Stale diagrams found | 0                                           |
| Unresolved decisions | 0                                           |
+====================================================================+
```

## Premise Gate

Resolved on `2026-04-22`.

User choice:

- `B` — pull a narrow form of candidate-targeted retrieval into phase 1 now.

Resulting phase-1 premise:

- Phase 1 is still a discovery foundation, not a full discovery engine.
- It now includes shallow shortlist-targeted retrieval for promoted candidates.
- Broader universe construction and full evidence scoring still remain deferred.

### Phase 1 transition summary

**Phase 1 complete.** Codex: unavailable. Claude subagent: 5 strategic concerns.

Consensus: no confirmed cross-model consensus because only one outside voice completed.

Premise gate passed. Phase 2 is skipped because there is no meaningful UI scope. Continue to Phase 3 Eng review.

<!-- AUTONOMOUS DECISION LOG -->
## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | CEO | Use `SELECTIVE EXPANSION` mode | Auto | P3, P5 | Existing runtime iteration, not a greenfield rewrite. Keep scope ambitious but bounded. | Full expansion, hold scope |
| 2 | CEO | Upgrade coverage work into recall-first discovery accounting | Auto | P1, P2 | Miss visibility is necessary for discovery quality and stays inside the current blast radius. | Generic ops-only counters |
| 3 | CEO | Accept user premise-gate choice `B` and move to `Approach C` | User override | P6 | Evidence relevance is already a bottleneck, so shortlist-targeted retrieval is now in phase 1. | Keeping retrieval deferred |
| 4 | Eng | Keep retrieval out of `board_scan.py` and place it after shortlist selection in `flows/scan.py` | Auto | P5 | Scan should remain structural; retrieval is orchestration. This keeps boundaries boring and testable. | Embedding retrieval in scan layer |
| 5 | Eng | Reuse `EvidenceItem` as the only evidence shape | Auto | P5 | A second evidence payload type would create avoidable merge and downgrade drift. | Raw retrieval dicts or parallel merge path |
| 6 | Eng | Proceed with current scope despite complexity smell | Auto | P2, P6 | User explicitly chose the broader premise, and the slice is still manageable if module count stays capped. | Mid-review scope reduction |
| 7 | Design | Skip Phase 2 design review | Auto | P5 | No meaningful UI scope was detected, so a design review would be noise, not signal. | Forcing a UI review on backend runtime work |
| 8 | Eng | Mark external Codex eng voice unavailable after repeated stalled runs | Auto | P6 | Two invocations failed to return clean findings, so the review proceeds in degraded single-outside-voice mode. | Waiting indefinitely for a stuck external run |

---

## Design Review (Phase 2 / Autoplan)

`SKIPPED`

Reason:

- The plan has no meaningful UI surface.
- Retrieval, ranking, coverage, and snapshot work all land in backend runtime modules and tests.

---

## Eng Review (Phase 3 / Autoplan)

**Review status:** `DONE_WITH_CONCERNS`

### Step 0: Scope Challenge

#### Existing code leverage

| Sub-problem | Existing code | Reuse call | Eng review note |
| --- | --- | --- | --- |
| Market intake | `scanner/gamma_client.py`, `scanner/board_scan.py` | Reuse | Keep intake in scan layer; do not add retrieval here |
| Book quality / execution fields | `scanner/clob_client.py`, `scanner/normalizer.py` | Reuse and extend | Good place for richer snapshot fields |
| Seed creation and persistence | `board_scan.py` | Reuse | Avoid turning `AlertSeed` into an untyped dumping ground |
| Evidence loading | `flows/shared.py`, `sources/news_client.py`, `sources/x_client.py` | Reuse | Shortlist retrieval should reuse `EvidenceItem`, not invent a second evidence shape |
| Judgment handoff | `flows/scan.py`, `build_judgment_context()` | Reuse | Best place for post-shortlist retrieval and evidence merge |
| Test harness | `runtime/tests/integration/test_scan_pipeline.py`, `runtime/tests/integration/test_runtime_flow.py`, `runtime/tests/unit/test_source_feed_loading.py` | Reuse and extend | Strong starting point, but not enough for shape drift and retrieval fallback |

#### Minimum set of changes

Must ship together:

- richer typed snapshot fields across `ScanCandidate` and `AlertSeed`
- family summary for same-event siblings
- dedicated ranking module
- shortlist-targeted retrieval that runs only after shortlist selection
- recall-aware coverage and rejection accounting
- unit + integration tests for serialization, retrieval fallback, and counters

Can still be deferred:

- broader universe construction
- cross-event equivalent-expression discovery
- claim-level dedupe and settlement-direct evidence scoring

#### Complexity check

Complexity smell triggered.

- 10+ existing files touched
- 3 new files already planned

**Auto-decision:** proceed as scoped, but with a hard engineering constraint:

- no new module beyond `scanner/ranking.py`, `sources/shortlist_retrieval.py`, and optional `scanner/family.py`
- retrieval stays in `flows/scan.py` orchestration, not `board_scan.py`
- no second evidence object shape

Reason:

- The user explicitly chose the broader premise.
- The scope is still lake-sized if boundaries remain sharp.

#### Search check

No novel framework primitive, queueing model, or concurrency abstraction is being introduced here. This is mostly a boundary-and-data-contract refactor around existing `httpx`, feed loaders, and runtime flow code. No additional external pattern search changed the architectural recommendation.

#### TODOS cross-reference

Current `TODOS.md` items on alert scorecards, prompt harnesses, and packaging boundaries do not block this plan.

This plan creates two new follow-up TODOs worth recording after review:

- broader universe construction strategy
- cross-event equivalent-expression discovery

#### Completeness check

The complete version is still justified here. Rich snapshot, retrieval fallback, and explicit counter semantics are all cheap compared with the cost of debugging a silent discovery regression later.

#### Distribution check

No new user-facing artifact type is introduced. No packaging or publish pipeline work is required for this slice.

### CLAUDE SUBAGENT (eng — independent review)

Independent findings:

1. **High:** schema changes are spread across `normalizer`, `board_scan`, `flows/shared`, and `flows/scan`, but the current boundary still relies on ad hoc dict payloads. Fix: introduce one explicit market-snapshot contract plus contract tests.
2. **High:** live scan already fetches CLOB books in a per-token loop before prefiltering. At 10x markets plus targeted retrieval, network latency and degraded-book rates become the first scale bottleneck. Fix: keep retrieval bounded and leave room for later batching.
3. **High:** missing-data semantics for bid/ask/mid, deadline, category, and outcome labels are underdefined. Fix: preserve per-field missing reasons and test partial-data ranking.
4. **Medium:** current test plan is too happy-path. Fix: add malformed payload, duplicate-expression, degraded-book, and fallback regression tests.
5. **Medium:** richer text fields and family summaries expand prompt-injection and payload-bloat risk. Fix: cap lengths, sanitize control characters, and separate raw text from rendered summaries.
6. **Medium:** current family identity is too question-text-driven. Fix: use stable ids first, question text second.

### CODEX SAYS (eng — architecture challenge)

Status: `[unavailable]`

An external Codex eng review was invoked twice. Both runs stayed stuck in repository loading / plugin warnings and did not return a clean final finding set. Phase 3 therefore proceeds with a single outside eng voice.

### ENG DUAL VOICES — CONSENSUS TABLE

| Dimension | Claude subagent | Codex | Consensus |
| --- | --- | --- | --- |
| 1. Architecture sound? | Mostly, but boundaries are too dict-shaped today | N/A | N/A |
| 2. Test coverage sufficient? | No | N/A | N/A |
| 3. Performance risks addressed? | Partly | N/A | N/A |
| 4. Security threats covered? | Partly | N/A | N/A |
| 5. Error paths handled? | No | N/A | N/A |
| 6. Deployment risk manageable? | Yes, if rollout stays config-safe | N/A | N/A |

Missing voice means `not confirmed`, not `accepted`.

### Section 1: Architecture Review

**Issues found:** `4`

#### Architecture diagram

```text
Gamma pull + CLOB books
  -> normalize_candidates
  -> family summary
  -> ranking.py
  -> shortlist selection
  -> flows/scan.py orchestrates shortlist retrieval
  -> _merge_evidence / build_judgment_context
  -> judgment engine
  -> archive + delivery + run accounting
```

Findings:

1. `board_scan.py` should stay structural. It should not own shortlist retrieval. Retrieval is flow orchestration and belongs after shortlist selection in `flows/scan.py`.
2. `ScanCandidate`, `AlertSeed`, `_seed_candidate_facts()`, and `_seed_executable_fields()` currently form a fragile implicit contract. That contract needs one explicit serializer boundary, otherwise scan and monitor will drift again.
3. `shortlist_retrieval.py` should emit normalized `EvidenceItem` objects plus degraded reasons. Do not return a second raw evidence shape that later needs another merge path.
4. `family.py` is optional only if it reduces coupling. If family logic stays tiny, keep it near normalization instead of creating a third orchestration hub.

### Section 2: Code Quality Review

**Issues found:** `4`

Findings:

1. Ranking ownership must move fully out of `_candidate_priority_key()` in `board_scan.py`. Leaving half the logic in-place guarantees future drift.
2. Event metadata extraction needs one source of truth. Do not parse title/tag/deadline in both `gamma_client.py` and `normalizer.py`.
3. `AlertSeed.evidence_seeds` is already an ad hoc dict tuple. Expanding it without a typed adapter will make retrieval plumbing brittle.
4. Counter semantics such as `scanned_events = total_markets` already drifted once. Coverage fields need explicit names before new retrieval counters are added.

### Section 3: Test Review

**Diagram produced:** `Yes`
**Gaps identified:** `6`

Test framework:

- runtime: `pytest`
- no planned `skills/prediction-market-analysis/SKILL.md` edits in this slice, so no skill-eval suite expansion is required yet
- runtime contract fixtures and integration tests do need expansion because judgment input shape changes

#### Test diagram

```text
CODE PATH COVERAGE
===========================
[+] scan_board prefilter + counters
    ├── [★★★ TESTED] Current tradable/degraded/rejected accounting
    │               -> runtime/tests/integration/test_scan_pipeline.py
    ├── [GAP]       Retrieved-shortlist counters
    └── [GAP]       Corrected run counter semantics (`scanned_events` naming)

[+] run_scan live orchestration
    ├── [★★★ TESTED] Seed persistence and max_judgment_candidates cap
    │               -> runtime/tests/integration/test_scan_pipeline.py
    ├── [GAP]       Rich snapshot survives scan -> seed -> candidate_facts/executable_fields
    ├── [GAP]       Family summary survives scan -> judgment context
    └── [GAP]       Partial metadata does not silently discard candidates

[+] feed loading and runtime evidence path
    ├── [★★★ TESTED] Configured feed loading and strict downgrade semantics
    │               -> runtime/tests/integration/test_runtime_flow.py
    ├── [★★★ TESTED] News/X feed client normalization
    │               -> runtime/tests/unit/test_source_feed_loading.py
    ├── [GAP]       shortlist-targeted retrieval input generation
    ├── [GAP]       retrieval no-hit / parse-failure fallback
    └── [GAP]       targeted evidence caps and payload-size protection

USER / OPERATOR FLOW COVERAGE
===========================
[+] scan -> shortlist -> retrieval -> judgment -> archive
    ├── [GAP] [→INTEGRATION] promoted candidate gets targeted evidence
    ├── [GAP] [→INTEGRATION] retrieval degraded but run remains non-silent
    └── [GAP] [→INTEGRATION] archive / heartbeat still render correctly with new counters

─────────────────────────────────
COVERAGE: base paths covered, new phase-1 paths undercovered
GAPS: 6 critical new-path tests
─────────────────────────────────
```

Required new tests:

1. `runtime/tests/integration/test_scan_pipeline.py`
   Add a contract test proving best bid / ask / mid, deadline/category, and family summary survive scan -> seed -> context.
2. `runtime/tests/unit/test_scan_ranking.py`
   Add deterministic scoring tests including missing-deadline, missing-category, and family-richness cases.
3. `runtime/tests/unit/test_shortlist_retrieval.py`
   Add retrieval-input, retrieval-cap, and retrieval-fallback tests.
4. `runtime/tests/integration/test_runtime_flow.py`
   Add one integration path where targeted retrieval enriches promoted evidence and one where retrieval fails and falls back cleanly.
5. `runtime/tests/unit/test_source_feed_loading.py`
   Extend with candidate-filtered feed narrowing and over-broad result trimming.
6. `runtime/tests/unit/test_settings.py`
   Add config coverage for any new retrieval limits / toggles.

### Section 4: Performance Review

**Issues found:** `3`

Findings:

1. `board_scan._run_live_scan()` already fetches one CLOB book per token before prefiltering. This is the first 10x bottleneck, not Python ranking math.
2. Shortlist retrieval fanout must be bounded by both `number_of_promoted_candidates` and `max_items_per_candidate`. Otherwise latency and prompt size will explode together.
3. Family summaries and targeted evidence both increase context size. The plan must include strict caps before archive rendering and judgment submission.

### Failure Modes

| Codepath | Failure mode | Test? | Error handling? | User sees? | Critical gap? |
| --- | --- | --- | --- | --- | --- |
| rich snapshot serialization | missing bid/ask/deadline/category silently dropped | No | Partial | silent ranking distortion | **Yes** |
| family summary assembly | sibling set oversized or malformed | No | No | prompt/context bloat | **Yes** |
| ranking | partial metadata over-penalizes good candidate | No | No | silent shortlist regression | **Yes** |
| shortlist retrieval | no-hit or parse failure falls through unclearly | No | No | inconsistent evidence quality | **Yes** |
| run accounting | counter names drift again | No | Partial | false coverage confidence | No |
| archive/render | larger payload shape breaks memo output | Partial | Partial | broken alert artifact | No |

### Parallelization Strategy

#### Dependency table

| Step | Modules touched | Depends on |
| --- | --- | --- |
| Rich snapshot + family summary | `scanner/`, `flows/shared.py` | — |
| Ranking module + shortlist selection | `scanner/` | Rich snapshot + family summary |
| Shortlist retrieval + flow merge | `sources/`, `flows/scan.py`, `flows/shared.py` | Ranking module + shortlist selection |
| Coverage counters + integration tests | `scanner/`, `flows/`, `runtime/tests/` | Ranking + retrieval merge |

#### Parallel lanes

- Lane A: rich snapshot + family summary -> ranking (sequential, shared `scanner/`)
- Lane B: shortlist retrieval scaffolding (can start in parallel conceptually, but merges only after snapshot field names are fixed)
- Lane C: coverage + tests after A and B merge

#### Execution order

- Launch early scanner boundary work first.
- Start retrieval scaffolding once snapshot field names are fixed.
- Merge both before coverage and integration-test work.

#### Conflict flags

- Lanes A and B both converge on `flows/shared.py` semantics.
- Lanes B and C both touch `flows/scan.py` and integration tests.
- Practical recommendation: limited parallelization only. This is mostly sequential with a short sidecar lane for retrieval scaffolding.

### Cross-Phase Themes

1. Data-contract drift is the main landmine. The same problem showed up in both CEO and Eng review.
2. Retrieval is valuable only if it stays narrow, typed, and post-shortlist.
3. Bias and recall are still the main strategic debt even after this slice.
4. Observability and tests matter more here than clever ranking heuristics.

### Eng Completion Summary

- Step 0: Scope Challenge — scope accepted as-is, with hard module-boundary constraints
- Architecture Review: 4 issues found
- Code Quality Review: 4 issues found
- Test Review: diagram produced, 6 gaps identified
- Performance Review: 3 issues found
- NOT in scope: existing section remains current
- What already exists: existing section remains current
- TODOS.md updates: 2 items proposed
- Failure modes: 4 critical gaps flagged
- Outside voice: ran (claude), codex unavailable
- Parallelization: 3 lanes, 1 limited-parallel / 2 effectively sequential
- Lake Score: 3/3 major recommendations chose the complete option

## Final Approval Gate

### Review verdict

- CEO Review: `DONE_WITH_CONCERNS`
- Design Review: `SKIPPED (no UI scope)`
- Eng Review: `DONE_WITH_CONCERNS`

### Recommendation

Approve the plan **with the engineering constraints captured in Phase 3**.

That means:

1. Retrieval stays post-shortlist in `flows/scan.py`, not in `board_scan.py`.
2. Snapshot and evidence contracts become explicit and typed enough to stop scan/judgment drift.
3. The six new test gaps in Eng Review are treated as required plan scope, not nice-to-have.
4. Retrieval, family summary, and coverage counters all get hard caps / degraded semantics before implementation.

### Remaining known debt after approval

- biased intake / universe construction
- settlement-direct evidence scoring and claim dedupe
- cross-event equivalent-expression discovery

### Approval posture

If approved, the next stage under gstack is `ship`, based on this revised plan rather than the original narrower phase-1 slice.
