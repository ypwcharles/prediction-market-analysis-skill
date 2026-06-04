# Disputed Resolution Optionality

Use this reference when a Polymarket or similar prediction market is in, near, or likely to enter a disputed resolution state and the proposed trade is not primarily "hold to final payout," but "buy extreme low-price optionality and exit before the final UMA/oracle ruling if the market reprices."

## Core Distinction

Do not confuse three different trades:

1. **Resolution arb:** the event is known and the oracle path is clean enough to hold for final payout.
2. **Disputed resolution arb:** the real-world facts may support one side, but rules, UMA, platform interpretation, or governance can still defeat the trade.
3. **Disputed resolution optionality:** the side may be near-zero priced after a collapse, but still has a non-zero interpretation/reversal/repricing path before final adjudication. The edge is mainly convexity and exit timing, not final settlement certainty.

The third trade can be a real opportunity, but it must be sized and reported as an optionality trade, not as evidence that final resolution is certain.

## Entry Conditions

A disputed-resolution optionality trade can be considered only when most of these hold:

- price is in an extreme low band, normally around 0.1c-2c, where a small repricing can produce a multi-x move
- the market is disputed, governance-sensitive, or awaiting UMA/oracle/platform clarification
- the near-zero side still has a concrete non-zero path: ambiguous rule wording, unresolved proposal, credible evidence conflict, official-source ambiguity, or plausible voter/platform reversal
- order book depth supports the intended small fixed-loss entry without paying absurd spread/slippage
- there is a visible pre-final catalyst: UMA voting window, dispute escalation, platform comment, official document, holder campaign, or credible evidence drop
- the plan is to sell into repricing before final ruling unless final-resolution confidence is separately high

Reject the optionality setup if the only case is "it used to trade higher," "it is down a lot," or "the payout is huge if it somehow wins."

## Exit Thesis

The default exit is **before final UMA/oracle resolution**.

Valid exits:

- sell part or all after a repricing multiple such as 3x-10x from an extreme low-price entry
- sell into liquidity created by renewed dispute attention
- sell if bid depth appears after a platform/UMA update, even if the final answer remains uncertain
- cut or abandon if the dispute path is procedurally closed against the position

Do not let a pre-resolution swing trade silently mutate into a final-resolution conviction bet.

## Sizing Guardrails

Use fixed-loss sizing first, Kelly second.

Defaults:

- classify as `lottery lane` or `hazard lane`, not `core lane`
- use pre-reserved cash, not emergency averaging-down after a large failed core position
- cap normal optionality entries at 0.5%-3% of bankroll at risk
- allow 3%-5% only when liquidity is excellent, the non-zero path is specific, and the exit catalyst is near
- never use this structure to justify a 20%+ position while settlement ambiguity remains material
- do not average down a high-cost resolution-arb position and call it optionality; it must be a fresh low-price thesis with its own entry, exit, and max loss

Account-level sizing should stay small enough that a total write-off does not impair later opportunities. If the trade requires large size to matter, it is probably not the right expression for the account.

## Analysis Requirements

When analyzing this setup, explicitly report:

- current price band and executable depth
- whether the side has a specific non-zero resolution/repricing path
- whether the intended profit comes from final payout or pre-final repricing
- the expected holding period and catalyst window
- maximum fixed loss
- first profit-taking level and final exit level
- why the setup is not just revenge trading after a failed high-price entry

## Generic Failure Pattern

A common disputed-resolution failure pattern:

- the factual thesis is strong, but settlement pipeline risk is under-modeled
- a high-price entry is treated like a near-certain resolution arb despite open oracle/platform interpretation risk
- adverse price movement is interpreted as "cheaper" rather than potential governance-risk repricing
- averaging down consumes cash that should have been reserved for extreme low-price optionality
- a later extreme-low entry may be attractive as convexity, but only if it has its own fixed-loss size, catalyst, and exit plan

Permanent rule: **real-world truth does not pay directly; rule interpretation and oracle settlement pay.** A disputed market can be an opportunity, but the opportunity must be separated into high-price resolution confidence and low-price convexity. These require opposite sizing discipline.

## Kill Criteria

Exit or cancel when:

- UMA/oracle/platform process closes the non-zero path
- a new official clarification removes the ambiguity the trade depends on
- price rebounds to the planned target but liquidity is thin; take the available bid instead of waiting for perfect exit
- the bid disappears and no catalyst remains before final resolution
- the rationale changes from "pre-final repricing optionality" to "final resolution conviction" without new settlement evidence
