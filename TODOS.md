# TODOS

## Deferred From Runtime Hardening Review

### 1. Alert quality scorecard and operator-trust metrics

- What: Add a lightweight scorecard for false positives, stale alerts, degraded-run rate, and operator time-to-triage.
- Why: The hardening plan improves trust plumbing, but it still does not measure whether the alerts are actually getting better.
- Pros: Makes the runtime self-measuring and gives future product decisions real feedback loops.
- Cons: Adds instrumentation and review work that is outside the smallest hardening slice.
- Context: Both CEO and engineering review phases independently flagged that runtime cleanliness without quality measurement does not create a moat. Start from `.runtime-data/sqlite/`, run summaries, and alert/archive metadata.
- Effort estimate: M human / S with CC+gstack
- Priority: P1
- Depends on / blocked by: Contract SSOT, stable run outcomes, and truthful health / degraded surfacing

### 2. Prompt and skill eval harness beyond JSON syntax / parity

- What: Add a repo-native harness that can exercise `skills/prediction-market-analysis/SKILL.md` and `evals/evals.json` automatically instead of relying on fixture syntax and manual review.
- Why: The repo currently lacks a first-class prompt-eval path for the skill surface, so runtime contract hardening still leaves part of the user-facing behavior weakly guarded.
- Pros: Makes skill changes safer and reduces the gap between runtime parity and real prompt behavior.
- Cons: Requires choosing an evaluation runner and maintaining prompt fixtures over time.
- Context: During the review, the runtime test surface was strong, but the prompt / skill surface was not. Start from `evals/evals.json` and the `evals/runtime-v1-*.json` fixtures.
- Effort estimate: M human / S with CC+gstack
- Priority: P1
- Depends on / blocked by: Canonical contract parity work so the harness has a stable target

### 3. Packaging boundary between reusable skill and operational runtime

- What: Decide whether the reusable judgment skill and the alert runtime should remain in one repo long-term or split into separate packages / repos.
- Why: The current repo can work after hardening, but the boundary is still conceptually fuzzy and will matter more as the runtime grows.
- Pros: Reduces future drift and clarifies ownership if the product surface expands.
- Cons: Prematurely doing it now would slow shipping and add migration cost with little immediate user value.
- Context: Both review phases flagged the boundary as real, but not urgent enough for this hardening cycle. Revisit after the runtime is self-consistent and measured.
- Effort estimate: L human / M with CC+gstack
- Priority: P2
- Depends on / blocked by: Successful completion of current hardening plan and stable alert-quality instrumentation

## Deferred From Scan Discovery Foundation Autoplan

### 1. Multi-entry universe construction beyond `volume24hr`

- What: Replace the single top-volume Gamma intake with a broader universe-construction strategy, such as category buckets, deadline buckets, or multiple board slices.
- Why: Ranking and shortlist retrieval can only improve contracts that were actually fetched. The current runtime still starts from a biased universe.
- Pros: Improves recall, reduces hot-market crowding bias, and increases the chance of finding cleaner middle-board opportunities.
- Cons: Adds more HTTP calls, more candidate bookkeeping, and a larger calibration surface.
- Context: Both CEO and Eng review phases agreed that biased intake remains the biggest debt after this phase. Start from `runtime/src/polymarket_alert_bot/scanner/gamma_client.py` and `runtime/src/polymarket_alert_bot/scanner/board_scan.py`.
- Effort estimate: M human / S with CC+gstack
- Priority: P1
- Depends on / blocked by: Stable ranking, truthful coverage counters, and clear shortlist semantics from the current phase

### 2. Cross-event equivalent-expression discovery

- What: Add logic to detect cleaner expressions across related events, not just same-event siblings.
- Why: Same-event family summaries recover only part of the contract-selection wedge. Many of the best alternatives live across events, buckets, or rule-scope variants.
- Pros: Better expression selection, more opportunities to reject the asked contract in favor of a cleaner nearby one, and stronger use of the prediction-market-analysis skill's actual methodology.
- Cons: Higher ambiguity, more false matches, and likely need for stronger identity / dominance logic.
- Context: The current phase intentionally keeps family logic same-event only. Revisit after family summaries, retrieval, and coverage accounting are stable.
- Effort estimate: L human / M with CC+gstack
- Priority: P2
- Depends on / blocked by: Stable same-event family summaries plus a stronger evidence / rule-scope comparison layer
