# Ultra Core project review — 11 November 2026

## Scope and conclusion

This is an investigation, not a strategy change. The production source, strategy settings, credentials, deployment and live account were not intentionally changed. Review scripts and outputs are isolated in this directory. No bot startup, order placement, broker-history download, Telegram notification or deployment was invoked. The November 2026 forward holdout was not opened. These are diagnostic reproductions of already-used historical windows; their trial-ledger writes are disabled so reproducing an existing trial does not create selection trials.

The project has a substantial execution and research framework. Its current four-leg portfolio has not established a durable positive edge. The corrected historical results are reproducible, while several statistical, provenance and reporting problems still deserve repair. Those problems warrant more careful interpretation of the research; they do not, by themselves, turn the negative historical record into a profitable strategy.

This review covers the architecture and critical execution/research paths, the existing research record, the complete non-live test suite, cached data integrity, fresh portfolio replays and selected fixed stress scenarios. It is not a line-by-line security audit of every archived strategy, an exhaustive rerun of every historical parameter search, a current production health check, or verification of today's external prop-firm rules.

## Project map

The inventory contains 86 Python source files (20,646 lines), 55 script files (8,435 lines), and 36 test files (6,154 lines). The project is Python with NumPy, pandas, SciPy and Windows MetaTrader5 bindings.

| Component | Responsibility | Main files |
|---|---|---|
| Orchestration | Startup refusals, account/feed checks, 60-second scan, reconnection, state and shutdown | `src/core/main_loop.py`, `resilience.py`, `data_fetcher.py`, `scripts/watchdog.py` |
| Signal to order | Closed-candle evaluation, D1 filter, deduplication, conviction ranking, cooldown, risk and Atlas gates, recording | `src/core/order_flow.py`, `conviction.py`, `execution_handler.py` |
| Risk | ATR stops, balance-based lots, account exposure, daily/weekly/monthly/peak caps, streak pauses | `risk_manager.py`, `risk_rules.py`, `sizing_ladder.py`, `pre_trade_veto.py` |
| Atlas | Rule loading, stateful account checks, equity/daily floors, news, minimum hold and payout-related constraints | `src/atlas/rules.py`, `src/core/atlas_bridge.py`, `config/atlas_access.json` |
| Operations | Persistent halt, measurement-only mode, heartbeat, alerts, journal, own-vs-account position scope | `ops.py`, `alerts.py`, `journal.py`, `scope.py`, `live_status.py` |
| Historical replay | M15 strategy clock with M1 execution, costs, D1 reconstruction, production risk helpers and parity switches | `src/backtesting/engine.py`, `costs.py` |
| Data | Broker/archive merge priority, archive timezone conversion, provenance, warmup, holdout cutoff | `src/backtesting/master.py`, `data.py` |
| Research | Features, candidate libraries, coarse screening, matched controls, full replay and validation studies | `src/research/`, `scripts/research/`, `scripts/validation/` |
| Governance | Configuration fingerprints, validation records, trial and holdout ledgers, preregistrations and decision history | `system_config.py`, `validation_ledger.py`, `src/research/ledger.py`, `research/registry/`, `DECISIONS.md` |

Atlas mode selects `portfolio_atlas.py`: AsianRangeFilteredV6, AsianBreakoutV6, LondonMomentumTightV6, NYSessionReversalV6. Non-Atlas mode selects a different portfolio, the single DonchianTrendV6 in `portfolio_v6.py`. The four-leg results must not be attributed to non-Atlas mode. The deployed process and its environment were not queried.

The Asian legs share a breakout event; they are not independent sources of risk. Conviction ranking selects the winner when multiple signals collide. London momentum uses the earlier session's direction; NY reversal uses a sweep/rejection of the London range. Stops and targets are ATR multiples. The D1 gate uses the previous closed daily candle with a permitted bullish-to-bearish intraday override. Lots come from the sizing ladder, not the caller's requested lot size.

## Checks executed

* `venv/Scripts/python.exe -m pytest -m 'not live'`: **513 passed**, 22.98 seconds reported by pytest.
* `venv/Scripts/python.exe -m pip check`: **failed**; `realtime 1.0.6` requires `websockets>=11,<13`, but `17.0.1` is installed. The test suite passing does not resolve this environment inconsistency. This does not establish that the trading path uses the conflicting package.
* `venv/Scripts/python.exe -I scripts/validation/prereg_check.py`: **failed**; `RESULT_MetricSuite_2026-11-09.md` has no corresponding preregistration/protocol. The CI workflow invokes this check separately from pytest, so a green local pytest run is insufficient for green CI. Three studies have preregistration and result in the same commit, which the checker labels weak.
* Cached-data inspection: **17 NPY datasets**, zero mismatches against available manifests. Individual cache hashes matching does not resolve the merged-data hashing defect below.
* Fresh DEV, TEST, RECENT and five historical-era replays: `reproduce.py`. Uses the existing audit harness for the Atlas-guarded modern windows and the same baseline engine assumptions as the existing long-history study for the older eras.
* Fixed RECENT cost/fill diagnostics: `stress.py`, including frictionless, doubled spread/tripled slippage with ECN commission retained, and gap-aware stops. These scenarios do not select a replacement configuration.
* Independent gross/net/commission/balance arithmetic, trade bootstrap, month-block bootstrap and order reshuffles: `aggregate.py`, output `independent_statistics.json`.

