---
description: Strict boundaries on autonomous decision making for the trading bot.
---

# Agent Boundaries & Trading Logic

**CRITICAL RULE:**
The AI agent must **NEVER** unilaterally make important trading logic decisions or impose directional biases (such as forcing "BUY ONLY" or "SELL ONLY" modes) without the explicit, unequivocal instruction from the USER.

1. **Mathematical Objectivity:** The bot must trade strictly based on the mathematical indicators programmed into the strategy. 
2. **No Unilateral Filters:** Do not hardcode filters, disable strategies, or restrict trade directions based on your own macro market analysis unless the user explicitly requests you to build a filter.
3. **Always Ask:** If you believe a safety measure is necessary, you must present it as a question or proposal, and wait for the user's direct confirmation before modifying any live trading code.

## User-approved measures (do not treat these as violations of the above)

Current as of 2026-11-01, each with the owner's explicit approval and backtest
evidence:
- **D1 EMA20 bias gate, ON for all four legs** — trade only with the daily
  trend. It is a formula (daily close against the daily EMA20), not discretion.
  The owner kept it after seeing the A/B result; turning it off was worse.
- **0.02 lots per order, 0.06 lots of exposure, 3 positions** — owner's
  directive, see `account_growth_rule.md`.
- **Trailing stops and pyramiding disabled**, and the code removed — both
  measured net-negative (the A/B is recorded in `main_loop.py`'s header:
  PF 0.592 with them on against 1.478 with them off).
- **Atlas rule engine in front of every order**, with STOP_NEW at 60% of a
  limit and FLATTEN at 80%.

Changing any of these back also requires explicit user instruction.
