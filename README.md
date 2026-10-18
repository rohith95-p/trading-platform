# Ultra Core — XAUUSD (gold) MT5 trading research platform

> **Status (2026-10-17): research + demo, gold only. NOT validated for real money.**
> The live demo bot runs a 4-leg XAUUSD portfolio on an Exness **demo** account (`Exness-MT5Trial11`).
> On the corrected backtest engine that portfolio loses money (2022-08→2026-07: PF 0.88, win 22 %, −$1,340 at 0.01 lot).
> No strategy tested in this repository has shown a statistically significant, repeatable edge after costs.
> See §7 and `docs/FINAL_AUDIT_2026-10-16.md`.

This project trades **XAUUSD only**. Forex, crypto and multi-asset code, data and research that were briefly added on
2026-10-16 were removed on 2026-10-17 (they are recoverable from git history, commits `3f5964f`–`0cde15f`).
Older performance claims (PF 1.1–1.3, "live holdout PF 2.0", Monte-Carlo ruin figures) came from an engine that did
not test a new position on its entry bar when 1-minute data was missing; they are superseded by the numbers below.

---

## 1. Repository layout

```
src/
  core/          live demo bot: main_loop, risk_manager, execution_handler, sizing_ladder, risk_rules,
                 pre_trade_veto, market_hours, news_filter, resilience, trade_log, alerts, validation_ledger
  strategies/    live legs (portfolio_v5_core), retired/archived strategies, research candidates
                 (h1_donchian, new_*), shared BaseStrategy
  backtesting/   engine (entry-bar-corrected), costs, data (hashed broker bars), metrics
  atlas/         Atlas Funded "Access" prop-firm rule engine (pure logic; config in config/atlas_access.json)
  research/      feature library, candidate libraries, screener
scripts/         watchdog, monitors, validation runners (incl. engine-vs-broker reconciliation), research/
research/        cached XAUUSDm bars (git-ignored .npy + manifests), validation ledger
docs/            audit, research and operating documents
tests/           pytest suite
```

## 2. Data

Broker bars from the Exness MT5 terminal: XAUUSDm M15 from 2022-07, H1/D1, M1 only from 2026-07 (terminal cap: 100,000 bars
per M15/M5/M1 series). Before 2026-07 the engine runs at M15 resolution; the entry bar is tested (§4).

## 3. How the live demo bot works (`python -m src.core.main_loop`, normally via `scripts/watchdog.py`)

60-second loop, IST clock, symbol `XAUUSDm`, fixed SL/TP in ATR14 multiples, no trailing/pyramiding.
1. Safety gates: single-instance lock, `STOP` file kill switch, Friday 22:30 IST flatten, spread, ±15-min news blackout, daily-loss cap, data freshness.
2. Direction: **D1 EMA20 gate** (on, by design): a BEARISH daily trend blocks buys, a BULLISH one blocks sells. The intraday override (threshold 1.0×, not backtested) may only **tighten** the gate (bullish→bearish on a crash day), never turn a bearish trend bullish; and if the daily bias cannot be computed the gate **fails closed** (no new entries). (Changed 2026-10-17 after two counter-trend buys got through on 2026-10-15.)
3. Entries only 06:00–21:30 IST; evaluation skipped 15:30–17:30 IST (`LONDON_NY_OVERLAP`).
4. Legs (SL/TP = 0.5/1.5 ATR): `TREND_PULLBACK_V5`, `BB_MEAN_REVERSION_V5`, `NVMR_TARGET_10_V5`, `FVG_NY_TIGHT_V5`; one signal per candle (Highlander ranking).
5. Order path: `SizingLadder` (0.01 lot below $800) → `PreTradeVeto` → `risk_rules` (ENFORCE=True: daily 3 %/6 %, 2 losing trades/day below $400, 3-loss pause, week/month caps, 30 % peak-drawdown halt) → market order with SL/TP attached.
6. `scripts/protect_profit.py` (separate process) may close green positions early.

Operations: a `STOP` file in the repo root flattens and halts; `logs/trades/YYYY-MM-DD.jsonl` is the structured log; `logs/heartbeat` is liveness.
Operations (added 2026-10-18, see `docs/OPS_RUNBOOK.md`): `scripts/supervisor.py` restarts the bot after a crash (measurement-only by default), a persistent halt latch (`python -m scripts.halt`) survives restarts, and a status heartbeat is POSTed to `ULTRA_HEARTBEAT_URL` for an external dead-man alert. Known weakness: the old Windows scheduled task failed to start the bot after PC sleep; the supervisor task installer is provided but not applied.

