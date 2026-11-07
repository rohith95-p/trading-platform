# PREREG: a fresh entry-signal search, chosen on 2004-2016, judged on 2022-2026 (2026-11-07)

**Owner's instruction, 2026-11-07:** "Start the search."

Successor to `RESULT_SignalOrCost_2026-11-07.md`, which proved the four live legs'
entries carry no directional information (PF 1.02 against a 0.91-1.04 coin-flip
band at zero cost). This searches for entry logic that does, under the cost
structure measured today.

## Measured design inputs, all taken before the candidates were chosen

These are measurements, not assumptions, and they determined the design:

1. **Spread is flat across the clock.** Median realised spread on XAUUSDm is
   ~200 points in *every* UTC hour (101,095 M15 bars, 2022-08..2026-11) —
   **$0.400 round trip at 0.02 lots**. Exness quotes a near-fixed spread, so
   **entry timing is not a cost lever**. Only the tails move (22-23 UTC mean 232
   and 220 points, rollover widening). This killed one intended search dimension
   before it cost anything.
2. **Cost floor is ~$0.51 per round trip**: $0.40 spread + $0.07 commission
   (ECN $3.50/lot) + $0.04 slippage (20 points). Measured realised cost over the
   18 years was $0.613, the balance being swap on positions held overnight.
3. **Swap is brutally asymmetric**: at 0.02 lots a **long pays $1.031 per night**
   and a **short pays exactly zero** (`costs.py`, verified live on XAUUSDm
   2026-09-01: long -515.5 points, short 0.0). Applying today's rate across
   2004-2022 is an assumption and is tested both ways (below).
4. **Holds are capped at about four nights** regardless: the Friday flatten in
   `market_hours.should_flatten_for_weekend` is unconditional, so nothing crosses
   a weekend.
5. **Required edge, computed from 2 and 3** — win rate needed for net PF 1.15
   above the 37.8% chance level, at reward/risk 1.65:

   | avg win | 0 nights | 2 nights | 5 nights |
   |---|---|---|---|
   | $13 (current legs) | 6.4 pts | 11.4 | 18.8 |
   | $26 (2x) | 4.9 | 7.4 | 11.2 |
   | $39 (3x) | 4.3 | 6.0 | 8.6 |
   | $104 (8x) | 3.7 | 4.4 | 5.3 |

   Read that carefully: **bigger targets help, but holding longs overnight more
   than cancels the gain.** A 3x-target system held five nights needs 8.6 points —
   worse than the current intraday legs' 6.4. This corrects a claim I made to the
   owner earlier today, which assumed cost stayed at $0.613 per trade regardless
   of hold length. It does not.
6. **Chance is worth 0.13 PF** on 4,250 trades (three coin-flip seeds returned
   0.91, 1.02, 1.04). No PF difference smaller than that means anything at that
   sample size, and less at smaller ones.

## Windows — a three-way split, stricter than previously committed

The 18-year holdout's pre-registration promised candidates chosen on 2004-2022
and judged on 2022-2026. This splits the selection half again, which is strictly
stronger, and nothing is loosened:

| stage | window | used for | state |
|---|---|---|---|
| SELECT | 2004-07-01 .. 2016-01-01 | generating and ranking candidates | never used for anything |
| CONFIRM | 2016-01-01 .. 2022-08-01 | cutting finalists | never used for anything |
| JUDGE | 2022-08-01 .. 2026-11-01 | the single reported number | **weakened** |

**JUDGE is declared weak, up front.** 2022-2026 has been the selection set for
most of this project — 48 screened strategies, the stop/target sweep, and at
least eight closed hypotheses in `research/registry/`. My priors about which
families to try are therefore partly shaped by it. The mitigation is that the
candidate list below is frozen in this document before anything runs, so family
choice is auditable rather than trusted. CONFIRM, which is genuinely untouched,
is the stage that carries the real weight.

`HOLDOUT_FROM = 2026-11-01` remains enforced in `load_master`; nothing after it
is read.

## Candidates — 7 signals x 3 geometries = 21, frozen here

All signals derive from the M15 view the engine passes
(`evaluate(m15_view, m5_view)`; strategies get no D1), evaluated **once per day**
at the first M15 close at or after **13:00 UTC** — chosen for liquidity, since
measurement 1 showed cost does not vary by hour. One new entry per candidate per
day. Each candidate runs **solo**, not in a portfolio, so it is judged on itself.

