# WMC Genesis: original-bytecode XAUUSD research results

Date: 2026-11-11. Decision: none of the tested configurations qualifies for deployment or an Atlas evaluation purchase on this evidence. This is a negative research screen, not proof that every possible configuration of the full application loses money.

## Work completed

- Inspected the supplied handoff, hash manifests, original strategy/analyzer/selector disassembly and trade-management/application wiring. Preserved original bytecode and ran only reviewed offline modules, without MT5 or application startup.
- Evaluated 203,642 original closed-M5 decisions across 2013, 2018 and 2025. Fixed years were chosen before P&L inspection for different market conditions; they are inspected samples, not pristine out-of-sample validation.
- Tested seven standalone rules and three routers, each with static exits, original management wiring, and corrected constant-initial-risk management. Added two explicitly separate Reversal repairs and static frictionless execution diagnostics.
- 138 original year/scenario cells plus 36 independent 2025 coverage-segment cells. Thirty-six costed candidate configurations; no parameter search was used to choose a winner.
- Verified management actions and peak state against the recovered original manager on 5,000 randomized inputs. Checked cash identities, executable entry prices and static first-hit exits independently of the simulator.

Validation completed: independent audits cover 218,912 scenario-specific baskets, 254,703 exit legs and 64,661 static first-hit exits, with zero cash/entry/static-exit mismatches. These are overlapping configurations, not independent market observations. The final non-live test suite passed all 556 tests. These checks validate the stated mechanics; they do not validate missing prices, full application parity or profitability.

## Original strategy results

Profit factor after modeled costs. Static exits isolate the entry/initial bracket; they do not reproduce the full application. 2025 uses the coverage-segment sensitivity explained below. PF is gross winning basket P&L divided by absolute gross losing basket P&L; partial legs are grouped by position.

| Strategy | 2013 PF | 2018 PF | 2025 covered-sample PF | 2025 trades | 2025 win rate |
|---|---:|---:|---:|---:|---:|
| TrendFollowing | 0.683 | 0.613 | 0.965 | 566 | 32.5% |
| RangeTrading | 0.649 | 0.415 | 0.799 | 1059 | 15.7% |
| Breakout | 1.742 | 0.527 | 0.610 | 61 | 24.6% |
| Pullback | 0.736 | 0.461 | 0.936 | 1357 | 30.7% |
| Reversal | No trades | No trades | No trades | 0 | N/A |
| Momentum | 0.955 | 0.832 | 1.040 | 613 | 30.7% |
| SwingTrend | 0.897 | 0.983 | 0.775 | 316 | 14.6% |

**No configuration reaches PF 1.3 with at least 30 trades in each screened year.** In 2018 every costed original strategy/router/exit variant has PF below 1.0; the best is SwingTrend static at 0.983. Neither Reversal repair passes. Frictionless static execution also produces no candidate meeting PF 1.3 in all three years, so removing fees alone does not establish the required edge.

Breakout looks attractive in 2013 in isolation: 56 trades, PF 1.742, +$69.85 at .02 lot. Its other screened years lose. Choosing it using only that year would be selective reporting.

Momentum static is the least unpromising original standalone entry in the recent covered samples, not a qualifying strategy: 2025 PF 1.040, 613 trades, 30.7% wins, +$305.53, approximately 14.64% sampled liquidation drawdown relative to a $5,000 starting balance. The drawdown is sampled at minute opens, not tick-perfect or Atlas-certified. Its 2013 and 2018 PFs are below 1.0.

## Source defects and execution issues

1. **Reversal trigger contradiction:** the normal analyzer path requires closes outside a range and the same current close back inside it. The original rule produced no actionable Reversal signals. Repairs are research variants; no source bytecode was patched.
2. **Reversal direction:** the original comparison against the prior high can select SELL for a failed-down breakout. Tested a trigger-only repair and a trigger-plus-direction repair. Their static PFs (2013 / 2018 / 2025 covered) were 0.673 / 0.421 / 0.804 and 0.645 / 0.472 / 0.831 respectively. Correcting a defect did not create a demonstrated edge.
3. **Risk denominator rebases:** AI_Brain._manage_open_trades passes the current broker SL as both initial_sl and current_sl (recovered source-line marker 475). After break-even, a tiny remaining entry-to-stop distance can turn an ordinary move into an enormous computed R and trigger partial closing. The constant-initial-risk variant was tested separately and did not qualify.
4. **Fitness is not win probability.** Highest-fitness selection can choose a strategy whose entry refuses to trade. Tested that selector, first-actionable routing, and a causal history-weighted router. Learning does not rescue this screen.
5. **Timing and broker units matter.** Original application reads a forming M5 candle and monitors positions about every ten seconds. This screen deliberately uses closed candles and minute-open management. Original 30/60 spread-point thresholds are broker-specific; .001 dataset point units are explicit, but the Genesis broker profile is unverified.
6. **10% packaged base risk is unsuitable as an assumed Atlas configuration.** Research used fixed .02 lot and one position per isolated test. This is not approval of either sizing scheme for a real account.

## Data coverage correction

