# Research and Open Source Foundations

## Key Research Findings

The skill is grounded in a few durable findings from prediction-market and trading research:

1. Markets can be fairly well calibrated overall while most traders still lose money.
2. Large trades and cross-platform flows can contain real information.
3. Event markets react differently to different classes of news; not every jump should be chased.
4. Logical inconsistencies and cross-market arbitrage exist and can be more reliable than pure directional betting.
5. Market microstructure matters. Execution quality can dominate nominal edge.
6. Kelly should be shrunk when the probability estimate itself is uncertain.
7. Longshot contracts can be structurally overpaid, especially when traders buy lottery-like `Yes` exposure.
8. Price-history models can be useful diagnostics, but stationarity, sample depth, and execution costs decide whether their signal is tradeable.

## Named Research Threads

- Reichenbach / Walther on Polymarket calibration, trader skill, and bias
- Ng et al. on cross-platform price discovery and large-trade informativeness
- Tsang / Yang on election-market structure and reaction dynamics
- Saguillo et al. on arbitrage in related prediction contracts
- Becker on maker/taker wealth transfer in CLOB-style prediction markets
- Baker / McHale and related work on conservative Kelly under uncertainty
- price-state / Markov-chain modeling as a diagnostic framework for market behavior, not a replacement for settlement and evidence analysis

## Open-Source Inspirations

### `polymarket/agents`

Useful for:

- separating market metadata, research, and decision logic

### `quantified-uncertainty/metaforecast`

Useful for:

- cross-market discovery and aggregation

### `terauss/Polymarket-Kalshi-Arbitrage-bot`

Useful for:

- proving that related markets should be compared, not analyzed in isolation

### `warproxxx/poly-maker`

Useful for:

- emphasizing execution and microstructure constraints

### `Will-Howard/manifolio`

Useful for:

- portfolio-aware prediction-market sizing

### `wdm0006/keeks`

Useful for:

- Kelly variants and conservative bankroll logic

## Concepts Borrowed

- reject-first trade discipline
- cross-market sanity checking
- executable, not theoretical, edge
- portfolio-aware sizing
- conservative Kelly from the lower confidence boundary
- longshot-bias and price-band calibration
- maker/taker execution discipline
- walk-forward validation before trusting historical price-path signals

## How to Use Price-Dynamics Research

Use Markov, transition-matrix, or Monte Carlo price-state models only after the exact market expression is known and the historical sample is deep enough.

Good uses:

- flagging a candidate for deeper rule and evidence review
- detecting stale or noisy markets where quoted edge is not executable
- adding a model-risk haircut to low-price longshot trades
- deciding whether a signal is maker-only, taker-safe, or not tradeable

Bad uses:

- replacing the written settlement rule with a price-history probability
- treating sparse transition rows as real probabilities
- using a model trained across structural breaks without disclosure
- approving cheap `Yes` trades because the payoff looks large
- ignoring spread, full-depth slippage, fees, queue risk, or adverse selection

## Concepts Explicitly Not Copied

- always-on automatic execution
- blind trust in social sentiment
- treating market price as literal truth
- treating Markov or Monte Carlo output as literal truth
- aggressive Kelly based on a central estimate
- forcing a trade when evidence quality is mediocre
