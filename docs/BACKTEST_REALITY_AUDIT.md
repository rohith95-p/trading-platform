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
| Balance-only drawdown evidence | Equity output contained only realized balance | Separate opt-in open/end samples expose gross floating and assumed net-liquidation equity and sampled drawdowns | Synthetic side/spread/fee/swap/recovery/invariance tests and fixed real-cache replay with independent quote/cash/mark/DD reconciliation |
| Delayed daily realized loss | Daily totals refreshed only after M15 block | `_close` immediately updates the IST exit-date total used by next scan | Later signal in same M15 blocks after loss; IST-midnight date boundary checked |
| Equity evidence classification | Balance path could be mislabeled floating equity | Diagnostics declare `equity_kind="closed_balance"`, `floating_drawdown_verified=False` | Exported result evidence flags checked |

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
   within the subsequent minute remains unknown. The daily realized accumulator
   now updates immediately on each close with the existing IST exit-date
   attribution; account certification still requires finer state reconciliation.
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
4. **Floating drawdown.** `BacktestResult.equity` remains realized closed balance.
   `record_equity_samples=True` now emits a separate `equity_samples` record at
   open, post-order open and interval end. It includes gross floating equity and
   modeled net-liquidation equity after accrued swap/pending commission reserves.
   Sampled drawdowns are measured separately for each. These quotes miss any
   intraminute adverse extremes and do not certify continuous broker equity
   floors or pathwise ruin. `floating_drawdown_verified=False` remains explicit;
   consumers must distinguish sampled marks from continuous tick equity.
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

The original correction set passed **82 tests**; with sampled-equity checks,
the same command plus `tests/test_sampled_equity.py` passed **87 focused tests**
on 2026-11-18. The chronology extension and follow-up daily-loss/
equity-evidence criteria were committed before their
implementation/tests in `PREREG_MinuteChronology_2026-11-18.md`. Synthetic tests establish these contracts only.
They provide no profit factor, execution accuracy percentage or account pass
probability. Broader regression suite remains the parent finalization task's job.

## Required next validation

First complete intended-broker quote-level state reconciliation. Extend auditor
compatibility for dynamic management. Re-run a fixed committed candidate with its exact input hashes and
record all changed trades and costs against the old engine. Then acquire intended
broker demo quote/deal logs, estimate conditional fill costs and implement an
independent quote replay. Reconcile a fixed signal list against equivalent native
MT5 tests and prospective demo orders. Keep the November holdout closed until
candidate rules and all acceptance criteria are fixed.

Current release classification: **offline research only; no execution-certified
strategy and no new deployment approval**.

## Frozen real-cache verification, sampled equity extension

The precommitted `PREREG_SampledEquity_2026-11-18.md` fixed an unchanged original
four-leg replay on Sep 1–15, 2026, $5,000 / 0.02 lots and existing ECN costs.
Actual result: **5 trades, +$0.858, PF 1.007196**; closed-balance DD **$90.306**
versus sampled gross/net equity DD **$119.50** (approximately **2.3648%**).
All **40,366 samples** reconciled independently against raw cached M1 quotes,
trade positions, cash, fees and drawdown, with **0 errors**; all five trade
arithmetic checks also passed. Source files were unchanged during the run.

Coverage excluded 13 partial M15 candles containing 27 missing M1 observations;
no position was open across those skipped candles (`exits_unchecked_no_m1=0`).
The short previously explored benchmark is engineering evidence only. It is not
a new edge, holdout evaluation, Atlas pass/payout simulation or broker fill audit.
See `research/registry/RESULT_SampledEquity_2026-11-18.md` and full machine-readable
records under `research/results/sampled_equity_2026-11-18/`.

## Raw-tick source attempt and read-only demo capture fallback

The precommitted `PREREG_TickReconciliation_2026-11-18.md` fixed a Jan 6, 2025,
12:00–13:00 UTC raw-quote comparison. The official archive connection reset;
one alternate official-domain API request returned HTTP 202 with WAF challenge
and an empty body. This was recorded as blocked acquisition, never empty market
data. No retry, challenge bypass or paid storage was used. Historical tick
execution reconciliation therefore **remains incomplete**.

A standard local native cache inventory found one Oct 2026 XAUUSDm `.tkc` under
an Exness-MT5Trial11 directory. No MT5 terminal was running; demo identity was not
verified and the proprietary file was not decoded or relabeled certified ticks.

`scripts/validation/mt5_demo_tick_capture.py` now provides bounded, pre-holdout,
read-only capture from an explicitly pinned **already-running demo** terminal.
It checks exact executable path, login/server and actual demo mode; real/contest
accounts and identity changes fail closed. It never signs in, auto-launches a
terminal, changes trading settings or sends orders. It has not been connected to
an actual terminal in this study.

`scripts/validation/tick_fixture_reconciliation.py` was executed using **66 toy
quotes**, explicitly synthetic, against the actual M1 engine and a separate
ordered bid/ask quote replay. Known target-before-stop ordering and ask-only
spread widening produce opposite protective exits between tick and M1 paths.
These cases verify why M1 approximation can differ; they do not measure how
often that happens historically or calibrate intended-broker execution. **14
focused capture/replay tests passed**, using an offline mock terminal. Complete
source-status, fixture and price/time/P&L/DD evidence is under
`research/results/tick_reconciliation_2026-11-18/`; see the matching RESULT report.
