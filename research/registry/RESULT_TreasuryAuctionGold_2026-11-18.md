# Retire the pre-auction XAUUSD short

The frozen trade lost $18.21 after modeled costs across 186 monthly auction dates, with pooled PF 0.963. Of 202 qualifying Treasury auction dates, 16 lacked a complete paired observation. Each period below starts at $5,000 with a fixed 0.02-lot position. Net and expectancy are USD. Drawdown uses sampled net-liquidation equity and can understate the within-minute loss.

| Auction year | Pairs | Wins | PF | Net | Net/trade | Sampled DD | Same short one week earlier, net | Paired advantage/trade, 95% interval |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2010–2018 | 100 | 53.0% | 1.234 | +46.12 | +0.46 | 1.47% | −124.73 | +1.71 [−0.14, +3.53] |
| 2019–2024 | 72 | 41.7% | 0.947 | −9.52 | −0.13 | 0.82% | +37.83 | −0.66 [−2.81, +1.28] |
| 2025 | 11 | 36.4% | 0.457 | −59.05 | −5.37 | 1.86% | −63.43 | +0.40 [−13.08, +10.28] |
| 2026 through October | 3 | 33.3% | 1.446 | +4.24 | +1.41 | 0.85% | +17.18 | −4.31 [−9.45, +5.97] |

The trade sold at 11:45 New York time and closed at 12:45 or on a protective exit. Both main periods fell below PF 1.30. Both paired uncertainty intervals include zero. Removing the best 2019–2024 trade leaves −$47.63. Later periods together lost $54.81. The only three usable 2026 pairs were August, September and October. A 95% interval based on two 2026 calendar quarters has little inferential value. These results retire the fixed rule under the registered stopping condition. Stress, multiple-testing qualification and Atlas payout simulation were conditional on a base pass.

The [official Treasury calendar](https://fiscaldata.treasury.gov/datasets/treasury-securities-auctions-data/) provides the scheduled dates and prior public announcement dates. Research documents pre-auction Treasury yield pressure. Transmission to gold was the mechanism tested here. [New York Fed staff report](https://www.newyorkfed.org/research/staff_reports/sr1188.html)

The simulator used master XAUUSDm M1/M15 bars, bar spread with fallback, 20 points of adverse slippage and $3.50 commission per lot round trip. These are historical-feed cost assumptions. The declared 2025 M1 hole and incomplete dates were excluded. The engine requires all 15 minutes in the bucket containing the 12:45 exit, including minutes after the exit. The matched design also excludes an otherwise tradable day if its comparison lacks data. The November holdout was excluded.

Reproduce from the project root with `python -m scripts.research.treasury_auction_gold`. The committed [schedule](../results/treasury_auction_gold_2026-11-18/calendar.json) fixes the source snapshot. The [trade ledger](../results/treasury_auction_gold_2026-11-18/backtest.json) contains both arms, the exclusions, annual cash results, per-period risk metrics and the calendar hash. Independent arithmetic checks reconciled all 372 records against the short fills at two ounces and $0.07 commission, verified the clock and seven-day pairing, and reproduced each period's PF and net. The two arms together produced 341 time exits, 25 stops and six targets. [Preregistered protocol](PREREG_TreasuryAuctionGold_2026-11-18.md)
