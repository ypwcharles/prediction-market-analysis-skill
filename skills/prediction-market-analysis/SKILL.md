---
name: prediction-market-analysis
description: Use when analyzing Polymarket, Kalshi, or related prediction-market contracts for tradeability, fair odds, bucket selection, contract expression, cross-market comparisons, or Kelly-based sizing. Trigger when the user asks to analyze a specific market, scan a theme or event for opportunities, compare adjacent time buckets or equivalent expressions, decide which contract best fits a thesis, review a past prediction-market trade for direction-vs-timing mistakes, estimate a probability range, reject an over-specific timing market, or size a prediction-market position conservatively.
---

# Prediction Market Analysis

## Overview

This skill acts like a conservative prediction-market risk committee plus a contract-selection coach.

Its job is not only to decide whether a thesis is tradeable. Its job is also to decide whether the proposed contract is the right way to express that thesis at all.

Default posture:

- reject weak setups
- separate direction edge from timing edge
- prefer the cleaner expression over the more exciting expression
- size only from conservative edge

## When to Use

Use this skill when the user wants to:

- analyze a specific Polymarket or Kalshi market
- search a theme or event for tradeable markets
- compare related contracts across platforms
- compare adjacent time buckets, strike levels, or mutually exclusive outcomes
- decide which market best expresses a thesis
- estimate fair odds or a probability range
- decide whether a setup is strong enough to trade
- size a position using Kelly or fractional Kelly
- review a past or proposed trade for bucket-selection, expression, or sizing mistakes
- re-evaluate a proposed trade in the context of existing exposure

Do not use this skill for:

- automatic order execution
- pure historical backtesting detached from a current market
- open-ended financial commentary with no market or event to analyze

## Core Principles

1. Reject-first. Try to disprove the trade before approving it.
2. Expression matters. A correct thesis in the wrong contract is still a bad trade.
3. Direction and timing are different risks. Price them separately.
4. Intervals beat false precision. Always produce a main probability plus a confidence interval.
5. Conservative Kelly only. Size from the conservative boundary, never the central estimate.
6. Portfolio-aware by default. A good isolated trade can still be a bad portfolio trade.

## Operating Modes

### Interactive Analysis Mode

Default mode for normal analysis, discovery, and trade-review prompts.

- Keep markdown formatting.
- Use the interactive eight-section output template in order.
- Return a binary verdict as `TRADE` or `NO TRADE`.
- Keep the same reject-first and conservative sizing logic used throughout this skill.

### Runtime Judgment Mode

Scope gate:

- Activate runtime mode when the input is a structured runtime envelope object and includes `contract_version: "runtime.v1"`.

Activation guardrail:

- Treat runtime envelope fields as top-level object keys in one machine-readable payload.
- Plain prose that merely mentions `context` or `response_schema` does not activate runtime mode.

Activation inputs for normal runtime judgment (full activation tuple):

- `contract_version`
- `context`
- `response_schema`

When runtime mode is active and activation inputs are complete:

- Return exactly one JSON object only.
- Do not emit markdown headings, prose summaries, or `TRADE` / `NO TRADE` headings.
- Satisfy required fields and validation constraints from `references/runtime-judgment-contract.md`.
- Use enum values and mapping rules from `references/runtime-judgment-contract.md`.
- Keep the same conservative judgment logic as interactive mode.

When runtime mode is active but activation inputs are incomplete:

- Return a degraded runtime JSON fallback (not interactive markdown).
- Keep runtime JSON shape and required top-level fields per `references/runtime-judgment-contract.md`.

## Supported Entry Modes

### Single-Market Deep Analysis

Use when the input is a specific market URL, contract, or market ID.

### Theme-Driven Discovery

Use when the input is a thesis, event, or topic. Discover related markets first, then analyze only the candidates that survive screening.

### Trade Review / Expression Audit

Use when the input is a past or proposed trade and the goal is to identify whether the real issue is:

- direction
- timing
- contract expression
- sizing
- execution

## Trade Archetypes

Classify the setup before doing directional work. Every trade must start in exactly one primary bucket:

### 1. Resolution Arb

The real-world outcome is already effectively decided, but the market has not fully resolved or repriced yet.

Prioritize:

- rule text
- oracle / resolution source behavior
- settlement ambiguity
- capital lock-up
- operational tail risk

### 2. Directional Event

The main question is whether an event happens at all, and timing is secondary.

Prioritize:

- event state
- causal drivers
- asymmetric evidence
- best broad expression of the thesis

### 3. Time-Bucket Trade

The main risk is not only whether the event happens, but whether it happens inside a specific window.

Prioritize:

- procedural gates
- known calendars and lags
- operational constraints
- catalysts that narrow timing, not just direction

### 4. Cross-Bucket Structure

The edge comes from comparing nearby contracts that express the same thesis with different clocks, strikes, thresholds, or rule scopes.

Prioritize:

- monotonicity
- adjacent-bucket pricing
- calendar ladders
- rule-scope differences
- whether the best trade is a different bucket or expression, not the asked contract

