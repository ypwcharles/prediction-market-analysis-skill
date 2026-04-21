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