## Fresh modern-window results

All use $5,000 starting balance, 0.02 lots, maximum three positions, D1 gate on, profit protector off, 24-hour entry-window switch and realistic ECN costs. The audit wrapper adds Atlas monitoring. It is not the entire production gate chain: it does not call the live Atlas pre-order/news service for every order.

| Window | Dates, UTC, end exclusive | Trades | Net | PF | Win rate | Max realized drawdown |
|---|---|---:|---:|---:|---:|---:|
| DEV | 2022-08-01 to 2024-06-01 | 132 | -$294.90 | 0.658 | 28.0% | $305.87 |
| TEST | 2024-06-01 to 2026-01-01 | 253 | +$1,058.48 | 1.395 | 42.3% | $238.99 |
| RECENT | 2026-07-06 to 2026-10-30 | 54 | +$790.14 | 1.809 | 50.0% | $193.52 |

These reproduce the corrected November 1 audit, not the older positive DEV result still advertised in the README. They are already-used historical windows and are not fresh evidence from an untouched test set. Drawdown here means closed-trade balance drawdown, not intratrade equity drawdown.

DEV/TEST/RECENT have respectively 4 / 2,130 / 0 M15 candles skipped because M1 is absent; zero open-position exits were left unchecked across those wholly missing candles. Partial M1 coverage remains: 761 / 402 / 102 candles, missing 1,204 / 1,000 / 199 minutes. Minute resolution is an improvement over M15 resolution, not proof that all intrabar paths are known.

The audit's DEV account can stop opening trades because of account rules even when the `halts` list is empty: that list records FLATTEN events, not every STOP_NEW event. Do not infer uninterrupted account eligibility from `halts=[]`.

## Quant analysis findings

### Fresh long-history reproduction and independent uncertainty checks

| Era | Dates, UTC, end exclusive | Trades | Net | PF |
|---|---|---:|---:|---:|
| OOS 1 | 2004-07-01 to 2008-01-01 | 331 | -$254.97 | 0.748 |
| OOS 2 | 2008-01-01 to 2012-01-01 | 643 | -$742.80 | 0.820 |
| OOS 3 | 2012-01-01 to 2016-01-01 | 567 | +$5.28 | 1.002 |
| OOS 4 | 2016-01-01 to 2020-01-01 | 578 | -$146.50 | 0.931 |
| OOS 5 | 2020-01-01 to 2022-08-01 | 437 | -$172.36 | 0.944 |
| Pooled | Separate era runs combined | **2,556** | **-$1,311.35** | **0.900** |

The historical baseline has no Atlas wrapper; it is not a prop-account survival result. Pooled win rate is 35.64%, expectancy -$0.513/trade, and realized synthetic pooled drawdown $1,412.91. All four individual strategies have negative pooled net P&L; their details are in `independent_statistics.json`.

Independent arithmetic checked all **2,995 trades** across the eight replays. There were zero gross-P&L, net-P&L, ECN commission, running-balance, reversed-time or out-of-window exit discrepancies. This validates these arithmetic identities; it does not independently validate every historical signal or M1 barrier hit.

With seed 20261111 and 5,000 samples, the pooled per-trade expectancy's IID bootstrap 95% interval is **[-$0.965, -$0.046]**. Resampling whole observed trade-bearing months gives **[-$1.024, +$0.006]**. The latter narrowly includes zero. This is a material qualification: the sample loses money, but a claim that all dependence-aware 95% intervals exclude breakeven would be false. Both exercises assume the observed history can represent a resampling population and do not establish future regime behavior.

Trade resampling gives 98.44% of synthetic fixed-length samples finishing below the initial balance, rather than the permutation report's mechanically fixed 100%. This fraction is conditional on the empirical trade population, not a forecast probability. Order permutations yield median/p95 maximum drawdown of **$1,505/$1,788**. The corrected target-zero per-trade Sortino is **-0.0684**, rather than the old nonstandard -0.1042.

### RECENT cost/fill scenarios

| Fixed scenario | Trades | Net | PF |
|---|---:|---:|---:|
| ECN baseline, Atlas audit wrapper | 54 | +$790.14 | 1.809 |
| Frictionless fills, baseline engine | 54 | +$871.18 | 1.920 |
| ECN with 2x spread and 3x slippage, baseline engine | 54 | +$787.98 | 1.805 |
| ECN with gap-aware stops, baseline engine | 54 | +$790.14 | 1.809 |