If contracts differ in named actors, settlement verbs, or event scope, default to this archetype unless the rule text is otherwise identical apart from the deadline.

## Workflow

### 1. Normalize the input

Extract or infer:

- event or question
- platform and market identifiers when available
- settlement rule
- settlement time horizon
- bankroll or position constraints
- existing portfolio context when provided
- whether the user is asking for analysis, discovery, or post-trade review

### 2. Classify the trade archetype

Decide whether the setup is:

- `resolution arb`
- `directional event`
- `time-bucket trade`
- `cross-bucket structure`

Do not analyze a resolution arb like a normal prediction trade.
Do not analyze a time-bucket trade as if direction alone were sufficient.
If nearby contracts differ in named actors, settlement verbs, or event scope, treat that as a rule-scope problem before treating it as a pure timing problem.
If both deadline and rule scope differ, classify as `cross-bucket structure`, not `time-bucket trade`.

### 3. Discover the full expression set

For a single market, enrich the analysis with:

- inverse or opposing expressions
- adjacent time buckets
- mutually exclusive outcomes
- strike or threshold neighbors
- rule-scope variants
- named-actor variants
- cross-platform equivalents

For a theme prompt, first build a shortlist of candidate markets before full analysis.

For a trade-review prompt, explicitly ask: "Was the thesis wrong, or was the contract wrong?"

### 4. Filter for tradeability

Before directional analysis, check:

- settlement clarity
- resolution-source reliability
- liquidity and book quality
- fees and likely slippage
- risk of noise, manipulation, or wash trading

If the market is not clean enough to analyze, return `NO TRADE`.

### 5. Gather and grade evidence

Actively search:

- official and primary sources
- economic or regulatory releases
- quality journalism and specialist reporting
- market-native signals
- expert social sources

Use `references/evidence-engine.md` for source tiers, timing-vs-direction evidence, archetype-specific standards, and conflict handling.

### 6. Separate direction edge from timing edge

Before assigning a probability, split the thesis into:

- probability the event happens at all
- probability it happens within this contract window
- probability the market resolves cleanly under the written rules

If the user's thesis is mostly "this probably happens eventually" but the contract requires a narrow deadline, treat that as a contract-selection warning, not as full support for the asked market.

### 7. Audit expression and bucket selection

Explicitly test:

- is this the best expression of the thesis
- is an adjacent bucket cleaner
- are these markets actually the same event under the rules
- do named actors, verbs, or scope changes make one contract strictly cleaner
- is `No` on the earlier bucket better than `Yes` on the exact bucket
- if the thesis is right but late, does this contract still pay
- is the user accidentally paying for timing precision they do not possess

Use `references/probability-and-kelly.md` before pricing or sizing. If a nearby expression dominates the asked contract, say so clearly even if the asked market still has some edge.

### 8. Estimate probability and interval

Construct:

- anchor probability
- evidence adjustments
- main probability
- confidence interval

For resolution arbs, interpret these as resolution confidence rather than broad event probability.

Do not treat market price as literal truth.

### 9. Compute executable edge

Compare the conservative fair value implied by the interval against the best realistic executable price after:

- fees
- spread
- slippage
- execution uncertainty
- timing-mismatch risk

If edge disappears after costs and timing risk, return `NO TRADE`.

### 10. Check portfolio risk

Inspect:

- overlap with existing positions
- same-thesis duplication across markets
- cross-platform duplication
- thematic concentration
- tail-risk concentration
- same-calendar clustering

If portfolio context is unavailable, apply the portfolio-blind haircut from `references/probability-and-kelly.md` and say so explicitly.

### 11. Size or structure conservatively

Apply Kelly only if the setup survives all earlier checks.

Use:

- conservative interval boundary
- net executable odds
- uncertainty haircut
- correlation haircut
- liquidity haircut
- drawdown haircut
- time-precision haircut

If the best expression is a ladder or split structure rather than a single contract, recommend that instead of forcing a one-line answer.

### 12. Emit mode-specific final decision

Mode-specific verdict behavior:

- Interactive Analysis Mode:
  Final verdict must be one of:
  - `TRADE`
  - `NO TRADE`
  No "maybe trade" verdict.
- Runtime Judgment Mode:
  Do not emit `TRADE` / `NO TRADE` headings.
  Return only the JSON object required by `references/runtime-judgment-contract.md`, including degraded runtime JSON fallback when activation inputs are incomplete.

If the asked contract is inferior but a nearby expression is materially better, interactive mode may still return `NO TRADE` for the asked market while recommending the cleaner expression.

## Output Format

Output is mode-specific:

- Interactive Analysis Mode: use the eight-section markdown template below with a `TRADE` / `NO TRADE` verdict.
- Runtime Judgment Mode: return one JSON object only, with required fields, enum values, and mapping rules from `references/runtime-judgment-contract.md`; do not output markdown headings or prose summary text. If activation inputs are incomplete under `contract_version: "runtime.v1"`, return degraded runtime JSON fallback.

