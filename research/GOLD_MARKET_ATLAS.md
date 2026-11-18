# Gold market atlas — 2026-11-18

Exploratory empirical evidence, not a profitable strategy or independent holdout test.

Protocol committed before computation, with a committed clarification after the first run exposed empty hourly/daily groups: volatility uses previous60 valid adjacent returns, not60 consecutive elapsed bars. That first run failed serialization; this correction is disclosed rather than called independent confirmation. Frozen November2026 observations excluded. All historical eras here have influenced prior project research; splitting them again does not restore independence.

## Distributions and dependence

| TF | Bars | Return pairs | Skew | Excess kurtosis | Return lag1 | Absolute lag1 |
|---|---:|---:|---:|---:|---:|---:|
| M1 | 6,887,193 | 6,673,009 | -0.091 | 74.36 | -0.0224 | 0.3558 |
| M5 | 100,000 | 99,631 | -0.494 | 40.23 | 0.0064 | 0.3483 |
| M15 | 514,712 | 505,979 | -0.407 | 41.48 | -0.0176 | 0.3199 |
| H1 | 126,553 | 119,754 | -0.465 | 22.33 | -0.0020 | 0.2820 |
| H4 | 7,498 | 7,249 | -0.659 | 15.45 | 0.0193 | 0.2290 |
| D1 | 7,074 | 3,767 | -0.285 | 6.65 | -0.0123 | 0.1345 |

Adjacent exact-duration returns only; market closures and missing observations are excluded. This conditions the sample toward continuous trading and understates reopening jump exposure. Fat tails and volatility persistence describe risk; neither establishes directional trading edge.

## Fixed conditional effects

Extreme means absolute return >2× previous60-bar RMS. Subsequent return must be adjacent. Monthly cluster bootstrap999 resamples, seed20261118; Bonferroni18 applies only to this fixed family, not prior research searches.

| TF | Effect | N | Mean bps | 95% interval bps | Adjusted p |
|---|---|---:|---:|---|---:|
| M1 | extreme_continuation | 398,154 | -0.162 | [-0.202, -0.126] | 0.018 |
| M1 | ordinary_continuation | 6,151,151 | -0.003 | [-0.015, 0.010] | 1.000 |
| M1 | extreme_next_volatility_premium | 398,154 | 0.751 | [0.705, 0.803] | 0.018 |
| M5 | extreme_continuation | 6,409 | 0.238 | [-0.068, 0.542] | 1.000 |
| M5 | ordinary_continuation | 92,795 | 0.018 | [-0.028, 0.059] | 1.000 |
| M5 | extreme_next_volatility_premium | 6,409 | 2.713 | [2.251, 3.313] | 0.018 |
| M15 | extreme_continuation | 34,985 | -0.359 | [-0.556, -0.173] | 0.018 |
| M15 | ordinary_continuation | 463,534 | -0.096 | [-0.143, -0.049] | 0.018 |
| M15 | extreme_next_volatility_premium | 34,985 | 4.841 | [4.592, 5.118] | 0.018 |
| H1 | extreme_continuation | 7,136 | 0.376 | [-0.390, 1.224] | 1.000 |
| H1 | ordinary_continuation | 106,100 | -0.228 | [-0.368, -0.089] | 0.036 |
| H1 | extreme_next_volatility_premium | 7,136 | 9.128 | [8.362, 9.879] | 0.018 |
| H4 | extreme_continuation | 433 | 2.978 | [-2.239, 7.667] | 1.000 |
| H4 | ordinary_continuation | 6,509 | 0.859 | [-0.043, 2.006] | 1.000 |
| H4 | extreme_next_volatility_premium | 433 | 11.132 | [5.177, 18.059] | 0.018 |
| D1 | extreme_continuation | 174 | -0.705 | [-19.151, 16.417] | 1.000 |
| D1 | ordinary_continuation | 2,584 | -3.016 | [-7.847, 1.253] | 1.000 |
| D1 | extreme_next_volatility_premium | 174 | 4.586 | [-9.607, 19.514] | 1.000 |

A volatility premium predicts movement magnitude, not profitable direction. Signed continuation is measured from close to next close, before executable spread/fees/slippage. Monthly resampling assumes month clusters exchangeable and does not establish stationary regimes. Microstructure bid bounce, source differences and close-price conventions can dominate tiny signed effects.

## Sessions, excursions and regimes

Machine-readable results include24 local-clock bins for London, NewYork and Tokyo with daylight-saving conversion, fixed-era extreme-return effects, and next-bar range excursions. These are descriptive; no best session is selected. Range extrema do not identify first passage, executable path, or stop-before-target order. Separate native resolutions have different coverage; H1 is constructed from complete four-M15 groups because BarSet exposes no H1 field. Cross-timeframe rankings are confounded by source and era.

## Macro explanations versus predictions

| Variable | Complete rows | Same-row correlation | Previous-row correlation |
|---|---:|---:|---:|
| dxy | 6525 | -0.3969 | -0.0475 |
| y10 | 6525 | -0.1627 | -0.0434 |
| vix | 6525 | -0.0054 | -0.0612 |
| spx | 6525 | 0.0111 | 0.0516 |
| gld | 5473 | 0.8900 | 0.1137 |

Daily proxy CSVs have no certified quote timestamp, release vintage or synchronous close. Gold may be a futures proxy; ETF exposure mechanically tracks gold. Same-row association is explanatory, and previous-row association is only a candidate feature audit. No economic-announcement surprise can be reconstructed from release dates alone.

## Economic model and next evidence

For observable information F_t and executable action a, V(a|F_t)=E[liquidation cashflow−entry cashflow−commission−financing−slippage|F_t]. Abstain when the lower uncertainty bound on incremental V relative to matched-time random-direction and exposure controls is nonpositive. Estimate outcomes with real bid/ask paths and full account constraints. Price-return dependence alone is insufficient.

The fixed extreme-return study is a mechanism screen. Any candidate needs a separate committed specification, strictly causal features, BacktestEngine minute execution, historical-cost stress, matched-time controls and prospective demo confirmation. No new strategy is approved from this atlas. The remaining gaps include PACF/MI/change-point formal tests, calibrated live slippage, quote/trade arrival data, joint DXY/yield timestamp alignment, barrier-time distributions, and central-bank data with publication vintages. These are not claimed completed.

Reproduce: `venv/Scripts/python.exe -m scripts.research.market_atlas`. Inputs, source provenance, code hash and detailed results: `research/results/finalization_2026-11-18/market_atlas.json`.
