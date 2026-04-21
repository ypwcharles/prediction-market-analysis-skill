# Evidence Engine

## Purpose

This reference defines how to decide whether information should change the probability estimate at all. The goal is not to collect the largest pile of evidence. The goal is to isolate the smallest set of high-impact, resolution-relevant facts.

It also defines how to tell apart:

- evidence that changes direction
- evidence that changes timing
- evidence that changes resolution confidence

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

## Archetype-Specific Evidence Tests

### Resolution Arb

Ask:

1. Has the real-world state already crossed the practical finish line?
2. Do the written rules still clearly map that state to the expected outcome?
3. Is there any material oracle, admin, or interpretation risk left?
4. Is the remaining uncertainty about reality, or only about settlement mechanics?

The decisive evidence is usually the combination of rule text plus a primary source showing the underlying state is already settled in substance.

### Directional Event

Ask:

1. Does this evidence change whether the event happens at all?
2. Is it causal, or just narrative?
3. Has the market likely already absorbed it?

### Time-Bucket Trade

Ask:

1. Does this evidence change when the event happens, not merely whether it happens?
2. Does it speak to a hard calendar, procedural gate, operational bottleneck, or institutional incentive to wait?
3. Would this still matter if the deadline moved back by a month?

If the answer to the third question is yes, it may be direction evidence rather than timing evidence.

### Cross-Bucket Structure

Ask:

1. Which evidence differentiates the nearby buckets from each other?
2. What exactly makes the early bucket miss while the later bucket still works?
3. Is the market paying for precision, or for genuinely different states of the world?
4. Are the contracts actually describing the same event, or only a related event family?
5. Could the same real-world facts make one resolve `Yes` and the other `No`?

If the answer to 4 or 5 is yes, this is not a pure timing comparison. It is also a rule-scope comparison.
In that case, the final analysis should describe the setup as `cross-bucket structure` or equivalent cross-expression language, not as a pure time-bucket trade.

## Rule-Scope Differences

When adjacent contracts differ by language, explicitly compare:

- named actors or countries
- verbs like `ceasefire`, `conflict ends`, `approval`, `launch`, `enter`, `ban`
- formal declaration requirements versus practical reality
- broad conflict conditions versus bilateral conditions
- whether one market requires a narrower legal or operational threshold

Do not let a looser or broader real-world thesis override a narrower written contract.

## Scoring Dimensions

Score each evidence item on:

- `source_quality`
- `directness_to_settlement`
- `timeliness`
- `uniqueness`
- `falsifiability`
- `impact_on_resolution`

Do not allow low-impact evidence to dominate just because it is recent or widely repeated.

For time-bucket trades, score `directness_to_settlement` and `impact_on_resolution` against the specific deadline, not the broad event.
For rule-scope comparisons, score those dimensions against the written contract language, not your shorthand thesis.

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

When two related markets seem to disagree, first check whether the disagreement is genuine conflict or simply different settlement language.

## Timing Evidence vs Direction Evidence

Treat the following as direction-heavy but timing-weak unless paired with a deadline mechanism:

- "talks are progressing"
- "approval is likely"
- "momentum is building"
- "market sentiment is shifting"
- "participants expect action soon"

Treat the following as timing-relevant when verified:

- statutory or regulatory deadlines
- court calendars and filing schedules
- product launch windows with locked prerequisites
- weather models tied to the resolution location and date
- known logistics, settlement, or delivery constraints
- official statements that narrow timing rather than merely tone

Treat the following as timing-relevant for earlier non-occurrence positions when verified:

- official emphasis on wanting more data before acting
- explicit preference to preserve optionality
- close upcoming meetings or windows that lower the cost of waiting
- institutional norms of moving only with consensus or updated forecasts
- evidence that acting now carries more reputational or policy cost than waiting

These often leave the broad thesis alive while weakening the immediate-action bucket.

For clarity:

- in binary markets, the earlier non-occurrence leg is often `No`
- in multi-outcome markets, it can be `Yes` on a named no-action bucket such as `No change`

An event becoming more likely eventually is not enough to justify buying a narrow `Yes` bucket.
And a broad thesis becoming more likely is not enough to justify buying a narrower rule-scope contract.

## What Should Move Probability

Probability should move only when the evidence:

- directly changes the event state
- materially changes the likelihood of the event
- changes the distribution of possible outcomes
- changes who has superior information

Information can be true and still fail this test.

For time-bucket trades, probability should move only when the evidence changes the deadline-sensitive path, not just the eventual outcome.

For institutional-decision markets, probability should also move when the evidence changes the chance of waiting despite eventual action.

## Deferred-Action Evidence

Central banks, regulators, courts, boards, and committees often have real option value in waiting.

Treat deferability as genuine timing evidence when primary sources show:

- patience or data dependence is still the stated base case
- another scheduled meeting or decision window is close enough to matter
- the institution can preserve credibility by waiting rather than forcing action now
- the broader thesis remains intact even if the immediate window misses

Do not dismiss this as mere rhetoric when the institution has both the ability and the incentive to defer.

## When Evidence Is Too Weak To Proceed

Return `NO TRADE` if:

- the thesis is mostly powered by L4/L5 evidence
- the decisive evidence cannot be verified
- the strongest evidence points in opposite directions and cannot be resolved
- the key supporting claim depends on ambiguous interpretation
- the thesis depends on timing precision but the supporting evidence mostly changes direction only
- the setup is a supposed resolution arb but still depends on debatable rule interpretation
- the trade thesis is broader than the actual contract language and no rule-scope adjustment has been made

## Practical Heuristic

Before changing the probability, ask:

1. Is this new?
2. Is this real?
3. Is this independent?
4. Does this matter for settlement?
5. Has the market already absorbed it?

If any answer is unclear, reduce its influence or discard it.

For narrow buckets, add:

6. Does this matter for this deadline, or only for the broader event?
7. Does this matter for this contract language, or only for a broader related event?
8. Does this support action now, or only action eventually?
