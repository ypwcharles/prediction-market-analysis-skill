# JD Vance / Iran Market Note

Saved: 2026-04-13 HKT  
Scope: consolidate the prior discussion about the Polymarket "JD Vance diplomatic meeting with Iran by...?" buckets, with emphasis on `Apr 10 No` and the existing `Apr 15 Yes @ 89c` position.

## Context

- Event page: <https://polymarket.com/event/jd-vance-diplomatic-meeting-with-iran-by>
- Related expression:
  - "Where will the next US-Iran diplomatic meeting happen?" Pakistan bucket
- Analysis window used in the discussion:
  - public reporting checked on 2026-04-10 / 2026-04-11 HKT
  - saved into this note on 2026-04-13 HKT

## Key Timeline Inputs

- User-provided flight activity screenshot implied departure at:
  - `2026-04-10 12:47 UTC`
  - `2026-04-10 08:47 EDT`
  - `2026-04-10 17:47 PKT`
  - `2026-04-10 20:47 HKT`
- `Apr 10 ET` market cutoff converts to:
  - `2026-04-10 23:59:59 EDT`
  - `2026-04-11 08:59:59 PKT`
- Time from departure to cutoff:
  - about `15.22 hours`

## Flight Constraint Notes

- Approximate Joint Base Andrews to Islamabad great-circle distance:
  - `6,147 nm`
  - `7,073 mi`
  - `11,383 km`
- Public C-32 fact sheet range used in the discussion:
  - about `5,500 nautical miles unrefueled`
- Working implication:
  - do not assume a clean no-stop Washington-area to Islamabad flight
  - a technical stop is materially plausible
  - if a stop is required, `Apr 10 No` gets stronger

### Arrival Window Scenarios Used

Assuming `2026-04-10 08:47 EDT` departure:

- direct_fast: `2026-04-11 05:50 PKT`
- direct_mid: `2026-04-11 06:19 PKT`
- direct_slow: `2026-04-11 06:51 PKT`
- one_stop_fast: `2026-04-11 08:17 PKT`
- one_stop_mid: `2026-04-11 09:17 PKT`
- one_stop_slow: `2026-04-11 10:17 PKT`

Interpretation:

- direct-flight cases can still leave a narrow path for `Apr 10 Yes`
- one-stop cases make `Apr 10 Yes` much harder
- the market still requires a qualifying in-person meeting after arrival, not just wheels down

## Public Evidence Used

### High-signal directional evidence

- AP/WTOP reported Vance departing for Islamabad on 2026-04-10.
- AP/WTOP also described the talks as expected to start on Saturday in Islamabad.

### High-signal timing-negative evidence

- Iranian-aligned and Anadolu reporting indicated that the Iranian team had not yet arrived in Islamabad and might condition participation on ceasefire compliance in Lebanon.

### Rule-scope note

- The Polymarket rule text allows an `indirect but in-person` mediated meeting.
- That matters because a same-room formal sit-down is not required for a `Yes`.

## Apr 10 No

### 1. Verdict

- `TRADE`

### 2. Market Summary

- platform: Polymarket
- market title: `JD Vance diplomatic meeting with Iran by April 10, 2026`
- trade archetype: `time-bucket trade`
- expression / rule-scope differences:
  - very narrow timing bucket
  - rule allows mediated in-person participation
- settlement rule:
  - Vance must personally participate in an in-person diplomatic meeting as the US representative
  - confirmation must come from official sources or a consensus of credible reporting
- settlement time:
  - `2026-04-10 11:59 PM ET`
  - `2026-04-11 08:59:59 PKT`
- executable price used in the latest sizing pass:
  - `Buy No 93.2c`
  - `Buy Yes 7.8c`
- liquidity / fee notes:
  - spread and thin near-term bucket conditions matter more than theoretical edge

### 3. Probability Assessment

- anchor probability: market around `93.2%` for `No`
- adjusted main probability: `95.5%` for `No`
- confidence interval: `94.0% - 97.0%`
- direction vs timing decomposition:
  - eventual talks still looked likely
  - talks before the `Apr 10 ET` cutoff looked materially less likely
- main uncertainty drivers:
  - whether the departure time and aircraft identification were correct
  - whether a technical stop was required
  - whether an overnight mediated session could begin immediately after arrival

### 4. Evidence Review

- decisive evidence:
  - departure around `08:47 EDT`
  - only `15.22` hours to cutoff
  - public C-32 range looked short versus the route distance
- rule-scope differences:
  - mediated in-person talks could still count as `Yes`
