# Ultra Core — Deep Audit (2026-10-16)

Scope: whole repository (live engine, MT5 integration, risk layers, strategies, backtest engine,
validation ledger, ops/watchdog, scripts, docs, secrets) as of `master` @ `3c1d1af` **plus the 8 uncommitted files**.
Method: read every file on the live path line by line; read the engine and validation tooling; inspected live
state (`logs/`, scheduled task, processes); ran the test suite (70 passed); ran one controlled A/B backtest (§2.1).
Nothing in the live system was modified. Secrets are referred to by location only, never reproduced.

Account context: Exness **demo** `#198874999` (server `Exness-MT5Trial11`), symbol `XAUUSDm`, balance ≈ $177–186.

---

## 0. Verdict in five lines

1. The **engineering shell is good** (lockfile, kill switch, dedup, SL/TP attached server-side, fail-closed balance check, config-fingerprint gate, structured log). Most of what earlier audits flagged is genuinely fixed.
2. The **evidence that the strategies have an edge is not trustworthy**. ~96 % of the backtest history is simulated at coarse M15 resolution, and in the one window where both resolutions exist the same 4 legs go from **PF 1.375 → PF 0.926** (§2.1).
3. The **"CONFIG VALIDATED" gate does not validate what actually trades**. It stamps the *live* fingerprint onto whatever backtest ran, and the fingerprint omits many live-only behaviours (§2.2, §2.3).
4. There are **live secrets exposure issues** (Telegram bot token in pushed git history; a plaintext MT5 password in an uncommitted script) (§2.4).
5. **Operations are not reliable yet**: the bot is not running right now, the auto-start task failed to fire on Oct 15, and there was a ~20 h gap with no alert (§2.5). Do not move real money on this basis — the README itself says NOT READY, and the corrections below make the case weaker, not stronger.

---

## 1. How the system works, from scratch to final push

### 1.1 Data flow

```
MT5 terminal (Exness, server time = UTC)
   │ copy_rates_from_pos  M15×250, M5×100, D1×50 (+M15×20 for management)
   ▼
DataFetcher ──► main_loop.run()  (60 s loop, IST clock)
                 │ 1. heartbeat + save_state + record closed trades
                 │ 2. STOP-file kill switch / Friday-22:30-IST flatten
                 │ 3. spread gate (350 pts)  → news gate (±15 min)  → daily-loss gate (6 %)
                 │ 4. data-freshness check → D1 EMA20 bias (+ intraday override)
                 │ 5. skip evaluation entirely in "LONDON_NY_OVERLAP" (15:30–17:30 IST)
                 │ 6. each strategy.evaluate(M15) on the last CLOSED bar (index -2)
                 │ 7. D1 gate → cooldown → Highlander (one winner by fixed rank)
                 ▼
         _execute_signal: trading window (06:00–21:30 IST) → per-leg spread cap
                 → can_open → risk_rules.evaluate (ENFORCE=True) → dedup key
                 ▼
         ExecutionHandler.send_order: SizingLadder(balance) → PreTradeVeto (6 layers)
                 → legacy caps → order_send (market, IOC, dev 30, SL+TP attached, 3 retries)
```

Side processes: `scripts/watchdog.py` (restarts `main_loop` and `protect_profit`), `scripts/protect_profit.py`
(second MT5 client that closes green positions on "giveback"/"reversal" and writes `logs/positions.txt` + `logs/cooldown.json`),
`scripts/hourly_monitor.py` (Telegram audit), Task Scheduler job `UltraCoreBot` (05:55 IST daily → `start_ultra_core.bat` → watchdog).

### 1.2 Every MT5 touch-point

| MT5 call | Where | Purpose / note |
|---|---|---|
| `initialize` / `shutdown` | `main_loop._run_guarded`, `resilience.note_fetch_result` | start; reconnect after 3 failed fetches |
| `account_info` | `resilience.startup_safety_check`, `RiskManager.check_daily_drawdown` (fails closed), `ExecutionHandler.send_order`, `main_loop` | login check, balance for ladder/veto/limits |
| `terminal_info` | `resilience.check_connection_and_freshness` | broker-connected flag |
| `symbol_info` / `symbol_select` | startup check, `RiskManager.is_spread_ok` | spread in **points** (gate 350; FVG leg 250) |
| `symbol_info_tick` | `DataFetcher.get_tick`, retry loop, `close_position` | price for order; refreshed each retry |
| `copy_rates_from_pos` | `DataFetcher` (M15 250 / M5 100 / D1 50) | index `-1` = forming bar, `-2` = last closed |
| `positions_get` | `DataFetcher`, `ExecutionHandler` | caps, close detection |
| `history_deals_get` | `get_todays_closed_pl`, `_record_closed_trades`, VI.3 tripwire | realised P/L incl. swap+commission |
| `order_send` | `ExecutionHandler` (open/close/modify), `protect_profit.py` | `TRADE_ACTION_DEAL`, IOC filling hard-coded |
| `login` | `scripts/daily_stats.py` | **hard-coded password (see S2)** |

