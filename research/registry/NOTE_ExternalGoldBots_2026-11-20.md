# External gold bots and execution comparison, 20 November 2026

## Independent engine check

Downloaded Aurum at commit 49f073dfdb2f8831e2fcb39b321c1a02bc4bba5f from https://github.com/zero-was-here/tradingbot. The authors report no selection-adjusted edge in their published protocol. The reusable part for this project is their execution simulator. Our targeted engine and tick tests passed (60), as did 46 standalone Aurum cost and simulator tests with the unrelated data-suite configuration disabled.

The frozen quote-activity reversal had zero entries over 1,748 eligible London mornings. The first public pullback specification also had zero entries because it required uninterrupted overnight M15 history. Both original ledgers are preserved. The separately preregistered session-aware rule permits gaps up to two hours in risk/signal history, including nightly maintenance. It buys or sells a completed EMA8 recross in the EMA8/21 trend at 10:00 London. It is a research interpretation of the public indicator description, not a replica of a commercial cBot.

Both engines received the same signed orders and ATR levels. Ultra Core used bid bars with the minute-opening spread. Aurum converted these to equivalent mid bars and trigger levels, with matched slippage and commissions. These are independent execution implementations sharing a signal and risk specification. Baseline P&L for all 111 trades agrees to under one cent. A chronological bid/ask replay of 562,071 underlying quotes checked the same trades, entry prices and exit brackets. Seven trades differed by more than one cent, maximum $0.14. Tick-based net was $33.87 and PF 1.110. Tick fills assume immediate execution on the observed quote, two ounces, $0.020/oz slippage per market fill and $0.07 round-trip commission.

| Dates | Trades | Wins | Engine net | PF |
| --- | ---: | ---: | ---: | ---: |
| 2019–21 | 43 | 16 | -$12.70 | 0.847 |
| 2022–24 | 53 | 25 | $4.05 | 1.036 |
| Jan–Oct 2026 | 15 | 6 | $42.94 | 1.386 |
| Pooled | 111 | 47 | $34.30 | 1.112 |

Pooled stress net -$42.13. Remove the largest winner and pooled net becomes -$26.58. Opposite direction on the same dates netted -$129.79. The candidate fails the preregistered gates and does not advance to Atlas. Funded payouts, time to first payout and breach probabilities were not simulated. These checks cover this market order, bracket and timed exit. Actual broker slippage, queueing, requotes, and the Atlas feed are unmeasured.

## Screenshot and download inventory

- Paid [Ai_Scalper Pro_Max](https://ctrader.com/products/2287) shows PF 2.44 and drawdown 25.93%. The listing describes 10 days and leverage 1:500. The advertised configuration is unsuitable for the 6% trailing and 3% daily funded limits on [Atlas Access](https://help.atlasfunded.com/access). Its short test period cannot establish repeatability at reduced size.
- The same seller offers [Ai_Scalping](https://ctrader.com/products/2278) free. Its EMA, stochastic, RSI and ATR descriptions supply research ideas. Native cTrader is a separate platform and these two .ex5 downloads are MT5 binaries. No proprietary cBot binary was replayed by Aurum.
- The XauBot dashboard screenshot shows Metals, Multilevel Strategy, 50% drawdown and AI support off. This is distinct from the Velora FX presets. Public [Velora guide](https://xaubot.com/xaubot-velora-guide/) covers its baskets, licensing and native backtesting. Both supplied presets list seven FX crosses, hidden stops, grid settings and up to eight trades. Neither includes gold. Luna contains XAUBOT TEAM and xaubot.com metadata. Matching the name of a different marketplace product is insufficient for identifying the binary.
- Research reproduction uses scripts.research.london_absorption_data, scripts.research.london_quote_absorption (no flag, --public-pullback, then --public-pullback --maintenance), and scripts.research.public_pullback_tick_check. The original source ZIPs and derived minutes stay local. Calendar dates refer to London, and all tests end before November 2026.

## Native MT5 trials

The existing Exness demo login supplied price history for two local portable Strategy Testers. The October reports use $5,000, 1:50 leverage, M15 and real ticks. No orders were submitted to the account. Report files are in research/external_review_20261120/Luna and Velora. Both experts logged WebRequest 4014 and file error 5004 during the five-day checks. External features remain unverified.

Luna earned $80.75 over 66 trades (44 wins, PF 1.69) with 0.94% maximum relative equity drawdown. Peak closed profit was $80.75 against the $150 evaluation target. The best net day was $10.38 against $25 for a qualifying day. Matching all 66 durations by opening-position and closing-order ticket identified 21 profitable trades under three minutes totaling $73.38. Applying the funded short-duration rule alone leaves $7.37, equivalent PF 1.06 before other deductions. The October path earned no payout. The earlier five-day trial earned $2.14 from one trade. Each trial starts with a fresh EA state.

Velora's original low-risk preset recorded zero trades in the five-day test. The full October trial changed only its symbol list to XAUUSDm. It also recorded zero trades and repeatedly logged spread rejections. Its PF is undefined.

Sources: [Atlas Access](https://help.atlasfunded.com/access) and [funded short trades](https://help.atlasfunded.com/short-trades).
