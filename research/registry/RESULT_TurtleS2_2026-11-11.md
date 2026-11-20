# Turtle System Two: recent signal strength, no Atlas qualification

Primary rules: https://tradingblox.com/originalturtles/originalturtlerules.htm and author
document mirrored at https://www.tradingwithrayner.com/wp-content/uploads/2014/11/OriginalTurtleRules.pdf .
Prior DONCH55 project tests were different midday entries with fixed M15 ATR targets.
This independent adaptation uses actual prior-session55 channels,20-session exits and2N
stops, both directions. Fixed .02lot units, XAUUSD only, optional four-unit favorable adds.
It omits original multi-market diversification and dynamic unit sizing; not full replication.

| Units | Era | Baskets | Basket win % | PF | Net USD | Closed-balance DD |
|---|---|---:|---:|---:|---:|---:|
| 1 | 2005–11 | 35 | 28.6 | .611 | -573.22 | 15.77% |
| 1 | 2012–18 | 38 | 28.9 | .854 | -243.30 | 17.59% |
| 1 | 2019–25 | 28 | 42.9 | 3.294 | 2495.50 | 9.97% |
| 4 max | 2005–11 | 38 | 18.4 | .680 | -1318.16 | 32.43% |
| 4 max | 2012–18 | 42 | 26.2 | .915 | -441.46 | 41.46% |
| 4 max | 2019–25 | 33 | 24.2 | 2.459 | 7529.14 | 67.51% |

Recent returns deserve retention as a low-frequency research benchmark, but no variant
passes every-era base-cost PF>=1.3. Twenty-eight single-unit baskets in seven years also
misses the protocol30-basket minimum; neither version supplies everyday entries. The
four-unit high PF is accompanied by unacceptable drawdown at this fixed size. DD is on
closed baskets, not full floating equity, so it cannot establish Atlas safety.

Financing matters, but cannot explain away all weaknesses. Removing funding while
keeping the same executable basket paths/fees yields single-unit PF1.431/1.227/4.874,
four-unit PF1.793/1.282/3.464. Both still miss1.3 in2012–18. The separately replayed
frictionless scenario can have different trades/stops because fill prices change; its PF
is not equivalent to simply deleting commissions/financing from fixed trades.
Funding sensitivity: turtle_funding_sensitivity.json, with exact uniform long-dollar/oz/day
break-even rates, short funding assumed zero. These are not Atlas quotes or historical
financing observations. Base financing is the project's current Exness-style model applied
across history, not verified point-in-time Atlas contract costs.

Official Atlas references checked2026-11-11:
https://help.atlasfunded.com/en/articles/9904228-can-i-hold-trades-overnight-or-over-the-weekend
and https://docs.atlasfunded.com/trading-mechanics . They describe holding and swaps but
do not supply this user's exact XAUUSD rates. An optional swap-free configuration mentioned
at https://docs.atlasfunded.com/platforms-kyc is not proof that Access/XAUUSD is eligible or
free of replacement fees. No signup, checkout, paid data, external message or live trade done.

Minimum-unit scenarios in turtle_min_lot_feasibility.json assume .01lot=1oz and $5000
equity, not confirmed Atlas settings. Recent single-unit median planned stop loss is
$47.60; none of those28 entries fits the provisional .25% ($12.50) budget, while15 fit
1% ($50). These internal budgets are not Atlas hard rules. Funding/gap reserves and actual
equity path remain excluded, so those eligibility counts are not deployment authorization.

Source/result/protocol hashes are preserved where generated. Main outputs turtle_s2.json
include basket records, unit counts, costs, risk ratios, ablation and Monte Carlo ordering.
The aligned matrix now contains28 recovered candidate/execution versions, not28 independent
families or the complete historical search count. Eras were previously inspected. November
2026 holdout untouched. No Atlas evaluation/payout probability is claimed from these results.

Tests cover closed-session channel construction, future-prefix invariance, long/short
gap fills with ask costs, four-unit cap and simultaneous basket liquidation, and analytic
funding-threshold arithmetic. M15 entry-order ambiguities are explicitly counted (zero
for both base arms in all eras), but this does not replace M1/tick/account-policy validation.
Decision: retain research records; do not activate the fixed-size system.
