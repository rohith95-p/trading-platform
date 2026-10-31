---
name: xauusd-trading-prep
description: The "tomorrow's plan" workflow for the Ultra Core XAUUSD bot — regenerate the daily macro analysis and battle plan from live data, matched to what the bot actually runs.
---

# XAUUSD Trading Preparation

## When to activate

- The owner asks for "tomorrow's plan" or a daily plan
- The owner asks to analyse gold conditions or review the day's trades

## The "Tomorrow's Plan" workflow

**1. Pull cross-asset data.** Prefer the MT5 broker feed (it matches what the bot
trades) over yfinance. Available Exness symbols: `XAUUSDm`, `XAGUSDm`, `DXYm`,
`USOILm`, `UKOILm`, `EURUSDm`, `USDJPYm`, `US500_x100m`, `USTEC_x100m`. Take
5-day D1 changes. yfinance is a fallback only (`GC=F`, `SI=F`, `DX-Y.NYB`,
`^TNX`, `CL=F`, `^VIX`).

**2. Regenerate `docs/plans/DAILY_MARKET_ANALYSIS.md`:**
- 5-day cross-asset table with the implication for gold
- Gold D1 price structure (recent OHLC, distance from the D1 EMA20)
- **The D1 EMA20 level** — the number that flips the live bias gate. State how
  far price is from it and whether that is within one session's range.
- ⚠️ **Never quote the two macro-rule trigger phrases in this file.**
  `RiskManager._load_macro_rules()` greps it and will switch every short to a
  hardcoded 1.0x/2.0x ATR stop if both appear. Reference `risk_manager.py`
  instead, and keep the warning header the file already carries.

**3. Regenerate `docs/plans/DAILY_BATTLE_PLAN.md`:**
- Market condition (macro against price structure — say so when they disagree)
- The four live legs, their sessions and their stops (from `portfolio_atlas.py`)
- Direction: decided by the D1 gate, not by discretion. While price is below the
  D1 EMA20 it is shorts only; longs are detected and logged as blocked.
- The hard risk rules (below)
- A review of the day's closed trades, read against price action, separating
  "was the direction right" from "was the size or exit right"
- A watch list of specific price levels

## What the bot actually runs

`portfolio_atlas` via `python -m src.core.main_loop`:

| Leg | Entry, IST | Stop / target (x ATR) |
|---|---|---|
| AsianRangeFilteredV6 | 12:45 | 2.5 / 3.5 |
| AsianBreakoutV6 | 12:45 | 3.0 / 5.0 |
| LondonMomentumTightV6 | 17:45 | 2.0 / 4.0 |
| NYSessionReversalV6 | 17:45–21:30 | 2.5 / 4.5 |

Strategy candidates live in `src/research/candidates.py` (XAU-nnn ids); their
grades are in `docs/research/STRATEGY_REGISTRY.md`.

## Hard risk rules (enforced in code)

- 0.02 lots per order, always (`FIXED_LOT_SIZE`)
- 0.06 lots of total exposure, at most 3 concurrent (`MAX_TOTAL_VOLUME`)
- The Atlas rule engine gates every order: STOP_NEW at 60% of a limit, FLATTEN
  at 80%. A daily-loss halt clears itself at the next UTC midnight.
- No trailing stops, no pyramiding — both measured net-negative, code removed
- D1 EMA20 bias gate — trade only with the daily trend

At 0.02 lots a stop costs roughly $30–80 depending on the leg and the day's
volatility. The account is $5,000, the evaluation fails at a $500 trailing
drawdown, and $150 of profit passes it. Do not widen stops or raise the lot to
reach the target faster without the owner asking.

## Account context

Atlas 1-Step $5,000 evaluation, rehearsed on an Exness MT5 demo of the same size
on an AWS Windows VPS. Frame everything in real dollars at 0.02 lots. The
honest backtest picture is in `research/results/audit_stats.json`: this
portfolio earns in trending gold and bleeds in quiet gold, so a flat month is
the expected bad case, not a surprise.
