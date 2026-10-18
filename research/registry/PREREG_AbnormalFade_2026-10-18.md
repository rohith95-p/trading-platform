# Pre-registration — Daily abnormal-return fade on XAUUSDm (trial #643)

Frozen 2026-10-18 BEFORE any result was computed. No governor/regime filter (the volatility governor failed its own gate, RESULT_VolGovernor). No change after the first run; failure closes the hypothesis.
Hypothesis: after an abnormally large daily move (|return| > 2 sigma of the prior 60 days), gold partially reverts the next day (documented pattern: intraday momentum, next-day mean reversion).
Expected sample is small (roughly 4-5% of days exceed 2 sigma, fewer after filters), so a pass is unlikely to reach the 100-trade bar. That is stated now: with < 100 trades in DEV+VALIDATE the verdict is "inconclusive", not a pass, and the descriptive long-history check below carries the weight of evidence.

## A. Descriptive mechanism check (one test, the long history)
- Data: research/data/kaggle_22yr/XAUUSDm_D1.npy (the archived long daily history) — daily close-to-close simple returns r_t.
- z_t = r_t / std(r over the 60 days BEFORE day t). Event days: |z_t| > 2.
- Statistic: fade_return = -sign(r_t) * r_{t+1} (next-day close-to-close return in the direction opposing the move), in %. Test mean = 0 (t-test, normal approximation) and report mean, hit rate, n, and the same by decade/era (first/second half) for stability. One test, alpha 0.05; no multiple-testing family.
- Interpretation: only if the mean fade is positive, significant, and the same sign in both halves does the trading rule below count as having a mechanism.

## B. Trading rule (broker data, 2022-07..)
- Data: research/data/XAUUSDm_D1.npy and XAUUSDm_M15.npy (UTC).
- Signal day D (a completed UTC D1 bar): z_D = (close_D/close_{D-1} - 1) / std of the 60 prior daily returns; |z_D| > 2.
- Direction: FADE: z_D > 2 -> SHORT; z_D < -2 -> LONG.
- Skips: day D contains an FOMC_STATEMENT (the move may be caused by the decision); any event in research/events/usd_high_impact_2022_2026.csv within 4 hours AFTER the entry time; no 07:00 UTC M15 bar on day D+1; insufficient history (< 60 returns or ATR).
- Entry: OPEN of the 07:00 UTC M15 bar on the next UTC day (long at ask = open + bar spread, short at bid).
- Stop: 1.0 x ATR14 (Wilder) of the D1 series as of day D's close. Target: 1.5 x risk. Time exit: close of the last M15 bar of day D+1 (shorts pay the spread). Stop-first when one M15 bar touches both; stops checked from the entry bar.
- One position, one trade per signal, no re-entry, no pyramiding, no recovery sizing.
- Costs: bar spread at entry (long) and exit (short); swap -0.5 price units per 0.01 lot per rollover night for longs (the position is held within one UTC day, 0 nights unless the exit crosses a rollover); stress run = spread x2 + $0.30 slippage per fill. R = pnl / stop distance; reporting curve 0.25% per trade on $5,000.

## Splits and gates
DEV 2022-08-01..2024-12-31 · VALIDATE 2025-01-01..2026-06-30 · HOLDOUT 2026-07-01..end of data (2026-10-13; already seen by #640/#641, so it can falsify, not prove).
| Stage | Pass |
|---|---|
| DEV and VALIDATE | each: PF > 1.25 net of costs, expectancy > 0 |
| Combined DEV+VALIDATE | >= 100 trades (else "inconclusive"), max DD < 8% of the curve (< 32 R), no quarter > 40% of net R, no single trade > 15% of net R |
| Stress | expectancy > 0 on DEV+VALIDATE under 2x spread + $0.30 |
| HOLDOUT | PF > 1.0 and expectancy > 0 -> 90-day frozen forward test; else CLOSE #643 |
DSR with N = 643 (V = 1/T). If DSR < 0.95 the result is not claimed as an edge even with PF > 1.

## Report
As #640/#641, plus long/short split, event/non-event, exits, and part A's table.