## 4. Backtesting

`BacktestEngine` replays the live loop: M1 fills where cached, otherwise M15 with the entry bar tested
(`EngineConfig.walk_entry_bar_coarse=True`), stop-first on ambiguous bars, bid/ask spread from the bar field, swap, D1 gate, live trading
window, dedup, Highlander ranking. Gold results are pinned by `tests/test_engine_gold_regression.py`.

**Engine vs broker (reconciled 2026-10-17, read-only; `scripts/validation/reconcile_live_parity.py`):** over the window 2026-10-05 18:00 -> 10-15 22:00 IST the live bot made 18 trades (+$23.40). With `EngineConfig(live_parity=True)` (opt-in; default OFF so research results are unchanged) the engine takes 17-24 trades, reproduces 15 of the 18 real trades (same leg, direction, entry within 5 min) and per-trade P&L correlates at r = 0.73-0.87 (about 1.0 without the single worst pair). Entry-price gap vs broker is $+0.28 mean (within noise). The live-only rules now modelled: `risk_rules` (ENFORCE), the 15:30-17:30 IST skip, the FVG spread cap, sizing-ladder concurrency, the D1 intraday override, `protect_profit.py` early closes, and a 30 s entry delay. Residual differences are mostly days the bot was probably not running (uptime for 10-06..10-09 is unknown), one-minute-bar noise, and two 10-15 BUYs the live bot took while the D1 gate read BEARISH (suspected fail-open when the D1 fetch returns too few bars; unconfirmed). Sample is small (18 trades): this validates the engine's mechanics, not any strategy.

## 5. Atlas Funded rule engine (pure logic, no broker calls)

`src/atlas/rules.py` + `config/atlas_access.json` encode the Atlas **Access** rules (3 % target, 10 %/6 % trailing equity drawdown, 5 %/3 % daily
loss, protector, news ±5 min, 3-minute hold, margin 80 %, weekend entries, consistency 40 %, payout eligibility). Each rule carries its
source URL, retrieval date and a `verified-official` / `conflict` / `unverified` status; unresolved rules block enforcement until
acknowledged. **No Atlas execution adapter exists.**

## 6. Research methodology

Hypotheses are registered before testing, split chronologically (development / validation / untouched holdout), costed from broker spread
and swap, and corrected for multiple testing. Gold work: 322 candidate rules, 42 strategy classes, SL/TP geometry sweeps, walk-forward
geometry selection, H1 Donchian family (`docs/DEEP_AUDIT_2026-10-16.md` §6).

## 7. Results that matter

| Question | Answer |
|---|---|
| Live 4-leg portfolio, corrected engine, 2022-08→2026-07, 0.01 lot | PF 0.88, win 22 %, −$1,340 |
| Same, 2026 only, from $186 | PF 0.74, account reaches $0; without TrendPullback PF 1.09 (+$185) |
| Demo account, broker history since 2026-09-28 (V5 legs) | 34 trades, +$6.13, PF 1.11 — too small to infer an edge |
| Best candidate for a prop account | H1 Donchian-100 (SL4/TP12): PF 1.56 over 2023-08→2026-10, positive only in the 2025–26 rally |
| Statistical evidence of an edge | none after multiple-testing correction |

## 8. Setup

```bash
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env.local             # MT5_LOGIN / MT5_PASSWORD / MT5_SERVER, ULTRA_ALERT_* — never commit
python -m pytest tests -q                # full suite
python -m scripts.watchdog               # demo bot + keep-alive
```

## 9. Security

Credentials only via environment / `.env.local` (git-ignored). A Telegram bot token exists in older git history and should be revoked.
`scripts/daily_stats.py` reads `MT5_LOGIN`/`MT5_PASSWORD`/`MT5_SERVER` from the environment.

## 10. Known limitations / blockers

No proven edge · M1 history only from 2026-07 · validation gate is hollow (`export_final_backtest.py` stamps the live fingerprint) ·
live-only rules are simulated only with `live_parity=True` (small 18-trade reconciliation) · no Atlas execution adapter · Atlas rules partly unverified · scheduler/uptime issue.
Full list with scores: `docs/FINAL_AUDIT_2026-10-16.md`.
