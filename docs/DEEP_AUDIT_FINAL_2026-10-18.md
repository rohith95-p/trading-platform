# Ultra Core — Deep audit, final state (2026-10-18)

Supersedes `FINAL_AUDIT_2026-10-16.md` (kept for history). Scope: the whole repository as it stands today (XAUUSD only).
Evidence base: code reading, 245 automated tests, controlled backtests on the corrected engine, a read-only reconciliation against the broker's real deal history, official-source rule capture (Atlas), and ~640 pre-registered or logged hypothesis tests.
Nothing in this audit sent an order; the live demo bot was not modified or restarted (it is not running).

## 1. Verdict
**A strong research laboratory and a weak trading product. Not ready for real money.**
No strategy in the repository has shown a statistically significant, repeatable edge after costs. The live 4-leg gold portfolio loses money on the corrected engine. The engineering shell (engine, risk rules, logging, tests, rule capture) is good and honest; the trading edge is absent.

## 2. What the system is (verified from code)
| Area | What exists |
|---|---|
| Live demo bot (`src/core`, ~4.2k lines) | 60 s loop on `XAUUSDm`; gates: lock, STOP kill switch, Friday flatten, spread, news ±15 min, daily loss, freshness; D1 EMA20 gate; legs TrendPullback, BB mean-reversion, NVMR, FVG (SL/TP 0.5/1.5 ATR, 0.01 lot via ladder); `risk_rules` ENFORCE=True; watchdog; separate `protect_profit.py` |
| Backtest engine (`src/backtesting`, ~2.9k lines) | M1/M15 replay, bid/ask spread, swap, D1 gate, live window, dedup; entry-bar test in coarse mode; **opt-in `live_parity` switches** (risk_rules, overlap skip, FVG cap, ladder, D1 override, protect_profit, entry delay) |
| Atlas rule engine (`src/atlas`, 0.8k lines + `config/atlas_access.json`) | Official Atlas Access rules with source URL, date and status per rule; refuses to load unresolved rules |
| Research (`scripts/research`, `research/registry`, `research/events`) | Pre-registered tests, registry, 220-event USD calendar, simulators (FvgGold, regime trend, EA31337 hypotheses) |
| Tests | 17 files, 245 tests, all passing; gold engine results pinned by regression tests |
| Size | 93 script files (~15.7k lines, mostly legacy research), 57 top-level scripts, 36 docs |

## 3. Backtesting audit (the central question)
**Defects found and fixed**
1. Coarse mode (M15 only, ~96 % of history) never tested the entry bar → inflated PF. Fixed (`walk_entry_bar_coarse`). Effect: live 4 legs 2022-08→2026-07 PF 1.27 → **0.88**.
2. Engine omitted live-only rules → ~2× trades vs live. Modelled as opt-in `live_parity`.
3. The validation ledger stamps the live fingerprint on any passing run (**still open**, see §9).

**Reconciliation against the broker (read-only, 2026-10-05..15, 18 real trades, +$23.40)**
- Engine (parity on) takes 17–24 trades, reproduces **15 of 18**, per-trade P&L correlation **r = 0.73–0.87** (≈ 1.0 without the worst pair); mean entry gap +$0.28 (noise).
- Same-config trades agree closely per trade (+10.49 vs +10.33, −3.90 vs −3.84).
- Residual: bot uptime on some days unknown, one 1-minute-bar ordering case, two Oct-15 buys explained by the D1 override at 1.0×.
- My earlier statement that the engine was "2× too generous on matched trades" was **wrong** (the gap came from the old 0.1×ATR-stop week); corrected.

**Confidence:** direction of conclusions — high. Exact dollar figures — roughly ±10–20 %. Sample for reconciliation — small.