The engine uses each cost scenario throughout the replay, so scenario results can change signals taken, stop placement and realized paths; they are not a constant fee deducted from identical locked trades. The frictionless cost model leaves configured entry spread gates active. This is a diagnostic on a previously selected favorable window, not proof of robustness across history. No gap-aware change appeared in this window; the earlier long-history bias report found gap costs elsewhere.

### 1. Effective-trial correlation is not aligned in time

`src/backtesting/metrics.py:k_eff_correction` truncates each P&L list to the shortest length, then calls `np.corrcoef` by trade index. Trade 50 of one strategy can have occurred years away from trade 50 of another. `src/research/ledger.py` saves P&Ls without their dates, so the lost alignment cannot be recovered from those records.

The example in `diagnostics.json` supplies the same six outcomes for two hypothetical, non-overlapping periods and obtains K_eff=1. The API has no dates with which to distinguish those periods. Consequently, the reported K_eff=20.38 in the volume-search report is not a validated estimate of economic trial dependence. Its numerical closeness to the raw count is not evidence that the original 48 strategies were similarly independent.

A repair would require common-calendar returns or marked-to-market equity increments, one series for each complete candidate evaluated on the same sample, plus explicit missing-data conventions. Trials on disjoint windows should not be treated as contemporaneous strategy variants.

### 2. Trial identity omits strategy parameters, source revision and data identity

`src/research/ledger.py:trial_id` hashes strategy names, window, EngineConfig and costs. `BacktestEngine.run` supplies names, not a snapshot of each strategy's instance parameters. Changing an ATR stop or range threshold on a class whose name stays the same can retain the same trial ID. Re-running after source/data changes can also replace the record at that ID. This can undercount distinct research decisions and lose earlier evidence. The issue is conditional on those values changing without a corresponding engine/name change; it is not a claim that every existing row collided.

### 3. Master-series data hashes do not identify the data

`master.load_master` constructs a BarSet with `manifests={}`. `BarSet.hash_key` hashes only the manifest entries, so every such master dataset gets `e3b0c44298fc1c14`, the prefix of SHA-256 of the empty string. Confirmed on two different arrays in `diagnostics.json`. Source files may individually be intact while the replay's reported `data_hash` remains uninformative. Hash the merged arrays, their contract specification and transformation/merge policy.

### 4. Sortino's downside denominator is incorrect for the stated metric

