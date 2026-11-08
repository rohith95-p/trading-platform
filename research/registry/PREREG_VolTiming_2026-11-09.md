# PREREG: is the breakout-timing payoff real, and is it big enough to matter? (2026-11-09)

**Owner's instruction, 2026-11-09:** "I need the real edge. Try combinations,
experiment, test over past data. And test till you can find the real edge."

## Two corrections that come first

**1. Position size does not change whether an edge exists.** On 2026-11-07 I told
the owner that at 0.20 lots "the same edge needs about a tenth as much to clear."
That is wrong. Every cost component here is charged per lot — spread, slippage,
commission and swap all scale with size — so the cost-to-win ratio is invariant:

| lots | cost/round trip | avg win | cost as % of win |
|---|---|---|---|
| 0.02 | $0.510 | $12.94 | **3.94%** |
| 0.05 | $1.275 | $32.35 | **3.94%** |
| 0.20 | $5.100 | $129.40 | **3.94%** |
| 1.00 | $25.500 | $647.00 | **3.94%** |

Size changes how many dollars a result is worth. It does not change the win rate
required to make one. Retracted.

**2. Cheaper trading cannot rescue a coin flip.** With costs set to **zero**, the
live legs returned PF 1.02 (`RESULT_SignalOrCost_2026-11-07.md`). So moving to a
raw-spread account — which genuinely would cut the round trip from ~$0.51 to
~$0.17 — takes the 18-year PF from 0.90 to roughly 0.97, not to 1.15. Lower cost
is worth having and is a real, actionable improvement, but **it cannot
manufacture an edge where there is none.** Only an edge can.

## Why this test exists

Every one of the ~70 variants this project has tested asked the same question:
*which way will price go?* The answer, repeatedly and now conclusively, is that
these signals cannot tell.

But the control arms of the 2026-11-07 search produced something nobody designed
for. Randomising the **direction** at a 20-day Donchian breakout, keeping the
entry timing identical, returned:

| geometry | coin seeds | mean |
|---|---|---|
| DONCH20 6/10 ATR | 1.033, 1.027, 1.042 | 1.034 |
| DONCH20 8/16 ATR | 1.157, 1.220, 1.098 | 1.158 |

**Six of six above 1.00, after costs.** A coin flip made money. (DONCH55's three
were 1.146, 0.847, 0.719 on only 152 trades and are not relied on here.)

**Proposed mechanism:** volatility clustering. Realised volatility is elevated
immediately after a range breakout, so a target placed at 1.67x the stop distance
is reached more often than the static random-walk probability of
`S/(S+T)` = 37.5% predicts. That is a property of *when* you enter, not of *which
way* you point — and it is the first thing in this project's history that is not a
directional claim.

**Second, independent idea it enables:** if direction genuinely does not matter,
then always trading **short** removes the swap entirely, because at 0.02 lots a
long pays $1.031 per night and a short pays exactly zero.

## What this test can and cannot win — stated before running

The implied win rate behind a PF of 1.03-1.16 at reward/risk 1.6 is about
**40-42%**, against a 37.8% chance level. So the mechanism, if real, is worth
roughly **2 to 3 points** of win rate.

The bar for real money at this geometry is about **4.3 to 4.9 points**.

**So I expect this effect to be real but too small to trade.** I am not testing
"does the effect exist"; I am testing "is it big enough to matter," and my
recorded expectation is **no**. Saying so now because an effect that is real,
publishable and unprofitable is the most seductive trap left in this project.

## Arms

Signals: **DONCH20 at 6/10** and **DONCH20 at 8/16** — the two whose control arms
were all above 1.00. Nothing new is invented and no threshold is swept.

| arm | what it does |
|---|---|
| `as_is` | the breakout's own direction (reference; already known to be 0.82 on CONFIRM at 6/10) |
| `long_only` | take only upside breakouts |
| `short_only` | take only downside breakouts |
| `force_short` | take **every** breakout, always short — direction-independent, zero swap |
| `force_long` | take every breakout, always long — the swap-paying mirror |
| `coin` x3 | seeded coin-flip direction: the chance band |

## Windows

| stage | window | state for *this* question |
|---|---|---|
| generated on | 2004-2016 | observed; this is where the hypothesis came from |
| **TEST** | **2016-2022** | control arms were **never run** here (CONFIRM ran no controls — no candidate cleared its gate), so every arm above except `as_is` is unobserved |
| CONFIRM | 2022-2026 | **completely unspent.** Touched only if TEST passes |

`HOLDOUT_FROM = 2026-11-01` stays enforced.

## Gate

Unchanged from the search it descends from, and deliberately not lowered to fit a
small effect:

> **>= 150 trades, net PF >= 1.15 after `realistic_ecn` costs, and PF above the
> maximum of its own 3-seed coin-flip band.**

A PF of 1.05 is not a pass. It would not survive real slippage, and it cannot
carry an Atlas drawdown limit. If the effect is real and lands at 1.05, the
correct verdict is **"real but not tradeable,"** and that is a fail.

With 10 arms, roughly one is expected to clear a nominal gate by luck. Only an arm
that beats its own control band advances, and at most **one** arm goes to CONFIRM.

## Pre-committed consequences

1. **Nothing clears TEST → the volatility-timing idea is closed**, and with it the
   signal-search route to real money. I will say plainly that this project has no
   demonstrated path to a funded account through strategy search, rather than
   proposing a further variation.
2. An arm clears TEST → **one** arm is run once on 2022-2026, and that single
   number is the verdict.
3. Even a pass at CONFIRM is not a real-money proposal: it would still need an
   Atlas survivability test and a forward demo period, each pre-registered.
4. No swept thresholds, no new geometries, no re-cut windows, no second look.

Run: `python -I scripts/validation/vol_timing.py --stage test`
