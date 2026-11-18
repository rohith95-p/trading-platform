# Profitable XAUUSD results: requested periods

Requested on2026-11-11. Profitable means net trade P&L after the modeled spread, slippage, commission and applicable funding is greater than zero. The2019-2024 criterion is aggregate profit across the six years, not a promise of profit every year.

The2026 price-rule tests cover January1 through October29 inclusive (October30 exclusive), the existing research data cutoff. This is neither the full calendar year nor through today. November holdout was not consumed. The separately audited original-portfolio record covers July6 through October29 only.

## Exact-window price-rule replays

Replayed12 fixed candidate variants in both requested windows, starting flat and liquidating at the last in-window quote. No parameter optimization. Each unit is .02lot (100oz perlot); Turtle four-unit losses also remain in the complete JSON. Signal histories warm up before the start. M15/coarser execution, no full Atlas evaluation/funded/payout engine. Positive results are retrospective screens, not independently established tradable edge.

The table lists every candidate profitable in either exact-window test. Negative opposite-period results are retained for context.

| Strategy | 2019-2024 net | PF | Trades | 2026 available net | PF | Trades |
|---|---:|---:|---:|---:|---:|---:|
| Forecast-to-Fill Core | $922.49 | 1.266 | 143 | $618.49 | 1.278 | 13 |
| Daily RSI(2) Pullback | $516.95 | 1.558 | 55 | $-424.32 | 0.554 | 6 |
| Asia clock long | $168.41 | 1.021 | 1546 | $-519.53 | 0.932 | 214 |
| Turtle System 2, one unit (M15) | $100.70 | 1.093 | 26 | $-290.93 | 0.723 | 5 |
| Supertrend 1H | $61.45 | 1.005 | 838 | $-141.56 | 0.982 | 118 |
| Supertrend 4H | $-1,530.57 | 0.793 | 255 | $4,085.50 | 3.582 | 26 |
| RSI(2) R3, 2H | $-934.37 | 0.739 | 353 | $1,174.20 | 2.201 | 36 |
| US-to-Asia continuation | $158.96 | 1.049 | 639 | $-285.95 | 0.900 | 80 |

**Forecast-to-Fill Core is the only one of these price-rule candidates positive in both windows.** Its PFs1.266/1.278 remain below1.30. The long-history Daily RSI2 winner loses in2026, while the strong2026 Supertrend4H and RSI2 R3 winners lose over2019-2024. This is regime sensitivity, not evidence of a universally profitable strategy.

| Strategy | 2019-2024 closed-balance DD | 2026 closed-balance DD | 2026 win rate |
|---|---:|---:|---:|
| Forecast-to-Fill Core | 12.93% | 15.83% | 30.8% |
| Daily RSI(2) Pullback | 7.29% | 17.83% | 83.3% |
| Asia clock long | 9.20% | 27.87% | 49.5% |
| Turtle System 2, one unit (M15) | 9.97% | 16.41% | 60.0% |
| Supertrend 1H | 20.35% | 24.42% | 33.9% |
| Supertrend 4H | 46.39% | 8.58% | 53.8% |
| RSI(2) R3, 2H | 21.44% | 10.23% | 75.0% |
| US-to-Asia continuation | 8.31% | 23.63% | 42.5% |

Drawdowns above exclude floating intratrade losses. They cannot establish daily/trailing drawdown compliance. Some screening rules have no protective stop. Small samples such as26 Supertrend4H trades in2026 or55 daily RSI2 trades across six years need stronger validation before promotion. PF and win rate measure different things: high win rate alone does not imply profit.

## Additional positive archived cash candidates

These are realized cash allocations from saved dated runs, filtered by exit date, not newly bounded replays. They are kept separate because aggregation can omit period-end floating P&L and can inherit resets between old studies. We recovered30 named dated candidates and reviewed all of those allocations. The table lists additional positive candidates not already represented above, plus the minute-execution Turtle variant.

