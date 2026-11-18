# CPI surprise continuation on XAUUSD, 18 November 2026

Decision: retire the fixed rule. The initial primary-source check collected 79 dated weekly survey forecasts from 82 target releases. The missing releases are 10 August 2023, 14 November 2023 and 10 April 2026. Weekly consensus can change before the release. The PDF issue date and its modification metadata predate the release, but a historical public delivery timestamp is unavailable. PDF copies and SHA-256 values are in research/data/cpi_consensus_pdfs and research/events/us_headline_cpi_consensus_coverage.csv. Actuals are reconstructed from the Philadelphia Fed first-release growth rate with 100 * ((1 + annualized / 100) ** (1 / 12) - 1), rounded to one decimal. The BLS URLs identify releases. Scheduled times use the Eastern release clock.

Primary preregistration e3fdbca. Forty-seven directional release windows lacked recorded spread inputs in the master and three lacked continuous M1. Twenty-eight releases tied, three lacked forecasts. One fill earned $14.15. Removing it leaves zero.

Spread sensitivity preregistration 4901476. Identical rule, with minute-opening Exness Standard quote spreads on the master bid series for both the spread filter and execution. This is a hybrid simulation. Two historical windows may have different prices across venues even at the same time. Filters and stops use only prior data when deciding entry. Run from project root with the project Python, first -m scripts.research.cpi_survey_continuation then -m scripts.research.cpi_survey_spread_proxy. Detailed ledgers are in the two matching registry JSON files. The metrics file covers both baselines, controls and stressed costs.

| Release years | Trades | Win rate | PF | Net USD |
| --- | ---: | ---: | ---: | ---: |
| 2019–21 | 12 | 50.0% | 0.642 | -17.07 |
| 2022–24 | 18 | 33.3% | 0.462 | -92.08 |
| Jan–Oct 2026 | 1 | 1/1 | undefined | 14.15 |
| Combined | 31 | 41.9% | 0.566 | -95.00 |

Removing the best trade gives -$116.80, stress net is -$105.55, closed-trade drawdown $128.22 and expectancy -$3.06 per fill. Mean excess over the preceding eligible non-release weekday is -$0.43 per jointly observable opportunity (45 pairs, including filter rejections). The project high-impact calendar has incomplete coverage of other announcements in early years. These controls exclude known releases. A one-trade 2026 sample cannot estimate repeatability. No trial-family Sharpe variance was established for a selection-adjusted DSR. Account replay was conditional on passing the edge screen, so cash per attempt, breach rate and time to first payout are unmeasured. No holdout use.
