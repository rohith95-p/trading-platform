# Backtest reality audit — 2026-11-18

Status: **improved research simulator, not broker-validated execution**. No new
strategy profitability result, live order, remote terminal connection, or
2026-11-01 onward observation was used in this audit.

## Evidence and scope

Inspected the actual engine loop, position lifecycle, cost model, source-bar
views, independent audit script, live execution handler and existing parity tests.
Earlier profitable archives remain historical artifacts under their recorded
assumptions; changing defaults does not retroactively validate those results.

Acceptance protocol:
`research/registry/PREREG_ExecutionReality_2026-11-18.md`. Its criteria were
committed before running tests, but the first engineering edits existed before
that commit; this is not presented as a pre-implementation Git registration.
These are synthetic implementation checks, not strategy selection experiments.

## Verified corrections

| Issue | Observed old behavior | Current behavior | Regression evidence |
|---|---|---|---|
| Subminute entry interpolation | For delay d, filled at O+(C-O)d/60 using the minute's future close | Nonzero delay fails closed; explicit `entry_delay_model="legacy_interpolated"` retains biased historical reproduction and diagnostics identify it | Delay 1/20/59 rejected; legacy formula separately pinned |
| Entry-minute protection | New M1 positions were not walked through their own entry minute | Default `walk_entry_bar_m1=True` tests entry-minute stops/targets immediately, stop first on unknown order | Both legacy and live-order gate branches exit on same-minute co-touch |
| Stop gaps | Default `gap_fill_stops=False` booked stop level even with adverse opening gap | Default True books worse long bid / short reconstructed ask open plus slip | Existing long/short gap and no-gap unit cases |
| Partial M1 gaps | `require` rejected only completely absent candles; partial holes proceeded | Exact 15 scheduled minute timestamps required; `require` raises, `skip` skips whole candle and counts risk exposure | First/middle/last missing minute, duplicate masking missing minute, skip-entry case |
| Purported delay sensitivity | Applied assumed monetary penalties but described shifted entries | Explicitly labeled assumed P&L penalties, no empirical calibration | Existing arithmetic test passes; output identifies method |
| Cross-experiment geometry leakage | `_make_risk_manager` overwrote module TP/trailing constants | Production method code bound to per-manager globals; module constants unchanged | Construct custom then default managers; execute both stop formulas and recheck the custom manager |
| Auditor stale fill assumptions | Excluded entry minute and assumed stop-level fills | Independent helper honors recorded entry-minute, gap and ambiguity policies; exporter records config/cost/spec | Archived-versus-new entry indices, long/short gaps, both-touch, configured triple swap |
| Same-minute future account state | Later range exits released cash and slots before entries at the earlier minute open | Default `causal_minute_order=True`: only opening-quote events precede entry gates; full minute range runs afterward, including scan-skip branches | Both gate paths preserve occupied slot until later exit; future cash/floating values excluded; genuine opening gaps settle first; entry range walked once; protection survives downtime/spread/cadence skips |

`walk_entry_bar_m1=False`, `gap_fill_stops=False`, and legacy interpolation are
reproduction options. Their explicit config identities must accompany historical
comparisons. Current defaults change results and require fresh candidate replay;
old summary statistics cannot be promoted to the corrected engine.

`EngineConfig.live_parity_preset()` still records the nonzero live scan phase.
It now correctly refuses execution from minute bars unless the caller explicitly
chooses `entry_delay_sec=0` (bar-open approximation) or biased legacy reproduction.
Legacy interpolation also requires `causal_minute_order=False`. Zero-delay replay
is not verified live latency parity. No causal tick/pending-order
delay engine has been implemented in this change.

Strict partial coverage checks deliberately err on the side of rejecting a
candle that contains a legitimate session opening/closure without all 15 minutes.
An instrument-specific, independently verified trading calendar could distinguish
scheduled closure from missing observations. No interpolation or padding is used.

## Material unresolved limitations

1. **Minute chronology scope.** The open/range order is corrected and the old
   behavior survives only under explicit `causal_minute_order=False`, recorded in
   configuration and diagnostics. At each opening, existing positions are marked
   to that quote; opening protective events may settle; entry gates and management
   then see only opening prices; full range protective fills follow. A finally
   block preserves broker protection when scan gates skip the minute. Account
   policies see opening state and subsequently interval-end state. This is a
   causal bar approximation, not a timestamped tick event engine. Exact ordering
   within the subsequent minute remains unknown. The main engine's daily realized
   P&L accumulator is refreshed per M15 block, so same-block realized losses may
   reach that daily gate late; account certification still requires finer state
   reconciliation.
2. **Ask reconstruction.** Shorts test ask extrema as bid extrema plus one
   minute spread. A bar spread is not a synchronized ask high/low. The existing
   separate 2025 Dukascopy bid/ask snapshot is not integrated into this engine
   and is neither the intended Atlas broker nor verified raw tick history.
