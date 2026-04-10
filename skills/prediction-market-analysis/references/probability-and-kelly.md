# Probability and Kelly

## Goal

Turn market context plus evidence into:

- an anchor probability
- a main probability
- a confidence interval
- a conservative Kelly recommendation
- the right contract expression for the thesis

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

For resolution arbs, the anchor is usually not broad event probability. It is the current confidence that the written rules and oracle path will resolve in the expected direction.

## Evidence Adjustments

Adjust the anchor only for evidence that survives the evidence-engine filters.

For each meaningful adjustment, record:

- why the adjustment exists
- direction of the adjustment
- magnitude of the adjustment
- what assumption would invalidate the adjustment

Multiple weak adjustments do not outrank one strong decisive fact.

## Direction vs Timing Decomposition

Before pricing a contract, separate:

- `P(event eventually happens)`
- `P(event happens within this contract window)`
- `P(market resolves the way the real-world event suggests)`

These are not interchangeable.

For narrow time buckets:

- strong directional evidence with weak timing evidence should not be treated as full support for `Yes`
- weak timing precision often supports `No` on the early bucket better than `Yes` on the exact bucket
- "soon", "likely", and "momentum is building" are timing-weak statements unless tied to a calendar, procedural gate, or operational constraint

## Bucket Selection Audit

When related time buckets or threshold ladders exist, explicitly ask:

1. Is the asked market the cleanest expression of the thesis?
2. Would a later bucket retain the same directional edge with less clock risk?
3. Would `No` on the earlier bucket dominate `Yes` on the exact bucket?
4. If the thesis is right but late, which contract gets paid?
5. Is the market charging too much for time precision the evidence does not justify?

If a nearby expression dominates on risk-adjusted edge, recommend that expression even if the asked contract is not absurd.

## Rule-Scope Audit

Before treating nearby markets as a ladder, explicitly ask:

1. Do the contracts require the same actors, the same action, and the same threshold?
2. Is one market broader while the other requires a narrower formal condition?
3. Could the same thesis be right in spirit but wrong under one market's written language?
4. Is the better trade a different expression rather than a later bucket?

If the answer to any of these is yes, do not reduce the comparison to clock risk alone.

## Adjacent-Market Consistency

For calendars and ladders, compare:

- earlier bucket `No` vs later bucket `Yes`
- neighboring strikes or thresholds
- mutually exclusive partitions
- cross-platform equivalents
- scope differences in contract language

Look for contradictions in implied ordering. If the pattern is incoherent, either explain why or reject the setup.

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

For time-bucket trades, widen further when:

- the deadline is short relative to the event cadence
- a key step depends on bureaucracy, logistics, weather, litigation, or market hours
- the thesis is directionally strong but exact timing remains soft

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
- time-mismatch risk
- rule / resolution risk for arbs

If the net edge is marginal, reject.

## Kelly Framework

Kelly exists to size edge, not to prove edge exists.

Workflow:

1. Estimate the main probability.
2. Build a confidence interval.
3. Use the conservative boundary only.
4. Apply Kelly to net executable odds.
5. Haircut the result for model risk and portfolio context.

For resolution arbs, Kelly is usually secondary to operational risk. Start with resolution confidence, then haircut harder for:

- ambiguous rule interpretation
- admin or oracle discretion
- long capital lock-up
- inability to hedge or exit

## Required Haircuts

Apply at least:

- uncertainty haircut
- interval-width haircut
- correlation haircut
- liquidity haircut
- drawdown haircut
- time-precision haircut for narrow windows
- concentration haircut for same-thesis ladders

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

## Same-Thesis Ladder Rules

If multiple buckets express the same thesis:

- size the highest-conviction, least assumption-heavy bucket as the core
- size earlier or narrower buckets as satellites, not as the main risk
- absent strong timing evidence, near buckets should usually be materially smaller than later buckets

A good default for event-driven discretionary trading is:

- far bucket = core size
- mid bucket = reduced size
- near bucket = small probe or no position

If the user wants only one contract, prefer the one that wins more often when the thesis is directionally right but timing is imperfect.

## Concentration Guardrails

For one narrative cluster or same causal driver:

- treat adjacent buckets as correlated, not diversified
- treat nearby rule-scope variants as correlated unless they are truly hedging different outcomes
- do not count multiple versions of the same thesis as independent edge
- if several positions all lose when the same clock slips, apply a heavy haircut

Without strong hedging logic, one thematic cluster should rarely dominate the deployed-risk budget.

## Default Sizing Philosophy

Normalize conservative buckets:

- `0 Kelly`
- `0.1 Kelly`
- `0.25 Kelly`
- rarely `0.5 Kelly`

Do not normalize full Kelly or large concentration bets.
