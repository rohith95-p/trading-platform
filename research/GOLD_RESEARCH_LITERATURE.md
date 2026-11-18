# Gold research literature — bounded primary-source review

Review date: 18 November 2026. This is a mechanism and validation review, not evidence that any local strategy is profitable. Eleven selected primary records, their 13 requested metadata fields, reading depth and limitations are in [literature.json](results/finalization_2026-11-18/literature.json). No strategy evaluation or November holdout access was performed for this review.

## Search and inclusion method

Search families covered gold intraday stylized facts, spot/futures price discovery, announcement surprises, realized-volatility forecasting, commodity trend controls, selection bias, and point-in-time macro data. Public publisher, author, university, exchange and institutional sources were preferred. Search results and the existing `external_strategy_database.md` supplied leads; a headline, abstract or external performance claim was not accepted as replicated alpha. Date of an uploaded/crawled PDF was not substituted for its manuscript/publication date.

The resulting inventory is deliberately bounded. Google/Scholar-style indexing, university repositories, AQR, World Gold Council, CME and author papers were searched. This pass did not exhaust SSRN, arXiv, NBER, RePEc, Man AHL, Winton, MQL5, QuantConnect or public discussion communities. Those venues are useful for additional leads; their absence is an explicit coverage gap rather than a claim that no relevant research exists. Previous retail/forum/code surveys remain in the external database and original experiment reports, with their unverified status retained.

## Evidence map

| ID | Primary record | Reading depth | Role in this project |
|---|---|---|---|
| L01 | [Batten et al., 2017](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0174232) | Publisher methods/results inspected | Conditional session and magnitude baselines |
| L02 | [Hauptfleisch, Putnins & Lucey, 2016](https://www.pure.ed.ac.uk/ws/files/82358957/GoldILS_JFutMkt_Forthcoming.pdf) | University manuscript data/method/results inspected | Cross-venue information versus quote noise |
| L03 | [Elder, Miao & Ramchander, 2012](https://mountainscholar.org/bitstream/10217/206884/1/Miao_H_BanFin_2012.pdf) | Manuscript regressions/results/conclusions inspected | Announcement timing and executable information |
| L04 | [Corsi, 2009](https://statmath.wu.ac.at/~hauser/LVs/FinEtricsQF/References/Corsi2009JFinEtrics_LMmodelRealizedVola.pdf) | Model and conclusions inspected | Parsimonious volatility forecasting control |
| L05 | [Moskowitz, Ooi & Pedersen original data](https://www.aqr.com/Insights/Datasets/Time-Series-Momentum-Original-Paper-Data) | Dataset page; full paper not reread | Trend-exposure control, horizon mismatch warning |
| L06 | [Bailey & Lopez de Prado, 2014](https://davidhbailey.com/dhbpapers/deflated-sharpe.pdf) | Equations/examples/conclusion inspected | Search-adjusted Sharpe evidence |
| L07 | [Bailey et al., 2015 manuscript](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf) | CSCV procedure and limitations inspected | Selection-rank stability |
| L08 | [World Gold Council GRAM](https://www.gold.org/goldhub/tools/gold-return-attribution-model) | Landing page only; methodology PDF403 | Economic factor taxonomy, not forecast proof |
| L09 | [FRED/ALFRED real-time periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html) | Documentation read | Point-in-time macro reconstruction |
| L10 | [CME Gold specifications](https://www.cmegroup.com/markets/metals/precious/gold-futures.contractSpecs.html) | Specification/overview inspected | Separate futures market from CFD assumptions |
| L11 | [Acosta et al., revised August2026](https://www.frbsf.org/wp-content/uploads/wp2025-30.pdf) | Introduction/methodology inspected | Public event calendar and availability discipline |

Full-text accessibility is different from a line-by-line reading or an independent reproduction. Neither is claimed where it was not done. The original licensed samples were not obtained. Links allow verification but are mutable; this inventory is not a frozen archive of all source contents.

## Synthesis: what is worth measuring

The following are **our proposed inferences and research designs**, not paper results or approved trading rules. They require a committed pre-registration before evaluation under repository policy.

1. **Conditional magnitude before direction.** Compare a lagged daily/weekly/monthly realized-variance forecast against session-only and recent-variance controls, with chronological fit/predict cycles. Score QLIKE and squared log-variance error. Improved risk prediction is useful for exposure and abstention; it supplies no directional edge by itself.
2. **Information arrival after release, not clairvoyance.** A scheduled event indicator can be known in advance; the surprise cannot. Inspect delayed post-release outcomes only after the chosen information/fill latency and funded news window. Match non-event observations on session and pre-event volatility. Check costs and negative controls before defining entries. The prior CPI/NFP fade test is already explored; a new hypothesis must differ mechanically and be counted as another trial.
3. **Cross-venue confirmation only when observable.** A spot bar does not reveal futures aggressor flow. Defer an order-flow strategy until synchronized accessible GC quotes/trades exist. With current free data, study source disagreement as a quality/execution diagnostic rather than inventing a futures signal.
4. **Regime-aware abstention must beat matched abstention.** Require a forecast filter to improve net expectancy against an equal-frequency control, not merely improve PF by deleting losing observations post hoc. Freeze the gate using development data and report omitted periods, capital downtime and trade count.
5. **Macro disagreement is a feature-availability problem first.** Align dollar/yield series by actual publication time and vintage. Compare lagged gold-only models with nested macro additions, with identical decision times. Current revised daily data or same-day closes cannot be assumed available earlier in the trading day.

## Corrections to earlier reasoning

The existing external database correctly labels its external performance numbers unverified, but several interpretations need restraint. A wide stop does not create a signal or solve insufficient capital; it can increase minimum-lot account risk. Session periodicity does not establish a directional trade. An attribution regression is not an ex-ante forecast. A futures discovery lead is not executable retail arbitrage. A strategy advertised on a different instrument/timeframe is not an independent XAUUSD replication. Repeatedly testing the same period changes its evidence status even if each new variant has a different name.

## Validation implications

Keep a complete experiment ledger with unsuccessful trials and aligned return vectors. The number of effective historical searches is uncertain, so existing DSR values must remain sensitivity analyses. CSCV/PBO needs the full comparable candidate matrix, not only winners; its estimated selection instability is not the probability of tomorrow's loss. Neither DSR nor PBO repairs future-information leakage or incorrect fills. Chronological tests, execution audits and prospective demo reconciliation remain separate requirements.

A useful new mechanism may fail the trading test. The appropriate next output is a small falsifiable experiment with costs and controls, rather than another catalog of promising strategy names.

## Executed macro mechanism follow-up

The original project FOMC normalized-shock propagation experiment was preregistered and executed through BacktestEngine with strict minute coverage. Public calendar metadata was used; retrospective financial surprise columns were excluded. Positive small historical samples failed uncertainty and control gates. See [FOMC_SHOCK_PROPAGATION.md](FOMC_SHOCK_PROPAGATION.md), including an independent fill/accounting audit and an explicitly preserved invalid bootstrap run. The literature prompted a falsifiable experiment, not a profitability endorsement.
