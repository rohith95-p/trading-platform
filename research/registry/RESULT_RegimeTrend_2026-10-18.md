# Result — Regime-conditional trend (trial #640): CLOSED

Run once, exactly as frozen in `PREREG_RegimeTrend_2026-10-18.md` (commit d570fc4). Simulator `scripts/research/regime_trend_sim.py`; raw output `regime_trend_result_2026-10-18.json`. Event calendar: `research/events/` (220 events from official BLS/BEA/Fed pages).

| Period | Trades | Win % | PF | Expectancy | Net | Max DD | DSR (N=640) |
|---|---|---|---|---|---|---|---|
| DEV 2022-08..2024-12 | 68 | 29.4 | **0.79** | **-0.149R** | -10.1R | 15.4R | 0.000 |
| VALIDATE 2025-01..2026-06 | 54 | 42.6 | 1.46 | +0.265R | +14.3R | 9.2R | 0.032 |
| HOLDOUT 2026-07..10-13 | 2 | 50 | n/a | n/a | +1.0R | 1.0R | n/a |
| DEV+VALIDATE | 122 | 35.2 | 1.05 | +0.034R | +4.2R | 18.0R | 0.002 |

Stress (spread x2, +$0.30 slippage/fill): DEV PF 0.47, VALIDATE 1.37, DEV+VALIDATE PF 0.80.

Decision per the frozen rule: **fails the DEV gate (PF < 1.0, negative expectancy) -> hypothesis closed, no retuning.**
Other observations (not used to rescue it): validation profit is concentrated (84% of net R in one quarter, 56% in one month) and 100% long in gold's rally; DSR far below 0.95 in every window; the rule is so selective the 3.5-month holdout produced only 2 trades, so the holdout gate cannot be evaluated; event-day vs normal-day PF in validation 0.53 vs 1.73 (9 vs 45 trades; small samples).
