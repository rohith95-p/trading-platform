# Previous-day breakout: rejected

Source: https://github.com/allanninal/prior-day-breakout-pine
Protocol: PREREG_PriorDayBreakout_2026-11-11.md
Runner: scripts/research/prior_day_breakout.py
Metrics: prior_day_breakout.json

Public-rule adaptation, M15 XAUUSD, 2R, 0.02 lots, next-bar executable entry,
bid/ask costs, gap-aware stops and forced session flat. No parameter optimization.

| Already-inspected development period | Trades | Wins | Win rate | PF | Net USD | Realized-balance max DD |
|---|---:|---:|---:|---:|---:|---:|
| 2005–2011 | 1461 | 692 | 47.4% | 0.950 | -557.38 | 22.68% |
| 2012–2018 | 1381 | 610 | 44.2% | 0.886 | -1253.96 | 29.14% |
| 2019–2025 | 1475 | 699 | 47.4% | 1.038 | 712.73 | 20.77% |

4317 trades, combined net -1098.61 USD. Every era fails PF >=1.3. Do not promote.
Drawdown above is based on closed trades, not intratrade equity or Atlas trailing-floor replay.
No payout or evaluation pass claim is supported. Full statistics include Sortino, Omega,
Calmar, recovery, expectancy, best/worst trade ablation and trade-order randomization.
Randomization preserves total P&L: its final-loss fraction is not a forecast probability.
The recovered dated-search comparison now covers 14 candidate arms; older searches remain
outside this recovered subset, so this count is not the complete number of research trials.

Two deterministic execution cases cover next-open entry and adverse gap exit on both sides,
including short ask spread. Appending a later bar with extreme prices preserves the completed
trade. These tests do not establish complete broker simulator parity or Atlas compliance.
November 2026 forward holdout was not accessed.
