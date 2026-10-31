# Decision log: every change to what trades live

One row per change to the live system. "Chosen on" is the data that was looked at when deciding; "Judged on" is
data that was NOT looked at. A change chosen and judged on the same data is marked **post-hoc**: its backtest gain
is an upper bound, not an estimate.

## Rule from 2026-11-01
1. **Frozen holdout:** price data from 2026-11-01 onward is never used to choose a setting. It is only used to judge.
2. **Pre-register first:** before testing a change, write `research/registry/PREREG_<name>_<date>.md` with the
   hypothesis, the exact variants, the data used to choose, and the pass bar (for example "PF on the holdout ≥ the
   live PF and not worse in any window"). The test may not add variants after it starts.
3. **Live changes need the live record:** a strategy or exit change goes live only if it passes its pre-registered
   bar, and it is reviewed again against the live journal (`logs/trade_journal.csv`) after 40 live trades.
4. Every live change adds a row below and updates `tests/test_live_freeze.py` in the same commit.

## Log
| Date | Change | Chosen on | Judged on | Result | Status |
|---|---|---|---|---|---|
| 2026-10-29 | 5-leg Atlas portfolio (+London Momentum Tight, +NY Session Reversal) | DEV/TEST/RECENT screen of 48 strategies | none unseen | PF 1.14 / 1.39 / 1.48 (coarse-gated engine) | post-hoc |
| 2026-10-30 | Profit protector off | DEV/TEST/RECENT A/B | none unseen | TEST net $1,113 vs $639 | post-hoc |
| 2026-10-30 | Daily trend gate applied to every leg (live had skipped it) | DEV/TEST/RECENT | none unseen | pooled PF 1.29 vs 0.99 | post-hoc, but it restores what every earlier test assumed |
| 2026-10-30 | Donchian Trend removed (4 legs) | DEV/TEST/RECENT | none unseen | +$1,687 vs +$1,627 | post-hoc |
| 2026-10-30 | Trailing stop: not adopted | DEV/TEST/RECENT | n/a | fixed targets best in all variants | no change |
| 2026-10-30 | Asian Range Filtered stop 2.0 → 2.5 ATR | DEV + TEST (60-combination sweep) | RECENT (2026-07..10) | better in all three windows; all +$2,020 vs +$1,687 | partly out-of-sample (RECENT unseen for this choice only) |
| 2026-10-31 | Structure (swing / range) stops: not adopted | DEV + TEST, pre-registered (PREREG_StructureStops) | RECENT | all 4 strategies fail the pre-set bar (RESULT_StructureStops) | no change |

## What this means for the numbers
Every live setting above was picked while looking at 2022-08 → 2026-10. The backtest's +$2,020 / PF 1.42 is the
best case for that period, not a forecast. The first honest test of the current system is live trading from
2026-11-01, compared with the backtest after 40 trades and again after 100.
