# Result — entry search: 0 of 21 survived. Search closed.

Pre-registered in `PREREG_EntrySearch_2026-11-07.md` (`29e8524`, addendum
`ac99cdd`, disclosure `23d9d4e`), all committed before the candidates ran.

**Verdict: no candidate cleared CONFIRM. The search is closed under its own
pre-registered terms.**

This matches the prior recorded before running: *"My expectation is that 0 of 21
clear all three stages."*

## Stage 1 — SELECT, 2004-2016 (the selection set)

21 candidates, `realistic_ecn`, 0.02 lots, solo, D1 gate off, Atlas off.

| candidate | trades | net $ | PF | win % | avg win | avg loss |
|---|---|---|---|---|---|---|
| NRX_S12_T24 | 82 | +573.85 | 1.51 | 52.4 | 39.53 | −28.88 |
| **DONCH20_S6_T10** | 254 | +845.19 | **1.34** | 45.7 | 28.43 | −17.77 |
| **DONCH55_S6_T10** | 152 | +307.68 | **1.20** | 42.8 | 28.66 | −17.88 |
| DONCH20_S8_T16 | 254 | +524.42 | 1.18 | 46.9 | 28.58 | −21.31 |
| DONCH20_S12_T24 | 254 | +460.59 | 1.15 | 49.6 | 28.48 | −24.43 |
| TSMOM40_S6_T10 | 2,325 | +359.28 | 1.01 | 42.6 | 24.09 | −17.60 |
| TSMOM10_S6_T10 | 2,046 | +51.66 | 1.00 | 43.3 | 23.07 | −17.57 |
| TSMOM20_S6_T10 | 2,213 | −575.75 | 0.97 | 42.2 | 23.59 | −17.68 |
| TSMOM40_S12_T24 | 1,784 | −1,064.84 | 0.96 | 46.0 | 31.81 | −28.23 |
| TSMOM20_S8_T16 | 1,524 | −2,529.01 | 0.86 | 41.5 | 24.84 | −20.48 |
| TSMOM10_S12_T24 | 919 | −2,616.37 | 0.79 | 44.7 | 23.43 | −24.10 |
| MR20_S12_T24 | 388 | −2,306.35 | 0.62 | 37.1 | 26.00 | −24.80 |
| MR20_S6_T10 | 385 | −2,125.50 | 0.55 | 34.5 | 19.82 | −18.89 |
| MR20_S8_T16 | 381 | −2,477.40 | 0.55 | 34.4 | 23.50 | −22.23 |

(Full 21 rows in `entry_search_select_2026-11-07.json`.)

Chance test, each candidate against **its own** 3-seed coin-flip band:

| candidate | real PF | control band | |
|---|---|---|---|
| DONCH20_S6_T10 | 1.34 | 1.03–1.04 | above chance |
| DONCH20_S8_T16 | 1.18 | 1.10–1.22 | inside chance |
| DONCH55_S6_T10 | 1.20 | 0.72–1.15 | above chance, barely |

Two advanced. `NRX` was filed **inconclusive** at 82 trades by the trade-count
gate — automatically, with no intervention. It topped the table at PF 1.51 and
had been flagged underpowered in the addendum *before* the run. A week ago that
1.51 is what would have reached the owner.

## Stage 2 — CONFIRM, 2016-2022 (never used for anything, by any search here)

| candidate | trades | net $ | PF | win % |
|---|---|---|---|---|
| DONCH55_S6_T10 | 78 | −15.44 | **0.98** | 42.3 |
| DONCH20_S6_T10 | 149 | −324.33 | **0.82** | 40.9 |

Both fail. Neither reaches the PF 1.10 bar; both lose money.

Both also land below the 150-trade power gate (149 and 78), so by the letter they
are **"failed to demonstrate" rather than "refuted"**. That distinction is
recorded honestly, but it is not a reprieve: PF 0.82 on a negative net is not a
near miss, and the trade rate is unchanged between stages (22/yr on SELECT,
23/yr on CONFIRM) — CONFIRM is simply a shorter window.

**The only uncontaminated number for DONCH20_S6_T10 is CONFIRM's PF 0.82.**
Pooling it with the data that selected it would be meaningless, and is not done.

## Stage 3 — JUDGE, 2022-2026: never run

The harness reads the advancing list from disk and refused:

```
nothing advanced from confirm -- per the pre-registration, stop here.
```

**2022-2026 was not touched by this search.** The weakened holdout is no weaker
than it was this morning, and is still available to a future search.

## What was actually learned

**1. Time-series momentum does not work here, and this is the best-powered
result in the project.** PF 0.79–1.01 across all nine variants on 900–2,300
trades each. It was my pre-registered pick for most likely survivor, on the
strength of decades of cross-asset literature. It failed on volume of evidence,
not on a thin sample. That is a real finding about XAUUSD at 0.02 lots under this
cost structure.

**2. Multi-day mean reversion on gold is actively negative**: PF 0.55–0.62 on
~380 trades per variant, win rate 34–37% against a 37.8% chance level. Not noise
— a consistent losing edge.

**3. A coin flip at a Donchian breakout is profitable.** The control arms
returned **PF 1.03–1.22**, above 1.00 even after costs. Direction is irrelevant
to that; what pays is *entering as volatility expands*, because a 1.67
reward-to-risk target then gets hit more often than the static geometry predicts.
So DONCH20's apparent 1.34 was really a **0.30 increment** over chance, and that
increment did not survive. This also means **any** future breakout-timed strategy
must be measured against a breakout-timed control, never against PF 1.00, or it
will look good for reasons that have nothing to do with its signal.

**4. Geometry sensitivity is a reliable warning.** DONCH20 read 1.34 / 1.18 /
1.15 across the three geometries, and only the tightest beat its control. Real
information should not be that sensitive to stop placement. The warning was
visible at SELECT and CONFIRM confirmed it.

**5. The chance band is wide enough to have fooled every earlier result here.**
Control seeds spanned 0.12 PF at 254 trades and **0.43 PF at 152 trades**. Every
historical "edge" in this repo was measured on a few hundred trades with no
control arm at all.

## Consequences, as pre-committed

1. **This search is closed.** No widened family list, no extra geometries, no
   swept thresholds, no re-cut windows, no second look at the two that advanced.
2. Nothing here is a real-money proposal. The live four legs remain retired
   (`RESULT_SignalOrCost_2026-11-07.md`), and nothing has replaced them.
3. 2022-2026 remains unspent by this search.

## What a next attempt would have to be, if there is one

Not a variation on these. The honest reading of today is that **session-timed and
daily-structure directional signals on XAUUSD do not clear a $0.51–0.61 round-trip
cost at 0.02 lots**, and that this repository has now tested that proposition
across roughly 70 strategy variants and 18 years without finding an exception.

Anything further should change a *structural* input rather than search the same
space again: a cheaper instrument or cost basis, a larger position size so the
fixed cost is a smaller share of each win, a data source other than price alone,
or a different holding horizon than intraday-to-four-days. Each of those is a
different project, not another sweep, and none should start without the same
pre-registration and control-arm discipline used here.
