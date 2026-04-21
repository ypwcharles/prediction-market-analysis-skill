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

For institutional-decision markets, also separate:

- `P(actor waits despite eventual action)`
- `P(action is deferred to a nearby later window)`

These are not interchangeable.

For narrow time buckets:

- strong directional evidence with weak timing evidence should not be treated as full support for `Yes`
- weak timing precision often supports `No` on the early bucket better than `Yes` on the exact bucket
- "soon", "likely", and "momentum is building" are timing-weak statements unless tied to a calendar, procedural gate, or operational constraint

## Deferred-Action / Earlier Non-Occurrence Audit

When analyzing an earlier non-occurrence leg, explicitly ask:

1. Can the actor rationally wait without disproving the broader thesis?
2. Do primary sources show data dependence, optionality, or consensus-building behavior?
3. Does the earlier non-occurrence leg win across multiple "right but later" paths?
4. Is the market charging a large premium for immediacy rather than for the broad event?

If the answer is yes across this set, treat the trade as a high-quality timing fade, not as a generic narrow-window punt.

## Bucket Selection Audit

When related time buckets or threshold ladders exist, explicitly ask:

1. Is the asked market the cleanest expression of the thesis?
2. Would a later bucket retain the same directional edge with less clock risk?
3. Would the earlier non-occurrence leg dominate the exact-action leg?
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

Do not reflexively apply the same extra widening to an earlier non-occurrence leg if:

- the position wins on several plausible late paths
- primary sources explicitly support waiting
- the main uncertainty is whether action is deferred rather than whether it happens

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

## Asymmetric Time-Precision Haircuts

Time-precision risk is not symmetric.

- Exact-bucket `Yes` usually deserves a heavier haircut because it needs both direction and clock precision.
- An earlier non-occurrence leg can deserve a smaller haircut when delay helps the position and multiple later paths still win.

Reduce the normal time-precision haircut only when all of the following hold:

- settlement is clean
- primary sources support waiting or deferability
- the trade wins if the thesis is right but late
- liquidity is good enough to enter and exit without fantasy fills

For clarity:

- in binary markets this is often `No`
- in multi-outcome markets this can be `Yes` on a named no-action bucket such as `No change`

## Kelly Framework

Kelly exists to size edge, not to prove edge exists.

Workflow:

1. Estimate the main probability.
2. Build a confidence interval.
3. Use the conservative boundary only.
4. Apply Kelly to net executable odds.
5. Haircut the result for model risk and portfolio context.

Do not upgrade size from realized profit alone. Upgrade only when the decisive edge was available ex ante and survives outcome-blind review.

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

Do not double-count timing risk when the trade benefits from timing uncertainty rather than being harmed by it.

## Edge Promotion Checklist

Before promoting a setup from `0.1 Kelly` territory toward `0.25 Kelly`, require explicit confirmation that:

- settlement was clean ex ante
- the best expression clearly dominated nearby alternatives
- decisive evidence was primary-source driven at entry, not discovered later
- the trade won across multiple plausible paths rather than one narrow lucky path
- contradictory primary evidence was limited or already incorporated in the interval
- executable liquidity was sufficient for the intended size

If any of these are missing, keep the setup in the smaller sizing bucket even if the trade ultimately worked.

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

Exception:

- an earlier non-occurrence leg can be the core leg when it wins across many "right but later" paths and the market is overcharging for immediate action

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

High-quality timing fades can qualify for the `0.25 Kelly` bucket after all haircuts when:

- deferability evidence is primary-source driven
- the earlier non-occurrence leg is the cleanest expression
- executable edge still exists on the conservative boundary
- liquidity and portfolio overlap are acceptable
- the edge promotion checklist passes on an outcome-blind basis

Ordinary narrow-window views should usually stay at `0 Kelly` or `0.1 Kelly`.

## Outcome-Blind Post-Trade Review

After a win or loss, review the trade in this order:

1. What was known at entry?
2. Which evidence was decisive at entry?
3. Which evidence arrived later and should not be credited to the original process?
4. Did the chosen contract still dominate nearby expressions?
5. Was the original size too small, appropriate, or too large for the ex ante edge quality?

Do not let a large mark-to-market gain overwrite a weak original case.