The raw 2025 M1 snapshot jumps from September 12 20:47 UTC to October 15 04:59 UTC. There is no observed tradable price path within that interval. Unsegmented RangeTrading and SwingTrend each carry a basket across it and record approximately -$1,055 and -$1,061 at reopening. Arithmetic correctness cannot certify that those stops would actually have filled there.

Original outputs are retained, but the main table uses independent samples before and after this gap. Each sample ends flat through retrospective boundary liquidation, learning history resets, and post-gap entries wait for 300 newly completed M5 bars. This uniform coverage rule also changes which later trades can occur; it is not merely deletion of two losses. It is a data-quality sensitivity, not a strategy that could anticipate missing data or a continuous funded-account simulation. Separate segment metrics are recorded in each result.

No interpolation, invented ticks or forward-filled prices were used. Minute bars cannot resolve the exact within-minute path: when both initial SL and TP can be touched, the screen uses stop first. The additional data gap prevents any claim of a complete observed 2025 account path.

## Assumptions and limits

- XAUUSD only; M5 from five contiguous aligned M1 bars; 300-bar signal history; next exact minute opening entry; one .02-lot position, 100 oz contract per lot, .01-lot partial closes.
- Costs: observed historical spread fields converted at .001 per point, $0.26 spread fallback, $0.02 market/stop slippage, $3.50 round-trip commission per lot ($0.07 at .02 lot), existing project funding model. Current funding assumptions applied to historical years are approximate; actual Atlas financing/contract terms are not verified.
- Includes partial closes, break-even, profit locks, trailing stops and invalid-side modification rejection in management variants. No verified broker minimum stop/freeze distances or ten-second/tick path.
- Does not reproduce full Genesis confidence, MTF confirmation, cooldown, news/session and account-risk gates, or every learning interaction. Running seven pure rules is not complete application parity.
- No claim that these strategies pass Atlas rules or produce eligible $100 payouts. Payout modeling cannot validate a nonexistent edge, and the missing interval prevents a continuous account-path claim. No evaluation account exists for broker-specification verification.

## Metrics and statistical interpretation

Per-year files include trade count, net P&L, win rate, expectancy, PF, closed-balance drawdown, minute-open sampled liquidation drawdown, Sortino, Omega, Calmar, recovery factor, skew and kurtosis. Trade-based ratios are labeled as such; Omega at zero equals PF here. Segment-level annualized fields use the helper's nominal one-year convention and must not be interpreted as actual segment-duration annualization.

The summary also runs best/worst-trade ablation, 1,000 trade-order permutations, 5,000 month-block bootstrap totals, Bonferroni correction and deflated Sharpe with expected-maximum-Sharpe sensitivities for 36 / 640 / 1,000 / 2,000 trials. These are diagnostics, not a calibrated chance of future profit. The total historical research trial count is unknown; all configurations share much of their information. Missing calendar dates encoded as zero cash do not demonstrate zero exposure. Pooling separated years/segments does not create a continuous equity track record.

For Momentum static, pooled across these observed samples: PF 1.008, net +$89.97, wins 29.70%. Removing the best single trade changes net to -$38.06; removing the best three changes it to -$266.98. Its conditional month-bootstrap 95% interval is about -$1,566 to +$2,025; the within-family Bonferroni value is 1.0. This is weak, fragile evidence. Trade permutations preserve final cash by construction: a zero frequency of negative final balances in that diagnostic is not a zero probability of future loss.

## Next work

Keep these rules in the research archive. Do not merge them into live trading or buy an evaluation based on this screen. To revisit Genesis, first obtain coherent bid/ask history and its actual broker settings, resolve forming-versus-closed-candle execution and the confirmed wiring defects, and replay the full documented gates without selecting parameters on these same outcomes. A frozen candidate would then need genuinely later data, execution stress, risk sizing, Atlas-rule and payout-path validation. The broader XAUUSD research objective remains unmet.

## Reproducibility and artifacts

- Protocol and explicit later amendments: ../../registry/PREREG_Genesis_2026-11-11.md
- Original exports: {year}.signals.jsonl.gz with manifests and SHA-256 hashes.
- Backtests: {year}.backtest.json, .repair.json, .frictionless.json; 2025.backtest.segments.json and 2025.backtest.repair.segments.json.
- Summaries: summary_coverage.json (preferred coverage sensitivity), summary.json (original unsegmented); daily_candidate_returns*.csv.
- Management parity: manager_parity.json. Independent audits: independent_audit.json and independent_audit_segments.json.
- Baseline runner source preserved under engine_versions; manifests record the actual runner hash. Research source: scripts/research/genesis_*.py and scripts/validation/genesis_*.py.

Commands from the repository root:

```powershell
.\venv\Scripts\python.exe -m scripts.research.genesis_backtest 2025 --coverage-segments
.\venv\Scripts\python.exe -m scripts.research.genesis_backtest 2025 --reversal-repair --coverage-segments
.\venv\Scripts\python.exe -m scripts.validation.genesis_independent_audit --segments-only
.\venv\Scripts\python.exe -m scripts.validation.genesis_summary --coverage-segments
.\venv\Scripts\python.exe -m pytest -m "not live"
```