`metrics.summarize`, `report.full_report`, and `scripts/validation/full_metric_suite.py` use the standard deviation of negative outcomes around their own mean. This is different from downside deviation around a chosen return target. Identical losses produce a zero denominator even though downside risk is positive. For `[2,-1,2,-1]`, current downside standard deviation is zero; target-zero semideviation is 0.7071 and the corresponding per-observation Sortino is 0.7071. The independent statistics use target-zero root-mean-square downside. Dollar P&L per trade should also be labeled separately from calendar return ratios. See [CFA Institute's discussion](https://rpc.cfainstitute.org/-/media/documents/code/gips/the-sortino-ratio.pdf).

### 5. The Monte Carlo interpretation overstates its evidence

`monte_carlo_paths` permutes a fixed set of trades. Every ordering necessarily has the same final P&L when lots and trades are held fixed. Thus a 100% fraction finishing below the starting balance is an arithmetic identity for that losing sample, not a 100% estimated probability of future loss. Permutation is useful for sequence-dependent drawdown. Resampling trades or blocks estimates different, explicitly conditional sampling uncertainty. None is a substitute for new forward evidence, and shuffled trades do not reapply Atlas state or account stops.

### 6. DSR results are presented too literally

The report's DSR=0.0011 is not a posterior 0.11% probability that the strategy has skill, nor is the N=1 result a 99.2% probability that PF 1.41 is real. DSR is a benchmark/significance calculation under modeling assumptions. In `full_metric_suite.py`, the cross-trial Sharpe variance is approximated from average win/loss pairs for 21 different search candidates, ignoring within-win/loss variation; it is not measured from the original 48 full return series. Per-trade outcomes also have irregular timing, changing dollar scale and dependence. The negative pooled P&L is a direct observation; the exact DSR confidence claims require more qualification. See [Bailey and López de Prado](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf).

### 7. The full robustness report exists but is not integrated into research callers

A source search finds `full_report` defined in `src/backtesting/report.py` and exercised in tests, but no production/research caller in `src` or `scripts`. The module's stated goal that every backtest emits all metrics is therefore not implemented. `summarize` also uses holding-duration-based annualization for Calmar, while `full_report` uses elapsed calendar years; the two values are not interchangeable. Drawdowns in these reports use realized P&L and omit floating adverse excursions.

### 8. Execution-delay sensitivity is a synthetic haircut

`scripts/validation/execution_delay_sensitivity.py` subtracts `delay * decay_rate_per_bar * average_absolute_P&L` from each trade. It never moves an entry through historical prices. This can be retained as a hypothetical P&L penalty scenario, but it is not empirical evidence that a strategy survives delayed fills. The engine's actual entry-delay settings are the suitable basis for a replay-based latency test.

## Other implementation findings

* Risk failures can permit continuation. `order_flow._execute_signal` still catches all exceptions around `risk_rules.evaluate` and continues, under a stale comment saying the rules are shadow-only, although ENFORCE=True. `risk_rules.load_state` returns a fresh default state for unreadable/corrupt files; `ExecutionHandler` also has a default empty-state fallback. The veto does not recreate all equity/peak/daily checks in the skipped evaluation. These are failure-path concerns found in code; no live bypass was induced.
* `SizingLadder.get_risk_pct` omits the contract/tick-value multiplier. At 0.02 lots and a $10 gold price stop on $5,000, it reports 0.004% instead of 0.4% for the cached 100-ounce contract. Search found calls only in its display/examples, not the live order-sizing path. This is a misleading risk-display helper, not evidence of 100-fold live lot sizing.
* `BacktestEngine.run` closes remaining positions using `self.m15[-1]`, rather than the last simulated bar. When the supplied BarSet extends past `end_ts`, an END_OF_DATA exit can use prices after the requested window. **Confirmed with a synthetic execution probe** in `boundary_probe.json`: requested end timestamp 1704346200, recorded exit timestamp 1704426300, 80,100 seconds later. The new historical reproductions supply end-bounded datasets and had zero out-of-window exits. A boundary-specific regression test is appropriate before using wider loaded datasets for truncated runs.
* `independent_audit_check.py` reads the fixed October 30 directory while `independent_audit_run.py` writes November 1. Running the advertised pair need not check the newly produced trades. Its truncation exclusion also spells `end_of_data` differently from the engine's `END_OF_DATA`. This review used separate accounting checks on its own output files.
* The config fingerprint tracks selected constants and stop/session settings, not all strategy entry parameters, code revisions, broker/account terms, Atlas rule contents or all risk switches. A matching fingerprint means selected values match a recorded configuration; it does not mean profitability was established. The validation-ledger module explicitly permits recording losing results.
* A holdout cutoff protects November 1 onward by default, but the spend ledger identifies histories by the provided name. It is not a universal interval-overlap guard. Existing scripts and direct cache loaders can also bypass the master-loader route. These are governance aids, not an impermeable statistical boundary.

## Interpreting the existing research

The original four legs and later stop choices were selected using the same modern windows now quoted as successful backtests. The long-history study and matched-direction controls are more relevant to generalization. Later entry-search and volume-search reports contain no candidate that passed their complete progression. That is evidence about those tested definitions and samples, not proof that every price/volume strategy is impossible or that all future searches must fail.

The early data contain incomplete minutes, changing tick-volume scale and largely absent historical spread fields; the engine substitutes a fixed spread for zero values. Contract, financing and slippage assumptions are imposed across long eras rather than observed contemporaneously. Each historical era restarts from $5,000 with fresh engine state, so summing eras is a pooled experiment, not a single uninterrupted Atlas account simulation. The modern Atlas wrapper and baseline historical engine also have different gate chains. These limitations should travel with every headline PF.

## Possibilities for the next phase

The immediate useful work is to make the evaluation trustworthy: calendar-aligned candidate returns, complete immutable trial records, real merged-data hashes, corrected metric definitions, reporting integrated into every research run, and explicit comparisons of live and replay gates. Risk-state read/evaluation failure behavior deserves a separate implementation decision.

After that, any strategy work can use a limited, declared hypothesis set with matched controls and calendar-based evaluation. A claim about a recent regime should be framed as a regime-specific hypothesis with adequate samples and costs, not rescued by selecting a favorable subperiod after looking. New information such as cross-asset or event features is a research possibility, not a validated edge. Raising leverage or target size does not establish predictive information.

No new parameter search, strategy recommendation, live change or production intervention was made. The next action remains the owner's decision after this review.

## Reproduction

From the project root, with the existing environment:

```powershell
venv/Scripts/python.exe research/results/project_review_2026-11-11/reproduce.py
venv/Scripts/python.exe research/results/project_review_2026-11-11/stress.py
venv/Scripts/python.exe research/results/project_review_2026-11-11/diagnostics.py
venv/Scripts/python.exe research/results/project_review_2026-11-11/boundary_probe.py
venv/Scripts/python.exe research/results/project_review_2026-11-11/aggregate.py
```

`aggregate.py` requires all eight replay JSON files. The raw outputs preserve trades, settings and diagnostics separately from this narrative. No original research result files were overwritten.
