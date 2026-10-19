# Pre-registration — overlap-window skip and time-of-day of the live 4-leg portfolio (descriptive + one decision)

Frozen 2026-10-19 BEFORE any result was computed. Owner questions: (1) would trading the 15:30-17:30 IST "LONDON_NY_OVERLAP" window (currently skipped by main_loop) have helped; (2) what are the best trading hours.
Prior: the corrected engine says this portfolio loses money overall (PF 0.93), so most sub-windows are expected to be negative; hour-of-day cuts over 16 hours are a multiple-testing trap, so "best hours" are only accepted if they hold out-of-sample.

## Runs (src/backtesting/engine.py, the corrected engine; cost scenario realistic_ecn; fixed 0.01 lot, $10,000 start so the sizing ladder cannot interfere; D1 bias gate ON; legs = PORTFOLIO in src/strategies/portfolio_v5_core.py)
- R0: skip_overlap_session = True (as the live bot runs). R1: skip_overlap_session = False (overlap allowed). Everything else identical.
- Coarse engine (no M1), 2022-08-01..2026-07-01: DEV 2022-08-01..2024-12-31, VALIDATE 2025-01-01..2026-06-30. M1-resolution run 2026-07-06..2026-10-13 as an accuracy check (short sample).
- Trade time = entry_time converted to IST.

## Question 1 — the overlap window
Trades in R1 whose entry falls in [15:30, 17:30) IST are exactly the ones the live skip removes. Report n, win%, PF, expectancy (R and $), net $ per period, plus whole-portfolio PF/net/maxDD for R0 vs R1.
**Decision rule:** allow the overlap only if, in BOTH DEV and VALIDATE (coarse), the overlap-window trades have PF > 1.0 and expectancy > 0 with n >= 100 over DEV+VALIDATE, and the M1 run does not contradict (PF >= 1.0 or n < 30). Otherwise keep the skip.

## Question 2 — hours
Trades from R1 grouped by IST entry hour (06..21). Per hour and per half (DEV, VALIDATE) and in M1: n, PF, expectancy R, net $.
**Selection (made on DEV only):** hours with n >= 40 in DEV, ranked by DEV expectancy; top 3 selected. They are "best hours" only if in VALIDATE each has PF > 1.0 and expectancy > 0 with n >= 40, and a combined top-3 set is positive in the M1 run. VALIDATE hour t-tests are Benjamini-Hochberg corrected over the 16 hours (normal approximation); any hour with BH p < 0.05 AND positive in both halves is flagged as a genuinely stable hour.
**Also reported (no gate):** worst hours (candidates to exclude), by leg, by direction.

## Limits (to be stated in the result)
Coarse-resolution results are optimistic for tight stops (known: PF 1.38 coarse vs 0.93 M1); only relative comparisons between windows are meaningful, and the M1 run is only ~3 months.
