---
description: Strict requirements for evaluating and backtesting trading strategies.
---

# Backtesting & validation guardrails

**Never** evaluate a strategy with a scratch script, a hand-counted signal list,
or a "fast vectorized" approximation that bypasses the real execution path.

1. **Use the engine.** Every backtest, sweep and validation runs through
   `src.backtesting.engine.BacktestEngine`. It enforces intrabar collision order
   (stops before targets), `edge_trigger` deduplication, position caps, costs and
   the daily halt. Bypassing it drops all of that and inflates win rate and
   profit factor.
2. **Use one source of bars:** `src.backtesting.master.load_master()`. It declares
   every source and which span each may supply, so two studies cannot silently
   test two different histories. Never load a `research/data*` folder directly.
3. **Minute data is not optional.** `m1_policy` defaults to `"require"`: the
   engine raises rather than resolving an exit on a 15-minute candle, which was
   the largest source of inflated results in this project (PF 0.93 on minute
   bars against 1.38 on coarse ones). `"skip"` leaves uncovered candles
   unsimulated and counts them; `"coarse"` reproduces the old behaviour and its
   numbers are not comparable. Report `exits_unchecked_no_m1` with any result.
4. **The archive is not the broker.** Before 2026 the minute bars come from a
   third-party archive. It agrees with the broker's own candles to about 5 cents
   through 2025 and breaks down from January 2026, which is where `KAGGLE_END`
   now stops. `scripts/validation/data_check.py` re-measures this.
5. **The holdout judges, never chooses.** Bars from 2026-11-01 onward are cut off
   unless a caller passes `allow_holdout=True`, and using it belongs in
   `research/DECISIONS.md`.
6. **Pre-register first.** See `.agents/AGENTS.md`; `prereg_check.py` and CI
   enforce it.
