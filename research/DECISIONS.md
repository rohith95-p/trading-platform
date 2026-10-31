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
| 2026-10-31 | Strategy-specific stops/targets (range, breakout candle, London range, sweep wick; 96 variants, fixed and equal-risk lots): not adopted | DEV + TEST, pre-registered (PREREG_StrategyStops) | TEST (walk-forward A), RECENT (walk-forward B), Monte Carlo | 0 of 8 pass all four checks (RESULT_StrategyStops) | no change |
| 2026-11-01 | Stop robustness (stability map, 6 volatility measures, flip test, cost stress, Monte Carlo): live ATR(14) M15 stops kept | pre-registered (PREREG_StopRobustness) | DEV / TEST / RECENT each | nothing beats live; edge is in the entries (RESULT_StopRobustness). Found: live ATR used the forming bar (5-9% tighter than backtest) | kept; forming-bar fix approved and applied 2026-11-01 |
| 2026-11-01 | Live stop ATR computed on closed 15-min bars only (was: including the bar that just opened) | parity fix, owner approved | backtest already used closed bars | live now matches the validated stops exactly | live |
| 2026-11-01 | Audit of the data and the engine (no trading change): engine refuses to resolve exits on 15-minute candles; archive trusted only to 2026-01-01; one master bar series; broker measured at startup; holdout enforced in code | n/a -- nothing was chosen | re-ran DEV / TEST / RECENT | corrected honest numbers: DEV -$295 (PF 0.66, Atlas guard freezes the account in May 2023; -$210 over the full window with the guard off), TEST +$1,058 (PF 1.40), RECENT +$790 (PF 1.81). Zero exits resolved without minute data in any window. See research/AUDIT_2026-11-01.md | live (tooling only) |

## What this means for the numbers
Every live setting above was picked while looking at 2022-08 → 2026-10, so the backtest is the best case for that
period, not a forecast. The first honest test of the current system is live trading from 2026-11-01, compared with
the backtest after 40 trades and again after 100.

The figures to compare against are the corrected ones from the 2026-11-01 audit, not the earlier +$2,020 / PF 1.42:
DEV **-$295**, TEST **+$1,058**, RECENT **+$790**. The earlier DEV figure (PF 1.07) came from a one-off script that
no longer exists; the current ones come from a committed pipeline that can be re-run
(`scripts/validation/audit_stats.py`). The shape of the result is the thing to remember: **this portfolio earns in
trending gold and bleeds in quiet gold.** It lost money across the range-bound 2022-23 stretch and would have had
its Atlas account frozen nine months in. A flat month is the expected bad case, not a surprise.
