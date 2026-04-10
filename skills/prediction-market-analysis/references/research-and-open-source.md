# Research and Open Source Foundations

## Key Research Findings

The skill is grounded in a few durable findings from prediction-market and trading research:

1. Markets can be fairly well calibrated overall while most traders still lose money.
2. Large trades and cross-platform flows can contain real information.
3. Event markets react differently to different classes of news; not every jump should be chased.
4. Logical inconsistencies and cross-market arbitrage exist and can be more reliable than pure directional betting.
5. Market microstructure matters. Execution quality can dominate nominal edge.
6. Kelly should be shrunk when the probability estimate itself is uncertain.

## Named Research Threads

- Reichenbach / Walther on Polymarket calibration, trader skill, and bias
- Ng et al. on cross-platform price discovery and large-trade informativeness
- Tsang / Yang on election-market structure and reaction dynamics
- Saguillo et al. on arbitrage in related prediction contracts
- Becker on maker/taker wealth transfer in CLOB-style prediction markets
- Baker / McHale and related work on conservative Kelly under uncertainty

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

## Concepts Explicitly Not Copied

- always-on automatic execution
- blind trust in social sentiment
- treating market price as literal truth
- aggressive Kelly based on a central estimate
- forcing a trade when evidence quality is mediocre
