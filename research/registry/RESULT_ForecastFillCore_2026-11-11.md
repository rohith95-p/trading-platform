# Forecast-to-Fill audit and XAUUSD core screen

Source: https://arxiv.org/html/2511.08571v1 . Exact replication is unresolved: fitted
smoothing values/search grid, deterministic choice between reducing/closing exposure,
and the ledger assigning overlapping OOS windows were not supplied in the located paper.
Execution baseline descriptions also differ between body and clarifications. The source
extends a price series beyond its stated observed-data endpoint by forward filling; those
rows are not additional observed market moves. No linked author code/data release was
located in the paper or the targeted search. These findings limit independent verification;
they do not prove the paper's underlying strategy fails.

The tested core is explicitly an adaptation. Fixed lambda=.9, 50-session momentum,
.6/.4 blend, .52 long activation, past-ten-calendar-year normalization frozen each
half-year, delayed executable entries, daily ATR hard/trailing stops and 30-session timeout.
Actual NY17 FX sessions from XAUUSD M15; .02 lot, broker ECN costs and financing.
No original optimized parameters, futures rolls, Kelly sizing or capacity model inferred.

| Period | Trades | Win % | PF | Net USD | Closed-trade max DD |
|---|---:|---:|---:|---:|---:|
| 2015–2018 | 84 | 34.5 | .657 | -541.31 | 13.26% |
| 2019–2021 | 73 | 37.0 | .877 | -224.30 | 12.67% |
| 2022–2025 | 105 | 48.6 | 1.692 | 2568.28 | 12.13% |

The latest period is promising in isolation, but the fixed rule fails the required PF>=1.3
in earlier eras. It does not qualify for promotion. Under the same fixed2oz cost model,
uninterrupted buy/hold nets -$1319.82 / -$37.10 / +$3471.53 respectively. The core trails
that recent benchmark by $903.25. This is a dollar-P&L comparison, not proof of negative
risk-adjusted alpha: the holding durations, exposure and drawdown differ. Neither the
benchmark nor the screen establishes Atlas margin/equity-floor compliance or payout ability.

Financing uses the configured current long swap across history, not point-in-time historical
swap; therefore absolute results are assumption-dependent. These are inspected development
eras, not fresh out-of-sample validation. No November2026 holdout data or live trades used.

Results: forecast_fill_core.json (22 normalization freezes, full trade list, ratios,
ablation, order-randomization); forecast_fill_benchmark.json (separate baseline and funding).
The initial dated export incorrectly declared coverage only between first/last trade of
each era. Its three immutable records were moved to dated_results/superseded_coverage;
one continuous full UTC-coverage record now supplies the aligned matrix, avoiding gaps
and overlapping calendar-date fragments at FX-session boundaries. Current recovered
matrix contains23 candidate/execution versions; this remains an incomplete research subset.

Tests verify that future prices cannot change earlier normalized signals or training
freezes, and that a session's future high cannot tighten a stop earlier in that session.
The deterministic overnight case also includes the expected swap charge.