Time model: MT5 bar `time` is treated as UTC (`_ist_hour` = `(t % 86400 + 19800)`); valid for Exness (server UTC) but silently wrong on any other broker.

### 1.3 Portfolio actually live (`src/strategies/portfolio_v5_core.py`)

| Leg | Magic | Rule (closed M15 bar) | Window IST | SL/TP (×ATR14) |
|---|---|---|---|---|
| `TREND_PULLBACK_V5` | 5001 | EMA13>EMA34, prior bar touched EMA13, close>prev close & >EMA13 | 11:30–21:30 | 0.5 / 1.5 |
| `BB_MEAN_REVERSION_V5` | 5002 | close outside BB(20,2σ) and RSI(14) <35 / >65 | 17:30–21:30 | 0.5 / 1.5 |
| `NVMR_TARGET_10_V5` | 5003 | z-score of close vs NY-session mean/σ beyond 1.7σ and RSI <35/>65 | 17:30–21:30 (hard-coded inside; object reports 0–24) | 0.5 / 1.5 |
| `FVG_NY_TIGHT_V5` | 5005 | unfiltered 3-bar fair-value gap, pullback inside gap within 5 bars | 17:30–21:30 | 0.5 / 1.5 |

Highlander rank: NVMR 6 > BB 5 > FVG 2 = TrendPullback 2 (arbitrary, not derived from data).
Sizing in practice: `SizingLadder` → **0.01 lot**, ≤2 positions at $100–$800, then risk_rules caps layered on top.

### 1.4 Git / delivery state
`master` is **14 commits ahead of `origin`**, 8 files modified and uncommitted (`main_loop.py`, `resilience.py`, 5 scripts, `.bat`). CI (`.github/workflows/ci.yml`) runs pytest on Linux with an MT5 stub. `.env.local` is correctly git-ignored.

---

## 2. Findings (ranked)

Severity: **C**ritical = invalidates the conclusion the project is built on · **H**igh = real money/loss or blind-spot risk · **M**edium · **L**ow.

### 2.1 [C1] Backtest evidence is mostly coarse-resolution — and coarse resolution is optimistic

