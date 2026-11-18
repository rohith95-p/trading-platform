# Performance reporting arithmetic audit — 2026-11-18

Scope: normal `src.backtesting.report.full_report` and
`src.backtesting.metrics.summarize` entry points, plus their PF/Sortino bootstrap.
No strategy, execution, live account or market dataset was evaluated. The prior
uncommitted downside-RMS correction was preserved and centralized, not discarded.
Protocol `PREREG_ReportingMath_2026-11-18.md` was committed before these changes.

## Material defects corrected

| Area | Previous behavior | Current calculation |
|---|---|---|
| Calmar in `summarize` | Invented annual trade count from average holding minutes and 252×6.5 hours, implicitly assuming continuous repeated opportunities | Calendar CAGR / maximum percentage observed closed-balance DD |
| Normal report consistency | `stats` and `ratios` independently used different annualization and drawdown data | Both sections share the same window-aware summary |
| Balance observations | Ignored the supplied equity argument and used trade `balance_after` fields | Use supplied chronological balance observations; otherwise reconstruct cumulative net-trade cash, with a note |
| Drawdown duration | Counted time flat at a peak, failed equal-high recovery, missed end-of-window underwater tails | Track complete underwater episodes from last observed high through recovery or explicit final boundary |
| DD percentage | Updated only when dollar DD set a new maximum | Maximize dollar and percentage DD independently |
| PF precision | Divided already-rounded winning/losing P&L sums | Divide unrounded positive/negative after-cost trade sums; round only output |
| Zero-loss/downside samples | PF could be infinite and Sortino could silently become zero | JSON null plus explicit undefined/unbounded status; losing-only PF is zero |
| Sortino units | Inconsistent calculations and unclear annualization | Mean net P&L per trade / zero-target downside RMS over **all** trades, unannualized |
| Bootstrap ratios | Interpolated infinite ratios into NaNs; zero-downside draws could become false zeros | Empirical inverse-CDF ranks retain unbounded outcomes; null bounds carry status and undefined/unbounded mass is disclosed |

Calmar's annualized-return / maximum-drawdown convention is documented by
[PerformanceAnalytics](https://search.r-project.org/CRAN/refmans/PerformanceAnalytics/html/CalmarRatio.html).
Our CAGR calculation uses the actual calendar interval and does not import an
equity-market 6.5-hour trading day into gold trading frequency. This is a
descriptive extrapolation; a short profitable sample does not establish annual
performance.

## Explicit observation windows and units

Preferred calls:

```python
stats = summarize(trades, closed_balance_points, starting_balance,
                  start_ts=frozen_window_start, end_ts=frozen_window_end)
report = full_report(trades, closed_balance_points, starting_balance,
                     start_ts=frozen_window_start, end_ts=frozen_window_end)
```

An explicit positive `years` remains supported. Conflicting exact years/bounds
are rejected. Without complete bounds, available equity/trade timestamps are
used and the output flags that inferred bounds can include engine warmup or
omit an idle tail. Callers must supply the **whole preregistered observation
period**, not only the first and last trade, for defensible annualization and
unrecovered duration. Average holding time has no role in annualization.

CAGR is unavailable after any nonpositive observed balance, even if later trades
recover. An ending balance inconsistent with starting capital plus net trades
also suppresses CAGR and Calmar, identifying possible cashflows/data inconsistency.
This ending check cannot identify offsetting intermediate deposits/withdrawals;
proper cashflow-adjusted performance requires an explicit cashflow ledger.

`gross_profit`/`gross_loss` are conventional sums of winning/losing **net trade
P&L after modeled costs**, not pre-fee individual gross P&L. Sortino and reported
Sharpe are per-trade **net-P&L** estimators, not annualized calendar return ratios;
variable capital, sizing and serial dependence constrain interpretation. Omega
at a zero-dollar threshold equals the same after-cost PF. No-loss PF or Sortino
is not evidence of estimated zero risk. Payoff/breakeven estimates are also
unavailable when either the win or loss group has not been observed.

Drawdowns remain **closed-balance observation** metrics. The separate engine
sampled-equity instrument and continuous broker drawdown must not be confused
with these values. Report metadata and printed output now identify the basis.

Bootstrap remains IID resampling of historical trades, not block-bootstrap or
future-loss probability. Unbounded empirical ratio outcomes remain in the
quantile distribution. Undefined 0/0 outcomes are disclosed separately; the
quantile convention is explicit rather than silently reporting finite-only bounds.
Trade-order Monte Carlo holds terminal net P&L fixed; it is not independent proof
of positive expectancy or an account-rule survival model.

## Hand-calculated verification through `full_report`

| Example | Expected and observed |
|---|---|
| Start $100, sparse trades −$10 and +$20 over a declared calendar year | CAGR 10%, maximum DD 10%, Calmar **1**, unchanged when holding minutes change by orders of magnitude |
| Balance $100→$50→$1,000→$900 | Maximum dollar DD **$100**, maximum percentage DD **50%**, independently maximized |
| $100→$90→$100, flat at $100 through day 5, falls to $90 on day 6, window ends day 10 | Equal high recovers first episode; longest episode **5 days**, not 8 and not the full flat period |
| +$0.004, −$0.001 | After-cost PF **4**, not infinity/zero from cent-rounding |
| +$4, −$2, $0 | Per-trade Sortino **1/√3 ≈ 0.577350**, invariant to uniform P&L scaling |
| All winning / all zero outcomes | PF/Sortino null with informative status; full report serializes with `allow_nan=False` |
| Balance becomes nonpositive then recovers | CAGR/Calmar unavailable rather than a fictitious financeable compound return |

```
.\venv\Scripts\python.exe -m pytest tests/test_reporting_math.py tests/test_report_suite.py tests/test_bootstrap_ci.py tests/test_research_ratios.py -q
```

**31 focused tests passed.** The new examples use the actual public reporting
entry point, including its bootstrap/ablation/Monte Carlo subreports. Machine
records and source hashes: `research/results/reporting_math_2026-11-18/examples.json`.

## Frozen historical result treatment

Previously saved strategy reports predate this correction and retain their old
reported ratios. They are **legacy arithmetic, not recalculated evidence**. No
historical result files were overwritten and no qualification was upgraded.

In particular, frozen `fomc_shock_propagation.json` predates this window-aware
reporting. Its SHA-256 remains
`4b6333d67cc7c926d1d14d563cd66d9bc519b6687b5f50cc575e2a4e1084fcb6`.
Corrected annualized risk ratios for that study require the complete separate
2016–2021 and 2022–2025 preregistered era boundaries supplied to the new API,
including non-event and no-position time. Reusing only event trade timestamps
would again omit idle exposure time. The original run hash, configuration,
outcomes and rejection classification remain intact.