| id | signal | definition |
|---|---|---|
| S1 | TSMOM-10 | direction of the 10-trading-day move (960 M15 bars), require \|move\| >= 6 x ATR14 |
| S2 | TSMOM-20 | same, 20 days (1,920 bars) |
| S3 | TSMOM-40 | same, 40 days (3,840 bars) |
| S4 | DONCH-20 | break of the 20-day high/low |
| S5 | DONCH-55 | break of the 55-day high/low (5,280 bars) |
| S6 | NRX | last 3 days' range narrowest of the last 20; enter on break of that 3-day range |
| S7 | MR-20 | z = (close - mean20d)/sd20d; short at z >= +2, long at z <= -2 |

Geometries, stop/target in M15-ATR multiples — deliberately far wider than the
live legs' 2.0-3.0, per measurement 5:

| id | stop | target |
|---|---|---|
| G1 | 6 | 10 |
| G2 | 8 | 16 |
| G3 | 12 | 24 |

Thresholds (6 x ATR, z = 2, N = 3/20, Donchian 20/55) are **fixed now and not
swept**. The Donchian values are the published turtle lengths, not fitted here.
Sweeping them would multiply the candidate count and is the mechanism that
produced the last false positive.

Engine: `live_parity_preset`, `m1_policy="skip"`, `realistic_ecn`, 0.02 lots,
3 concurrent, D1 EMA20 gate **off** (it was shown to add no information today),
Atlas rule engine **off** — an edge is established first, survivability second.

## The chance control, which is the point of this design

Every candidate that reaches a gate is run with **3 seeded coin-flip direction
arms on identical entry timing** (`scripts/validation/signal_or_cost.py`'s
mechanism). A candidate must beat **the maximum** of its own control band, not a
fixed PF number. This is a per-candidate permutation test on direction and it is
what the entire project lacked until today.

For compute economy, declared here rather than discovered later: controls run
only for candidates that first clear the trade-count and PF gate. A candidate
below the PF gate cannot pass regardless of its control band.

## Gates

| stage | bar |
|---|---|
| SELECT | >= 150 trades, net PF >= 1.15 after costs, **and** PF above its own 3-seed control maximum |
| advance | **at most the top 3** by SELECT PF. Hard cap, to limit multiple comparisons |
| CONFIRM | net PF >= 1.10 **and** above its own control maximum |
| JUDGE | run **once**. PF, net, win rate, control band, and swap-on vs swap-off, all reported |

**Multiple comparisons, stated plainly:** with 21 candidates, roughly one is
expected to clear SELECT by luck alone. That is precisely why CONFIRM and JUDGE
exist and why only three advance. A SELECT number is a generator output, never
evidence.

**Swap robustness:** any candidate passing only with swap disabled is reported as
**swap-dependent** and is not advanced as a real-money proposal, because the swap
rate is one live observation extrapolated across 18 years.

## Pre-committed consequences

1. **Nothing clears SELECT → report that and stop.** No widening the family list,
   no extra geometries, no swept thresholds, no re-cut windows. These 21 are all
   that get tested under this pre-registration.
2. Clears SELECT but fails CONFIRM → reported as a failed candidate. Not re-tuned.
3. Clears all three stages → **still not a real-money proposal.** It would then
   need an Atlas survivability test (daily loss, trailing drawdown, the
   consistency rule) and a forward demo period, each pre-registered separately.
   Atlas rules can only make a system harder to survive; they never create an
   edge and are never a tuning knob.

## Honest prior, recorded before the run

**I expect this to fail.** This repository has already closed regime-conditional
trend, three TradingView indicator families, daily abnormal-return fade, a
volatility-regime governor, a ~22-variation liquidity-sweep family, FVG and
EMA-stack. The bar is 3.7 to 6.4 percentage points of genuine win-rate edge
depending on geometry. My expectation is that **0 of 21 clear all three stages**.
If any family does, I expect it to be time-series momentum (S1-S3), which has the
strongest out-of-sample evidence across asset classes and decades, and whose long
holds are at least partly protected by the Friday flatten.

Recording that here so a failure cannot later be dressed up as insight, and a
success cannot be dressed up as foresight.

Run: `python -I scripts/validation/entry_search.py --stage select`
