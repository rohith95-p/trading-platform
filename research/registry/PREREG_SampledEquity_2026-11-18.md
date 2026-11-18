# Sampled floating equity instrumentation and frozen benchmark

Purpose: engineering verification, not evidence of a new profitable strategy.
Commit before implementation, tests or historical replay. No production edits,
broker calls, optimization, November holdout or strategy-rule changes.

## Fixed implementation contract

Retain `BacktestResult.equity` as the original closed-balance curve. Add a separate
sample record at the known opening quote and interval end, marking surviving
longs to bid and shorts to reconstructed ask. A post-order opening sample may
record immediate spread/cost burden. Distinguish gross floating account equity
from assumed net-liquidation equity (pending round-trip commission and accrued
swap under the same configured model). Do not label either continuous tick equity.

Compute sampled peak-to-trough maximum drawdown against the account's initial
balance and preserve sample order when adjacent close/open timestamps coincide.
Sample before any opening-gap liquidation and again after end-of-data settlement.
Store enough position state in each record to independently reproduce marks and
modeled costs. Do not let instrumentation change engine decisions.

Tests must establish long/short mark sides, immediate spread and commissions,
rollover financing, unrealized drawdown with zero realized loss, and distinction
between closed balance and sampled equity. Independently re-derive arithmetic
and sample drawdown without importing the engine's sampling implementation.

## Frozen cached verification replay

- Market XAUUSDm only, `load_master(("M15", "M1", "D1"))`.
- Window 2026-09-01 00:00 UTC inclusive to 2026-09-15 00:00 UTC exclusive.
- Existing four `PORTFOLIO` classes, unchanged source files hashed in output.
- Fixed 0.02 lots, initial $5,000, max 3 concurrent / 3 same-direction.
- 7,500-bar feature history, production default strategy geometry unchanged.
- Causal minute ordering, protective gap fills, zero-delay bar-open proxy,
  live order of entry gates, protector/trailing/pyramiding off.
- `m1_policy="skip"`, report all skipped/partial counts; no interpolation.
- ECN cost scenario already in repository, including its swap assumptions.
- Owner's 24-hour weekday window (`ULTRA_TRADE_24H=1`); no new account-rule wrapper.

This is a fixed operational smoke benchmark. Any profit factor is descriptive of
a short previously explored period, not an independent acceptance result. No
candidate can qualify from it. All trades, samples, input/code hashes, independent
reconciliation and material coverage limitations must be saved.
