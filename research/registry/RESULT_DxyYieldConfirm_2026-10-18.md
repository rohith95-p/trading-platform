# Result — DXY / yield confirmation of gold trend (trial #645, stage 1)

Run once as frozen (prereg 2ae6450, script committed before the run). Daily master series 2000-08-30..2026-09-03 (6,527 days; gold futures, DXY, US 10-year yield). Raw: dxy_yield_result_2026-10-18.json.

## Primary test: does confirmation add to gold's own trend?
Mean next-day signed return (position = trend direction, return in %):
- Confirmed days (C, n = 2,499): +0.0157% per day. Unconfirmed trend days (U, n = 3,928): -0.0037% per day.
- Difference +0.0194%/day, Welch t = 0.68, one-sided **p = 0.25** -> **FAIL** (needed p < 0.05).

## Stability by era (mean next-day signed return, C vs U)
| Era | C | U | Confirmed strategy (net ann. return, Sharpe) | Plain SMA100 trend (net ann. return, Sharpe) |
|---|---|---|---|---|
| 2000-2010 | -0.032% | -0.009% | -4.8%, -0.33 | -7.0%, -0.28 |
| 2011-2018 | +0.056% | -0.034% | +4.0%, 0.46 | -2.3%, -0.06 |
| 2019-2026 | +0.047% | +0.035% | +3.3%, 0.37 | +8.2%, 0.52 |
- C beats U in only 2 of 3 eras (requirement: all three), and C itself is negative in 2000-2010. Over the full sample the confirmed strategy earns about +0.3% a year (Sharpe 0.08), the plain trend rule about -1.2% (Sharpe 0.03). Neither is a usable return.
- In the rally era (2019-2026) the plain gold-trend rule beats the "confirmed" version (+8.2% vs +3.3% a year): confirmation just kept the strategy out of the market during gold's biggest run.
- Drawdown figures are computed as peak/trough - 1 on a full-leverage daily equity curve and exceed 100% in the weak eras; they are comparable between arms but not realistic for a sized strategy.

## Verdict: CLOSED
The primary test fails and the era stability fails. The dollar and the 10-year yield add no reliable information to gold's own trend on 26 years of daily data. Stage 2 (intraday H4-pullback/M15 version) is not built. No variants (other SMA lengths or yield windows) are allowed.
