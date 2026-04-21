# Prediction Market Analysis Skill Design

**Date:** 2026-04-10

**Goal:** Design a conservative, semi-automated analysis skill for prediction markets such as Polymarket and Kalshi that can determine whether a market offers a tradeable edge, reject weak setups by default, and size approved trades using a conservative Kelly-based framework.

## Problem Statement

Prediction markets create a dangerous failure mode for LLM-driven analysis: it is easy to collect a large amount of plausible-sounding information, overstate confidence, ignore execution reality, and recommend trades with negative net expectancy. The skill must be designed to solve the opposite problem. Its primary job is not to "find a trade" but to decide whether enough evidence, market structure, and portfolio capacity exist to justify a trade at all.

This skill should support two entry modes:

1. **Single-market deep analysis**
   Input is a specific market URL, market ID, or contract.
2. **Theme-driven market discovery**
   Input is an event, question, topic, or thesis. The skill discovers relevant markets and analyzes them comparatively.

Both modes must converge into one shared decision engine.

## Success Criteria

The skill is successful if it:

1. Produces structured, auditable analysis rather than vague trade opinions.
2. Rejects low-quality opportunities by default.
3. Outputs a main probability plus a confidence interval, not a single fragile point estimate.
4. Sizes only from the conservative edge implied by the confidence interval.
5. Incorporates existing portfolio exposure before sizing.
6. Remains platform-agnostic at the core while allowing market-specific extensions.

## Initial Platform Scope

V1 should be designed around:

1. Polymarket
2. Kalshi

The architecture should remain extensible to other prediction markets later, but the first implementation plan should assume these two platforms as the primary targets.

## Non-Goals

These are explicitly out of scope for v1:

1. Automatic order execution.
2. High-frequency market making or quote management.
3. Fully black-box probability models.
4. A guarantee of profitable trading.
5. Replacing human judgment on ambiguous settlement-rule interpretation.

## Core Design Principles

1. **Reject-first, trade-second**
   The skill should try to disprove the trade before it approves it.
2. **Net edge over paper edge**
   A trade exists only if edge remains after fees, slippage, liquidity, and execution uncertainty.
3. **Probability intervals over false precision**
   Main probability and confidence interval are both required outputs.
4. **Conservative Kelly only**
   Sizing must use the conservative boundary, not the central estimate.
5. **Portfolio-aware decisions**
   Trades are evaluated in the context of related positions and thematic exposure.
6. **General core, domain adapters**
   Politics, crypto, sports, and other categories should share a common engine with pluggable market-specific evidence rules.

## User-Facing Role of the Skill

The skill should behave like a conservative risk committee with real-time research capability.

When triggered, it should:

1. Gather the relevant market and evidence context.
2. Judge whether the market is analyzable and tradeable.
3. Estimate fair probability using structured reasoning.
4. Compare fair value with executable market prices.
5. Check portfolio risk and concentration.
6. Either:
   - output `NO TRADE`, with explicit reasons, or
   - output `TRADE`, with direction, probability range, edge explanation, and conservative Kelly sizing.

It should never feel pressure to produce an actionable trade if the evidence is weak.

## Triggering Conditions

The final skill should trigger when the user asks to:

1. Analyze a specific Polymarket, Kalshi, or other prediction market.
2. Evaluate whether a contract is mispriced.
3. Search for tradeable opportunities on a theme or event.
4. Compare related markets across platforms.
5. Estimate fair odds and size a position using Kelly or fractional Kelly.
6. Assess whether an existing or proposed position should be entered, resized, or rejected.

## Inputs

The skill must accept the following forms of input:

1. A direct market URL.
2. A market or contract identifier.
3. A natural-language thesis or event prompt.
4. Optional existing portfolio / exposure information.
5. Optional bankroll or capital constraints.
6. Optional user-supplied probability assumptions, if the user wants to override part of the model.

## Output Contract

Every run must produce a structured report with the following sections.

If the input is thematic and multiple candidate markets are discovered, the output should contain:

