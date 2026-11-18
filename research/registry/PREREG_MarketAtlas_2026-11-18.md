# Market atlas discovery protocol — 2026-11-18

This is descriptive market research, not a strategy backtest or independent validation. All pre-November-2026 histories are treated as previously explored. No data at or after 2026-11-01 is used for numerical price analysis. Raw file hashes and timestamp counts may cover entire files without revealing holdout outcomes.

## Fixed scope before computation

1. Inventory accessible research/data* NPY and CSV files, plus research/events CSVs: hashes, rows, columns, timestamp coverage, duplicates, missing values, OHLC validity, adjacent gaps. Never fill absent observations. Distinguish elapsed gaps from unexplained market closures; no asserted exchange calendar completeness.
2. Load M1, M5, M15, H1, H4 and D1 through load_master only. Use adjacent exact-duration observations for log returns; gaps are excluded, not bridged. Document source switches and incompatible resolutions.
3. Report moments, quantiles, signed-return lag-1 correlation, absolute-return lag-1 correlation, next-bar favorable/adverse excursion after extreme prior returns. Extremes: absolute log return >2 times trailing 60 valid-bar RMS, using only previous observations. No threshold sweep.
4. For each of six resolutions estimate three fixed conditional effects: signed continuation after extreme return, continuation after ordinary return, and next absolute return after extreme versus ordinary return (18 tests). Cluster by UTC month; 999 fixed-seed bootstrap resamples of monthly sufficient statistics. Report percentile95% intervals and two-sided centered-bootstrap p-values, Bonferroni18 correction. These are exploratory conditional summaries, not confirmation tests or complete search-adjusted significance.
5. Describe return/volatility/spread distributions by local clock hour (Europe/London, America/New_York, Asia/Tokyo), with daylight saving via zoneinfo. No session selection or extra significance claims. Report fixed eras 2004–2015, 2016–2021, 2022–October2026.
6. Inspect d1_study/master.csv using strictly lagged macro features, contemporaneous versus next-gold-return correlations separately; do not claim synchronized daily closes or vintage correctness. No strategy fitted on these data.

## Promotion and failure criteria

A signal can be proposed for a separately committed candidate preregistration only if effect has economically plausible mechanism, same sign in at least two eras, adjusted p<.05 and a reasonable executable-cost margin. Statistical volatility prediction alone is not directional alpha. Discovery p-values remain conditional on the declared18 tests, not the unknown project-wide search. No strategy is selected on this report. A subsequent candidate must use BacktestEngine, strict minute coverage, corrected chronology, after-cost risk metrics and baselines; November holdout remains unused until separately frozen confirmation.

## Deliverables

scripts/research/market_atlas.py, machine-readable forensics/atlas results, research/DATA_FORENSICS_REPORT.md, research/GOLD_MARKET_ATLAS.md, research/MARKET_EDGE_DISCOVERY.md. Record defects and unsupported areas rather than replacing missing evidence with estimates.

## Implementation clarification before second computation

The first run computed all six resolutions but failed JSON serialization because empty H1/H4/D1 extreme groups produced NaN. Inspection found that requiring60 consecutive elapsed bars makes historical volatility undefined on hourly/daily series with routine market closures. Use the previous60 valid adjacent returns, across closures, without including a return across any gap. The current and next return must still be adjacent. This is a disclosed methodology correction after observing empty groups, not a new threshold or an independently untouched test. Empty summaries are null. Commit this amendment before rerunning.
