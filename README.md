# Ultra Core — XAUUSD Algorithmic Trading System

An automated XAUUSD (gold) trading system built on MetaTrader 5, designed for Atlas Funded prop-firm evaluation accounts. Runs a 3-strategy portfolio with full risk management, position sizing, and prop-firm rule compliance.

## Architecture

```
src/
  core/           Trading engine: main_loop, risk_manager, execution_handler,
                  sizing_ladder, risk_rules, pre_trade_veto, market_hours,
                  news_filter, resilience, trade_log, alerts, validation_ledger
  strategies/     Active portfolio (portfolio_atlas.py) + BaseStrategy interface
  backtesting/    Replay engine with M1/M15 fills, realistic cost models, D1 gate
  atlas/          Atlas Funded rule engine (trailing DD, daily loss, consistency)
  research/       Feature library, candidate screening
scripts/          Watchdog, monitors, diagnostics, backtest runners
research/         Cached XAUUSDm bars (.npy, git-ignored), validation ledger
tests/            311 tests (pytest): strategy logic, risk rules, no-lookahead,
                  engine parity, sizing ladder, demo relaxation
config/           Atlas rules (atlas_access.json), magic numbers (ultra_magics.json)
docs/             OPS_RUNBOOK, ATLAS_TEST_PLAN, REPO_GUIDE
```

## Active Portfolio

Three strategies optimized for Atlas Funded evaluation + funded phases:

| Strategy | Magic | Logic | SL / TP (ATR14) |
|---|---|---|---|
| **DonchianTrendV6** | 7310 | 10-day Donchian breakout with EMA50 trend filter on D1 | 3.0x / 6.0x |
| **AsianRangeFilteredV6** | 7320 | Asian range breakout at London open, range must be 0.3%-1.6% of price | 2.0x / 3.5x |
| **AsianBreakoutV6** | 7311 | Unfiltered Asian breakout (catches wider ranges the filtered version skips) | 2.5x / 4.0x |

Holdout backtest (2025-06 to 2026-10, realistic ECN costs):
- **Profit Factor 1.44**, max drawdown 4.08%, worst single day -2.33%
- Atlas evaluation (10% DD, 5% daily loss): **PASS** with 59% safety margin
- Atlas funded (6% DD, 3% daily loss): **PASS** with 32% safety margin
- Estimated ~45 days to reach the 3% profit target ($150 on $5K)

## How It Works

**60-second loop**, IST clock, symbol `XAUUSDm`, fixed SL/TP in ATR14 multiples.

1. **Safety gates**: single-instance lock, `STOP` file kill switch, Friday 22:30 IST flatten, spread filter, ±15-min news blackout, daily-loss cap, data freshness check.
2. **D1 EMA20 gate**: bearish daily trend blocks buys, bullish blocks sells. Fails closed (no entries) if D1 data unavailable.
3. **Trading window**: entries only 06:00–21:30 IST.
4. **Signal generation**: strategies evaluate on M15/M5 bars, one signal per candle via Highlander ranking (best strategy wins when multiple fire).
5. **Order path**: `SizingLadder` → `PreTradeVeto` → `risk_rules` (ENFORCE=True) → market order with SL/TP attached.

## Risk Management

**Position sizing ladder** (balance-based):

| Balance | Lots | Max Positions | Max Exposure |
|---|---|---|---|
| $50–$200 | 0.01 | 1 | 0.01 |
| $200–$400 | 0.01 | 2 | 0.02 |
| $400–$800 | 0.01 | 3 | 0.03 |
| $800+ | 0.02 | 3 | 0.06 |

**Circuit breakers**: 3-consecutive-loss pause (4h), 5-loss day stop, daily loss cap (3%/6%), weekly cap (15%), monthly cap (25%), 30% peak-drawdown hard halt. Demo mode relaxes streak breakers and hard halts for forward testing.

## Atlas Funded Compliance

`src/atlas/rules.py` encodes Atlas **Access** rules from `config/atlas_access.json`:
- 3% profit target (evaluation), no target when funded
- 10% trailing equity drawdown (evaluation), 6% (funded)
- 5% daily loss (evaluation), 3% (funded)
- News ±5 min blackout, 3-minute minimum hold, 80% margin cap
- Consistency rule (40%), weekend entry restrictions

`AtlasRuleEngine.check_order()` vets every order pre-send; `monitor()` returns OK / STOP_NEW / FLATTEN. Activated with `ULTRA_ATLAS_MODE=1`.

## Backtesting

`BacktestEngine` replays the live loop: M1 fills where available (from 2026-07), M15 with entry-bar testing otherwise. Includes D1 gate, live trading window, dedup, Highlander ranking, realistic ECN costs (spread from bar data + 20pt slippage + $3.50/lot commission).

Data splits: **DEV** (2022-08 to 2024-02), **VALIDATE** (2024-02 to 2025-06), **HOLDOUT** (2025-06 to 2026-10).

## Setup

```bash
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env.local   # MT5_LOGIN, MT5_PASSWORD, MT5_SERVER
python -m pytest tests -q      # 311 tests
```

**Running the bot**:
```bash
python -m src.core.main_loop              # direct
python -m scripts.watchdog                # with keep-alive
```

**Environment variables**:
- `ULTRA_ATLAS_MODE=1` — activate Atlas rule engine
- `ULTRA_DEMO_MODE=1` — relax streak breakers and hard halts (demo accounts only)
- `ULTRA_ALLOW_UNVALIDATED=1` — bypass validation ledger check at startup

## Security

Credentials only via `.env.local` (git-ignored). No API keys, tokens or secrets in the repository.

## Test Suite

311 passing tests covering:
- Strategy signal generation and no-lookahead bias
- Risk rules, sizing ladder, circuit breakers
- Demo relaxation flags (DEMO_RELAX_HARD_HALTS, DEMO_RELAX_STREAK_BREAKERS, DEMO_RELAX_DAILY_CAP)
- Engine-vs-live parity (sizing ladder caps, execution order)
- Atlas portfolio integrity (magic uniqueness, config alignment)
- D1 gate, EMA calculation, market hours, ATR causality