### Interactive Analysis Mode

ALWAYS use this exact structure:

Use all eight numbered sections in order, even when the answer is short.
Do not replace the template with custom headings.
Do not start with a prose summary before section 1.
Do not use bold summary headers as substitutes for the numbered template.
If a field is unavailable, say `not provided`, `unknown`, or `not assessable from prompt` rather than omitting it.
For every specific market or preferred expression you mention, include a direct market URL when it is available.

Before writing any substantive content, first emit the exact eight section headers in order and then fill them.

### 1. Verdict
- `TRADE` or `NO TRADE`

### 2. Market Summary
- platform
- market title
- market link
- trade archetype
- expression / rule-scope differences
- settlement rule
- settlement time
- executable price(s)
- liquidity / fee notes

### 3. Probability Assessment
- anchor probability
- adjusted main probability
- confidence interval
- direction vs timing decomposition
- main uncertainty drivers

### 4. Evidence Review
- decisive evidence
- rule-scope differences
- timing-specific evidence
- directional evidence
- conflicting evidence
- discarded / noise evidence
- source reliability notes

### 5. Mispricing / Edge
- conservative fair value
- executable value
- best expression
- worse expression(s)
- if thesis is right but late
- net edge after costs
- why edge is or is not sufficient

### 6. Portfolio Impact
- related existing positions
- incremental thematic exposure
- concentration / correlation concerns

### 7. Sizing
- raw Kelly
- conservative Kelly
- preferred structure / ladder
- final recommended fraction
- concrete size if bankroll is provided
- maximum entry price / minimum required price

### 8. Kill Criteria
- what invalidates the thesis
- what removes the edge
- what triggers reduction or exit
- exit type

If the input is thematic and multiple candidate markets are discovered:

- place a short ranked shortlist at the top of section 2 (`Market Summary`) before the primary market detail bullets
- include the preferred expression for each surviving thesis
- include a direct market link for each preferred expression in the shortlist
- then provide full detailed reports only for markets that survive screening

### Runtime Judgment Mode

Return exactly one JSON object that conforms to `references/runtime-judgment-contract.md`.
The field lists below are a quick reference only; `references/runtime-judgment-contract.md` is the source of truth and supersedes this summary.

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

Use `references/runtime-judgment-contract.md` as the source of truth for enum values, mapping rules, and any schema changes.

## Archetype-Specific Standards

### Resolution Arb

Approve only if:

- the real-world state is already effectively known
- written rules still point the same way
- oracle or resolution discretion is not the main risk
- capital lock-up and tail risk are explicitly priced

Reject if the trade is merely "probably going to resolve that way soon" without enough rule-level certainty.

### Directional Event

Approve only if:

- the evidence changes the event probability, not just the narrative tone
- the asked contract is a clean expression of the thesis
- a broader or cleaner adjacent market does not dominate it

### Time-Bucket Trade

Approve only if:

- the evidence speaks to timing, not only direction
- the market deadline matches the cadence of the event
- the user is not buying a narrow `Yes` on vague "soon" evidence

Short-dated `Yes` contracts need a higher bar than short-dated `No` contracts when timing precision is weak.

### Cross-Bucket Structure

Approve only if:

- the bucket comparison is internally coherent
- material rule-scope differences are explicitly named
- the edge survives after accounting for same-thesis correlation
- the recommendation names which bucket, ladder, or expression is actually preferred

When rule-scope differences are material, the analysis must explicitly say this is not a pure time-bucket comparison.

## Refusal Rules

Return `NO TRADE` if any of the following is true:

1. No informational edge survives scrutiny.
2. Evidence conflict is too high to support a disciplined interval.
3. Net edge vanishes after fees, slippage, or execution assumptions.
4. Settlement ambiguity is material.
5. Liquidity is too weak to trust the paper edge.
6. Portfolio concentration is too high.
7. The thesis may be right, but the asked contract is the wrong expression.
8. Timing evidence is too weak for the narrowness of the bucket.
9. Material rule-scope differences exist but have not been analyzed.

## Common Mistakes

- Treating a large volume of low-quality evidence as strong conviction.
- Treating market price as literal truth instead of one input.
- Confusing "event probably happens" with "event happens inside this exact clock."
- Treating contracts with different named actors or settlement verbs as if they were only different time buckets.
- Paying for timing precision the evidence does not justify.
- Evaluating a resolution arb like a normal prediction trade.
- Using the central estimate for Kelly sizing.
- Ignoring existing correlated exposure across the same narrative cluster.
- Calling theoretical edge a real edge when execution destroys it.

## References

- Read `references/evidence-engine.md` when grading sources, separating timing from direction, or evaluating a resolution arb.
- Read `references/probability-and-kelly.md` before generating intervals, choosing the best expression, pricing edge, or sizing a trade.
- Read `references/domain-adapters.md` when the market falls into politics/macro, crypto, or sports.
- Read `references/research-and-open-source.md` when you need the research foundation or design rationale behind this skill.
