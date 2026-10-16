# Final audit — Ultra Core (2026-10-16)

Scope: whole repository incl. live demo bot, backtesting, research, new multi-asset/portfolio/Atlas modules.
Method: independent code reading, controlled experiments, official-source rule capture, 316 automated tests.
Nothing here enables live trading; no order was sent by any audit or research step.

## 1. Verdict
**Not ready for real money.** The engineering shell is decent and now has a corrected backtester, multi-asset cost
models, a portfolio risk layer and a verified-source Atlas rule engine. But **no strategy tested shows a statistically
significant, repeatable edge after costs**, the live gold portfolio loses money on the corrected engine, and several
operational/validation blockers remain (§10).

## 2. Repository changes (this engagement; 21 local commits, see `git log`)
- Corrected backtest engine (entry-bar test in coarse mode; per-asset costs/margin/P&L; weekend trading for crypto).
- `src/instruments/` metadata registry (6 instruments), `cost_model_for`, `risk_lots`.
- `src/portfolio/risk.py` — pure portfolio risk layer (90 tests).
- `src/atlas/rules.py` + `config/atlas_access.json` — Atlas Access rules with sources/status (108 tests).
- Live-bot fixes (tripwire magics, order/closed logging, absolute paths, test isolation), password removed from a script, broken shim fixed.
- Research: scripts, pre-registered registry, data coverage report, new strategy candidates.
- README rewritten to match reality.

## 3. Strategies researched
Gold: 42 strategy classes (live, retired, archived, new), 322 candidate rules, SL/TP geometry sweeps, walk-forward geometry selection, H1 Donchian family.
Multi-asset: 13 H1 hypotheses × 6 instruments (78 tests); 61 slow D1/H4 tests (momentum, EMA cross, Donchian, ER-gated, carry proxy, cross-sectional, portfolios).

## 4. Accepted / rejected / awaiting evidence
| Status | Items |
|---|---|
| Accepted | **none** |
| Awaiting evidence | XAUUSDm H1 Donchian-100 (best prop candidate, regime-dependent); XAUUSDm V1a squeeze; ETHUSDm 60d momentum; cross-sectional momentum 60d portfolio |
| Rejected | live legs as configured (PF 0.88); all Bollinger/RSI fades on crypto/EURUSD/USDJPY (significantly negative); USDJPY squeeze/carry proxy; EUR/GBP trend, pullback, breakout, momentum; NY/Asia/London candidates that failed IS/OOS |

## 5. Verified performance (corrected engine unless stated)
| Item | Result |
|---|---|
| Live 4 legs, 0.01 lot, 2022-08→2026-07 | PF 0.88, win 22 %, −$1,340 (old engine said PF 1.27, +$2,733) |
| Live 4 legs, 2026 only from $186 | PF 0.74, account $0; without TrendPullback PF 1.09 |
| Per leg 4-year PF | TrendPullback 0.86, BB 0.86, NVMR 0.84, FVG 0.97 |
| Demo account (broker history), since 2026-09-28 (V5 legs) | 34 trades, +$6.13, PF 1.11, 9 days; best day 43 % of profit |
| H1 Donchian-100, 2023-08→2026-10 | PF 1.55 (2023-24: 1.01–1.27; 2025-26: 1.81–2.07), max DD 15–17 R |

## 6. Development / validation / holdout (Stage 1 and 1b)
Splits: DEV → 2024-12-31, VALIDATE 2025-01→2026-06, HOLDOUT 2026-07→end (read once).
Multiple-testing: min BH q = 0.98 (slow screen); 0/75 significant positives, 5/75 significantly negative (H1 screen).
The July–Oct 2026 holdout is negative for most trend/momentum variants.

## 7. Cost and execution stress
Spread/swap are broker values; geometry sweep shows 0.5×ATR stops pay ~5 % of risk in spread; widening stops helps only in 2025-26 and loses −$4.4 k (2022-24) at 2×ATR. Slippage beyond spread, latency and partial fills are **not** modeled in the research screens (only 20-pt slippage in the `realistic_ecn` engine runs). Crypto swap units unverified.

## 8. Portfolio-level risk assessment
Layer exists and is tested (stop risk from contract specs, USD/currency exposure, correlated groups, margin, stale data, kill-switch). It is **not wired into any live path**, and the live demo uses the older `risk_rules`/veto stack, which no backtest simulates. Defaults (5× net USD) are meant for larger accounts — a $100–$200 account at 0.01 lot would be denied.

