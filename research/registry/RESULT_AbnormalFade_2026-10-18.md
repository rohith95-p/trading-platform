# Result — daily abnormal-return fade (trial #643)

Run once, exactly as frozen (prereg be2d28c, simulator committed before the run, no governor filter). Raw: abnormal_fade_result_2026-10-18.json.

## A. Mechanism check on the 22-year daily history (2004-06 .. 2026-02, 5,558 days)
342 days with |return| > 2 sigma (prior 60 days). Next-day fade return (against the move):
- Mean **-0.098%** (negative: no reversal, if anything slight continuation), hit rate 48.0%, t = -1.38, p = 0.17 -> **not significant, wrong sign**.
- First half -0.011% (49.7% hit), second half -0.186% (46.2%); positive in only 9 of 23 years.
- Conclusion: the "next-day mean reversion after abnormal moves" premise is NOT supported on gold's own long history. The rule has no mechanism.

## B. Trading rule on broker data
| Period | Trades | Win % | PF | Expectancy | Net R | Max DD | Stress (2x spread + $0.30) PF |
|---|---|---|---|---|---|---|---|
| DEV 2022-08..2024-12 | 31 | 42 | **0.78** | -0.08 R | -2.3 | 5.7 R | 0.71 |
| VALIDATE 2025-01..2026-06 | 26 | 38 | **0.99** | -0.01 R | -0.1 | 5.0 R | 0.94 |
| HOLDOUT 2026-07..2026-10-13 | 3 | 67 | 1.58 | +0.07 R | +0.2 | 0.4 R | 1.48 |
| DEV+VALIDATE | 57 | 40 | 0.88 | -0.04 R | -2.5 | 6.8 R | 0.82 |
Most trades exit on the time stop (38 of 57); only 7 hit the 1.5R target. DSR (N=643) ~ 0.

## Verdict: CLOSED
DEV and VALIDATE both fail the PF > 1.25 gate (0.78 and 0.99), expectancy is negative, and 57 trades is below the 100-trade bar (inconclusive even if it had passed). The 3-trade holdout proves nothing. Part A shows the premise itself does not hold on 22 years. No forward test, no tuning.