| Saved candidate | Cash realized in2019-2024 | Declared coverage | 2026 status |
|---|---:|---|---|
| COT managed-money crowding fade | $69.80 | Full2019-2024 declared | Not verified |
| GLD creations flow | $148.90 | Full2019-2024 declared | Not verified |
| Post-CPI/NFP reaction fade | $104.83 | Full2019-2024 declared | Not verified |
| PAXG flow | $60.73 | Only2022-2024 within requested period | Not verified |
| Turtle System2 one-unit M1 audit | $100.04 | Full2019-2024 declared | Not verified |

Historical input publication vintages, release schedules and the actual provider/contract cost assumptions retain the limitations of their original protocols. PAXG has no2019-2021 history here; those dates are unknown, not zero-return years. Do not promote these additional candidates based solely on small positive cash totals.

## Original four-strategy portfolio: audited2026 slice

Saved fresh replay and independent check: research/results/fresh_recent_2026-11-11/trades.json and check.json. The following are contributions within the shared portfolio, with shared entry slots/gates, not independent standalone tests. Starting reference balance$5,000, .02lot, protector off. The audited engine wrapper does not establish full current Atlas account-rule compliance.

| Strategy | July6-October29 net | PF | Trades |
|---|---:|---:|---:|
| ASIAN_BREAKOUT_V6 | $79.83 | Undefined (no losses) | 1 |
| ASIAN_RANGE_FILTERED_V6 | $141.33 | 1.724 | 11 |
| LONDON_MOMENTUM_TIGHT_V6 | $340.78 | 2.150 | 21 |
| NY_SESSION_REVERSAL_V6 | $228.20 | 1.470 | 21 |

AsianBreakout has only one winning trade in this slice. Its PF is undefined because there were no losses; this is not evidence of an infinite or reliable edge.

## Verification, scope and files

- Exact price replays: price_replays.json. All24 case counts, cash totals and annual allocations reconcile. Costs and the actual M15 input hash are recorded.
- Forecast2026 uses the unchanged semiannual training formula extended through2026, with each freeze using only preceding sessions. The default historical runner remains limited through2025. Three focused tests pass, including preservation of pre2026 features and strictly earlier training endpoints.
- Archived all-candidate positive/negative inventory and annual cash: archived_inventory.json. Names without2019-2024/2026 coverage remain unclassified; absence is not a losing result.
- Genesis/Chandelier only have earlier screens for selected years and do not supply complete2019-2024 plus2026 evidence. No profitability claim about those requested windows follows.
- This is all positive evidence found in the stated cohorts, not an exhaustive claim about every strategy ever created or every old aggregate-only experiment. Tests with pooled2019-2025 statistics and no dated trade record cannot be honestly relabeled2019-2024.
- No live changes, trades, account purchases, new optimization or November2026 holdout use.

## Original portfolio: exact2019-2024 replay

This fresh start-flat/end-liquidated replay uses the four current strategies together, three shared position slots, fixed .02lot, protector off, M1-required exits and no additional Atlas wrapper. It is a contribution analysis, not standalone strategy performance. The2026 slice above used its own audited Atlas wrapper, so the two cohorts are not identical gate chains.

| Strategy | 2019-2024 net | PF | Trades |
|---|---:|---:|---:|
| ASIAN_BREAKOUT_V6 | $27.16 | 1.142 | 30 |
| ASIAN_RANGE_FILTERED_V6 | $-33.24 | 0.980 | 286 |
| LONDON_MOMENTUM_TIGHT_V6 | $-251.68 | 0.897 | 426 |
| NY_SESSION_REVERSAL_V6 | $113.02 | 1.051 | 297 |

Positive in both available cohorts: AsianBreakout and NYSessionReversal. AsianBreakout has only one trade in the2026 cohort. Overall2019-2024 portfolio net: $-144.74. This does not establish that either contribution remains profitable when traded alone.

Minute-coverage diagnostics: {"bars_without_m1": 0, "bars_skipped_no_m1": 4, "exits_unchecked_no_m1": 0, "partial_m1_candles": 3032, "partial_m1_minutes_missing": 11180}. Partial minute coverage is not tick-perfect replay.

Final portfolio check: all1039 trade timestamps are within the requested window, and gross-minus-commission-plus-swap reconciles to net. This is an accounting check, not a new independent first-hit exit audit.
