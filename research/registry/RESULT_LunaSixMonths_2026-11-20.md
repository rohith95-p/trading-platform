# Luna under Atlas Access, May–October 2026

**Luna failed the $5,000 Atlas Access evaluation on both price feeds.** The primary replay used the original Exness demo symbol and breached on 19 June. The archive replay breached on 27 May. Both began on 1 May with the supplied defaults. Each simulation produced zero eligible payouts and a net cash result of −$5 after the evaluation fee. No purchase was made. These are two price feeds for the same historical window and starting date.

## Primary result on the original broker symbol

MT5 reported 100% real ticks for the native XAUUSDm run. The separate quote-by-quote audit processed exactly the same number of ticks, 39,584,500. Luna earned $690.29 unrestricted, with 338 wins in 430 trades, PF 1.93 and 7.51% maximum relative equity drawdown in the MT5 report.

On 19 June the daily reference equity was $5,123.07, setting the 5% floor at $4,866.9165. Five open buys totalling 0.16 lots left the account long 16 ounces. At 04:54:26.158 UTC (10:24:26 IST) the broker bid was $4,125.768 and account equity reached $4,862.046. The last fill was over nine minutes earlier. The closed balance was still $5,129.34. The $5,150 target was first crossed on 24 June, after the evaluation had breached.

A separate May-only run of the original broker symbol produced nine trades and $18.42 net with no May breach. The tester journal recorded repeated spread-filter rejections. The median May bid/ask spread was $0.308 per ounce on the broker feed and $0.280 on the public archive. Feed differences changed entries and the first breach date. Neither feed came from an Atlas account.

[Broker MT5 report](../results/luna_six_month_20261120/sixmonth.htm) · [Broker ledger and rule events](../results/luna_six_month_20261120/broker_evaluation.json) · [Broker quote hashes](../results/luna_six_month_20261120/broker_provenance.json)

## Secondary result on the archived feed

On 27 May the balance and midnight UTC equity were $5,087.94. The Access evaluation daily floor was 95% of that, or $4,833.543. At 11:57:57.356 UTC (17:27:57 IST) the archived XAUUSDm quote was 4,429.526 bid / 4,429.806 ask. Luna was long 16 ounces. Marking those positions at bid put equity at $4,833.466. Equity subsequently fell to $4,757.56 that day, $75.98 below the floor. The account's 55 trades closed before the breach had taken the closed balance only as high as $5,087.94.

| Opened UTC | Lots bought | Fill price |
| --- | ---: | ---: |
| 10:45 | 0.01 | 4,465.943 |
| 11:00 | 0.01 | 4,446.329 |
| 11:15 | 0.02 | 4,451.457 |
| 11:30 | 0.04 | 4,441.248 |
| 11:45 | 0.08 | 4,443.339 |

The first failing quote was over 12 minutes after the last fill. In the unrestricted simulation Luna later added another 0.16 lots. The basket closed at 12:02:54 UTC with a net gain of $5.90. A backtest that checks only closed balances would miss the violation. The unrestricted balance first exceeded $5,150 on 9 June at 16:15:51 UTC, after the attempt had ended.

## Archive-feed performance without Atlas enforcement

Luna earned $839.95 after the charges in the demo report, finishing at $5,839.95. It won 390 of 502 trades (77.69%), with gross profit $1,797.31, gross loss $957.36, PF 1.88 and maximum relative equity drawdown 19.33% ($1,111.19). The native report covers all six calendar months, including the last October trading session on the 30th. Monthly net: May $114.56, June $175.89, July $147.17, August $143.12, September $132.77, October $126.44. The monthly figures come from one continuous run; restarting Luna each month would be a different test.

## Data, execution and verification

The supplied binary with its default inputs ran inside the native MT5 Strategy Tester, 1:100 evaluation leverage and M15 chart. The full-period run used an isolated symbol cloned from the Exness demo's XAUUSDm specification; the native terminal received Exness Standard bid/ask ticks in source order, plus same-source M1 history for warmup. MT5 reported 100% real ticks and exactly 39,802,823 ticks, matching the six verified source archives. All reported deals used that one symbol. This is Exness execution data, and the Atlas overlay applies the currently published standard Access rules retrospectively. Atlas-specific spreads, execution latency and slippage can change the result.

The independent equity reconstruction reconciles each closed deal to the MT5 balance, marks longs at bid and shorts at ask, resets the daily reference at 00:00 UTC, and checks the chronological order of loss-limit breaches, inactivity and the closed-balance target. This study uses the published multiplicative daily and trailing equity floors. The repo's general Atlas helper uses a different conservative dollar allowance; it was not used to classify this attempt. The valid attempt ended in evaluation, so no funded reset or deduction simulation was necessary.

A separate native replay using the original broker symbol and MT5's generated-tick model for May also breached the daily floor when its fills were marked to the archived quotes, at 11:57:57 UTC on 27 May. Its month-level report gave 6.49% maximum relative equity drawdown.

[Full MT5 report](../results/luna_six_month_20261120/sixmonth_local.htm) · [Ledger and daily equity checks](../results/luna_six_month_20261120/evaluation.json) · [Data hashes](../results/luna_six_month_20261120/provenance.json) · [Atlas Access](https://help.atlasfunded.com/access) · [Daily loss limit](https://help.atlasfunded.com/daily-loss) · [Maximum drawdown](https://help.atlasfunded.com/max-drawdown)
