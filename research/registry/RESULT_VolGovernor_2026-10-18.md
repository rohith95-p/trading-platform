# Result — volatility-regime governor replay (prereg 6eb6200; module/script committed before the run)

Run once. One infrastructure fix after the first launch (a missing `sys.path` entry; the script crashed on import before computing anything). Raw: vol_governor_result_2026-10-18.json. Placebo = same counts of blocked / 0.5x / 1.0x trades assigned to random trades, 5,000 shuffles.

| Replay set | Trades | Baseline net / max DD / Calmar | Governed net / max DD / Calmar | Placebo Calmar p95 | Beats baseline | Beats placebo |
|---|---|---|---|---|---|---|
| FvgGold B/path ($, 0.01 lot) | 2,297 | -$882 / $924 / -0.95 | -$567 / $614 / -0.92 | -0.92 | yes (barely) | yes (placebo p = 0.046) |
| Trial #640 (R) | 123 | +4.9 / 18.0 / 0.27 | +2.6 / 12.4 / 0.21 | 1.06 | **no** | **no** (p = 0.58) |
| Trial #641 (R, reported only) | 32 | +1.4 / 5.0 / 0.28 | -1.3 / 6.0 / -0.22 | 1.35 | no | no |

## Verdict: FAILS the pre-registered pass rule (needs both sets #1 and #2)
- On #640 the governor does worse than doing nothing and far worse than random assignment of the same exposure cuts. The regime carries no information about when #640 loses.
- On FvgGold the Calmar "improvement" is on a LOSING strategy (net -$882 either way): ratios of negative numbers are not an improvement. Drawdown fell ($924 to $614), but that is mostly the exposure cut. The marginal beat over the placebo (p = 0.046) is one test of three and would not survive any multiple-testing adjustment.

## What the regime table does show (descriptive, not promoted)
- **EVENT windows are the one clearly bad regime for FvgGold**: avg -$1.64 per trade over 81 trades vs -$0.32 in NORMAL, win rate 32% vs 53%. That agrees with the event study (volatility spikes) and with the news blackout the live bot already applies. #640/#641 already exclude events, so they cannot test it.
- LOW and HIGH volatility do not behave the way the governor assumed: for FvgGold, LOW is worse than NORMAL and HIGH is the least bad. The 0.5x multipliers for those buckets have no support.

## Decision
Not wired into the bot, and not credited as an improvement. A blunt event blackout (already live) is the only part with support. Any further regime idea must come from a new pre-registration, not from re-cutting these buckets.
