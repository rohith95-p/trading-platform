# Luna on XAUUSD under the $5,000 Atlas Access rules

**Reject the tested configuration.** The constrained EA lost $755.93 over 48 months. The evaluation opened on 1 November 2022 never reached the $5,150 target and breached the trailing equity floor on 22 July 2025. It received no funded account or payout. Counting the $5 simulated entry fee gives net cash of −$5 for the attempt.

## Annual results in USD

| Period | Default net trading P&L | Constrained net trading P&L | Constrained PF | Constrained trades | Eligible cash payouts on initial constrained attempt |
|---|---:|---:|---:|---:|---:|
| 2022 (Nov–Dec) | +143.86 | -144.53 | 0.46 | 109 | $0 |
| 2023 | +1,053.32 | -77.61 | 0.93 | 700 | $0 |
| 2024 | +1,213.86 | -46.73 | 0.96 | 843 | $0 |
| 2025 | +1,335.51 | -249.80 | 0.84 | 926 | $0 |
| 2026 (Jan–Oct) | +1,241.21 | -237.26 | 0.83 | 701 | $0 |
| **Total (USD)** | **+4,987.76** | **−755.93** | **0.86** | **3,279** | **$0** |

With the constrained preset, 2,342 of 3,279 trades won (71.42%). The original settings had an unrestricted MT5 maximum relative equity drawdown of 32.33% (2 528.43) and profit factor 1.62. The original-settings attempt that began on 1 November 2022 breached its daily floor on 4 November 2022. In its separate 48 monthly-start ledger replays, 29 reached the evaluation target first and 19 breached the daily limit first. Baseline funded outcomes were not used to qualify the constrained preset. Annual figures use the realized deal ledger including reported fees and swap. Their sums match both native MT5 reports to the cent.

[Original preset MT5 report](arch48_default.htm) · [Original preset equity audit](arch48_default.json)

## What the constraints changed

The compiled Luna expert ran in the desktop MT5 Strategy Tester. The supplied defaults and the frozen risk preset used the same continuous Exness Standard XAUUSD bid/ask history, a $5,000 deposit and 1:100 evaluation leverage. The archive contains 227,209,462 checked quotes from 48 monthly files, plus two preceding months for warm-up. Earlier years on the original demo symbol lacked broker real ticks. Both archive runs use a custom symbol cloned from its contract specifications. June 2026 was used to design the controls, so this window includes the design period. Atlas execution and a live account were not tested.

The preset caps individual order size at 0.02 lots and the trade-count input at two, sets the EA drawdown input to 1.0, and enables visible grid stops with a distance input of 1000. The June probe showed a stop $10 per ounce from the first entry. Order modifications followed the entry fills. In 13 of 13 probe entries the order itself had no stop attached at submission. A stopped position could be followed by another entry within 73 seconds. The controls target $50 combined open loss. The largest order actually used was 0.01 lot and the largest quote-marked floating loss was $31.39.

## Evaluation and payouts

In the main attempt, peak equity of approximately $5,001.73 established a trailing floor of $4,501.56. On 22 July 2025 at 13:31:31.541 UTC, equity of $4,501.52 was unambiguously below the floor at cent precision. That day's minimum was $4,496.27. Full-period figures below include trading after the breach to show what the EA did in every requested year.

The monthly-start diagnostic replays the same recorded fills from a fresh flat $5,000 balance starting each month. If the existing run held positions at the boundary, the replay waits until that basket is flat. The 48 overlapping paths produced 29 trailing breaches, 19 still in evaluation at the cutoff, and zero passes. They are dependent scenarios rather than independent trials. A full four-year account has a longer observation period than the later starts. No scenario reached the funded phase, so activation fees and eligible payout totals are zero. Time to first payout was never reached. If all 48 starts were purchased separately, the summed entry fees would be $240. They are alternatives to the single-attempt result.

Only one UTC day in the full constrained ledger generated at least $25 of net closed profit before any funded deductions, 17 June 2026 at $44.22. The funded program requires three such days per cycle. Wins averaged $2.05, losses averaged $5.94 and expectancy was −$0.23 per trade. The high win rate was insufficient to cover the size of the losses.

## Atlas rules used

The current standard Access evaluation has a 3% closed-profit target, 5% daily equity loss limit, 10% trailing equity drawdown and a 30-day inactivity deadline. The current funded MT5 account uses 1:50 leverage, 3% daily and 6% trailing limits. At 2% floating loss Atlas Protector closes the positions and reduces the split to 50% on the first trigger. A second trigger breaches the funded account. Other funded rules address missing stops, margin usage, high-impact news within five minutes and trades under three minutes. Eligible payouts require at least $100 profit, three qualifying days of at least 0.5%, and a best day no greater than 20% of cycle profit. The standard split is 90% and windows open after 28 days, then every 14. The rules were applied retrospectively. Prices and fills are from Exness.

[Atlas Access terms](https://help.atlasfunded.com/access) · [Rule enforcement](https://help.atlasfunded.com/rules) · [Daily loss formula](https://help.atlasfunded.com/daily-loss) · [Equity drawdown](https://help.atlasfunded.com/max-drawdown)

[Constrained MT5 report](arch48_guard.htm) · [Rolling results](arch48_guard.json) · [Quote coverage and hashes](tick_coverage.json) · [Frozen test settings](LunaGuard01.set)