1. a short ranked shortlist of candidate markets, and
2. a full detailed report for each market that survives the initial screening threshold

Only markets that survive full analysis should receive a final `TRADE` or `NO TRADE` verdict.

### 1. Verdict

- `TRADE` or `NO TRADE`

### 2. Market Summary

- platform
- market title
- settlement rule
- settlement time
- current executable price(s)
- liquidity / fee notes

### 3. Probability Assessment

- anchor probability
- adjusted main probability
- confidence interval
- most important uncertainty drivers

### 4. Evidence Review

- decisive evidence
- directional evidence
- conflicting evidence
- discarded / noise evidence
- source reliability notes

### 5. Mispricing / Edge

- conservative fair value
- current executable value
- net edge after cost assumptions
- why edge is or is not large enough

### 6. Portfolio Impact

- related existing positions
- incremental thematic exposure
- concentration and correlation concerns

### 7. Sizing

- raw Kelly
- conservative Kelly
- recommended fraction after risk haircuts
- final suggested position size
- position size format:
  - if bankroll is provided, give both bankroll fraction and concrete size
  - if bankroll is not provided, give bankroll fraction only
- maximum entry price / minimum required price

### 8. Kill Criteria

- what invalidates the thesis
- what removes the edge
- what would trigger reduction or exit

## Unified Decision Pipeline

This is the core workflow that both input modes must follow.

### 1. Input Normalization

Convert the user prompt into a structured analysis object:

- event / question
- market(s)
- settlement rule
- time horizon
- user constraints

### 2. Candidate Market Discovery

If the prompt is thematic:

- discover relevant markets across supported platforms
- discover opposing markets, related time buckets, and substitute expressions of the same event

If the prompt is a specific market:

- enrich it with related and cross-platform comparison markets

### 3. Tradeability Filter

Before any directional analysis, judge whether the market deserves analysis:

- settlement-rule clarity
- resolution-source reliability
- available liquidity
- fee burden
- slippage / execution feasibility
- manipulation / wash-trading risk
- ambiguity of mapping between event and contract resolution

Failure here should usually produce `NO TRADE`.

### 4. Evidence Collection and Grading

Actively gather:

- official / primary sources
- economic data
- company / regulatory disclosures
- mainstream reporting
- specialist reporting / research
- X / expert social feeds
- related market prices and order-flow context

Every item should be graded.

### 5. Thesis Construction

Organize evidence into:

- evidence for the event / outcome
- evidence against the event / outcome
- evidence that truly changes probability
- evidence that is informative but not decisive
- noise or duplicated reporting

The skill must explicitly search for disconfirming evidence.

### 6. Probability Generation

Generate:

- an anchor probability
- evidence-driven adjustments
- a main probability
- a confidence interval

Do not let the market price become the only anchor by default.

### 7. Edge Computation

Compare the conservative fair price implied by the confidence interval with the best executable market price after:

- fees
- slippage
- execution uncertainty
- spread / fill assumptions

### 8. Portfolio Risk Check

Estimate:

- incremental exposure
- overlap with existing positions
- thematic concentration
- tail-risk concentration

### 9. Conservative Kelly Sizing

Apply Kelly only if the trade has survived all previous filters.

Sizing must use:

- conservative probability boundary
- net executable odds
- uncertainty haircut
- correlation haircut
- liquidity haircut
- drawdown haircut

### 10. Final Decision

Output only one of two states:

1. `NO TRADE`
2. `TRADE`

No hedged "maybe trade" final verdict.

## Evidence Architecture

### Evidence Tiers

The skill should use these source tiers.

#### L1: Primary / Resolution-Relevant Sources

- official announcements
- legal / regulatory filings
- original economic releases
- company formal disclosures
- court documents
- official sports / event sources
- raw on-chain or market-native source data

#### L2: High-Quality Secondary Sources

- major media
- specialist reporters
- respected data vendors
- reputable research institutions

#### L3: Market-Native Signals

- market prices
- cross-platform prices
- order-book conditions
- large-trade imbalance
- related market movement

