# Native MT5 retained-book test

Each report uses the original Exness XAUUSDm bid/ask archive in the 100% real-tick native MT5 Strategy Tester, with hedging, fixed position size, visible server stops and targets. Each January starts a separate $5,000 simulated evaluation. A successful evaluation starts a fresh $5,000 funded account on the next weekday. 2026 ends at the October 31 cutoff. Quarterly starts and the continuous account are listed separately.

The funded guard allows one 0.01-lot position, requires initial stop risk plus a $5 allowance to fit a $35 budget, and requests a market liquidation at $60 total floating loss. Signals, stops and targets come from the original retained strategy rules. The selector uses filtered Asian, breakout, then London priority. The book makes no filler trades for inactivity. 'uniform' applies the guard during both phases. 'phase_split' evaluates at the original native 0.02-lot settings and activates the same frozen guard for the funded phase.

A native equity/deal reconciliation is followed by the Atlas rule replay, including eligible $100 modeled cash withdrawals. MT5 net profit is the native full-window trading profit at the tested leverage and before payout deductions. The simulated account stops at a rule failure. Subtract $5 evaluation and $78 activation per activated account from eligible receipts. Whole-window trading P&L and cash withdrawn measure different outcomes.

## January phase-split attempts

| Book | Year | Funded trading P&L | PF | Result at cutoff | Conditional cash after fees |
|---|---:|---:|---:|---|---:|
| breakout | 2025 | +256.48 | 2.03 | active | +17.00 |
| filtered | 2025 | +191.79 | 2.00 | active | -83.00 |
| london | 2025 | +153.18 | 2.27 | active | -83.00 |
| both Asians | 2025 | +208.95 | 1.95 | active | +17.00 |
| filtered + London | 2025 | +350.76 | 1.77 | active | +17.00 |
| breakout + London | 2025 | +356.88 | 1.73 | active | +17.00 |
| three-leg | 2025 | +345.38 | 1.71 | active | +17.00 |
| breakout | 2026 | +174.54 | 1.61 | inactivity breach | -83.00 |
| filtered | 2026 | +118.90 | 1.74 | inactivity breach | -83.00 |
| london | 2026 | +230.09 | 1.64 | active | -83.00 |
| both Asians | 2026 | +199.62 | 2.02 | inactivity breach | -83.00 |
| filtered + London | 2026 | +317.05 | 1.59 | active | +17.00 |
| breakout + London | 2026 | +321.61 | 1.47 | active | -83.00 |
| three-leg | 2026 | +346.69 | 1.58 | active | +17.00 |

## Full native results

