# Native MT5 XAUUSD results without Luna | 2022–2024

Both portfolios failed to produce a modeled payout in all three January-start attempts. Both lost money during the 2022 and 2023 evaluation windows, and neither reached the $150 target. In 2024 both passed on May 2, started fresh funded accounts on May 3, and finished active after losing money. No real cash was paid.

Full-window MT5 evaluation P&L includes simulated trades after an evaluation pass or a modeled breach. Funded P&L comes from a separate native tester account. Cash after fees counts $5 for each evaluation and $78 for each funded activation. Time to first payout was never reached.

| Year | Book and native evaluation report | Eval P&L | Eval PF | Wins / trades | Eval max DD | Atlas evaluation | Funded P&L | Funded PF | Funded account at cutoff | Modeled payout | Cash after fees |
|---|---|---:|---:|---:|---:|---|---:|---:|---|---:|---:|
| 2022 | [2 strategies](2022_portfolio_mask5_phase_split_early.htm) | -212.96 | 0.69 | 30 / 107 | 4.89% | [active](2022_portfolio_mask5_phase_split_early_audit.json) | — | — | — | 0 | -5 |
| 2022 | [3 strategies](2022_portfolio_phase_split_early.htm) | -240.23 | 0.66 | 30 / 110 | 5.43% | [active](2022_portfolio_phase_split_early_audit.json) | — | — | — | 0 | -5 |
| 2022 | [Asian Breakout](2022_breakout_phase_split_early.htm) | -192.27 | 0.51 | 12 / 48 | 4.56% | [inactivity breach 2022-02-20](2022_breakout_phase_split_early_audit.json) | — | — | — | 0 | -5 |
| 2022 | [Asian Range Filtered](2022_filtered_phase_split_early.htm) | -111.91 | 0.61 | 14 / 45 | 3.06% | [inactivity breach 2022-02-20](2022_filtered_phase_split_early_audit.json) | — | — | — | 0 | -5 |
| 2022 | [London Momentum Tight](2022_london_phase_split_early.htm) | -103.96 | 0.75 | 17 / 65 | 3.25% | [active](2022_london_phase_split_early_audit.json) | — | — | — | 0 | -5 |
| 2023 | [2 strategies](2023_portfolio_mask5_phase_split_early.htm) | -108.26 | 0.81 | 35 / 107 | 4.34% | [active](2023_portfolio_mask5_phase_split_early_audit.json) | — | — | — | 0 | -5 |
| 2023 | [3 strategies](2023_portfolio_phase_split_early.htm) | -111.18 | 0.82 | 37 / 116 | 4.76% | [active](2023_portfolio_phase_split_early_audit.json) | — | — | — | 0 | -5 |
| 2023 | [Asian Breakout](2023_breakout_phase_split_early.htm) | -61.46 | 0.82 | 16 / 48 | 3.31% | [inactivity breach 2023-09-02](2023_breakout_phase_split_early_audit.json) | — | — | — | 0 | -5 |
| 2023 | [Asian Range Filtered](2023_filtered_phase_split_early.htm) | -93.48 | 0.60 | 13 / 38 | 2.65% | [inactivity breach 2023-09-02](2023_filtered_phase_split_early_audit.json) | — | — | — | 0 | -5 |
| 2023 | [London Momentum Tight](2023_london_phase_split_early.htm) | -22.58 | 0.93 | 22 / 70 | 2.12% | [inactivity breach 2023-12-13](2023_london_phase_split_early_audit.json) | — | — | — | 0 | -5 |
| 2024 | [2 strategies](2024_portfolio_mask5_phase_split_early.htm) | -5.17 | 0.99 | 40 / 115 | 6.22% | [passed 2024-05-02](2024_portfolio_mask5_phase_split_early_audit.json) | [-120.14](2024_portfolio_funded_mask5_phase_split_early.htm) | 0.63 | [active, USD 4,869.59](2024_portfolio_funded_mask5_phase_split_early_audit.json) | 0 | -83 |
| 2024 | [3 strategies](2024_portfolio_phase_split_early.htm) | +100.61 | 1.12 | 46 / 122 | 4.31% | [passed 2024-05-02](2024_portfolio_phase_split_early_audit.json) | [-73.95](2024_portfolio_funded_phase_split_early.htm) | 0.78 | [active, USD 4,915.78](2024_portfolio_funded_phase_split_early_audit.json) | 0 | -83 |
| 2024 | [Asian Breakout](2024_breakout_phase_split_early.htm) | +217.57 | 1.58 | 22 / 48 | 2.53% | [inactivity breach 2024-02-28](2024_breakout_phase_split_early_audit.json) | — | — | — | 0 | -5 |
| 2024 | [Asian Range Filtered](2024_filtered_phase_split_early.htm) | +36.21 | 1.12 | 16 / 41 | 2.26% | [inactivity breach 2024-02-28](2024_filtered_phase_split_early_audit.json) | — | — | — | 0 | -5 |
| 2024 | [London Momentum Tight](2024_london_phase_split_early.htm) | -41.38 | 0.92 | 24 / 74 | 4.78% | [active](2024_london_phase_split_early_audit.json) | — | — | — | 0 | -5 |

## Data and reproducibility

Native calendar-run tick counts matched the Exness archive exactly for every strategy. The yearly counts were 27,539,454 in 2022, 26,113,921 in 2023, and 39,715,935 in 2024. MT5 labeled 2022 history 99% real ticks and both later years 100%. The native report retains that distinction. The first archived 2022 quote is January 2 at 23:05 UTC. The new importer supplied September–December 2021 M1 warmup and the January–October 2022 ticks missing from the existing custom MT5 symbol. Native fill records were reconciled against each HTML report.

The two retained signals are Asian Range Filtered and London Momentum Tight. The three-strategy version adds Asian Breakout. Each calendar-year evaluation used 0.02 lots at 1:100. Fresh funded runs used the existing 0.01-lot guard at 1:50. Audit JSON contains the quote-based Atlas events and standardized ECN sensitivity. Historical Atlas contract terms, trading costs and the complete all-currency news calendar remain unverified. This is historical sensitivity on previously explored years.

To reproduce, use the same isolated Windows MT5 tester, compile the retained EA from source, and verify the matching custom-symbol Exness archive. For 2022, prepare the import binaries with `python -m scripts.research.retained_early_archive <terminal MQL5/Files/RetainedEarly directory>` then run the importer in the isolated terminal. Run one year at a time per terminal with `python -m scripts.research.retained_early_years <2022|2023|2024> --terminal <terminal directory>`.

[Run summary CSV](summary.csv) · [Frozen protocol](../../registry/PREREG_RetainedPortfoliosEarlyYears_2026-11-20.md) · [Archive importer](../../mt5_retained/ImportEarlyQuotes.mq5) · [2025–2026 comparison](../guarded_retained_mt5/payout_decision.md)