#### L4: High-Quality Social Signals

- expert X accounts
- trusted domain commentators
- fast-reporting specialists

#### L5: Low-Quality / Narrative Sources

- anonymous commentary
- low-quality reposts
- derivative summaries
- marketing content
- non-verifiable screenshots or charts

### Evidence Scoring Dimensions

Every collected item should be assessed on:

- source quality
- directness to settlement
- timeliness
- uniqueness
- falsifiability
- likely impact on resolution

### Evidence Use Rules

1. Low-tier evidence must not dominate the main probability.
2. Repeated reporting of the same underlying fact does not count as independent evidence.
3. Market-based evidence can influence probability, but should not override stronger primary evidence without explanation.
4. Evidence that is true but not resolution-relevant should not move the estimate.

## Probability Engine

### Probability Construction Method

The probability engine should use:

1. **Anchor**
   Candidate anchors may include:
   - current market consensus
   - cross-platform consensus
   - historical base rate
   - domain-specific prior
   - related market-implied probability

2. **Evidence Adjustments**
   Each meaningful evidence item shifts the anchor with explicit reasoning.

3. **Consistency Checks**
   The output is tested against:
   - related markets
   - inverse markets
   - time-bucket relations
   - mutually exclusive outcome sums
   - cross-platform price relationships

4. **Confidence Interval Construction**
   The interval should widen or narrow based on:
   - settlement clarity
   - evidence quality
   - evidence conflict
   - event distance
   - market structural stability

### Default Calibration Corrections

The engine should support conservative, configurable default adjustments such as:

- skepticism toward `YES` / default-option crowding in some market types
- reduced trust in noisy, low-liquidity markets
- increased trust in liquid cross-platform consensus where relevant
- awareness that prediction-market prices are often useful but not literal truth

These are defaults, not universal laws.

## Edge Rules

The skill should define edge conservatively.

A trade should only pass if:

1. The conservative fair value exceeds the executable price by a meaningful net margin.
2. The edge survives cost assumptions.
3. The edge survives confidence-interval uncertainty.
4. The edge is not explained away by related-market inconsistencies.

### Hard Reject Conditions for Edge

Return `NO TRADE` if:

1. Edge exists only at non-executable prices.
2. Edge vanishes after cost assumptions.
3. Edge depends on ambiguous settlement interpretation.
4. Confidence interval is too wide for conservative Kelly to remain positive.

## Portfolio Risk Rules

Sizing must incorporate existing exposure.

The portfolio engine should reason about:

- same-event duplication
- same-thesis exposure across different contracts
- cross-platform duplication
- correlated tail-risk concentration
- maximum thematic drawdown contribution

### Missing Portfolio Context Rule

If portfolio context is unavailable:

1. the skill may still analyze the market and compute an isolated conservative Kelly fraction,
2. but it must apply an additional "portfolio-blind" haircut,
3. and it must explicitly state that concentration control is incomplete.

If the trade is only attractive under aggressive sizing, the missing portfolio context should force `NO TRADE`.

### Hard Reject Conditions for Portfolio Risk

Return `NO TRADE` or materially reduce sizing if:

1. The new trade duplicates large existing exposure.
2. Combined positions create excessive single-theme concentration.
3. Tail-risk stacking exceeds predefined risk limits.

## Kelly and Risk Sizing Rules

### Kelly Inputs

Use:

- conservative probability boundary
- net odds after fees / slippage
- bankroll or risk budget

### Kelly Modifiers

Apply at least these downward adjustments:

- model uncertainty haircut
- interval-width haircut
- portfolio-correlation haircut
- liquidity haircut
- drawdown-protection haircut

### Recommended Default Sizing Philosophy

The final recommendation should usually land in conservative buckets such as:

- 0 Kelly
- 0.1 Kelly
- 0.25 Kelly
- rarely 0.5 Kelly maximum

The skill should not normalize aggressive sizing.

## Refusal and Rejection Policy

The skill must treat rejection as a first-class output.

Standard reject categories:

