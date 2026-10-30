# Ultra Core — XAUUSD Algorithmic Trading System

An automated XAUUSD (gold) trading system built on MetaTrader 5, designed for Atlas Funded prop-firm evaluation accounts. Runs a 5-strategy portfolio with full risk management, position sizing, and prop-firm rule compliance. Day-to-day operation (Telegram messages, strategy times, VPS commands): [docs/OPS_RUNBOOK.md](docs/OPS_RUNBOOK.md).

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
scripts/          Watchdog, VPS update/check scripts, halt CLI, research and validation runners
research/         Cached XAUUSDm bars (.npy, git-ignored), validation ledger
tests/            pytest suite: strategy logic, risk rules, no-lookahead, engine parity,
                  sizing ladder, alert priorities, live-config freeze guard
config/           Atlas rules (atlas_access.json), magic numbers (ultra_magics.json)
docs/             OPS_RUNBOOK, ATLAS_TEST_PLAN, REPO_GUIDE
```

## Active Portfolio

Five strategies (`src/strategies/portfolio_atlas.py`), each one order of 0.02 lots with a fixed stop and target:

| Strategy | Magic | Entry (IST) | Logic | SL / TP (ATR14) |
|---|---|---|---|---|
| **DonchianTrendV6** | 7310 | 06:15 | 10-day Donchian breakout | 2.0x / 4.0x |
| **AsianRangeFilteredV6** | 7320 | 12:45 | Asian range breakout at London open, range-size gate | 2.0x / 3.5x |
| **AsianBreakoutV6** | 7311 | 12:45 | Unfiltered Asian breakout | 3.0x / 5.0x |
| **LondonMomentumTightV6** | 7324 | 17:45 | London/NY overlap continuation | 2.0x / 4.0x |
| **NYSessionReversalV6** | 7313 | 17:45-21:30 | NY session sweep reversal | 2.5x / 4.5x |

Independent audit 2026-10-30 (M1 data only, $5K, 0.02 lots, protector off, 24h, Atlas guard, realistic ECN costs;
`research/results/audit_2026-10-30/README.md`): PF 1.07 DEV (2022-08 to 2024-06), 1.32 TEST (2024-06 to 2026-02),
1.53 RECENT (2026-07 to 2026-10); about 14 trades a month, 25-42% of months lose money.
These are the numbers with the daily trend gate on, which live applies to all five legs since 2026-10-30;
skipping the gate (as live did before) was break-even (pooled PF 0.99). See section 3 of the audit.

## How It Works

**60-second loop**, IST clock, symbol `XAUUSDm`, fixed SL/TP in ATR14 multiples.

1. **Safety gates**: single-instance lock, `STOP` file kill switch, Friday 22:30 IST flatten, spread filter, ±15-min news blackout, daily-loss cap, data freshness check.
2. **D1 EMA20 gate**: bearish daily trend blocks buys, bullish blocks sells. Fails closed (no entries) if D1 data unavailable.
3. **Trading window**: 06:00–21:30 IST by default; `ULTRA_TRADE_24H=1` (set live) lifts it. Weekend and Friday cut-offs always apply.
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

`BacktestEngine` replays the live loop: M1 fills where M1 bars exist, M15 with entry-bar testing otherwise (coarse M15 is optimistic; the M1 merge has a hole 2025-09-12 to 2025-10-15). Includes D1 gate, live trading window, dedup, Highlander ranking, realistic ECN costs (spread from bar data + 20pt slippage + $3.50/lot commission).

Data splits used for the live portfolio: **DEV** (2022-08 to 2024-06), **TEST** (2024-06 to 2026-02), **RECENT** (2026-07 to 2026-10).

## Setup

```bash
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env.local   # MT5_LOGIN, MT5_PASSWORD, MT5_SERVER
python -m pytest tests -q
```

**Running the bot**: `start_ultra_core.bat` (starts the watchdog, which starts and supervises the trading loop).
On the VPS, update with `scripts\vps_update.ps1` and check with `scripts\vps_check.ps1` (see the runbook).

**Environment variables**:
- `ULTRA_ATLAS_MODE=1` — activate Atlas rule engine
- `ULTRA_DEMO_MODE=1` — relax streak breakers and hard halts (demo accounts only)
- `ULTRA_ALLOW_UNVALIDATED=1` — bypass validation ledger check at startup
- `ULTRA_TRADE_24H=1` — lift the 06:00–21:30 IST entry window
- `ULTRA_PROTECT_PROFIT=0` — do not run the profit protector (live setting since 2026-10-30)
- `ULTRA_PULSE_EVERY_H` — hourly Telegram pulse interval (default 1, 0 = off)

## Security

Credentials only via `.env.local` (git-ignored). No API keys, tokens or secrets in the repository.

## Test Suite

Tests cover:
- Strategy signal generation and no-lookahead bias
- Risk rules, sizing ladder, circuit breakers
- Demo relaxation flags (DEMO_RELAX_HARD_HALTS, DEMO_RELAX_STREAK_BREAKERS, DEMO_RELAX_DAILY_CAP)
- Engine-vs-live parity (sizing ladder caps, execution order)
- Atlas portfolio integrity (magic uniqueness, config alignment)
- D1 gate, EMA calculation, market hours, ATR causality
- Telegram priorities and layout, hourly pulse, halt stand-down
- Live-config freeze guard (`tests/test_live_freeze.py`)
