# Luna four-year constraint test

Research only. The test window is November 1, 2022 through October 31, 2026, UTC. This is a continuous $5,000 MT5 test on XAUUSD, M15 with real bid/ask ticks and no annual balance resets. Report realized P&L for each calendar year and mark the two partial years. Compare the supplied Luna expert defaults with a frozen preset. The June 2026 failure is a design case.

## Tested controls

The constrained preset reduces MaximumLot from 100 to 0.02, sets MaximumTrades to 2, MaximumDrawdown to 1.0, GridSL to 1000, and HiddenStopLoss to false. The June probe showed server-side stop modifications at $10 per ounce from the first entry, and stop fills followed by fresh entries. Order size alone does not cap cumulative daily losses. The stop is execution-dependent. The $50 intended basket ceiling must be checked against quotes.

## Acceptance

Any chronological breach eliminates this preset. Unrestricted annual trading P&L, evaluation outcomes, and funded payouts must be reported separately. Partial data, unresolved historical news eligibility or missing Atlas execution cannot establish eligibility. No account purchase or live trading.
