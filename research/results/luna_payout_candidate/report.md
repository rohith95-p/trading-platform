# Original Luna and the L2 risk preset

**Exclude both configurations from the final trading roster.** The original failed the historical evaluation risk test. The new L2 configuration stayed inside the modeled daily, trailing and inactivity limits in its January 2026 evaluation attempt, but lost $412.71 and finished in evaluation. Its 700 trades produced 540 wins and just one UTC day with at least $25 in realized profit. No funded account or payout was reached.

| Jan–Oct 2026 | L2 |
|---|---:|
| Closed profit / loss | −$412.71 |
| Winners / completed trades | 540 / 700 (77.14%) |
| Gross wins / gross losses | $1,235.45 / $1,648.16 |
| Profit factor | 0.75 |
| Expectancy / trade | −$0.59 |
| Relative equity drawdown | 9.00% ($453.54) |
| Net after removing best trade | −$445.53 |
| Max quote-marked floating loss | $49.94 |
| Max quote-marked daily loss | $76.68 |
| Observed max single order / open lots | 0.04 / 0.08 |
| Evaluation passes / breaches on Jan 1 attempt | 0 / 0 through cutoff |
| Withdrawals / cash after $5 evaluation fee | $0 / −$5 |

MT5 ran the compiled Luna EX5 through 80,478,503 real Exness ticks on the XAUUSDm.L48 symbol. The evaluation started at $5,000 and 1:100 leverage. The auditor reconciled the quote count and final balance with the native report. Fill timestamps from the HTML report have one-second precision. This is a previously studied period. The validation rule stops after the 2026 failure, so L2 did not advance to 2025.

The journal confirms that MT5 loaded MaximumLot=0.01, MaximumTrades=4, MaximumDrawdown=1.0, GridSL=1500.0 and HiddenStopLoss=false. Luna placed orders up to 0.04 lots. On February 19 a 0.02-lot entry had its stop attached five seconds later. Every one of the 700 entry order records had an empty stop field at submission. Atlas says that 80% or more of trades placed without a stop can cause a funded breach. [Input readback](tester_inputs.txt) · [Order and stop modification](lot_cap_violation.txt) · [Atlas stop rules](https://help.atlasfunded.com/stop-loss)

Of 391 L2 trades closed in under 180 seconds, 359 were winners totaling $794.59. Subtracting those short-duration wins from the entire L2 ledger gives −$1,207.30. This sensitivity uses evaluation trades and illustrates the cost of the funded rule. L2 never reached funding. [Counts](l2_durations.json) · [Atlas short-trade deduction](https://help.atlasfunded.com/short-trades)

The original Luna earned $1,241.21 before rules over the same Jan–Oct calendar slice of its continuous 48-month native run. Removing the original's 342 short-duration wins costs $1,254.62. All 749 original entry orders in this window had an empty stop field. [Original results by year](original_funded_sensitivity.md)

[Native MT5 report](luna_l2_2026.htm) · [Evaluation equity audit, trades and robustness metrics](audit_2026.json) · [Frozen protocol](protocol.md) · [Provenance](provenance.json)
