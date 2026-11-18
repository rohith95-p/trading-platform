# Independent XAUUSD tick versus minute execution fixture

Engineering comparison, not a candidate strategy or profitability experiment.
Commit before acquisition/replay. No orders, paid data, live account connection,
or data at/after 2026-11-01. No production source/configuration changes.

## Fixed bounded scope

Attempt one official Dukascopy raw tick hour: **2025-01-06 12:00–13:00 UTC**.
First try its known public historical `.bi5` endpoint; if unavailable, try one
legitimate official alternate API/download endpoint. Do not retry a rate-limited
endpoint, bypass restrictions, use requester-pays storage or credentials, or
change the date after seeing execution outcomes. Record URLs/status/hashes.

If ticks are available, validate monotonic millisecond times, bid<=ask, positive
prices and supplied sizes; retain duplicated timestamp observations in source
order. Cross-check price scale and M1 aggregation against the existing separate
Dukascopy 2025 bid/ask chart snapshot, disclosing any mismatch.

Two independent, deterministic order fixtures (not production strategies): BUY
at 12:15 UTC and SELL at 12:30 UTC, each simulated separately, 0.02 lots, $1/oz
initial stop distance and $1.50/oz target, no management, no overnight holdings.
Apply fixed existing ECN commission and adverse 0.02/oz slippage to market/stop
fills; targets at their levels. Tick fills use the first actual quote at/after
the signal; long exits on bid, shorts on ask, stop-market fills at the actual
first crossing quote plus adverse slip. Force close at the last recorded quote
if no protective exit, explicitly identify the terminal boundary assumption.

Replay matched M1 bar approximations through the actual BacktestEngine with the
same deterministic fixture/risk geometry. This is explicitly an execution fixture
fed bars aggregated from the frozen ticks, not an alternate candidate backtester
or a splice into the master history. Compare counts, price/time discrepancies,
net P&L and sampled/full-tick floating-equity drawdown. Disclose assumed minute
spread reconstruction versus observed ask ticks. Use master-loader history only
where ordinary strategy-history plumbing needs it; record all fixture provenance.

If source acquisition fails, deliver read-only pre-holdout MT5 capture tooling
that explicitly requires verified demo identity and cannot send orders; execute
its parser/replay on a safe offline fixture. No unsupported claim of historical
tick verification is permitted. Preserve current source/date-independent tests.