## 4. Strategy results (corrected engine)
| Test | Result |
|---|---|
| Live 4 legs, 2022-08→2026-07, 0.01 lot | PF **0.88**, win 22 %, −$1,340 |
| Live 4 legs, last 2 years, 0.02 lot, $10k base | 3,359 trades, PF **0.95**, −$968, max DD 13 %, losing streak 24 |
| Same on a **$200** account at 0.02 lot | falls to **$29** by Apr 2025 (−86 %), PF 0.87 |
| 2026 only from $186 | PF 0.74, account reaches $0; without TrendPullback PF 1.09 (+$185) |
| Per leg (2-year, 0.02 lot) | TrendPullback PF 0.89 (−$1,045, 58 % of trades); BB **1.12** (+$151); FVG 0.99; NVMR 0.99 |
| Demo account, broker history since 2026-09-28 | 34 trades, +$6.13, PF 1.11 (too small to infer) |
| SL/TP geometry (sum of 4 legs) | 0.5/1.5: −$1,297 / −$254 / −$51 (2022-24 / 2025 / 2026); 2/4: −$4,426 / +$1,691 / +$886 — wide stops pay only in the 2025-26 rally |
| H1 Donchian-100 (SL4/TP12) | PF 1.56 (2023-08→2026-10; 1.27 in 2023-24, 1.81 in 2025-26), max DD 15R; ≈ +7.5 %/yr at bar-compliant risk; closest candidate but regime-dependent |
| Other best candidates | SQUEEZE_ASIA PF 1.29, SUPERTREND_EMA 1.13, BB at 2/4 geometry 1.15 |