| Window | Book | Policy | Stage | Native positions | Native net | PF | Outcome | Conditional cash |
|---|---|---|---|---:|---:|---:|---|---:|
| 2025-01-01 to 2025-12-31 | [breakout](2025_breakout.htm) | uniform | evaluation | 49 | +341.17 | 2.07 | passed 2025-06-02 | 0.00 |
| 2025-06-03 to 2025-12-31 | [breakout](2025_breakout_funded.htm) | uniform | funded | 29 | +185.38 | 1.90 | active at cutoff | 0.00 |
| 2025-04-17 to 2025-12-31 | [breakout](2025_breakout_funded_phase_split.htm) | phase_split | funded | 35 | +256.48 | 2.03 | active at cutoff | 100.00 |
| 2025-01-01 to 2025-12-31 | [filtered](2025_filtered.htm) | uniform | evaluation | 47 | +277.05 | 2.18 | passed 2025-06-03 | 0.00 |
| 2025-06-04 to 2025-12-31 | [filtered](2025_filtered_funded.htm) | uniform | funded | 31 | +116.65 | 1.61 | active at cutoff | 0.00 |
| 2025-05-13 to 2025-12-31 | [filtered](2025_filtered_funded_phase_split.htm) | phase_split | funded | 35 | +191.79 | 2.00 | active at cutoff | 0.00 |
| 2025-01-01 to 2025-12-31 | [london](2025_london.htm) | uniform | evaluation | 69 | +170.38 | 1.44 | passed 2025-10-27 | 0.00 |
| 2025-10-28 to 2025-12-31 | [london](2025_london_funded.htm) | uniform | funded | 14 | +13.22 | 1.11 | active at cutoff | 0.00 |
| 2025-10-20 to 2025-12-31 | [london](2025_london_funded_phase_split.htm) | phase_split | funded | 17 | +153.18 | 2.27 | active at cutoff | 0.00 |
| 2025-01-01 to 2025-12-31 | [three-leg](2025_portfolio.htm) | uniform | evaluation | 111 | +448.35 | 1.75 | passed 2025-06-02 | 0.00 |
| 2025-06-03 to 2025-12-31 | [three-leg](2025_portfolio_funded.htm) | uniform | funded | 71 | +291.76 | 1.71 | active at cutoff | 0.00 |
| 2025-06-03 to 2025-12-31 | [both Asians](2025_portfolio_funded_mask3.htm) | uniform | funded | 32 | +136.76 | 1.71 | active at cutoff | 0.00 |
| 2025-04-17 to 2025-12-31 | [both Asians](2025_portfolio_funded_mask3_phase_split_m01d01x3.htm) | phase_split | funded | 38 | +208.95 | 1.95 | active at cutoff | 100.00 |
| 2025-06-11 to 2025-12-31 | [filtered + London](2025_portfolio_funded_mask5.htm) | uniform | funded | 69 | +255.46 | 1.62 | active at cutoff | 0.00 |
| 2025-04-29 to 2026-10-31 | [filtered + London](2025_portfolio_funded_mask5_phase_split_continuous.htm) | phase_split | funded | 151 | +626.42 | 1.54 | active at cutoff | 200.00 |
| 2025-04-29 to 2025-12-31 | [filtered + London](2025_portfolio_funded_mask5_phase_split_m01d01x5.htm) | phase_split | funded | 80 | +350.76 | 1.77 | active at cutoff | 100.00 |
| 2025-05-15 to 2025-12-31 | [filtered + London](2025_portfolio_funded_mask5_phase_split_m04d01x5.htm) | phase_split | funded | 75 | +334.33 | 1.79 | active at cutoff | 100.00 |
| 2025-10-01 to 2025-12-31 | [filtered + London](2025_portfolio_funded_mask5_phase_split_m07d01x5.htm) | phase_split | funded | 29 | +175.19 | 1.76 | active at cutoff | 0.00 |
| 2025-10-22 to 2025-12-31 | [filtered + London](2025_portfolio_funded_mask5_phase_split_m10d01x5.htm) | phase_split | funded | 22 | +145.50 | 1.88 | active at cutoff | 0.00 |
| 2025-06-17 to 2025-12-31 | [breakout + London](2025_portfolio_funded_mask6.htm) | uniform | funded | 61 | +301.01 | 1.79 | active at cutoff | 0.00 |
| 2025-04-22 to 2025-12-31 | [breakout + London](2025_portfolio_funded_mask6_phase_split_m01d01x6.htm) | phase_split | funded | 74 | +356.88 | 1.73 | active at cutoff | 100.00 |
| 2025-04-22 to 2025-12-31 | [three-leg](2025_portfolio_funded_phase_split.htm) | phase_split | funded | 82 | +345.38 | 1.71 | active at cutoff | 100.00 |
| 2025-04-22 to 2026-10-31 | [three-leg](2025_portfolio_funded_phase_split_continuous.htm) | phase_split | funded | 153 | +627.72 | 1.53 | active at cutoff | 200.00 |
| 2025-04-22 to 2025-12-31 | [three-leg](2025_portfolio_funded_phase_split_m04d01x7.htm) | phase_split | funded | 82 | +345.38 | 1.71 | active at cutoff | 100.00 |
| 2025-10-01 to 2025-12-31 | [three-leg](2025_portfolio_funded_phase_split_m07d01x7.htm) | phase_split | funded | 29 | +175.19 | 1.76 | active at cutoff | 0.00 |
| 2025-10-22 to 2025-12-31 | [three-leg](2025_portfolio_funded_phase_split_m10d01x7.htm) | phase_split | funded | 22 | +145.50 | 1.88 | active at cutoff | 0.00 |
| 2025-01-01 to 2025-12-31 | [both Asians](2025_portfolio_mask3.htm) | uniform | evaluation | 52 | +290.33 | 2.06 | passed 2025-06-02 | 0.00 |
| 2025-01-01 to 2025-12-31 | [both Asians](2025_portfolio_mask3_phase_split_m01d01x3.htm) | phase_split | evaluation | 52 | +580.78 | 2.06 | passed 2025-04-16 | 0.00 |
| 2025-01-01 to 2025-12-31 | [filtered + London](2025_portfolio_mask5.htm) | uniform | evaluation | 108 | +413.54 | 1.71 | passed 2025-06-10 | 0.00 |
| 2025-01-01 to 2025-12-31 | [filtered + London](2025_portfolio_mask5_phase_split_m01d01x5.htm) | phase_split | evaluation | 114 | +930.15 | 1.77 | passed 2025-04-28 | 0.00 |
| 2025-04-01 to 2025-12-31 | [filtered + London](2025_portfolio_mask5_phase_split_m04d01x5.htm) | phase_split | evaluation | 92 | +911.05 | 1.89 | passed 2025-05-14 | 0.00 |
| 2025-07-01 to 2025-12-31 | [filtered + London](2025_portfolio_mask5_phase_split_m07d01x5.htm) | phase_split | evaluation | 63 | +547.36 | 1.74 | passed 2025-09-30 | 0.00 |
| 2025-10-01 to 2025-12-31 | [filtered + London](2025_portfolio_mask5_phase_split_m10d01x5.htm) | phase_split | evaluation | 30 | +388.42 | 1.83 | passed 2025-10-21 | 0.00 |
| 2025-01-01 to 2025-12-31 | [breakout + London](2025_portfolio_mask6.htm) | uniform | evaluation | 103 | +470.54 | 1.76 | passed 2025-06-16 | 0.00 |
| 2025-01-01 to 2025-12-31 | [breakout + London](2025_portfolio_mask6_phase_split_m01d01x6.htm) | phase_split | evaluation | 121 | +1176.39 | 1.79 | passed 2025-04-21 | 0.00 |
| 2025-04-01 to 2025-12-31 | [three-leg](2025_portfolio_phase_split_m04d01x7.htm) | phase_split | evaluation | 94 | +937.79 | 1.87 | passed 2025-04-21 | 0.00 |
| 2025-07-01 to 2025-12-31 | [three-leg](2025_portfolio_phase_split_m07d01x7.htm) | phase_split | evaluation | 63 | +547.36 | 1.74 | passed 2025-09-30 | 0.00 |
| 2025-10-01 to 2025-12-31 | [three-leg](2025_portfolio_phase_split_m10d01x7.htm) | phase_split | evaluation | 30 | +388.42 | 1.83 | passed 2025-10-21 | 0.00 |
| 2026-01-01 to 2026-10-31 | [breakout](2026_breakout.htm) | uniform | evaluation | 25 | +221.44 | 1.77 | inactivity breach 2026-03-22 | 0.00 |
| 2026-02-05 to 2026-10-31 | [breakout](2026_breakout_funded_phase_split.htm) | phase_split | funded | 24 | +174.54 | 1.61 | inactivity breach 2026-03-22 | 0.00 |
| 2026-01-01 to 2026-10-31 | [filtered](2026_filtered.htm) | uniform | evaluation | 25 | +162.63 | 1.72 | inactivity breach 2026-03-22 | 0.00 |
| 2026-05-06 to 2026-10-31 | [filtered](2026_filtered_funded_phase_split.htm) | phase_split | funded | 18 | +118.90 | 1.74 | inactivity breach 2026-10-23 | 0.00 |
| 2026-01-01 to 2026-10-31 | [london](2026_london.htm) | uniform | evaluation | 48 | +172.62 | 1.37 | passed 2026-10-19 | 0.00 |
| 2026-10-20 to 2026-10-31 | [london](2026_london_funded.htm) | uniform | funded | 3 | +1.47 | 1.05 | active at cutoff | 0.00 |
| 2026-03-20 to 2026-10-31 | [london](2026_london_funded_phase_split.htm) | phase_split | funded | 40 | +230.09 | 1.64 | active at cutoff | 0.00 |
| 2026-01-01 to 2026-10-31 | [three-leg](2026_portfolio.htm) | uniform | evaluation | 71 | +282.34 | 1.41 | passed 2026-09-14 | 0.00 |
| 2026-09-15 to 2026-10-31 | [three-leg](2026_portfolio_funded.htm) | uniform | funded | 14 | +117.17 | 2.27 | active at cutoff | 0.00 |
| 2026-02-05 to 2026-10-31 | [both Asians](2026_portfolio_funded_mask3_phase_split_m01d01x3.htm) | phase_split | funded | 24 | +199.62 | 2.02 | inactivity breach 2026-03-22 | 0.00 |
| 2026-09-15 to 2026-10-31 | [filtered + London](2026_portfolio_funded_mask5.htm) | uniform | funded | 14 | +110.49 | 2.20 | active at cutoff | 0.00 |
| 2026-03-20 to 2026-10-31 | [filtered + London](2026_portfolio_funded_mask5_phase_split_m01d01x5.htm) | phase_split | funded | 59 | +317.05 | 1.59 | active at cutoff | 100.00 |
| 2026-05-13 to 2026-10-31 | [filtered + London](2026_portfolio_funded_mask5_phase_split_m04d01x5.htm) | phase_split | funded | 43 | +209.40 | 1.55 | active at cutoff | 0.00 |
| 2026-08-06 to 2026-10-31 | [filtered + London](2026_portfolio_funded_mask5_phase_split_m07d01x5.htm) | phase_split | funded | 26 | +222.18 | 2.22 | active at cutoff | 100.00 |
| 2026-09-15 to 2026-10-31 | [breakout + London](2026_portfolio_funded_mask6.htm) | uniform | funded | 14 | +146.49 | 2.52 | active at cutoff | 0.00 |
| 2026-02-09 to 2026-10-31 | [breakout + London](2026_portfolio_funded_mask6_phase_split_m01d01x6.htm) | phase_split | funded | 64 | +321.61 | 1.47 | active at cutoff | 0.00 |
| 2026-02-09 to 2026-10-31 | [three-leg](2026_portfolio_funded_phase_split.htm) | phase_split | funded | 64 | +346.69 | 1.58 | active at cutoff | 100.00 |
| 2026-05-13 to 2026-10-31 | [three-leg](2026_portfolio_funded_phase_split_m04d01x7.htm) | phase_split | funded | 43 | +216.08 | 1.56 | active at cutoff | 0.00 |
| 2026-08-06 to 2026-10-31 | [three-leg](2026_portfolio_funded_phase_split_m07d01x7.htm) | phase_split | funded | 26 | +228.86 | 2.26 | active at cutoff | 100.00 |
| 2026-01-01 to 2026-10-31 | [both Asians](2026_portfolio_mask3.htm) | uniform | evaluation | 26 | +202.55 | 1.90 | inactivity breach 2026-03-22 | 0.00 |
| 2026-01-01 to 2026-10-31 | [both Asians](2026_portfolio_mask3_phase_split_m01d01x3.htm) | phase_split | evaluation | 31 | +381.02 | 1.45 | passed 2026-02-04 | 0.00 |
| 2026-01-01 to 2026-10-31 | [filtered + London](2026_portfolio_mask5.htm) | uniform | evaluation | 71 | +275.66 | 1.40 | passed 2026-09-14 | 0.00 |
| 2026-01-01 to 2026-10-31 | [filtered + London](2026_portfolio_mask5_phase_split_m01d01x5.htm) | phase_split | evaluation | 77 | +1004.60 | 1.69 | passed 2026-03-19 | 0.00 |
| 2026-04-01 to 2026-10-31 | [filtered + London](2026_portfolio_mask5_phase_split_m04d01x5.htm) | phase_split | evaluation | 59 | +686.81 | 1.67 | passed 2026-05-12 | 0.00 |
| 2026-07-01 to 2026-10-31 | [filtered + London](2026_portfolio_mask5_phase_split_m07d01x5.htm) | phase_split | evaluation | 34 | +667.99 | 2.42 | passed 2026-08-05 | 0.00 |
| 2026-10-01 to 2026-10-31 | [filtered + London](2026_portfolio_mask5_phase_split_m10d01x5.htm) | phase_split | evaluation | 7 | +117.72 | 2.50 | active at cutoff | 0.00 |
| 2026-01-01 to 2026-10-31 | [breakout + London](2026_portfolio_mask6.htm) | uniform | evaluation | 70 | +301.23 | 1.40 | passed 2026-09-14 | 0.00 |
| 2026-01-01 to 2026-10-31 | [breakout + London](2026_portfolio_mask6_phase_split_m01d01x6.htm) | phase_split | evaluation | 82 | +967.48 | 1.47 | passed 2026-02-06 | 0.00 |
| 2026-04-01 to 2026-10-31 | [three-leg](2026_portfolio_phase_split_m04d01x7.htm) | phase_split | evaluation | 60 | +766.65 | 1.75 | passed 2026-05-12 | 0.00 |
| 2026-07-01 to 2026-10-31 | [three-leg](2026_portfolio_phase_split_m07d01x7.htm) | phase_split | evaluation | 35 | +747.83 | 2.59 | passed 2026-08-05 | 0.00 |
| 2026-10-01 to 2026-10-31 | [three-leg](2026_portfolio_phase_split_m10d01x7.htm) | phase_split | evaluation | 7 | +117.72 | 2.50 | active at cutoff | 0.00 |

JSON audits preserve chronological terminal equity extrema, Atlas events and payout timestamps, plus a modeled commission, swap and slippage sensitivity that holds native fills fixed. This research uses selected historical USD news events. The full Atlas all-currency calendar, Atlas-specific symbol trading sessions and complete cost history are unverified. No cash was received or paid. Earlier results informed the phase choice and guard settings.

The robustness export reports trade-outcome bootstrap intervals, best/worst-trade removals, random reorderings, ratios, and within-batch multiple-testing estimates. The DSR calculation uses the cross-book variance of daily Sharpe across same-window uniformly guarded candidates. These trial counts exclude earlier strategy development. The funder compliance and payout decision do not use Monte Carlo or bootstrap paths.

[Summary CSV](summary.csv) · [Robustness and metric inputs](robustness.json) · [Native original evaluation records](../retained_mt5/native_comparison.md)
