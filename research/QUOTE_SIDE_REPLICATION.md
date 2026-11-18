# Quote-side replication of extreme-return reversal

Fixed preregistered mechanism study on the saved independent-source Dukascopy bid/ask2025 snapshot. **No strategy, account or payout result is claimed.** November2026 holdout untouched. Previously researched2025 is exploratory replication, not independent temporal confirmation.

| Resolution | Extreme observations | Reference reversal $/oz | Causal mid-open outcome $/oz | Observed quote-side outcome $/oz | Default after-friction mean [95% interval] $/oz |
|---|---:|---:|---:|---:|---|
| M1 | 21,087 | 0.03852 | 0.03767 | -0.60155 | -0.67655 [-0.70850, -0.64774] |
| M15 | 1,457 | 0.07102 | 0.07014 | -0.58963 | -0.66463 [-0.96247, -0.31282] |

Default friction is observed endpoint spreads plus assumed$0.035/oz commission and$0.04/oz round-trip adverse slippage. The nine fixed spread/slippage stress combinations, month counts/means, matched-control comparisons, weekly bootstrap uncertainty and hashes are in `results/finalization_2026-11-18/quote_side_replication.json`.

## Controls and uncertainty

- M1: 20847 matched observations, 19134 unique prior controls, maximum reuse7. Matched extreme-minus-ordinary default mean-0.14612 $/oz, interval[-0.17756583688930005, -0.11784456843980008]; Bonferroni4 p=0.0020. Default event mean uses53 UTC-week clusters; Bonferroni4 p=0.0020. Balanced-direction same-time default outcome=-0.71422 $/oz.
- M15: 1391 matched observations, 1232 unique prior controls, maximum reuse4. Matched extreme-minus-ordinary default mean-0.58710 $/oz, interval[-0.9790958328457993, -0.17491885273579502]; Bonferroni4 p=0.0100. Default event mean uses53 UTC-week clusters; Bonferroni4 p=0.0020. Balanced-direction same-time default outcome=-0.73477 $/oz.

A significant negative default mean is evidence against economic feasibility, not evidence of a profitable inverted strategy. Comparing extremes to ordinary observations can detect relative information while absolute outcomes remain negative. No threshold, holding interval or cost assumption is tuned to rescue the result.

## Disclosed control repair

The first run allowed an ordinary control whose outcome overlapped the extreme signal interval, creating an invalid positive relative contrast. That artifact is preserved as `quote_side_replication_superseded_overlap.json` and its matched contrasts must not be used. A committed protocol amendment and synthetic regression test now require every control outcome to end at or before the extreme signal interval starts. Absolute event outcomes were unaffected; corrected relative comparisons remain exploratory after inspection.

## Causality and limitations

Signals use completed mid-close returns and only previous60 valid-return RMS. Endpoints begin at the next quote open and end exactly one interval later. Missing boundary/intervening minutes are excluded rather than filled. Bid/ask side marking reconciles independently with mid movement minus endpoint half-spread sum. Matched controls are prior observations with the same month, UTC hour and return sign and comparable lagged volatility; their outcomes never select them. Overlap and reused controls limit independence even with week clustering. Separate bid/ask minute aggregates do not prove synchronous tick quotes or obtainable fills. Financing, latency beyond assumed slippage, stop execution, account constraints and Atlas contract verification remain outside scope.

## Decision

This study does not promote a strategy. Consult every fixed cost cell and primary interval in the machine-readable artifact before proposing a separately committed BacktestEngine candidate. No PF, account drawdown or payout rate has been manufactured for these descriptive event outcomes.

Reproduce: `.\venv\Scripts\python.exe -m scripts.research.quote_side_replication`. Protocol: `registry/PREREG_QuoteSideReplication_2026-11-18.md`.
