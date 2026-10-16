# Ultra Core — gold-first MT5 trading research platform

> **Status (2026-10-16): research + demo. NOT validated for real money.**
> The live demo bot runs a 4-leg XAUUSD portfolio on an Exness **demo** account (`Exness-MT5Trial11`).
> On the corrected backtest engine that portfolio loses money (2022-08→2026-07: PF 0.88). No strategy tested in
> this repository has yet shown a statistically significant, repeatable edge after costs. See §7 and
> `docs/FINAL_AUDIT_2026-10-16.md` for the evidence and the blockers.

This README describes what the code actually does today. Older performance claims (PF 1.1–1.3, "live holdout PF 2.0",
Monte-Carlo ruin figures) came from a backtest engine that did not test a new position on its entry bar when 1-minute
data was missing; they are superseded by the corrected results below.

---

## 1. What is in the repository

```
src/
  core/          live demo bot: main_loop, risk_manager, execution_handler, sizing_ladder, risk_rules,
                 pre_trade_veto, market_hours, news_filter, resilience, trade_log, alerts, validation_ledger
  strategies/    live legs (portfolio_v5_core), retired/archived strategies, research candidates
                 (h1_donchian, new_*), shared BaseStrategy
  backtesting/   engine (corrected, multi-asset aware), costs, data (hashed broker bars), metrics
  instruments/   instrument metadata + per-asset cost models + risk-based lot sizing (XAU, EUR, GBP, JPY, BTC, ETH)
  portfolio/     portfolio-level risk layer: stop-loss risk, currency/USD exposure aggregation, limits, kill switch
  atlas/         Atlas Funded "Access" rule engine (pure logic, config in config/atlas_access.json)
  research/      feature library, candidate libraries, screener
scripts/         watchdog, monitors, validation runners, research/ (all studies are re-runnable scripts)
research/        cached broker bars (git-ignored .npy + committed manifests), validation ledger, registry/
docs/            audit, research and operating documents
tests/           pytest suite
```

## 2. Supported markets (data + cost models)

| Instrument | Class | Bars cached | Notes |
|---|---|---|---|
| XAUUSDm | gold | M15 2022-07→, H1/D1, M1 from 2026-07 | the live bot trades only this |
| EURUSDm, GBPUSDm, USDJPYm | forex | H1/H4/D1 (EUR/GBP intraday from 2017-03), M15 ~4 yr | research only |
| BTCUSDm, ETHUSDm | crypto | H1/H4/D1 from 2021-10, M15 ~2.9 yr | research only; trades 7 days |

Data comes from the Exness MT5 terminal (cap: 100,000 bars per M15/M5/M1 series). Coverage, specs and gaps:
`docs/research/DATA_COVERAGE_2026-10-16.md`. **No live adapter exists for non-gold instruments.**

## 3. How the live demo bot works (`python -m src.core.main_loop`, normally via `scripts/watchdog.py`)

60-second loop, IST clock, symbol `XAUUSDm`, fixed SL/TP in ATR14 multiples, no trailing/pyramiding.
1. Safety gates: single-instance lock, `STOP` file kill switch, Friday 22:30 IST flatten, spread, ±15-min news blackout, daily-loss cap, data freshness.
2. Direction: **D1 EMA20 gate** (on) plus an intraday override (threshold 1.0× — not backtested).
3. Entries only 06:00–21:30 IST; evaluation skipped 15:30–17:30 IST (`LONDON_NY_OVERLAP`).
4. Legs (SL/TP = 0.5/1.5 ATR): `TREND_PULLBACK_V5`, `BB_MEAN_REVERSION_V5`, `NVMR_TARGET_10_V5`, `FVG_NY_TIGHT_V5`; one signal per candle (Highlander ranking).
5. Order path: `SizingLadder` (0.01 lot below $800) → `PreTradeVeto` (floor, circuit breakers, caps, macro override, news) → `risk_rules` (ENFORCE=True: daily 3 %/6 %, 2 losing trades/day below $400, 3-loss pause, week/month caps, 30 % peak-drawdown halt) → market order with SL/TP attached.
6. Separate process `scripts/protect_profit.py` may close green positions early (not backtested).

Operations: `STOP` file in the repo root flattens and halts; `logs/trades/YYYY-MM-DD.jsonl` is the structured log; `logs/heartbeat` is the liveness file.
Known weakness: the Windows scheduled task has failed to start the bot after sleep (see audit).

