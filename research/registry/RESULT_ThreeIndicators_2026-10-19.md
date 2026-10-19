# Result — three TradingView indicator strategies x fixed SL/TP sets (#646-#654)

Run once as frozen (prereg 2703b1b, simulator and mechanics tests committed before the run). Raw: three_indicators_result_2026-10-19.json. Broker M15 (real spreads), DEV 2022-08..2024-12, VALIDATE 2025-01..2026-06, HOLDOUT 2026-07..2026-10-13. These strategies trade often, so the samples are large (thousands of trades), which makes the verdict unusually clear.

## All nine trials (DEV+VALIDATE, net of costs; PF / expectancy in R)
| Strategy | SL/TP (xATR) | Trades | PF | Expectancy | Net R | Max DD | 2x-cost stress expectancy |
|---|---|---|---|---|---|---|---|
| A 20 EMA | 1.0 / 1.5 | 3,731 | 0.84 | -0.100 | -374 | 388 R | -0.377 |
| A 20 EMA | 1.5 / 3.0 | 2,767 | 0.90 | -0.064 | -178 | 206 R | -0.258 |
| A 20 EMA | **2.0 / 2.0 (carried)** | 2,599 | 0.90 | -0.051 | -133 | 149 R | -0.187 |
| B UT Bot | 1.0 / 1.5 | 7,398 | 0.91 | -0.056 | -412 | 446 R | -0.352 |
| B UT Bot | 1.5 / 3.0 | 4,548 | 0.88 | -0.078 | -353 | 367 R | -0.263 |
| B UT Bot | **2.0 / 2.0 (carried)** | 4,645 | 0.91 | -0.043 | -202 | 214 R | -0.194 |
| C QQE | 1.0 / 1.5 | 5,020 | 0.87 | -0.082 | -410 | 420 R | -0.370 |
| C QQE | **1.5 / 3.0 (carried)** | 3,717 | 0.93 | -0.047 | -173 | 194 R | -0.238 |
| C QQE | 2.0 / 2.0 | 3,785 | 0.93 | -0.034 | -128 | 165 R | -0.171 |
HOLDOUT (about 200-565 trades each): PF 0.92-1.02 across all nine, i.e. break-even to slightly negative.

## Verdict: all three CLOSED
- Every one of the nine configurations loses money after costs in DEV and in VALIDATE; no carried pair passes any of: PF > 1.25, positive expectancy, drawdown cap, stress, DSR, placebo.
- **Placebo:** random entries with the same exits and costs average about -0.02 R (p95 -0.015 to -0.020). The three indicator systems average -0.034 to -0.051 R: no better than random, if anything worse (placebo p = 0.36-0.58). The indicators carry no timing information on this data; what is left is the cost of crossing the spread.
- **22-year check (flat $0.30 spread assumed; descriptive):** negative in all three eras for all three strategies (PF 0.64-0.67 in 2004-2010, 0.76-0.78 in 2011-2018, 0.82-0.84 in 2019-2026). It never worked in any regime; it just loses less when gold is more volatile relative to the spread.
- Wider stops/targets lose less (the cost is a smaller share of each trade) but remain negative. Choosing "the best SL/TP" cannot rescue a signal with no information: that is exactly what the placebo shows.

No forward test, no further SL/TP variants. SL/TP placement cannot create an edge that the entry signal does not have.
