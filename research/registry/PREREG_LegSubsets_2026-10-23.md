# PREREG: which subset of the live legs, if any, has an edge (2026-10-23, written BEFORE any run)

Trigger: owner asked to "figure something out to be profitable". 3-day replay (10-20..10-23) showed TrendPullback = 25 of 32
trades and -$42.66, NVMR +$27.91 from 2 trades. That is 3 days: an anecdote, NOT evidence. This test uses the full history.

## Hypotheses (exactly 3, no others will be run or reported selectively)
- H1  all 4 live legs (baseline, current portfolio)
- H2  drop TrendPullback: BB_MEAN_REVERSION_V5 + NVMR_TARGET_10_V5 + FVG_NY_TIGHT_V5
- H3  NVMR_TARGET_10_V5 + BB_MEAN_REVERSION_V5 only

## Setup (frozen)
Corrected engine, coarse mode (M15, entry bar tested), D1 EMA20 gate ON, SL/TP 0.5/1.5 ATR as live, fixed 0.01 lot,
cost scenario `realistic_ecn`, starting balance $10,000 (so ruin/sizing never changes the trade set), no live_parity rules.
No parameter of any leg is changed or tuned.

## Chronological splits (frozen, never re-cut)
- DEV      2022-08-01 .. 2024-06-30
- VALIDATE 2024-07-01 .. 2025-06-30
- HOLDOUT  2025-07-01 .. 2026-07-01   (gold's strongest rally; a long bias flatters this window, so a pass here alone is NOT a pass)

## Pass rule (all must hold, for a single hypothesis)
1. PF >= 1.15 AND n >= 150 in DEV, and again in VALIDATE (not just one)
2. PF >= 1.00 in HOLDOUT
3. Bootstrap (trade-level, 5000 resamples) 5th-percentile PF over DEV+VALIDATE combined > 1.00
Multiple-testing: 3 hypotheses -> a pass is only "worth a demo trial" if it also clears rule 3.

## What will NOT be done
No re-running with different thresholds, windows, SL/TP, or legs after seeing results. If nothing passes, the answer is "no".
