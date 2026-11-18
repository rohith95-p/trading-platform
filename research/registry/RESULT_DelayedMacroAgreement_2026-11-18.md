# Delayed dollar and yield agreement failed its spot-market test

Protocol `2a7d847` fixed the signal, trading hours, costs and rejection criteria before this test. A signal required agreement between changes in the dollar and the nominal ten-year yield. The second most recent macro row strictly before each New York session provided the signal. A missing 15-minute interval excluded the entire session. Across the archive, 472 candidate session starts lacked a complete grid.

| Spot XAUUSD session cohort | Observations | Long signals | Estimated net move per ounce | At double costs |
| --- | ---: | ---: | ---: | ---: |
| 2005–2013 | 922 | 492 | $0.05575 | −$0.27925 |
| 2014–2020 | 982 | 502 | −$0.41958 | −$0.75458 |
| 2021–September 3, 2026 | 851 | 396 | $0.42858 | $0.14440 |
| Combined | 2,755 | 1,390 | $0.00149 | −$0.31782 |

The middle era lost money at ordinary costs. The pooled advantage over always buying the same sessions was $0.54768 per ounce, with a monthly bootstrap 95% interval of −$0.14664 to $1.36392. Both findings fail the frozen promotion rule. The daily proxy relationship did not establish a persistent tradable advantage over the tested spot hours. Price endpoints, reconstructed spreads and assumed friction support a feasibility estimate. Account P&L, drawdown and payouts would require a path simulation.

Reproduce with `python -m scripts.research.delayed_macro_agreement`. The full result, matched controls and input hashes are in `research/results/finalization_2026-11-18/delayed_macro_agreement.json`.