3. **Stop/target chronology and timestamps.** M1 cannot establish high/low
   order. Stop-first is a conservative convention, not observed tick sequence.
   Exit timestamps use minute-open labels even for later intraminute fills;
   minute-level holding periods and financing at boundaries need interval-aware
   treatment. Recorded MAE/MFE include the entire exit minute, potentially moves
   after the true exit. They are bar-range bounds, not exact realized excursions.
4. **Floating drawdown.** `BacktestResult.equity` is appended on realized closes
   as balance. It is not a continuously sampled mark-to-market equity series.
   Closed-balance DD cannot certify prop-firm equity floors or pathwise ruin.
5. **Remaining shared module bindings.** TP/trailing geometry isolation is fixed.
   The engine still replaces risk-manager and strategy module MT5 references with
   its offline stub. Run research in a dedicated process; do not run a live
   broker loop inside the same interpreter. This is not thread-safe concurrent
   engine/live execution.
6. **Broker constraints.** Margin uses an approximate leverage formula; fixed
   lots are not explicitly checked against volume_min/max/step in `_open`.
   Broker stop/freeze distance, tick rounding, dynamic margin tiers, stop-out,
   fill policy, reject/retry behavior and conversion currency are not fully modeled.
7. **Forced closes and management.** Causal mode now marks the current opening
   quote before weekend flatten. End-of-data close still omits explicit market
   slippage; protection/consolidation exits have simplifying poll assumptions.
   Causal protection/giveback management sees the opening quote and prior extrema,
   rather than the later minute low/high. Pyramiding is disabled in production;
   optional additions now receive the same deferred range protection, but this
   audit does not establish full pyramiding/live parity.
8. **Costs uncalibrated for target account.** Spread, fixed adverse slippage,
   commission and asymmetric swap are scenario assumptions or prior broker
   observations. Current Atlas contract terms, historical financing, exact triple
   rollover and actual fill distributions have not been verified here. Constant
   slippage cannot model news tails, liquidity rejection or variable latency.
9. **Auditor compatibility boundary.** The checker now reads exporter metadata
   and independently honors entry-minute/gap/ambiguity and cost settings. Missing
   metadata falls back to archived assumptions and is explicitly marked
   `legacy_assumptions_unverified`; it does not establish those assumptions.
   Dynamic stop histories, actual ask extrema and quote chronology still need a
   richer independent replay. No historical checker run was performed in this
   audit. Previous zero arithmetic discrepancies do not prove realistic fills.
10. **Production parity scope.** Synthetic gates and shared RiskManager calls
    support individual equivalence checks. They do not reconcile every production
    signal, quote, order request, broker rejection and deal. No native MT5
    equivalent-MQL5 real-tick test or prospective demo reconciliation was run.

## Professional-method comparison

- MetaQuotes documents that real-tick testing may substitute generated ticks
  when tick history is missing or disagrees with minute bars. An MT5 report must
  record real-tick coverage and substitutions; selecting its real-tick mode alone
  is insufficient. [MQL5 testing reference](https://www.mql5.com/en/docs/runtime/testing).
- LEAN's published fill model distinguishes tick/quote/bar inputs and permits
  adverse stop fills. Matching its generic model is not proof of this broker's
  execution. [QuantConnect Immediate Fill Model](https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/trade-fills/supported-models/immediate-model).
- NautilusTrader distinguishes bars from quotes, trades and depth, and states
  that bars cannot establish intrabar order or spread. This supports requiring
  finer validation for timing-sensitive effects, not adding costly L2 by default.
  [NautilusTrader data and venues](https://nautilustrader.io/docs/latest/concepts/backtesting/data-and-venues/).
- Backtrader and hftbacktest were requested for wider comparison but have not
  been reviewed in this scoped audit. No package was installed or benchmarked.

## Tests run

```
.\venv\Scripts\python.exe -m pytest tests/test_execution_reality.py tests/test_execution_audit_helpers.py tests/test_bias_audit_knobs.py tests/test_engine_live_parity.py tests/test_execution_delay.py -q
```

**79 passed** on 2026-11-18. The chronology extension was committed before its
implementation/tests in `PREREG_MinuteChronology_2026-11-18.md`. Synthetic tests establish these contracts only.
They provide no profit factor, execution accuracy percentage or account pass
probability. Broader regression suite remains the parent finalization task's job.

## Required next validation

First complete full-equity recording and finer daily-risk state reconciliation. Extend auditor
compatibility for dynamic management. Re-run a fixed committed candidate with its exact input hashes and
record all changed trades and costs against the old engine. Then acquire intended
broker demo quote/deal logs, estimate conditional fill costs and implement an
independent quote replay. Reconcile a fixed signal list against equivalent native
MT5 tests and prospective demo orders. Keep the November holdout closed until
candidate rules and all acceptance criteria are fixed.

Current release classification: **offline research only; no execution-certified
strategy and no new deployment approval**.
