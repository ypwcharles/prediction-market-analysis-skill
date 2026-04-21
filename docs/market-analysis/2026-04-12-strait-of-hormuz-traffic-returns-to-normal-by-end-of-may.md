# Strait of Hormuz Traffic Returns to Normal by End of May

- Analysis snapshot date: `2026-04-12`
- Saved on: `2026-04-13`
- Market: [Polymarket - Strait of Hormuz traffic returns to normal by end of May?](https://polymarket.com/event/strait-of-hormuz-traffic-returns-to-normal-by-end-of-may)
- Market data snapshot: [Gamma API event snapshot](https://gamma-api.polymarket.com/events?slug=strait-of-hormuz-traffic-returns-to-normal-by-end-of-may)

## 1. Verdict

- `NO TRADE`
- As of `2026-04-12`, `Yes` did not look undervalued.
- My central fair value for `Yes` was about `30c`, with a conservative fair value around `22c-25c`.

## 2. Market Summary

- Platform: Polymarket
- Market title: `Strait of Hormuz traffic returns to normal by end of May?`
- Trade archetype: `time-bucket trade`
- Expression / rule-scope differences: this is a pure timing extension versus the April 30 bucket; the rule text and threshold are the same
- Settlement rule: resolves `Yes` if IMF PortWatch publishes a `7-day moving average of transit calls >= 60` for any date between `2026-03-31` and `2026-05-31`
- Settlement time: `2026-05-31`, with early resolution if the threshold is hit sooner
- Executable prices at the time of analysis: `Yes bid 0.40 / ask 0.41`, midpoint about `0.405`
- Liquidity / fee notes: event liquidity was about `$59.5k`, 24h volume about `$98.3k`, spread `1c`; Gamma fields showed `feesEnabled=false`

Related market for cross-bucket comparison:

- [April 30 bucket snapshot](https://gamma-api.polymarket.com/events?slug=strait-of-hormuz-traffic-returns-to-normal-by-april-30)
- At the same time, `Apr 30 Yes` traded around `0.165`

## 3. Probability Assessment

- Anchor probability: market price around `40.5%`
- Adjusted main probability: `30%`
- Confidence interval: `22% - 38%`
- Direction vs timing decomposition:
  - `P(traffic eventually returns to 60+ on a 7-day average in 2026)` roughly `60% - 70%`
  - `P(it does so by 2026-05-31)` roughly `30%`
  - `P(the market resolves cleanly under the written rules)` roughly `98%`
- Main uncertainty drivers:
  - whether the ceasefire remains durable
  - mine-clearing speed
  - whether Iran keeps a restrictive permission / toll regime in place
  - when insurers and shipowners normalize routing behavior
  - whether backlog creates a temporary May surge large enough to lift the 7-day average to `60`

## 4. Evidence Review

### Decisive Evidence

- The key evidence was not headlines but the underlying PortWatch data source itself:
  - [IMF PortWatch page for the Strait of Hormuz](https://portwatch.imf.org/pages/cb5856222a5b4105adc6ee7e880a1730)
  - [ArcGIS daily chokepoints dataset query](https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/Daily_Chokepoints_Data/FeatureServer/0/query?where=portid%3D%27chokepoint6%27%20AND%20year%3E%3D2026&outFields=date,year,month,day,n_total&orderByFields=date%20ASC&f=pjson)
- As available on `2026-04-12`, the public dataset was only published through `2026-04-05`.
- The last published 7-day window, `2026-03-30` through `2026-04-05`, had daily totals:
  - `17, 6, 6, 6, 5, 10, 9`
- That implies a current 7-day moving average of only `8.4`.
- Using the same public series, the pre-disruption baseline from `2026-01-01` through `2026-02-27` averaged about `84.1` daily transits.

### Rule-Scope Differences

- The April 30 and May 31 contracts use the same source, same metric, and same `60+` threshold.
- This is not a scope mismatch trade. It is a pure deadline extension.

### Timing-Specific Evidence

- [U.S. MARAD advisory 2026-004](https://www.maritime.dot.gov/msci/2026-004-persian-gulf-strait-hormuz-and-gulf-oman-iranian-attacks-commercial-vessels) remained active and described recovery as a deliberate process rather than a snap-back.
- [Maersk operational update, 2026-04-09](https://www.maersk.com/news/articles/2026/04/09/middle-east-operational-update-19) still described ongoing restrictions and caution, which matters more for the timing of normalization than for the broad direction.

### Directional Evidence

- [Reuters-reported update via Al Jazeera, 2026-04-12](https://www.aljazeera.com/economy/2026/4/12/oil-tankers-exit-strait-of-hormuz-amid-fragile-us-iran-ceasefire) showed that some large crude carriers had resumed transit.
- That supports the idea that normalization is possible eventually.
- It does not, by itself, support a jump from an observed `8.4` 7-day average to `60+` before the end of May.

### Conflicting Evidence

- [AP report, 2026-04-12](https://apnews.com/article/iran-us-israel-trump-lebanon-april-12-2026-a8a0d22918fc3fb30bc3abf1cd5c5a13) indicated talks had stalled and the ceasefire remained fragile.
- That conflict widens the interval and weakens confidence in a fast recovery path.

### Discarded / Noise Evidence

- I did not use Polymarket comments or market-native narrative summaries as core valuation inputs.
- I treated the market price as an anchor, not as proof.

### Source Reliability Notes

- PortWatch and MARAD were treated as `L1` evidence.
- Maersk and major press reporting were treated as `L2`.
- The market price itself was treated as `L3`.

## 5. Mispricing / Edge

- Conservative fair value for `Yes`: `22c-25c`
- Central fair value for `Yes`: about `30c`
- Executable value at the time: `41c ask`
- Best expression of the thesis:
  - if the thesis is "normalization probably happens, but not by end of May," then `No` is cleaner than `Yes`
  - if the thesis is broadly bullish on normalization, a later bucket would be cleaner than this exact contract
- Worse expressions:
  - `Yes` on the asked market
  - `Yes` on the April 30 bucket was worse because it bought even more timing precision
- If the thesis is right but late:
  - if traffic normalizes in June, the asked contract still loses
- Net edge after costs:
  - versus my central fair value, `Yes` looked about `10.5c` rich
  - versus my conservative fair value, it looked about `16c-19c` rich
- Why the edge was insufficient:
  - the evidence supported "recovery has started"
  - the evidence did not support "the 7-day average reaches 60 before May 31"

## 6. Portfolio Impact

- Related existing positions: not provided
- Incremental thematic exposure:
  - U.S.-Iran ceasefire durability
  - mine-clearing
  - Gulf shipping normalization
  - oil risk premium compression
- Concentration / correlation concerns:
  - this contract is highly correlated with broad peace / de-escalation and lower-oil-risk views
  - it is not meaningful diversification if similar macro exposure already exists elsewhere in the portfolio

## 7. Sizing

- Raw Kelly on `Yes`: negative
- Conservative Kelly: `0%`
- Preferred structure / ladder:
  - `no position` in the asked market at the observed price
  - if forced to express the view, wait for a later bucket or a materially cheaper `Yes`
- Final recommended fraction: `0%`
- Concrete size if bankroll is provided: not provided
- Maximum entry price / minimum required price:
  - I would only reconsider `Yes` at roughly `<= 0.30`
  - at `0.41`, I would not buy

## 8. Kill Criteria

- What invalidates the thesis:
  - public PortWatch data begins printing sustained `40-50+` daily counts and the commercial shipping ecosystem normalizes faster than expected
- What removes the edge:
  - `Yes` falls toward `30c`
  - a later, cleaner bucket appears with better risk-adjusted pricing
- What triggers reduction or exit:
  - if holding `Yes`, reduce into headline-only spikes not backed by PortWatch data
  - if holding `No`, reduce quickly if the data begins stepping higher across multiple publications and operating restrictions visibly ease
- Exit type: `data-driven exit`, anchored to PortWatch releases, shipping line updates, and official maritime security guidance

## Bottom Line

If reduced to the user's original question, the answer was:

`Yes` did not look undervalued as of `2026-04-12`. It looked modestly overpriced.
