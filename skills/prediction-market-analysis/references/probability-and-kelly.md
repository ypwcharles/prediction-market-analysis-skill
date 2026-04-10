# Probability and Kelly

## Goal

Turn market context plus evidence into:

- an anchor probability
- a main probability
- a confidence interval
- a conservative Kelly recommendation

The output must remain robust under uncertainty.

## Anchor Selection

Start with the strongest available anchor, not necessarily the current market price.

Common anchors:

- current platform consensus
- cross-platform consensus
- historical base rate
- domain-specific prior
- related market-implied probability

Choose the anchor that is most defensible for this event type. Explain the choice.

## Evidence Adjustments

Adjust the anchor only for evidence that survives the evidence-engine filters.

For each meaningful adjustment, record:

- why the adjustment exists
- direction of the adjustment
- magnitude of the adjustment
- what assumption would invalidate the adjustment

Multiple weak adjustments do not outrank one strong decisive fact.

## Confidence Interval Rules

Widen the interval when:

- settlement rules are unclear
- evidence conflicts materially
- the event is far from resolution
- the market is illiquid or noisy
- there is cross-platform disagreement with no obvious explanation

Narrow the interval when:

- resolution rules are clear
- evidence quality is high
- decisive primary sources dominate
- event timing is near and the remaining uncertainty is genuinely low

## Consistency Checks

Before accepting the final probability, compare it against:

- inverse or opposing markets
- related time buckets
- mutually exclusive outcome sums
- cross-platform equivalents

If the estimate creates obvious contradictions, either revise it or reject the setup.

## Net Edge Computation

Never compute edge from midpoint fantasy prices when the user would have to cross the spread.

Compare:

- conservative fair value from the interval
- best executable price
- fees
- slippage
- execution uncertainty

If the net edge is marginal, reject.

## Kelly Framework

Kelly exists to size edge, not to prove edge exists.

Workflow:

1. Estimate the main probability.
2. Build a confidence interval.
3. Use the conservative boundary only.
4. Apply Kelly to net executable odds.
5. Haircut the result for model risk and portfolio context.

## Required Haircuts

Apply at least:

- uncertainty haircut
- interval-width haircut
- correlation haircut
- liquidity haircut
- drawdown haircut

The final recommendation should usually be much smaller than raw Kelly.

## Position Size Format

If bankroll is known:

- give a bankroll fraction
- give a concrete suggested size

If bankroll is unknown:

- give fraction only
- avoid pretending to know absolute size

## Portfolio-Blind Haircut Rule

If the user does not provide current exposure:

1. still compute a conservative isolated Kelly fraction
2. apply an additional portfolio-blind haircut
3. state clearly that concentration control is incomplete

If the trade is only attractive under aggressive sizing, missing portfolio context should push the verdict to `NO TRADE`.

## Default Sizing Philosophy

Normalize conservative buckets:

- `0 Kelly`
- `0.1 Kelly`
- `0.25 Kelly`
- rarely `0.5 Kelly`

Do not normalize full Kelly or large concentration bets.
