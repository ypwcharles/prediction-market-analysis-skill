# Microstructure and Price-Dynamics Models

Use this reference when a prediction-market setup depends on price-path behavior, Markov chains, transition matrices, longshot bias, maker/taker execution, scanner ranking, or a quoted edge that may disappear after real fills.

This layer is diagnostic. It can strengthen a case, weaken a case, cap size, or force `NO TRADE`, but it must not replace rule text, exact market expression, event evidence, or current order-book depth.

## Activation

Load this reference when:

- the user mentions Markov chains, state transitions, Monte Carlo, price buckets, or historical price paths
- the user asks whether a quoted edge is executable
- scanner output includes spread, depth, volume, price movement, or stale-book concerns
- the setup is a cheap longshot, especially low-price `Yes`
- the trade is maker-only or depends on avoiding taker fees

## Required Inputs

Before using a price-dynamics model, collect:

- exact market expression and outcome side
- current best bid, best ask, spread, and full depth for intended size
- fee metadata and tick/min-size constraints
- recent price history with timestamps
- volume, trade count, and spread history when available
- time to expiry and resolution clock
- major news timestamps or known structural breaks
- adjacent expressions and related buckets

If these inputs are missing, mark the diagnostic as incomplete rather than inventing a model.

## Markov / Transition-Matrix Gate

Only use a Markov-style price-state model when all of these are true:

- the exact contract expression is identified
- the market has enough history in the relevant regime
- every state row used for the current path has enough observed transitions, normally at least 20-30 observations
- the transition window excludes obvious structural breaks unless the model is explicitly post-break only
- state buckets are wide enough to avoid fake precision
- the model is evaluated out of sample or with a walk-forward sanity check when used for trade judgment

If the current state row is sparse, the model output is `model_invalid`, not "weak evidence."

## Markov Workflow

When the gate passes:

1. Discretize price into transparent buckets, such as 0-10c, 10-20c, and so on.
2. Build the transition matrix from the chosen rolling window.
3. Report row sample counts, not only the resulting transition probabilities.
4. Simulate paths from the current state to expiry only after the sample-count gate passes.
5. Compare terminal simulation results against market price, adjacent markets, and non-price evidence.
6. Apply calibration and model-risk haircuts before any Kelly calculation.

Never present the simulated terminal probability as the final fair probability. It is a market-behavior signal that still needs rule, evidence, expression, liquidity, and execution checks.

## Longshot Bias Calibration

Cheap contracts need extra discipline.

For low-price `Yes`:

- assume lottery demand and narrative optionality can overpay the upside
- require independent evidence that changes the real event probability
- haircut Markov or momentum signals harder unless out-of-sample calibration is strong
- reject if the only case is "large payoff if it happens"

For low-price `No`:

- do not assume it is automatically good because cheap `Yes` is often overpaid
- check settlement tail risk, ambiguity, and correlated ladder exposure
- size from executable edge after worst-plausible tail paths

Longshot calibration should adjust the probability interval or sizing haircut. It should not become a standalone reason to trade.

## Maker / Taker Execution

Compute edge from the executable route:

- taker route: cross the book, include spread, full-depth slippage, taker fee, and immediate fill certainty
- maker route: use limit price, include maker fee, queue risk, non-fill risk, and adverse-selection risk
- maker-only trade: state maximum entry and the condition under which the setup is cancelled instead of crossing the spread
- stale or news-sensitive book: increase adverse-selection risk and reject if passive entry mainly invites informed fills

Use `maker_taker_tax_bps` or an equivalent explicit note when runtime context supports it.

Reject when the edge exists only at midpoint, last trade, or a best quote too small for intended size.

## Scanner Ranking Guidance

For broad scans, price-dynamics features should prioritize review budget, not auto-approve trades.

Promote candidates for analysis when:

- spread is tight enough for executable entry
- depth supports the intended size
- recent volume is real enough to reduce stale-book risk
- adjacent markets show coherent ordering or a possible contradiction worth checking
- price movement aligns with fresh evidence rather than unsupported momentum

Demote or reject candidates when:

- spread is wide relative to claimed edge
- depth is too thin to fill size
- transition rows are sparse
- recent movement is a single unsupported jump
- low-price `Yes` depends on narrative optionality without primary evidence

## Runtime Fields

When runtime output supports optional diagnostics, use these fields when relevant:

- `price_state_bucket`
- `transition_sample_count`
- `markov_signal`
- `microstructure_bias`
- `maker_taker_tax_bps`
- `execution_mode`
- `adverse_selection_risk`
- `model_validity`
- `do_not_trade_reason`

Use plain string values when exact numeric values are unavailable. Prefer `model_invalid` or `insufficient_history` over false precision.

## Walk-Forward Guardrail

If historical price behavior materially affects the verdict, require a walk-forward or out-of-sample sanity check.

Minimum review questions:

1. Would the model have identified similar opportunities before the outcome was known?
2. Does it beat a simple market-price baseline on calibration, Brier score, log loss, or realized edge?
3. Does performance survive by market category, price band, and horizon?
4. Does the edge remain after executable spread, fees, and slippage?
5. Are losing regimes visible, especially news shocks and sparse low-liquidity markets?

If these checks are unavailable, cap the signal as exploratory and do not let it drive conviction sizing.
