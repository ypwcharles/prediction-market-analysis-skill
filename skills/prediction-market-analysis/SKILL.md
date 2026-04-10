---
name: prediction-market-analysis
description: Use when analyzing Polymarket, Kalshi, or related prediction-market contracts for tradeability, fair odds, mispricing, cross-market comparisons, or Kelly-based sizing. Trigger when the user asks to analyze a specific market, scan a theme or event for opportunities, compare related contracts across platforms, estimate a probability range, decide whether a market should be rejected as untradeable, or size a prediction-market position conservatively.
---

# Prediction Market Analysis

## Overview

This skill acts like a conservative prediction-market risk committee. Its job is not to find a trade every time. Its job is to decide whether enough evidence, market quality, execution edge, and portfolio capacity exist to justify a trade at all.

Default posture:

- reject weak setups
- express uncertainty explicitly
- size only from conservative edge

## When to Use

Use this skill when the user wants to:

- analyze a specific Polymarket or Kalshi market
- search a theme or event for tradeable markets
- compare related contracts across platforms
- estimate fair odds or a probability range
- decide whether a setup is strong enough to trade
- size a position using Kelly or fractional Kelly
- re-evaluate a proposed trade in the context of existing exposure

Do not use this skill for:

- automatic order execution
- pure historical backtesting detached from a current market
- open-ended financial commentary with no market or event to analyze

## Core Principles

1. Reject-first. Try to disprove the trade before approving it.
2. Net edge matters. A trade exists only if edge survives fees, slippage, and execution uncertainty.
3. Intervals beat false precision. Always produce a main probability plus a confidence interval.
4. Conservative Kelly only. Size from the conservative boundary, never the central estimate.
5. Portfolio-aware by default. A good isolated trade can still be a bad portfolio trade.

## Supported Entry Modes

### Single-Market Deep Analysis

Use when the input is a specific market URL, contract, or market ID.

### Theme-Driven Discovery

Use when the input is a thesis, event, or topic. Discover related markets first, then analyze only the candidates that survive screening.

## Workflow

### 1. Normalize the input

Extract or infer:

- event or question
- platform and market identifiers when available
- settlement rule
- settlement time horizon
- bankroll or position constraints
- existing portfolio context when provided

### 2. Discover related markets

For a single market, enrich the analysis with:

- inverse or opposing expressions
- related time buckets
- mutually exclusive outcomes
- cross-platform equivalents

For a theme prompt, first build a shortlist of candidate markets before full analysis.

### 3. Filter for tradeability

Before directional analysis, check:

- settlement clarity
- resolution-source reliability
- liquidity and book quality
- fees and likely slippage
- risk of noise, manipulation, or wash trading

If the market is not clean enough to analyze, return `NO TRADE`.

### 4. Gather and grade evidence

Actively search:

- official and primary sources
- economic or regulatory releases
- quality journalism and specialist reporting
- market-native signals
- expert social sources

Use `references/evidence-engine.md` for source tiers, scoring, deduplication, and conflict handling.

### 5. Build the thesis

Organize evidence into:

- supports the outcome
- supports the opposite outcome
- actually changes probability
- informative but non-decisive
- likely noise

Always seek disconfirming evidence.

### 6. Estimate probability and interval

Construct:

- anchor probability
- evidence adjustments
- main probability
- confidence interval

Do not treat market price as literal truth. Use `references/probability-and-kelly.md` before pricing or sizing.

### 7. Compute executable edge

Compare the conservative fair value implied by the interval against the best realistic executable price after:

- fees
- spread
- slippage
- execution uncertainty

If edge disappears after costs, return `NO TRADE`.

### 8. Check portfolio risk

Inspect:

- overlap with existing positions
- same-thesis duplication across markets
- cross-platform duplication
- thematic concentration
- tail-risk concentration

If portfolio context is unavailable, apply the portfolio-blind haircut from `references/probability-and-kelly.md` and say so explicitly.

### 9. Size conservatively

Apply Kelly only if the setup survives all earlier checks.

Use:

- conservative interval boundary
- net executable odds
- uncertainty haircut
- correlation haircut
- liquidity haircut
- drawdown haircut

### 10. Return a binary verdict

Final verdict must be one of:

- `TRADE`
- `NO TRADE`

No "maybe trade" verdict.

## Output Format

ALWAYS use this exact structure:

### 1. Verdict
- `TRADE` or `NO TRADE`

### 2. Market Summary
- platform
- market title
- settlement rule
- settlement time
- executable price(s)
- liquidity / fee notes

### 3. Probability Assessment
- anchor probability
- adjusted main probability
- confidence interval
- main uncertainty drivers

### 4. Evidence Review
- decisive evidence
- directional evidence
- conflicting evidence
- discarded / noise evidence
- source reliability notes

### 5. Mispricing / Edge
- conservative fair value
- executable value
- net edge after costs
- why edge is or is not sufficient

### 6. Portfolio Impact
- related existing positions
- incremental thematic exposure
- concentration / correlation concerns

### 7. Sizing
- raw Kelly
- conservative Kelly
- final recommended fraction
- concrete size if bankroll is provided
- maximum entry price / minimum required price

### 8. Kill Criteria
- what invalidates the thesis
- what removes the edge
- what triggers reduction or exit

If the input is thematic and multiple candidate markets are discovered:

- start with a short ranked shortlist
- then provide full detailed reports only for markets that survive screening

## Refusal Rules

Return `NO TRADE` if any of the following is true:

1. No informational edge survives scrutiny.
2. Evidence conflict is too high to support a disciplined interval.
3. Net edge vanishes after fees, slippage, or execution assumptions.
4. Settlement ambiguity is material.
5. Liquidity is too weak to trust the paper edge.
6. Portfolio concentration is too high.

## Common Mistakes

- Treating a large volume of low-quality evidence as strong conviction.
- Treating market price as literal truth instead of one input.
- Using the central estimate for Kelly sizing.
- Ignoring existing correlated exposure.
- Calling theoretical edge a real edge when execution destroys it.

## References

- Read `references/evidence-engine.md` when grading sources and resolving evidence conflicts.
- Read `references/probability-and-kelly.md` before generating intervals, pricing edge, or sizing a trade.
- Read `references/domain-adapters.md` when the market falls into politics/macro, crypto, or sports.
- Read `references/research-and-open-source.md` when you need the research foundation or design rationale behind this skill.
