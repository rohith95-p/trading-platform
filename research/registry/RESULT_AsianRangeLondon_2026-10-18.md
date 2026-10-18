# Result — Asian-range / London continuation (trial #641)

Run once, exactly as frozen in PREREG_AsianRangeLondon_2026-10-18.md (prereg commit a023252, simulator commit 2820ddb). Raw output: asian_london_result_2026-10-18.json.

| Period | Trades | Win % | PF | Expectancy | Net R | Max DD | Stress (2x spread + $0.30) PF |
|---|---|---|---|---|---|---|---|
| DEV 2022-08..2024-12 | 19 | 32 | **0.79** | -0.14 R | -2.7 | 4.0 R | 0.64 |
| VALIDATE 2025-01..2026-06 | 13 | 46 | 1.63 | +0.32 R | +4.1 | 2.6 R | 1.44 |
| HOLDOUT 2026-07..2026-10-13 | 1 | 0 | 0.00 | -1.0 R | -1.0 | 1.0 R | 0.00 |
| DEV+VALIDATE | 32 | 38 | 1.07 | +0.04 R | +1.4 | 5.0 R | **0.90** (net -2.1 R) |

## Verdict: CLOSED (falsified at the DEV gate; sample also inconclusive)
- DEV PF 0.79 < the 1.15 gate and expectancy is negative -> fail. No parameter rescue.
- Only 33 trades in four years (the stacked filters leave about one trade every six weeks): far below the 100-trade minimum, so even a pass would have been "inconclusive". DSR (N=641) is ~0.00-0.01 everywhere.
- The one good period (VALIDATE, 13 trades) is 2025-26, the gold rally regime, the same pattern as earlier trials. 2024 PF 0.57, 2022-23 about 1.0. With realistic stress the combined result is negative.
- 78% longs; every trade is in the London window by construction.

Nothing here supports a forward test. Trial #641 is closed; the next hypothesis needs a new pre-registration.
