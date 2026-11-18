# Reporting math regression result

Protocol: `PREREG_ReportingMath_2026-11-18.md`, committed in `f83e82c` before code
changes/tests. Engineering-only hand calculations; no strategy or historical
re-evaluation and no qualification changes.

Repaired `src.backtesting.metrics.summarize` and the normal
`src.backtesting.report.full_report` entry point. Calmar now uses calendar CAGR
and the same observed closed-balance drawdown in both report sections. Explicit
window endpoints/years are honored and inferred-period assumptions are labeled.
Fixed equal-high recovery, flat-at-peak periods, unrecovered duration tails,
independent dollar/percentage DD maxima, raw-P&L PF, zero-loss/downside statuses,
consistent unannualized Sortino units, and finite bootstrap serialization.

The existing pending downside-RMS corrections were preserved and centralized,
not reverted to the old standard deviation of losing trades. No other inherited
working-tree modifications were included in the implementation scope.

**31 focused tests passed** through normal report calls:

```
.\venv\Scripts\python.exe -m pytest tests/test_reporting_math.py tests/test_report_suite.py tests/test_bootstrap_ci.py tests/test_research_ratios.py -q
```

Notable hand results: sparse −$10/+20 trades on $100 over one calendar year give
CAGR 10%, DD 10%, Calmar **1**; $100→$50→$1,000→$900 gives maximum dollar DD
$100 and maximum percentage DD 50%; +$0.004/−$0.001 gives PF **4**;
Sortino(+4,−2,0) = **1/√3**. All-win and all-zero reports serialize with strict
JSON and explicit null/status outcomes. Bankruptcy followed by later recovery
cannot create a financeable CAGR, even if sparse equity observations omit the
intermediate exhausted balance.

Seven saved full-report examples and exact source hashes are in
`research/results/reporting_math_2026-11-18/examples.json`.
Full mathematical conventions/limits and legacy-artifact treatment are in
`docs/REPORTING_MATH_AUDIT.md`. Closed-balance DD remains distinct from sampled
or continuous floating equity. Bootstraps remain IID trade-P&L diagnostics.

The frozen FOMC JSON remains unchanged, SHA-256
`4b6333d67cc7c926d1d14d563cd66d9bc519b6687b5f50cc575e2a4e1084fcb6`.
Its saved risk ratios predate this implementation. Recomputing them requires
the whole fixed era windows (2016–2021 and 2022–2025), not event trade holding
durations or first/last trade alone. Original strategy findings and run hashes
are not retroactively altered.