* `research/data/XAUUSDm_M1.manifest.json`: M1 covers only **2026-07-02 → 2026-10-13** (100,000 bars = the per-call cap). M15 covers 2022-07 → 2026-10. So ≈ 96 % of the "4.2-year" test has no M1.
* In that case `BacktestEngine.run` falls back to the M15 bar (`engine.py:856-861`) and a new position is first walked on the **next** bar (`engine.py:953-960`, entries happen later in the same iteration at `:1084`) — the 15-minute bar in which a 0.5×ATR stop is most likely to be hit is never tested against the new position.
* Tell-tale in the ledger: median trade life = **1.0 "minute"** (it is one bar), 2,097 ambiguous trades, and monthly trade count jumps from ~150 to ~560 exactly when M1 begins (Jul-2026), with PF falling from 1.2–1.8 to 0.80–1.08 (Aug 0.798, Sep 0.879).
* **A/B I ran** (same window 2026-07-06 → 10-13, same 4 live legs, `realistic_ecn` costs, 0.01 lot, $10k start so ruin can't truncate; script in the session scratchpad):

| Resolution | Trades | Win % | PF | Net |
|---|---|---|---|---|
| M1 fills | 470 | 25.1 | **0.926** | −$115 |
| Coarse M15 | 468 | 32.9 | **1.375** | +$523 |

  Breakeven win-rate for 1:3 payoff is ≈ 26.4 %. At realistic resolution the system sits **at or below breakeven**. This is one 3-month window (wide error bars), but the *paired* difference on identical bars is the point: coarse resolution adds ≈ +0.45 PF.
* Consequences: PF 1.112/1.141 (4 yr), holdout PF 1.30, Oct-3→14 "PF 2.02", Monte-Carlo ruin (48.6 %), walk-forward — all inherit this bias. README claim "validated tick/minute execution" is not true for most of the data.

**Fix**
1. Backfill M1 (or ticks) in pages with `copy_rates_range` across the full window; if the broker only keeps N months, say so and treat everything before as *coarse, unvalidated*.
2. Until then, make the engine conservative in coarse mode: also walk the entry bar (stop-first on ambiguity), `engine.py` `_walk_minute` call before the `continue`.
3. Make `validation_ledger.record` refuse results whose M1 coverage of the window is < ~90 %, and print coverage in every report.
4. Treat the demo forward test (≥ 8 weeks, stated in `REAL_MONEY_READINESS` I.9) as the primary evidence; compare live vs M1-backtest weekly (`weekly_divergence_check.py` exists — it needs the log fixes in H5).

### 2.2 [C2] The validation gate validates a label, not the traded configuration

* `scripts/export_final_backtest.py:102` — `SystemConfig.from_live()` is recorded with whatever result just ran. Any run with PF ≥ 1.10 unlocks live trading for the *current* code, regardless of what the engine simulated.
* The ledger entry for the **currently live fingerprint `14b5467a4f969b25`** cites `simulate_4leg_portfolio.py`, which is **not in the repo and never appeared in git history** → the evidence is not reproducible.
* The fingerprint encodes `fixed_lot_size=0.02` and `max_total_volume=0.04`, but live trades **0.01** (ladder). It also reports NVMR's session as `0–24` while the strategy trades only 17:30–21:30, and `edge_trigger=True` for TrendPullback although nothing consumes it.
* `risk_rules_enforced=True` is stored in the record, but the engine does not simulate `risk_rules` at all.

**Fix**: record with `SystemConfig.from_engine_config(...)` from the *actual* `EngineConfig`; make the fingerprint include every behaviour in §2.3; commit the runner script; add a test that fails when a live-only gate exists that the engine does not implement (diff the gate list).

### 2.3 [H1] Live-only behaviour that no backtest has seen

| # | Behaviour | Where | Observed effect |
|---|---|---|---|
| a | **D1 intraday override**: flips bias to the live day's direction when the live D1 move ≥ **1.0×** the median |Δclose| (uncommitted change, was 2.0×). "ATR" here is a median close-to-close, not ATR | `main_loop.py:417-434` | Oct 15: BUY blocked at 20:20:24, bias flipped, BUY fired 20:20:41 → −$4.43; again 21:00 → −$4.44. Bias "flaps" intraday and lets counter-trend longs through exactly where the validated gate (daily close only) would block them |
| b | Skip all evaluation 15:30–17:30 IST (`LONDON_NY_OVERLAP`) | `main_loop.py:448`, `risk_manager.py:207-222` | Only TrendPullback is affected (other legs start 17:30). Backtest bucket for this slot was −$732 / PF 0.78, so skipping probably *helps*, but it is unvalidated |
| c | FVG leg `max_spread_pts = 250` | `portfolio_v4.py:192` | Spread median rose 200 → 240 pts; last 90 d **45 %** of NY-window bars are >250 (last 30 d: 20 %). Engine ignores per-leg caps → many FVG signals live are dropped that the backtest takes |
| d | `risk_rules` (ENFORCE=True): 3 % daily cap and **2 losing trades/day** below $400, 3-loss 4 h pause, 5-loss stop-day, week 15 %, month 25 %, **peak-DD 30 % hard halt** | `risk_rules.py`, `main_loop.py:786-800` | Oct 15: 2 losses ⇒ day done. Validated max-DD is 22–34 %, so the 30 % hard-halt will trip in "normal" conditions and needs a manual reset (no tool/procedure) |
| e | `protect_profit.py` closes green trades on giveback (peak ≥ $6 → ≤ $1) or "clean reversal" at ≥ $0.5 profit | `scripts/protect_profit.py` | Never simulated; same family as the trailing logic the project measured at PF 0.592. Thresholds were set for 0.02 lot. Also owns `positions.txt` that the monitors read |
| f | News filter ±15 min | `news_filter.py` | Not in engine; reasonable, but see M8 |
| g | `SizingLadder` lots 0.01 vs engine fixed 0.02 | `sizing_ladder.py` | Realised $ ≈ half of every ledger number; risk/trade ≈ 2.4 % of $186 |
| h | Order never placed on the bar if blocked by caps/veto — `last_fired_candle` is set anyway | `main_loop.py:549,557` | Engine keeps retrying within the bar; live forfeits the signal |

Live frequency evidence: 22 closed trades in the 13 trading days since logging began (≈ 1.7/day, +$23, PF 1.6 — a sample far too small to conclude anything) versus ≈ 8/day in the 4-year backtest.

**Fix**: port a–h into the engine as switches, run each A/B at M1 resolution, keep only what helps, delete the rest. Remove or properly define (true ATR, closed-bar only, hysteresis) the D1 override *before* trusting live results — as built it injects noise into the one filter the research says matters.

### 2.4 [H2] Secrets

* **S1 — Telegram bot token in pushed git history.** Present in commits from `6544e16` (2026-10-04) until removed by `6a27858` (2026-10-11); both are ancestors of `origin/master` (repo `github.com/rohith95-p/trading-platform`; I could not check visibility — `gh` is not installed). Files: `AWS_EC2_SETUP_GUIDE.md`, `START_MONDAY_CHECKLIST.md`, `THE_PLAN.md`. **Revoke it now** (BotFather → `/revoke`), put the new one only in `.env.local`. Rewriting history is optional; revoking is mandatory.
* **S2 — plaintext MT5 password** typed into the *uncommitted* `scripts/daily_stats.py:166` (the committed version had a redaction placeholder). Don't commit it; read from `MT5_PASSWORD` like `check_account.py`; since it has been written to disk in a tracked file, change that demo password.
* **S3** — `.env.local` holds unrelated production-type keys (Supabase service key, Google OAuth secret, Alpaca, NVIDIA) in the same folder as a bot that spawns subprocesses and ships logs. Keep the trading project's env file to the 3–4 variables it needs.
* `resilience.EXPECTED_LOGIN` defaults to the demo login; when you move to a real account you must change it (it will fail closed, which is correct).

### 2.5 [H3] Supervision / uptime

* At 00:28 IST Oct 16 **no `python` process is running** (only `terminal64.exe`); last heartbeat 2026-10-15 22:00:45.
* Task `UltraCoreBot` (daily 05:55 IST): `LastRunTime` 14-Oct 16:35, `NextRunTime` 16-Oct 05:55, `LastTaskResult` **0x800710E0** (typically a power/logon *Condition* refusing the start — e.g. "only on AC power" / "only when user is logged on"). It did **not** run on Oct 15.
* `alerts.log` has nothing between Oct 14 22:24 and Oct 15 18:23 → ≈ 20 h with no bot and no alert (the whole London session).
* Oct 14 22:23 "main_loop crashed (attempt 1/3)": the alert contains only INFO lines, not a traceback; cause unknown (could have been your restart for the uncommitted edits). The watchdog's snippet logic reads `main_loop.log`, but a manually started bot writes only to the console, so the next crash will have no traceback at all (`main_loop.log` last written Oct 14 22:24).
* `positions.txt` (used by hourly monitor/quick_status) is written by `protect_profit.py`, so those "status" views go stale if that process dies.
* PC sleep/hibernate is the likely root cause (Windows 11 Home, UserModePower events at 00:24).

**Fix**: task settings → "Run whether user is logged on or not", uncheck AC-only/stop-on-battery, "Run as soon as possible after a missed start", "Wake the computer"; `powercfg` never-sleep on AC; set `ULTRA_HEARTBEAT_URL` (healthchecks.io dead-man alert fires when pings stop); preferably move to the AWS VPS you already documented. Add a `RotatingFileHandler` to `main_loop` so logs exist however it is started; log only on change for the per-minute `D1 GATE` and "blocked" lines (log is 260 KB in two days, the same blocked signal repeats ~15×/candle).

### 2.6 [H4] Dead safety net: VI.3 rolling-PF tripwire
`main_loop.py:686` filters deals on magics `{3011,3012,3013,3014,3022}` (old portfolio). Live magics are 5001–5005, so the 30-trade PF alarm can never fire. **Fix**: derive magics from `PORTFOLIO` at runtime.

### 2.7 [H5] The trade record can't be trusted for reconciliation
* `trade_log.order(... lots=FIXED_LOT_SIZE)` records **0.02** while the executor sends **0.01** (`main_loop.py:823,839` vs `execution_handler.py:153`).
* `retcode`/`ticket` are always `null` for real orders: `send_order` returns a `TradeRecord` (has `ticket`, no `retcode`/`order`), so `getattr(result,"retcode")`/`"order"` fail; and the post-fill entry alert block at `main_loop.py:851` never runs (the executor sends its own).
* An "order" event is logged even when `send_order` returned `None` (veto/blocked/failed) → the log can show orders that never existed.
* `closed` events carry `strategy=""`; per-leg live attribution is impossible. `strategy_name = deals[0].comment` is also what the alert prints.
* **Tests write to the real log directory** (`TEST_STRATEGY`, price 2652.5, magic 5001 appear in `logs/trades/2026-10-1x.jsonl`). My own pytest run added two such lines; I removed that file (it contained only those two lines).

**Fix**: return a result object with `retcode/order/lots`; log from inside `send_order`; pass `strategy` through; point `LOG_DIR` at a temp dir under pytest.

### 2.8 Medium
* **M1 Two sizing ladders** (`sizing_ladder.py` vs `risk_rules.SIZING_LADDER`) disagree; README says "<$200 → 1 position", code allows 2 at $100–$200. One source of truth needed. Startup banner still prints "Lots: FIXED 0.02 | Max exposure 0.04".
* **M2 Relative paths** (`logs/risk_state.json`, `logs/cooldown.json`, `research/validation_ledger.json`, `docs/plans/news_calendar.json`, `logs/trades`): correct only if CWD = repo root. Started from anywhere else, breaker state silently forks. `resilience.py` already has `_ROOT`; use it everywhere.
* **M3 Hard-halt reset** has no documented/CLI path; ring-fence formula contains `milestone * 0.0` (dead term).
* **M4 False close on transient MT5 failure**: `positions_get` returning `None` becomes `[]`, so every known ticket looks "closed"; `history_deals_get` then returns only entry deals ⇒ `pl = 0` ⇒ recorded as a win (streak reset) and a bogus "TRADE CLOSED $0" alert (`main_loop.py:610-640`). Distinguish `None` from `()`; skip when no OUT deal exists.
* **M5 Order sending**: no `trade_stops_level`/freeze-level check, no `order_check`, `ORDER_FILLING_IOC` hard-coded (read `symbol_info.filling_mode`), SL/TP computed once from the first tick and not re-based after retries, `DONE_PARTIAL` treated as failure. Deviation 30 pts against a $4.4 stop is fine, but a fast market can move SL/TP distances.
* **M6 Freshness check** (`resilience.py:194`) treats a >25-min-old candle as stale; on holidays/maintenance this triggers reconnect/alert spam (every 5th failure).
* **M7 NVMR statistics**: session mean/σ are computed from as few as 4 closes *including the current bar*; with n=4 the largest attainable |z| is 1.73, n=5 → 2.0, so the 1.7σ trigger fires on almost any one-sided drift early in the session. Trade count swings 69 ↔ 780 depending on whether other legs occupy the 2 slots (the 6-leg vs 4-leg ledger entries) — i.e. the leg's results are portfolio-path-dependent.
* **M8 News calendar**: ends 2026-12-22 and fails open; hard-coded FOMC dates (Nov 5, Dec 16) look wrong versus the Fed's published 2026 schedule (I recall Oct 27–28 and Dec 8–9 — **verify**), though FOMC times (18:00/19:00 UTC) fall outside your 06:00–21:30 IST window anyway; the events that *do* hit your window (PPI, jobless claims every Thursday 12:30 UTC, ISM, ADP) are not listed.
* **M9 DST drift**: sessions are fixed in IST. UK DST ends 2026-10-25, US 2026-11-01 → "NY morning" shifts one hour relative to the actual NY open and to 13:30 UTC data. Re-check leg performance after the change; consider session definitions in exchange time.
* **M10 Repeated entries**: FVG (`edge_trigger=False`, TTL 5) and TrendPullback re-fire on the same setup; ledger shows **1,934 duplicate trades (21 %)** of the 6-leg run. Correlated stacking up to 2 positions in the same direction = one bet at 2× size.
* **M11 D1 gate parity**: engine builds the D1 view with a synthetic forming bar that duplicates the last close, so its EMA20 double-counts one close versus live's `[-2]` read — small but systematic.

### 2.9 Low / hygiene
* `portfolio_v4.py` still defines `TrendPullbackV5`, `BBMeanReversionV5`, … with **0.1 ATR stops and the same names/magics** as the live classes (lines 452-516). Importing from the wrong module silently gives the retired config. Archive them. `portfolio_v5_6_leg.py` is now a shim whose name is wrong (it exports the 4-leg).
* Docs disagree: README header fingerprint `14b5…` vs §7 `17a0…`; the "Validated Performance Baseline" table (9,121 trades, PF 1.112, DD 33.88 %) is the **6-leg** run presented as the 4-leg live config; "Recent Live Holdout Oct 3–14" is a **backtest**, not live; test count says 56/55, actual 70; REPO_GUIDE (2026-09-17) lists scripts that don't exist (`aug_5legs`).
* Docstrings claim WR 65–74 % / PF 1.4–2.2 for LARS/NVMR/PDHLR/LKOCS — never reproduced; delete or label as hypotheses.
* Unused/legacy: `FIXED_LOT_SIZE`, `MAX_TOTAL_VOLUME`, `edge_trigger` on TrendPullback, `src/risk` shim, `setup.py` shim, ~25 archived scripts; `LARS`/`LKOCS` unused.
* 8 uncommitted files with LF/CRLF warnings; 14 unpushed commits (so the secret-bearing commits are on GitHub but newer fixes are not).
* Tests (70, all passing) cover units and some lookahead, but nothing asserts **engine↔live parity** or `main_loop` gating order — which is where every material divergence above lives.

---

## 3. Strategy-by-strategy assessment

| Leg | What's sound | Problems | Recommendation |
|---|---|---|---|
| TREND_PULLBACK_V5 | Causal, simple, uses closed bar | 55 % of all trades, PF 1.089 even on coarse data; condition "prior bar low ≤ EMA13" is true on most bars in a trend, so it fires almost continuously; `edge_trigger` declared but not implemented; 20 % of its window skipped live | Bench until it shows PF > 1.15 at M1 resolution; if kept, add a real edge-trigger and a min-ATR/trend-strength filter |
| BB_MEAN_REVERSION_V5 | Best PF in both ledger runs (1.32 / 1.43), fewest trades | Counter-trend inside a trend-gated system; session-concentrated (17:30–21:30); sample 750–1,440 trades, all coarse | Keep as the research focus; re-test at M1; check news-hour clustering |
| NVMR_TARGET_10_V5 | Idea (fade extremes in NY) is plausible | Small-n z-score artifact (M7); trade count path-dependent; "Target 10" naming leftover; object reports wrong session | Use fixed lookback (e.g., last 24 bars, excluding the current bar) and re-validate; fix fingerprint session |
| FVG_NY_TIGHT_V5 | Detector is causal and well-reasoned | Class is called "LiquidityFiltered" but runs `baseline` (unfiltered); 45 % of recent bars exceed its live spread cap; repeats on same gap; tightest edge margin (PF 1.11) | Decide: either backtest with the live spread cap, or drop the cap and size for spread; add per-gap one-shot |

Portfolio-level: payoff 2.8 with 28.5 % win-rate leaves a **2.1-point margin over breakeven** (ledger: `win_rate_margin 2.12`). Median spread has risen ≈ 20 % over the history, and slippage in the engine is 0–20 pts on stops. That margin can disappear with ordinary cost drift. Highlander ranks are arbitrary; with a max of 2 same-direction positions the book is effectively one correlated bet.

---

## 4. Prioritised fix plan

**Today (≤ 1 h)**
1. Revoke the Telegram token; issue a new one into `.env.local` only. Remove the password from `scripts/daily_stats.py` and rotate it.
2. Fix Task Scheduler conditions + disable sleep; start the bot; set `ULTRA_HEARTBEAT_URL`.
3. Revert (or switch off) the D1 intraday override until it is backtested.

**This week**
4. Fix H4/H5 (tripwire magics, order/closed logging, tests writing to live logs) — small, mechanical, high value.
5. Backfill M1/ticks; make the engine walk the entry bar in coarse mode; re-run the 4-leg portfolio and holdout at M1 resolution. Expect PF to drop; decide on legs from *those* numbers.
6. Port the live-only gates (§2.3) into the engine; record the ledger from the real `EngineConfig`; commit the runner.
7. Unify the sizing ladder; absolute paths; rotating log file; commit + push the uncommitted work.

**Before any real money**
8. ≥ 8 weeks of *uninterrupted* demo with weekly live-vs-backtest divergence report; define the pre-agreed stop (e.g., PF < 0.8 over 30 trades *must* halt — currently the tripwire only logs).
9. Written reset procedure for risk-rules hard halts; decide whether a 30 % peak-DD kill is compatible with a 22–34 % backtested DD.
10. Re-validate across the DST change (Oct 25 / Nov 1) and refresh the news calendar for 2027.

---

## 5. What I verified vs. what I inferred

Verified directly: file contents and line refs above; test run (70 passed); ledger contents; data manifests (M1 coverage, spread statistics computed from `XAUUSDm_M15.npy`); scheduled-task state; absence of a running `python` process; git history for secrets (token regex search; password literal search); the A/B backtest.
Inferred / not verified: *why* the PC stopped the bot (sleep is likely, not proven); the cause of the Oct 14 22:23 "crash"; the real 2026 FOMC dates (from memory — please check); whether the GitHub repo is public; the exact semantic of `0x800710E0` for your task configuration.
Not covered line-by-line: `src/research/candidates*.py` (research only, 2.9k lines), archived scripts, and the research-only strategies not in `PORTFOLIO`.

---

## 6. Addendum (2026-10-16, later): corrected-engine results

Engine fix: `EngineConfig.walk_entry_bar_coarse` (default True) now tests a new position against its own entry bar when no M1 exists. 0.01 lot, `realistic_ecn` costs. Tools: `scripts/research/leg_solo_corrected.py`, `scripts/research/screen_is_oos.py`.

| Run | Trades | Win % | PF | Net |
|---|---|---|---|---|
| 4 legs, 2022-08→2026-07, old engine | 6,711 | 29.6 | 1.266 | +$2,733 |
| 4 legs, same, corrected engine | 6,776 | 22.1 | **0.883** | **−$1,340** |
| 4 legs, 2026-07→10, M1 fills | 470 | 25.1 | 0.926 | −$115 |
| 4 legs, 2026-07→10, corrected coarse | 470 | 24.3 | 0.876 | −$196 |

(Corrected coarse agrees with true M1 within noise — the fix removes the bias.)

Per leg, solo, corrected engine:

| Leg | 2022-08→2026-07 PF (n) | 2026-07→10 M1 PF (n) |
|---|---|---|
| TREND_PULLBACK_V5 | 0.861 (3,835) | 0.758 (259) |
| BB_MEAN_REVERSION_V5 | 0.855 (1,159) | 1.748 (69) |
| NVMR_TARGET_10_V5 | 0.835 (650) | 2.158 (25) |
| FVG_NY_TIGHT_V5 | 0.972 (2,013) | 0.806 (155) |

Replacement search: 322 candidates (v1+v2 libraries), tier-1 screener (tests entry bar, stop-first), split IS 2022-07→2024-12 / OOS 2025-01→2026-10. **0 of 320 reach PF ≥ 1.15 in both halves**; only 1 reaches ≥ 1.05 in both (XV2-180, daily-bias pullback NY: IS PF 1.05, OOS 1.11). With 320 tests that is within what chance produces. Only 7 % of candidates were profitable in-sample versus 32 % out-of-sample (2025-26 favoured gold trends).

### 6.1 New edge classes (scripts/research/screen_new_classes.py)

Pre-registered, IS = start→2024-12, OOS = 2025-01→2026-10, net of spread, $ per 0.01 lot.

| Class | Result |
|---|---|
| Time-of-day drift (144 bucket×horizon tests) | 2 buckets significant in-sample (chance ≈ 1.8). OOS pooled PF 1.14, t = 1.6 → not significant; both are 04:30/06:00 IST, outside the trading window |
| H4/H1 Donchian trend (4 variants) | Inconsistent: H4 20/10 IS 1.03 / OOS 1.36; H4 55/20 1.05 / 0.95; H1 100/50 1.28 / 1.90 (n=59, t 1.7); H1 200/100 1.24 / 0.98. Only H1 100/50 is positive in both, weakly, and its trades are multi-hour with stops that are large relative to a $186 account at 0.01 lot |
| D1 time-series momentum (3 lookbacks) | IS PF 1.00–1.14 and OOS 1.05–1.21 versus buy-and-hold 1.15 / 1.15: it is gold's trend beta, not timing skill (t ≤ 1.4) |

Conclusion: no new class clears an evidence bar that survives multiple testing. The only item worth a follow-up is slow H1 trend following (H1 100/50), as a hypothesis for the forward test, not as a deployable edge.

### 6.2 H1 Donchian 100 through the corrected engine ($186 start, 0.01 lot, `realistic_ecn`, D1 gate on, live trading window)

Strategy: `src/strategies/h1_donchian.py` (not in PORTFOLIO). Stops are in M15-ATR14 units (≈ $9 at current prices → SL 1.5× ≈ $13). Runner: `scripts/research/h1_donchian_engine.py`.

| SL/TP (×ATR) | Period | Trades | Win % | PF | Net | Min balance | Max DD | Avg loss |
|---|---|---|---|---|---|---|---|---|
| 1.5 / 4.5 | 2022-08→2026-07 (coarse, corrected) | 417 | 27.6 | 1.15 | +$293 | $60.5 | **$243 (49 %)** | $6.4 |
| 1.5 / 4.5 | 2026-07→10 (M1) | 31 | 29.0 | 1.03 | +$9 | $155 | $195 (56 %) | $14.7 |
| 3 / 9 | 2022-08→2026-07 | 51 | 15.7 | 0.36 | −$177 | $9 (ruin) | 95 % | $6.4 |
| 3 / 9 | 2026-07→10 (M1) | 27 | 40.7 | 1.80 | +$364 | $131 | $190 (29 %) | $28.4 |
| 6 / 18 | 2022-08→2026-07 | 32 | 21.9 | 0.33 | −$181 | $5 (ruin) | 97 % | $10.7 |
| 6 / 18 | 2026-07→10 (M1) | 4 | 0 | 0 | −$196 | <$0 | >100 % | $49.1 |

Reading: the only stop size a $186 account can survive (1.5×ATR) gives PF 1.15 / +$293 over 4 years (~$0.30/day) with a 49 % drawdown that came within $10 of the $50 trading floor — not tradable with real money. Wider stops (the ones the Donchian logic prefers) exceed what 0.01 lot on this balance can absorb. The recent M1 3/9 result (PF 1.80, n=27) is too small to count and the same setting ruined the account in the 4-year run. Because stop distances are in ATR units and gold has doubled, today's $ stop is roughly twice that of 2022–23, so risk per trade is rising with price.
Caveats: single leg only; `risk_rules` caps not simulated; strategy needs ~530 M15 bars versus the live 250-bar fetch.

### 6.3 Prop-account view of H1 Donchian (scripts/research/prop_r_series.py, prop_challenge_sim.py)

Size-independent test (R-multiples, corrected engine, 2022-08→2026-10, costs incl. spread; swap not in R):

| Variant | Trades/yr | PF(R) | Expectancy | IS ≤2024 PF | OOS 2025+ PF | Max R-drawdown | Worst losing streak |
|---|---|---|---|---|---|---|---|
| ch100 SL2/TP6 | 107 | 1.20 | +0.14R | 0.91 | 1.58 | 35R | 10 |
| ch100 SL3/TP9 | 100 | 1.30 | +0.19R | 0.81 | 2.07 | 36R | 13 |
| ch100 SL4/TP12 | 94 | 1.35 | +0.21R | 1.03 | 1.81 | 26R | 18 |

By year (SL3/TP9): 2022 PF 0.54, 2023 0.89, 2024 0.86, 2025 1.91, 2026 2.41. The whole profit is 2025-26, when gold went ~$2,600 → ~$4,160. It is trend beta, not a stable edge: flat-to-negative in 2022-24.
Rolling-start challenge (+8 % target, −10 % static DD): ~85 % pass at 0.5 %/trade, but windows overlap heavily, are dominated by the 2025-26 run, and a 26-36R drawdown is 13-18 % at 0.5 % risk — above a typical 10 % limit.

### 6.4 Is SL 0.5 / TP 1.5 the problem? (scripts/research/geometry_sweep.py)

Solo live legs, corrected engine, 0.01 lot, summed net of 4 legs:

| SL/TP (×ATR) | 2022-08→2024-12 | 2025 | 2026 (to Oct 13) |
|---|---|---|---|
| 0.5 / 1.5 (live) | −$1,297 | −$254 | −$51 |
| 1.0 / 2.0 | −$1,175 | +$298 | +$208 |
| 2.0 / 4.0 | −$4,426 | +$1,691 | +$886 |

Wider stops help in the 2025-26 trend and lose heavily before it. No geometry makes the legs profitable across all three periods. 2.0×ATR ≈ $18 per 0.01-lot loss, ~10 % of a $186 account.
