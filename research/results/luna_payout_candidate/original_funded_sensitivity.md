# Can original Luna retain its XAUUSD profit under Atlas funded rules?

Original Luna placed 3,865 native MT5 market entry orders in the 48-month test. Every entry order had a blank SL field. Atlas says that placing 80% or more funded trades without a stop loss can breach the account. Its stop policy and the lack of an order-attached stop are sufficient grounds to exclude the original preset. [Stop loss](https://help.atlasfunded.com/stop-loss)

| Calendar period | Closed net P&L | Wins held under 3 minutes | Profit on those wins | Net with just those wins deducted |
|---|---:|---:|---:|---:|
| Nov–Dec 2022 | $143.86 | 4 | $8.68 | $135.18 |
| 2023 | $1,053.32 | 58 | $220.98 | $832.34 |
| 2024 | $1,213.86 | 141 | $541.52 | $672.34 |
| 2025 | $1,335.51 | 267 | $996.87 | $338.64 |
| Jan–Oct 2026 | $1,241.21 | 342 | $1,254.62 | −$13.41 |

This is a deduction sensitivity on each complete calendar slice of one continuous historical account. It does not start a new funded account, impose changes in positions after rule triggers, or adjust for fees and other rules. The MT5 report stores deal times to the second. Each full exit was uniquely paired with its opening fill using side, volume, and money P&L before swap and fees. The native order table was cross-checked by order number to establish the SL on entry. [Official short-trade deduction](https://help.atlasfunded.com/short-trades) · [Annual counts](original_durations.json) · [Native report](../luna_four_year_20261120/arch48_default.htm)
