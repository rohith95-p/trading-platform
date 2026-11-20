# Retained XAUUSD strategies, 2025 and January–October 2026

New York Session Reversal was removed from the research roster after losing $610.74 on 48 standalone trades in 2026 (PF 0.65). The allocation was rerun with the other three eligible for selection. Both years were profitable for each individual strategy and the combined portfolio, so the test stopped after 2025. Every retained configuration breached its funded account during the 2026 replay. None qualifies under the zero-breach requirement.

## Trading and funded-account results

Net trading P&L is the continuous research result including modeled spread, slippage, commission and financing, even after a hypothetical Atlas breach. Each calendar-period attempt started with a fresh $5,000 evaluation. All eight selected evaluations passed. Each funded phase started afresh at 1:50 on the next trading date. This is one attempt per period per strategy or portfolio. All dollar amounts are USD.

| Period | Strategy / portfolio | Net trading P&L | Trades | Win rate | PF | Maximum equity drawdown on continuous path | Funded outcome at cutoff | Modeled payout | Net cash after $83 fees |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|
| 2026 | [Asian Range Filtered](./AsianRangeFilteredV6/trades.csv) | +422.22 | 26 | 57.7% | 1.93 | 3.14% | [inactivity breach 2026-10-23](./AsianRangeFilteredV6/funded/atlas.json) | 0.00 | -83.00 |
| 2026 | [Asian Breakout](./AsianBreakoutV6/trades.csv) | +386.30 | 31 | 48.4% | 1.37 | 8.22% | [inactivity breach 2026-10-28](./AsianBreakoutV6/funded/atlas.json) | 0.00 | -83.00 |
| 2026 | [London Momentum Tight](./LondonMomentumTightV6/trades.csv) | +476.14 | 51 | 41.2% | 1.46 | 7.65% | [trailing breach 2026-06-22](./LondonMomentumTightV6/funded/atlas.json) | 0.00 | -83.00 |
| 2026 | [Three-strategy portfolio](./retained_portfolio/trades.csv) | +850.40 | 82 | 46.3% | 1.45 | 10.16% | [trailing breach 2026-03-30](./retained_portfolio/funded/atlas.json) | 0.00 | -83.00 |
| 2025 | [Asian Range Filtered](../four_strategies_2025/AsianRangeFilteredV6/trades.csv) | +548.00 | 47 | 59.6% | 2.16 | 2.96% | [Active at cutoff](../four_strategies_2025/AsianRangeFilteredV6/funded/atlas.json) | 100.00 | +17.00 |
| 2025 | [Asian Breakout](../four_strategies_2025/AsianBreakoutV6/trades.csv) | +690.99 | 52 | 53.8% | 1.95 | 2.93% | [Active at cutoff](../four_strategies_2025/AsianBreakoutV6/funded/atlas.json) | 0.00 | -83.00 |
| 2025 | [London Momentum Tight](../four_strategies_2025/LondonMomentumTightV6/trades.csv) | +456.08 | 70 | 38.6% | 1.59 | 2.92% | [Active at cutoff](../four_strategies_2025/LondonMomentumTightV6/funded/atlas.json) | 0.00 | -83.00 |
| 2025 | [Three-strategy portfolio](../four_strategies_2025/retained_portfolio/trades.csv) | +941.18 | 119 | 46.2% | 1.73 | 4.23% | [Active at cutoff](../four_strategies_2025/retained_portfolio/funded/atlas.json) | 100.00 | +17.00 |

The 2026 portfolio passed evaluation on February 6. Its fresh funded account hit Atlas Protector on March 23. On March 30 its equity reached $5,073.81; the recorded $5,398.32 equity peak established a $5,074.42 trailing floor. The 2025 portfolio passed evaluation on April 21 and modeled a $100 payout on October 27. The standard $5 upfront and $78 activation charges leave $17 for that scenario. No payment was received.

## Selection and robustness

Every Asian Range Filtered standalone entry coincided with an Asian Breakout entry in both periods. They use different exits. The combined selector admitted just five Asian Breakout trades per period. Their total contributions were +$25.86 in 2025 and −$47.96 in 2026. The combined portfolio therefore has much less independent Asian-breakout exposure than adding the two standalone ledgers would imply.

Removing the single best portfolio trade left +$817.13 in 2025 and +$582.05 in 2026. The trade-resampled 95% PF interval was 1.13–2.65 in 2025 and 0.85–2.47 in 2026. The 2026 PF interval includes losses after costs. The older strategies were selected and tuned using historical data and removal of the losing leg used 2026 results. These periods do not supply untouched forward confirmation.

## Scope and assumptions

The original Python strategy code ran in the local Ultra Core backtester on Exness Standard XAUUSD quotes. The engine uses causal bid bars for signals and ordered bid/ask quotes for fills, with fixed 0.02-lot sizing and modeled execution costs. The 2025 run has 76,283,540 scored quotes and the Jan–Oct 2026 run has 80,478,503. Quote-source records are linked below. Results concern observed Exness prices. Historical Atlas fills, financing, and the full all-currency Atlas red-folder calendar were unavailable. The funded replay includes known events, short-trade deductions, forced liquidations where triggered, the consistency gate, payout windows and profit splits under the standard Access profile. A modeled $100 refers to cash after the split, before the account fees. No trading, purchase or transfer was performed.

[2025 robustness](../four_strategies_2025/robustness.json) · [2026 robustness](robustness.json) · [2025 source check](../four_strategies_2025/archive_crosscheck.json) · [2026 source check](archive_crosscheck.json) · [Combined trade records by run](individual_and_portfolio_trades_2025_2026.csv)

[Atlas Access rules](https://help.atlasfunded.com/access) · [Atlas news rules](https://help.atlasfunded.com/news-trading) · [Atlas standard fees](https://docs.atlasfunded.com/refunds)