1. No informational edge
2. Evidence conflict too high
3. Net edge insufficient after costs
4. Liquidity / execution too weak
5. Portfolio concentration too high
6. Settlement ambiguity too high

## Domain Extensibility

The core framework should stay generic. Domain adapters should only customize:

- preferred evidence sources
- base-rate anchors
- typical failure modes
- domain-specific calibration logic
- event-specific invalidation rules

Initial adapters to support later:

1. Politics / macro
2. Crypto
3. Sports

## Open-Source Inspirations and Borrowed Concepts

The design should borrow concepts from, but not blindly copy, existing projects.

### Framework / Agent Structure

- `polymarket/agents`
  Useful for modular separation of market metadata, research, and decision logic.

### Cross-Market Discovery and Aggregation

- `quantified-uncertainty/metaforecast`
  Useful for market discovery and comparative context.

### Arbitrage / Relative-Value Thinking

- `terauss/Polymarket-Kalshi-Arbitrage-bot`
  Useful as proof that cross-platform relative pricing matters.

### Maker / Microstructure Thinking

- `warproxxx/poly-maker`
  Useful as a reminder that execution quality and inventory constraints matter, even when v1 is analysis-first.

### Portfolio and Kelly Logic

- `Will-Howard/manifolio`
  Useful for portfolio-aware prediction-market sizing.

- `wdm0006/keeks`
  Useful for Kelly variants and risk-aware sizing.

## Research Foundations

The skill design should be informed by the following research themes:

1. Prediction-market calibration and trader skill on Polymarket.
2. Price discovery and large-trade informativeness across platforms.
3. Event-driven market reactions and market-stage dependence.
4. Arbitrage and logical inconsistency across related prediction contracts.
5. Market microstructure and maker / taker asymmetry.
6. Conservative Kelly under model uncertainty.

## Phased Roadmap

### V1: Conservative Analyst

Scope:

- both input modes
- evidence collection and grading
- main probability + interval
- edge detection
- portfolio-aware conservative Kelly
- structured `TRADE` / `NO TRADE`

### V2: Domain Adapters

Scope:

- politics / macro adapter
- crypto adapter
- sports adapter
- domain-specific calibration and evidence rules

### V3: Opportunity Scanner

Scope:

- broad topic scanning
- ranking of candidate markets
- cross-market edge surfacing
- portfolio-aware prioritization

Still preserve reject-first behavior.

## Error Handling and Failure Modes

The skill must explicitly handle:

1. Missing market metadata.
2. Conflicting settlement rules across sources.
3. Insufficient liquidity data.
4. Inability to verify critical evidence.
5. No access to portfolio context.
6. Contradictory cross-platform signals.

In these cases, the default action should be to widen the interval or reject the trade, not to proceed confidently.

## Evaluation Plan for the Future Skill

The final skill should be evaluated on:

1. Refusal quality
   Does it correctly say `NO TRADE` when edge is weak?
2. Structural completeness
   Does every report include market, evidence, probability, edge, portfolio, and sizing?
3. Probability discipline
   Does it produce intervals and use the conservative bound in sizing?
4. Cost realism
   Does it include fees, slippage, and executable prices?
5. Portfolio awareness
   Does it consider related existing positions?
6. Explanation quality
   Can a human understand why the skill traded or refused?

### Suggested Early Eval Prompts

1. Analyze a clearly liquid single market with strong official-source evidence and determine whether edge still exists after costs.
2. Analyze a noisy thematic prompt with conflicting X chatter and determine whether the correct output is `NO TRADE`.
3. Analyze a market that appears attractive in isolation but duplicates an existing portfolio thesis and determine whether sizing should be materially reduced or rejected.

## Implementation Readiness

This spec is intended to be sufficient for a planning phase that defines:

- the final skill structure
- SKILL.md organization
- supporting references
- evaluation prompts
- assertion strategy
- any later helper scripts

The plan should preserve the core thesis of this document:

**This skill exists to reject weak opportunities and size only the strongest ones conservatively.**
