# RESULT: are the live ATR stops the right stops? (2026-11-01)

Pre-registration: `PREREG_StopRobustness_2026-11-01.md`. Script: `scripts/validation/stop_robustness.py`.

**T1 Stability (60-combination grid, 2022-26):** live sits on a plateau, not a spike. All 8 grid neighbours are
profitable for every strategy. Ranks: Asian Range Filtered 4/60, NY Session Reversal 8/60, Asian Breakout 23/60,
London Momentum Tight 37/60 (its better-looking combinations failed on Jul-Oct 2026 in the earlier sweep).

**T2 Volatility measure (same average stop size):**

| Measure | DEV | TEST | RECENT |
|---|---|---|---|
| **Live: ATR(14), 15-min bars** | +$134 PF 1.08 | +$1,136 PF 1.48 | +$790 PF 1.81 |
| ATR(7), 15-min | +$82 | +$1,002 | +$720 |
| ATR(28), 15-min | +$174 | +$941 | +$520 |
| ATR(14), 1-hour | +$178 | +$560 | +$593 |
| ATR(14), daily | −$32 | +$470 | +$483 |
| Fixed-dollar stop (no adapting) | +$27 | −$191 | +$98 |

No measure beats live in all three windows; adapting to volatility is clearly better than a fixed-dollar stop.
An independently recomputed closed-bar ATR(14) reproduces the backtest's stops exactly.

**T3 Flip:** same entries, opposite direction: DEV −$375 (PF 0.79), TEST −$1,269 (0.61), RECENT −$727 (0.52).
The edge comes from the entry signals, not from the exit or cost model.

**T4 Costs:** spread x1.5: PF 1.04 / 1.45 / 1.80 · spread x2: 1.01 / 1.43 / 1.79 · 60-point stop slippage:
1.07 / 1.48 / 1.80. Robust to costs, but DEV (2022-24) drops to break-even with double spreads.

**T5 Monte Carlo (20,000 six-month paths from 42 real months):** 5th percentile −$173, median +$244, 95th +$916;
P(six months negative) 19%; P($500 drawdown) 0.4%; P(+$150 before −$500) 74%.

**Live/backtest gap found:** live computes ATR on 15-minute bars *including the bar that just opened*
(`main_loop` passes the full rates array, whose last row is the forming bar); the backtest uses closed bars. On
2026-10-30 the live ATR was 95% and 91% of the closed-bar ATR. Replaying with stops and targets 6% tighter:
DEV +$161, TEST +$1,064, **RECENT +$475 instead of +$790**. Fix: pass closed bars only to `calculate_atr_stops`
(owner decision pending; live code, freeze week).