- timing-specific evidence:
  - AP/WTOP "expected to start Saturday"
  - Iranian-side reporting pushing back on immediate participation
- directional evidence:
  - US side was clearly moving toward talks
- conflicting evidence:
  - public sources do not fully prove the exact aircraft capability and routing
  - the tail `Yes` path remained open
- discarded / noise evidence:
  - unverified social chatter
  - AI summaries
- source reliability notes:
  - aircraft/range logic plus mainstream reporting were weighted above commentary

### 5. Mispricing / Edge

- conservative fair value: about `94.0c`
- executable value: about `93.2c`
- best expression: `Apr 10 No`
- worse expression(s):
  - `Apr 10 Yes`
  - adding more `Apr 15 Yes` as a substitute for this timing view
- if thesis is right but late:
  - `Apr 10 No` wins if the first qualifying meeting begins after `2026-04-11 08:59 PKT`
- net edge after costs:
  - positive, but thin
  - roughly `0.8c - 1.8c` per share in the working range
- why edge is or is not sufficient:
  - enough for a small timing trade
  - not enough for a large concentrated bet

### 6. Portfolio Impact

- related existing positions:
  - existing `Apr 15 Yes @ 89c`
- incremental thematic exposure:
  - this is a timing hedge, not a new narrative
- concentration / correlation concerns:
  - both positions are highly correlated with the same diplomatic timeline

### 7. Sizing

- raw Kelly:
  - with `p = 95.5%` and `price = 93.2c`, about `33.8%` bankroll
- conservative Kelly:
  - with `p = 94.0%` and `price = 93.2c`, about `11.8%` bankroll
- preferred structure / ladder:
  - small `Apr 10 No` add-on against an existing `Apr 15 Yes`
- final recommended fraction:
  - `0.5% - 1.0% bankroll`
  - if existing correlated exposure is already meaningful: `0.5% bankroll` or less
- concrete size if bankroll is provided:
  - not provided
- maximum entry price / minimum required price:
  - acceptable only up to roughly `93.5c`
  - `94c+` removes most of the edge

### 8. Kill Criteria

- what invalidates the thesis:
  - credible confirmation of near-immediate arrival plus rapid start of a qualifying in-person mediated session
- what removes the edge:
  - `No` reprices to `94c+`
- what triggers reduction or exit:
  - public confirmation that talks begin overnight before the cutoff
- exit type:
  - news-driven stop or profit-taking

## Existing Position: Apr 15 Yes @ 89c

### Working conclusion

- `hold existing, do not add`

### Why

- The entry price around `89c` looked acceptable for a broader time window.
- The same evidence that strengthened `Apr 10 No` did not destroy the `Apr 15 Yes` thesis.
- The main remaining risk was that Iranian participation would slip beyond `Apr 15 ET`, not merely beyond `Apr 10 ET`.

### Working probability range

- main probability: `93% - 94%`
- interval: `89% - 96%`

### Practical handling

- reasonable to keep
- not attractive to chase at much higher prices
- if a news spike reprices the bucket sharply upward, profit-taking could make sense

## Operational Takeaways

- For this setup, the clean structure was:
  - core thesis: broader bucket such as `Apr 15 Yes`
  - satellite timing hedge: `Apr 10 No`
- The main analytical mistake to avoid was treating "talks are happening soon" as enough support for the ultra-near `Yes`.
- The key edge came from time conversion plus route feasibility, not from direction alone.

## Sources Referenced During The Discussion

- Polymarket market page: <https://polymarket.com/event/jd-vance-diplomatic-meeting-with-iran-by>
- AP/WTOP departure report: <https://wtop.com/news/2026/04/vance-warns-tehran-not-to-play-the-us-as-he-departs-for-islamabad-for-negotiations-aimed-at-ending-the-war-with-iran/>
- AP/WTOP Saturday-start framing: <https://wtop.com/news/2026/04/asian-stocks-mostly-higher-and-oil-gains-ahead-of-planned-u-s-iran-peace-talks/>
- Anadolu denial-style reporting: <https://www.aa.com.tr/en/world/no-iranian-team-in-pakistan-or-talks-with-us-until-attacks-on-lebanon-stopped-report/3900388>
- AMC C-32 fact sheet: <https://www.amc.af.mil/About-Us/Fact-Sheets/Display/Article/977502/c-32/>

## Notes

- This note reflects the working judgment from the discussion, not a claim of certainty.
- The departure time was based on a user-provided screenshot and was treated as an input assumption in the final timing pass.
