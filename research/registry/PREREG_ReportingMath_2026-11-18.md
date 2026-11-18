# Reporting math engineering audit

Synthetic/hand-calculated metric verification only, not strategy evaluation.
Commit before code changes or tests; preserve existing pending Sortino-RMS fixes.

Acceptance criteria at normal `report.full_report` and `metrics.summarize` calls:

- Calmar uses calendar CAGR / maximum percentage closed-balance drawdown.
  Never infer trading frequency from holding duration or a 6.5-hour equity day.
  Support explicit observation boundaries/years and disclose inferred span.
- Consume the supplied chronological closed-balance path, with a net-trade cash
  path fallback only when none is supplied. Identify cashflow/inconsistent-path
  cases rather than annualizing them as investment returns.
- Longest drawdown episode includes recovery at equal prior high and any
  unrecovered tail through the supplied window end, and excludes periods flat at
  the high-water mark. Percentage DD is maximized independently of dollar DD.
- Compute PF from unrounded positive/negative after-cost P&L sums; losing-only
  outcomes give zero; no-loss or no-information ratios have explicit nonfinite/
  undefined status and JSON-safe null values rather than false zeros/NaNs.
- Sortino means unannualized per-trade net-P&L mean / zero-target downside RMS
  across all trades. Preserve that convention consistently and label units.
- Bootstrap PF/Sortino outputs distinguish finite, unbounded and undefined
  empirical outcomes without `np.percentile(inf)` NaNs or conditional finite-only
  intervals silently discarding extreme samples.
- Verify sparse trades across a declared year, loss/recovery/equal-high/flat and
  unrecovered tails, differing max-dollar/max-percentage DD, tiny P&L rounding,
  all-win/all-loss/all-zero/no-trade cases and bootstrap serialization.

No historical result or acceptance decision is retroactively upgraded. State
that closed-balance DD differs from sampled/continuous floating-equity DD.

## Nullable-consumer compatibility follow-up

Before implementation: audit callers of normal summarize/full_report for direct
numeric formatting or comparisons against now-null PF/Calmar/Sortino. Preserve
undefined status; show n/a and never silently coerce to a passing numeric value.
Exercise actual reporting expressions on no-loss/no-trade reports without
importing legacy modules that execute historical backtests at import time.
Do not rerun strategy studies, alter legacy criteria, or repair unrelated research
architecture. Pure presentation/gate helpers may be shared where needed.