## 5. Research record (what was tried and the outcome)
| Study | Trials | Outcome |
|---|---|---|
| Gold candidate library, IS/OOS | 320 | **0** reach PF ≥ 1.15 in both halves |
| 42 strategy classes (live, retired, archive, new) on 2026 | 42 | top: H1 Donchian 2.01 (64 trades); live legs 0.84–1.25 |
| Time-of-day drift, H1/H4 Donchian, D1 momentum | ~160 | no significant edge |
| Multi-asset (gold, EUR, GBP, JPY, BTC, ETH) H1 + slow D1/H4 | 139 | min BH q = 0.98; 5 significantly negative (fades) — code and data **removed** when project re-scoped to gold |
| FvgGold-EA (GitHub) | 1 repo | **rejected**: claimed +48.7 % at 0.01 lot is arithmetically impossible (fixed $4.50 stop / $6.75 target); our reimplementation DEV+VAL PF 0.82, holdout 0.63; EA jams with unexpired pending orders |
| EA31337-style SuperTrend / MA breakout / Pinbar | 6 | none passes; best PF 1.04–1.13 in 2025-26, < 1 in 2022-24 |
| Other external repos (8 + 3 + 7 reviewed) | — | none prop-ready; no working daily-loss/drawdown guard in any; borrowable ideas only (tick-value lot formula, stop sent with order) |
| Regime-conditional trend (trial #640, pre-registered, frozen commit d570fc4) | 1 | **closed**: DEV PF 0.79 (fails gate), VALIDATE 1.46 but 84 % of profit in one quarter, DSR 0.03; holdout 2 trades |

Pattern across everything: rules that look good do so in **2025–26 (gold's rally)** and fail in 2022–24.

## 6. Live system and operations
- **Not running** (last heartbeat 2026-10-15 22:00 IST). The Windows scheduled task (05:55 IST) did not start the bot after PC sleep; one ~20 h gap with no alert.
- Risk state: peak equity $186.14, 2 consecutive losses, no hard halt.
- Safety features present: single-instance lock, `STOP` file, server-side SL/TP, dedup keys, restart state, structured JSON-lines logs.
- **D1 gate (owner rule 2026-10-17, takes effect on next start):** a bearish daily trend always blocks buys; the intraday override may only tighten (bullish→bearish); a missing D1 bias fails closed. 10 tests.
- Live-only components not covered by the main research path: intraday override (threshold 1.0×, not backtested before), `protect_profit.py`, ladder concurrency, risk caps (now simulated only with `live_parity`).

## 7. Atlas Funded (prop-firm) readiness
Rules captured from Atlas pages (retrieved 2026-10-16): evaluation target 3 %, drawdown 10 % trailing equity; funded 6 % trailing equity, 3 % daily, 40 % best-day consistency, protector 2 %, news ±5 min, 3-minute minimum hold, margin 80 %, no weekend entries, 90 % split, first payout after 28 days.
**Unresolved:** exact daily-loss computation, written EA approval (pages conflict), gold symbol/leverage on the server, funded fee per size, first-payout split wording. The rule engine refuses to load until acknowledged. **No Atlas execution adapter exists.**
Simulated lifecycle (H1 Donchian): evaluation pass 91–95 %, but first-payout eligibility only 3–13 % because of the "3 profit days of ≥ 0.5 % per cycle" rule.

## 8. Security and hygiene
- Tracked tree and all new commits: no secrets (pattern scan clean). Hard-coded password removed from `scripts/daily_stats.py` (now env vars).
- **Open:** a Telegram bot token exists in older, **already pushed** git history; a trading-bot process exposed an account login on its command line; `.env.local` holds unrelated production keys; `scipy` is missing from the venv (`src.research.metrics` does not import).
- Repo state: 76 commits, **14 local commits not pushed** (by owner request), `DSA LAB.docx` untracked and unrelated, 0 TODO/FIXME markers in `src`, `portfolio_v4.py` still contains stale class names that shadow the live ones (import trap), two sizing ladders (`sizing_ladder.py` vs `risk_rules.py`), a ~1,000-line monolithic `main_loop.py`.

## 9. Findings register
| # | Severity | Finding | Status |
|---|---|---|---|
| 1 | Critical | No strategy with a significant out-of-sample edge | **Open** (fundamental) |
| 2 | Critical | Coarse-mode backtest inflation (entry bar skipped) | **Fixed** |
| 3 | High | Validation gate stamps the live fingerprint; fingerprint omits live-only rules; the script behind the active fingerprint is missing | **Open** (fix would block demo restart until re-validated) |
| 4 | High | Engine lacked live-only rules | **Fixed** (opt-in `live_parity`, reconciled) |
| 5 | High | D1 gate let counter-trend buys through (override flip / fail-open) | **Fixed** (not yet running live) |
| 6 | High | Uptime: scheduler failure, sleep, no dead-man alert | **Open** |
| 7 | High | Telegram token in public history; credential on a process command line | **Open** (owner decision: not revoked) |
| 8 | Medium | VI.3 tripwire watched wrong magics; trade log lots/retcode/ticket wrong; tests wrote to live logs; relative paths | **Fixed** |
| 9 | Medium | Broken `src/risk` shim; stale strategy names in `portfolio_v4.py`; two sizing ladders | shim **fixed**; others **open** |
| 10 | Medium | M1 data only since 2026-07 (terminal cap); reconciliation sample = 18 trades | **Open** (time fixes it) |
| 11 | Medium | News calendar for the live bot ends Dec 2026, fails open, omits PPI/claims/ISM | **Open** (historical calendar for research now exists) |
| 12 | Low | 93 legacy scripts, 36 docs, some stale/contradictory | **Open** |
| 13 | Low | Multi-asset code/data (forex, crypto) | **Removed** (history in git) |

## 10. Scores (0–10)
| Dimension | Score | Change vs 10-16 | Basis |
|---|---|---|---|
| Architecture quality | 6 | = | clean layers, rule engine separated; monolithic main loop, duplicated config |
| Research quality | **8** | +1 | pre-registered, frozen commits, multiple-testing counts, calendar from official sources, failures kept |
| Backtesting credibility | **7** | +1 | entry-bar bug fixed, reconciled to broker (15/18); small sample, short M1 history |
| Statistical evidence of profitability | 1 | = | nothing significant; live legs negative |
| Execution readiness | 3 | = | gold demo path works; no verification layer, no Atlas adapter |
| Risk management | 6 | = | solid rules and Atlas encoding; live caps not independently validated |
| Testing reliability | 7 | = | 245 tests, regressions pinned; no end-to-end broker-failure tests |
| Operational readiness | 3 | = | uptime, hollow gate, exposed credentials |
| Security | 4 | new | no secrets in tree; token in public history; process credential exposure |
| Documentation | 6 | +1 | README rewritten to match code; legacy docs remain |

## 11. Recommendations (priority order)
1. Treat the project as research infrastructure. **Do not fund a live or prop account on the current strategies.**
2. Fix the safety items independent of any strategy: validation gate records the settings actually run; scheduler/uptime with dead-man alert; process credentials; (owner decision pending) token revocation.
3. Keep the demo as a measurement instrument and run the reconciliation weekly as samples accumulate.
4. Only if new hypotheses are tested, keep the protocol: frozen rules in a commit, event/regime conditions defined in advance, deflated-Sharpe hurdle with the full trial count (now ≥ 640), history as a **falsification gate** and a 60–90 day frozen **forward test** as the real acceptance test.
5. Before any funded account: resolve the Atlas unknowns in writing (EA approval, gold symbol/leverage, daily-loss definition) and build an observe-only adapter that routes every order through the Atlas rule engine.

## 12. Verified vs unverified
**Verified:** test results (245 pass), engine reconciliation numbers, all backtest figures above (re-run), broker deal history, secret scans, Atlas rules as captured.
**Not verified / hypotheses:** that H1 Donchian or any candidate will work forward; exact uptime history of the demo bot before Oct 12; Atlas pages vs actual account behaviour; whether crypto/forex research conclusions would survive other brokers' data (removed from scope).