## 4. Backtesting

`BacktestEngine` replays the live loop. Fills use M1 bars where cached, otherwise M15 with the entry bar now tested
(`EngineConfig.walk_entry_bar_coarse=True`), stop-first on ambiguous bars, bid/ask spread from the bar field, per-asset swap,
D1 gate, live trading window, dedup, Highlander ranking. Per-asset costs: `src.instruments.cost_model_for(symbol, scenario)`.
Known gaps: `risk_rules`, `protect_profit`, the FVG per-leg spread cap and the D1 intraday override are **not** simulated.

## 5. Portfolio risk layer and Atlas rules (pure logic, no broker calls)

- `src/portfolio/risk.py` — stop-loss risk from real contract specs, currency/USD exposure aggregation, correlated-group caps, margin and stale-data checks, soft/hard kill-switch state. Fails closed.
- `src/atlas/rules.py` + `config/atlas_access.json` — Atlas Funded **Access** rules (3 % target, 10 %/6 % trailing equity drawdown, 5 %/3 % daily loss, protector, news ±5 min, 3-minute hold, margin 80 %, weekend entries, consistency 40 %, payout eligibility) with source URL, retrieval date and a `verified-official` / `conflict` / `unverified` status per rule. Unresolved rules (gold symbol/leverage, funded-fee amount, bot-approval wording) block enforcement until confirmed.
- Neither module places orders. **There is no live Atlas execution adapter**; building one is a separate, not-yet-started step.

## 6. Research methodology

- Hypotheses are registered before testing (`research/registry/REGISTRY.md`), split chronologically into DEV / VALIDATE / HOLDOUT, corrected for multiple testing (Benjamini–Hochberg, Bonferroni), costs from broker spread and swap.
- Stage 1 (13 rules × 6 instruments, H1) and Stage 1b (61 slow D1/H4 tests incl. momentum, carry proxy, portfolios): **no significant positive result**; fades of H1 extremes on crypto/EURUSD/USDJPY are significantly negative.
- Earlier gold work: 322 candidates, 42 strategy classes, SL/TP geometry sweeps (`docs/DEEP_AUDIT_2026-10-16.md` §6).

## 7. Results that matter

| Question | Answer |
|---|---|
| Live 4-leg portfolio, corrected engine, 2022-08→2026-07, 0.01 lot | PF 0.88, win 22 %, −$1,340 |
| Same, 2026 only, from $186 | PF 0.74, account reaches $0; without TrendPullback PF 1.09 (+$185) |
| Demo account, broker history since 2026-09-28 (V5 legs) | 34 trades, +$6.13, PF 1.11 — too small to infer an edge |
| Best candidate for a prop account | H1 Donchian-100 (SL4/TP12): PF 1.56 over 2023-08→2026-10, but 2025–26 only; ~+7.5 %/yr at bar-compliant risk |
| Statistical evidence of an edge in any tested rule | none after multiple-testing correction |

## 8. Setup

```bash
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt          # includes scipy (src.research.metrics needs it)
copy .env.example .env.local             # MT5_LOGIN / MT5_PASSWORD / MT5_SERVER, ULTRA_ALERT_* — never commit
python -m pytest tests -q                # full suite (316 tests)
python -m scripts.watchdog               # demo bot + keep-alive
```

Re-run studies: `scripts/research/multi_asset_screen.py`, `multi_asset_slow.py`, `all_strategies_2026.py`, `geometry_sweep.py`, `atlas_score.py`.

## 9. Security

- Credentials only via environment / `.env.local` (git-ignored). A Telegram bot token exists in older git history and should be revoked; a trading-bot MCP process exposed an account login on its command line — move it to environment variables.
- `scripts/daily_stats.py` reads `MT5_LOGIN`/`MT5_PASSWORD`/`MT5_SERVER` from the environment.

## 10. Known limitations / blockers (summary)

No proven edge · M1 history only from 2026-07 (gold) · risk/validation gate hollow (`export_final_backtest.py` stamps the live fingerprint) · live-only logic unbacktested · no non-gold live adapter · Atlas rules partly unverified · scheduler/uptime issue · crypto swap units unverified.
Full list with scores: `docs/FINAL_AUDIT_2026-10-16.md`.
