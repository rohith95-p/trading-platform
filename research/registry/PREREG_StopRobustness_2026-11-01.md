# PREREG: are the live ATR stops the right stops? Robustness tests (2026-11-01)

**Owner question:** are we sure the ATR stops are the proper ones, and is the test method itself right?

**Live stop, as coded:** stop = multiple x ATR(14) of 15-minute bars including the bar that just opened
(`RiskManager.calculate_atr_stops`); the backtest engine builds the same forming bar (`BacktestEngine._view`).
Live multiples (stop / target): Asian Range Filtered 2.5 / 3.5, Asian Breakout 3.0 / 5.0, London Momentum Tight
2.0 / 4.0, NY Session Reversal 2.5 / 4.5. Entries: the live 4-leg entries, M1 exit replay with engine costs.

**T1 Stability:** on the 60-combination stop/target grid (`sltp_sweep_2026-10-30.json`), the live combination's rank
and the average of its grid neighbours, DEV+TEST and RECENT. A spike (live much better than its neighbours) = fragile.

**T2 Volatility measure:** same average stop size, different measure. For each measure X, both multiples are scaled by
median(live ATR) / median(X) over that strategy's DEV trades. Measures: ATR(7), ATR(14), ATR(28) on closed 15-minute
bars; ATR(14) on closed 1-hour bars; ATR(14) on closed daily bars; a fixed-dollar stop (the DEV median live stop,
same stop-to-target ratio). A measure "beats live" only if its net is higher in DEV, TEST and RECENT separately.

**T3 Flip:** same entry times, opposite direction, live exits. Expect a loss in every window; a profit would mean the
edge comes from the exit/cost model, not from the entry signals.

**T4 Costs:** live exits with spread x1.5, spread x2, and stop slippage 60 points instead of 20. Report PF per window.

**T5 Monte Carlo:** block bootstrap by calendar month of the live per-trade P&L (all M1 windows), 20,000 paths of
6 months; report the 5th/50th/95th percentile of 6-month net, P(a $500 drawdown from the running peak) and
P(+$150 reached before a $500 drawdown).

Decision rule: the live stops stay unless T2 finds a measure that beats live in all three windows (that would then
need a full-engine confirm and a decision-log entry; no live change during the freeze week).