## 9. Prop-firm (Atlas Access) compliance assessment
Rules captured from Atlas's own pages (retrieval 2026-10-16): evaluation 3 % target, 10 % trailing equity DD, 5 % daily; funded 6 % trailing equity, 3 % daily, 40 % best-day consistency, protector 2 %, news ±5 min, 3-minute hold, margin 80 %, no weekend entries. **Unresolved:** exact daily-loss computation, written EA approval (pages conflict), gold symbol/leverage on the server, funded fee per size, first-payout split wording. The engine refuses to load with those unacknowledged. **No Atlas execution adapter exists.** Compliance cannot be claimed.

## 10. Remaining blockers (exact)
1. No strategy with demonstrated, significant, out-of-sample edge (corrected engine).
2. Validation gate is hollow: `scripts/export_final_backtest.py` records the live fingerprint for any passing run; fingerprint omits live-only gates; the script that produced the active fingerprint (`simulate_4leg_portfolio.py`) is not in the repository. (Left unchanged because fixing it would make the demo bot refuse to start until re-validated.)
3. Live-only logic never backtested: D1 intraday override (threshold 1.0), 15:30–17:30 IST skip, FVG spread cap, risk_rules, protect_profit.
4. Reliability: scheduled task failed (~20 h gap); the bot is currently not running; `main_loop.log` not written when started manually.
5. No live adapter for Atlas/other instruments; no broker reconciliation, stop verification or order-status audit beyond the gold demo path.
6. Atlas rule unknowns (§9); crypto margin/swap units; ETH spread gate and min-lot flags in the registry.
7. Security: Telegram bot token in pushed git history (revoke); an MCP process exposes an account login on its command line; `.env.local` holds unrelated production keys.
8. Environment: `scipy` missing from the venv (`src.research.metrics` does not import).
9. M1 history only from 2026-07 (gold), terminal bar cap 100k; `research/data/_staging/` holds fresher FX copies not swapped in.

## 11. Test results
316 passed (118 pre-existing + 90 portfolio-risk + 108 Atlas rules). Gold regression tests pin engine trade lists. Gaps: no engine-vs-live parity test, no integration test across loop → veto → order, no broker-failure simulation for Atlas.

## 12. Security findings
No secrets in the working tree or new commits (pattern scan). Findings above (#7); hard-coded password removed from `scripts/daily_stats.py`; credentials only via env.

## 13. Deployment instructions
Demo bot: `python -m scripts.watchdog` (or the scheduled task) with `.env.local` populated; kill switch = `STOP` file. For any new asset or the Atlas account: **do not** enable live execution until blockers 1, 2, 5 and 6 are closed; then build the adapter as a separate observe-only process that calls `PortfolioRiskEngine.check` and `AtlasRuleEngine.check_order` before every order.

## 14. Scores (0–10, separate)
| Dimension | Score | Basis |
|---|---|---|
| Architecture quality | 6 | clear separation, new pure risk/rule layers; live loop still monolithic with duplicated ladders and gold-specific constants |
| Research quality | 7 | pre-registered, split, multiple-testing aware, failures kept; narrow strategy families, tier-1 simulation |
| Backtesting credibility | 6 | entry-bar bias fixed, costs per asset, regression-tested; live-only gates and slippage not modeled, M1 history short |
| Statistical evidence of profitability | 1 | nothing significant; live legs negative; best idea regime-dependent |
| Execution readiness | 3 | gold demo path works; no reconciliation/verification, no Atlas/other adapters |
| Risk management | 6 | strong pure modules + live caps; not integrated, live caps unvalidated |
| Testing reliability | 7 | 316 tests, regressions pinned; no parity/integration tests |
| Operational readiness | 3 | uptime failure, hollow validation gate, credential exposure |

Verified facts vs hypotheses: §5–§6 numbers are measured; "H1 Donchian works" and "trend returns in 2027" are hypotheses; Atlas rules are verified-official only where `config/atlas_access.json` says so.

## 15. Commit and push status
Local commits only (see `git log`); **not pushed** since commit `8c0e982`. `DSA LAB.docx` is untracked and excluded.
