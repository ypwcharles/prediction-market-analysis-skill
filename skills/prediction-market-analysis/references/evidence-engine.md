# Evidence Engine

## Purpose

This reference defines how to decide whether information should change the probability estimate at all. The goal is not to collect the largest pile of evidence. The goal is to isolate the smallest set of high-impact, resolution-relevant facts.

## Source Tiers

### L1: Primary / Resolution-Relevant Sources

Use highest priority for:

- official announcements
- legal or regulatory filings
- original economic data releases
- company formal disclosures
- court documents
- official event, sports, or league sources
- raw on-chain or platform-native data tied directly to settlement

### L2: High-Quality Secondary Sources

Use for interpretation and speed:

- major media
- specialist reporters
- quality research institutions
- reputable data vendors

### L3: Market-Native Signals

Use as evidence about price discovery and positioning, not as direct proof of reality:

- current prices
- cross-platform prices
- order-book conditions
- large-trade imbalance
- related market movement

### L4: High-Quality Social Signals

Use as early hints or corroboration:

- trusted expert X accounts
- fast-reporting domain specialists
- high-signal analysts with domain credibility

### L5: Low-Quality Narrative Sources

Treat as weak by default:

- anonymous commentary
- derivative reposts
- marketing content
- screenshots without provenance
- AI summaries with no original sourcing

## Scoring Dimensions

Score each evidence item on:

- `source_quality`
- `directness_to_settlement`
- `timeliness`
- `uniqueness`
- `falsifiability`
- `impact_on_resolution`

Do not allow low-impact evidence to dominate just because it is recent or widely repeated.

## Deduplication Rules

Repeated references to the same fact do not count as independent evidence.

Examples:

- Three articles citing the same government release count as one underlying fact.
- A viral X post repeating a Bloomberg headline does not create a second signal.
- Five screenshots of the same order-book move are one market event, not five.

When in doubt, collapse evidence by underlying claim rather than by URL.

## Conflict Handling

When evidence conflicts:

1. Prefer direct settlement relevance over general informativeness.
2. Prefer primary sources over secondary commentary.
3. Prefer verifiable evidence over interpretive evidence.
4. Prefer unique evidence over repeated narrative.

If conflict survives these filters, widen the interval. If the conflict is central to the thesis, reject the trade.

## What Should Move Probability

Probability should move only when the evidence:

- directly changes the event state
- materially changes the likelihood of the event
- changes the distribution of possible outcomes
- changes who has superior information

Information can be true and still fail this test.

## When Evidence Is Too Weak To Proceed

Return `NO TRADE` if:

- the thesis is mostly powered by L4/L5 evidence
- the decisive evidence cannot be verified
- the strongest evidence points in opposite directions and cannot be resolved
- the key supporting claim depends on ambiguous interpretation

## Practical Heuristic

Before changing the probability, ask:

1. Is this new?
2. Is this real?
3. Is this independent?
4. Does this matter for settlement?
5. Has the market already absorbed it?

If any answer is unclear, reduce its influence or discard it.
