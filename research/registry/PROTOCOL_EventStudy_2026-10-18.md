# Event study protocol — gold around scheduled USD releases (descriptive; NOT a trading trial)

Frozen 2026-10-18 before computing anything. This measures, it does not trade. No trial number is consumed; a trading rule may only be pre-registered (#642) if this study shows a stable, economically interpretable pattern.

Data: research/data/XAUUSDm_M15.npy (UTC, 2022-07..2026-10-13) and research/events/usd_high_impact_2022_2026.csv. Events: NFP, CPI, PCE, FOMC_STATEMENT (FOMC_PRESSER reported separately, secondary). All event times fall on M15 boundaries. Events with a gap in the bars from -60 min to +120 min are dropped and counted.
Not available (stated limitation): consensus/actual values, so NO surprise-direction or surprise-magnitude analysis. Only event type, year, and pre-event trend can be split.

## Definitions (per event, E = event time)
- Reference price P0 = OPEN of the M15 bar starting at E (the price at the release).
- r(h) = (close of the bar ending E+h minus P0) for h = 15, 30, 60, 120 min. Unit: price, and in multiples of A = mean true range (M15) of the 8 bars before E.
- Volatility ratio = mean M15 true range over E..E+60 min / A.
- Spread expansion = bar spread of the E bar and the E+15 bar relative to the median bar spread of the 8 pre-event bars.
- MFE/MAE(h) = max up / max down excursion from P0 within E..E+h (in A).
- Reversal test: sign(r(15)) vs sign(r(120) - r(15)); reversal = opposite sign. Pre-event trend = sign of (P0 - open of the bar 8 bars earlier).

## Pre-declared questions (the full list of tests; BH correction applied over them)
1. Volatility ratio > 1 (sign test + median) per category (4 + presser).
2. Mean r(15) = 0 per category (t-test).
3. Mean r(120) - r(15) = 0 per category (t-test) — drift after the first 15 minutes.
4. Reversal rate = 50% per category (binomial) — does the first 15 minutes continue or revert.
5. Spread at E+15 vs pre-event median (median ratio) — can a post-release rule even afford to enter.
Stability: every effect is also reported by calendar year; a pattern counts as stable only if the sign is the same in at least 3 of 4 full years (2023-2025 plus partial 2022/2026 shown) and the BH-adjusted p < 0.05.

## Decision
- Volatility/spread findings are descriptive facts that can be used for risk rules (stay out, widen stops) regardless.
- A directional or reversal trading rule may be pre-registered ONLY if questions 2-4 show a stable, BH-significant effect larger than the post-release spread cost. Otherwise: no trial; record "no tradable event pattern" and stop searching this family.
