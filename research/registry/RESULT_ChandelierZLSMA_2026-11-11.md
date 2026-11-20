# Chandelier Exit + ZLSMA: XAUUSD transfer screen

2026-11-11. Result: rejected for the current deployment shortlist. None of four fixed configurations meets net PF1.3 in the three inspected years. The additional 2025 bid/ask test also loses for every configuration. The broader search for a verified XAUUSD edge remains active.

## Source and specification

- Public original Pine: https://github.com/geraked/tradingview/blob/7919ccb7d4400109cb54837f9d198baf61fcef05/strategies/CEZLSMA.pine
- The source links https://www.youtube.com/watch?v=2U5VTWBBK8U . Direct video fetch failed; code was read, the video was not watched.
- The source advertises PF5.392 and 457 trades for approximately ten days of EURJPY M1. It does not establish a gold edge. TradingView documents the synthetic-price fill problem: https://www.tradingview.com/support/solutions/43000481029-strategy-produces-unrealistic-results-on-non-standard-chart-types-heikin-ashi-renko-etc/
- Frozen source, commit, SHA-256 and MIT license: research/sources/chandelier_zlsma/. Protocol: research/registry/PREREG_ChandelierZLSMA_2026-11-11.md. No parameter optimization.
- Source defaults: CE ATR1, multiplier2, ZLSMA50, flips filtered by close versus ZLSMA. Exit on opposite ZLSMA cross/reversal or the submitted CE stop. Source stop is submitted in entry-signal blocks; it is not automatically moved every bar.
- Four disclosed variants: M1/M5 with Heikin-Ashi signals, plus ordinary-candle signal ablations. Closed-bar decisions, subsequent actual minute-opening fills, fixed .02lot, no pyramiding. Signal candles never determine execution prices.

## Net profit factor

| Variant | 2013 old snapshot | 2018 old snapshot | 2025 old covered samples | 2025 Dukascopy bid/ask |
|---|---:|---:|---:|---:|
| M1 HA | 0.463 | 0.244 | 0.718 | 0.529 |
| M1 ordinary | 0.427 | 0.210 | 0.694 | 0.496 |
| M5 HA | 0.754 | 0.450 | 0.947 | 0.783 |
| M5 ordinary | 0.648 | 0.447 | 0.904 | 0.773 |

The old 2025 source has a month-long gap. Those tests use separate covered samples, fresh post-gap warmup and retrospective sample-end liquidation; they are not continuous account simulations. The new provider covers that interval, and is a separate complete-date-range snapshot, not a splice into old history. Both source versions and all outcomes are retained.

## Observed bid/ask 2025 details

| Variant | Trades | Win rate | Net at .02lot | Immediate opening stops |
|---|---:|---:|---:|---:|
| M1 HA | 14208 | 28.4% | $-21,356.90 | 73 |
| M1 ordinary | 19325 | 24.9% | $-29,059.47 | 182 |
| M5 HA | 2699 | 35.9% | $-3,492.29 | 1 |
| M5 ordinary | 3401 | 33.5% | $-4,291.27 | 3 |

**These cash totals are diagnostic fixed-lot trade distributions.** Tests continue to collect signals even after losses exceed a $5,000 starting balance; such a path is not financeable as an account. No result here establishes live survival, daily-loss compliance or payouts.

Execution uses observed bid OHLC and ask OHLC in the new snapshot, including ask highs for short stop triggers. Costs additionally include $0.02 adverse market/stop slippage, $0.07 round-trip commission per .02lot, and the project funding assumptions. They are not verified Atlas settings. The earlier snapshots use recorded spread/fallback costs and lack separate ask extrema.

Stop/order sequencing is an explicit approximation: an existing resting stop at an opening gap executes before newly actionable closed-bar market orders. A newly submitted stop already beyond the opening liquidation quote closes immediately and is counted instead of deleting the trade. Broker rejection/latency rules and full TradingView broker-emulator parity are not certified.

## Free data milestone

- Retrieved 369,312 matched bid/ask minute observations spanning December2024 warmup through end2025 from Dukascopy chart data, in26 cached pages. Exact request URLs and response hashes are recorded.
- No unmatched bid/ask timestamps, no non-finite prices, no invalid OHLC, no off-minute timestamps, no duplicate times and no crossed bid/ask OHLC extrema were found by the fetcher.
- Median observed opening spread: $0.58. This is one provider, not proof of Atlas pricing.
- Longest detected gap exceeds three days (approximately3.04 days). Calendar/session completeness and every missing minute have not been independently certified. Timestamp alignment is not tick-level completeness.
- Raw tick cross-check request returned HTTP429 Too Many Requests. No repeated requests were made. tick_crosscheck.json records status not_verified. Thus chart aggregation has not been independently reconciled to raw ticks.
- Snapshot: research/data/dukascopy_2025/XAUUSD_M1_bidask.npy. Manifest: research/data/dukascopy_2025/manifest.json. No older research snapshot was overwritten.

## Verification and metrics

- Four meaningful focused tests: LSMA against independent polynomial regression; Heikin-Ashi/ordinary prefix causality; real-quote entry/gap fills despite synthetic signal prices; short stops triggered by actual ask extremes.
- Final non-live suite:560 tests passed. The quote/cash auditor separately checks entries, cash/funding, aggregate totals and exit prices/touches. It does not independently reconstruct full indicator state or historical first-hit stops with every modification.
- Per-case outputs include PF, win rate, expectancy, downside-RMS Sortino, Omega, Calmar, recovery, closed-balance drawdown, segment minute-open liquidation drawdown and nonpositive-balance flags. Annualization of combined segments is nominal, not a continuous return track record.
- Best/worst-trade ablation and1,000 trade-order permutations are stored. Daily fixed-$5,000 cash diagnostics include deflated Sharpe, expected maximum SR and4/640/1,000/2,000-trial sensitivities, plus within-family Bonferroni bootstrap values. Missing source dates have zero realized cash for aggregation; they do not establish zero exposure. Disjoint years and incomplete source paths prevent treating these as forward significance or profit-probability estimates.

## Next research action

Use the separate bid/ask snapshot for execution validation of subsequent frozen candidates. The newly located public XAUUSD breakout/retest repository was also checked: its own frozen-headline out-of-sample grid reports31 trades, PF0.814 and negative expectancy for001A at2R/0.25% risk. This is an external author-reported result, not our reproduction. It does not supply a proven replacement; preserve it as another rejected lead while retaining the independently useful data-endpoint discovery. Reports and exact commit are frozen under research/sources/xauusd_001A/. Source: https://github.com/anirudhatalmale6-alt/xauusd-strategy-backtest . Continue source triage for explicit causal rules and economic rationale, then preregister candidates before outcome inspection. A newly discovered source is not a new untouched test set.

Artifacts: research/registry/chandelier_zlsma.json, chandelier_zlsma_bidask2025.json, chandelier_zlsma_audit.json. Runners: scripts/research/chandelier_zlsma.py, scripts/research/dukascopy_chart.py, scripts/validation/chandelier_audit.py.
