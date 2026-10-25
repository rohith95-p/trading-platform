# Decisions log — Ultra Core

Every **owner decision** that shapes the live system or the research direction,
newest first. One row = one decision. This exists because the same questions
(the D1 gate especially) have been re-opened and reversed across sessions;
if it's decided, it's here, and it's not re-litigated without *new evidence*.

**Rules for this file**
- Only decisions the owner made (or explicitly ratified). Not findings — those
  live in `RESEARCH_LEDGER.md`.
- Each row: date, the decision, the evidence it rests on, and its type.
- Type: **RULE** (hard, enforced in code) · **CONFIG** (live leg/param choice)
  · **RISK-ACCEPTED** (a known-bad thing kept on purpose) · **PROCESS** ·
  **DIRECTION** (what to research next).
- To reverse a row: add a *new* row that says so and why. Never edit an old one.

---

| Date | Decision | Type | Rests on | Notes |
|---|---|---|---|---|
| 2026-10-14 | **Acknowledge residual ruin risk: Monte Carlo P(ruin) = 8.15% accepted pending account scaling.** | RISK-ACCEPTED | 10,000 bootstrap paths on 2,319 OOS holdout trades | 8.15% ruin probability ($100 balance / $50 floor / 2% risk) is substantially improved from 48.6%, but remains above institutional <1% standard. Flagged as residual small-account risk until capital scales past $300-$500. Circuit breakers (`DAILY_LOSS_LIMIT_PCT = 0.06`, `risk_rules.ENFORCE = True`) are required live mitigants. |
| 2026-10-13 | **Reconcile `MAX_CONCURRENT_POSITIONS = 2` as canonical limit across execution and risk.** | RULE | Small-account risk philosophy & validated 4-leg baseline | Canonical value 2 set in `src/core/execution_handler.py` and imported by `src/core/risk_manager.py`. Contradictory comment claiming 3 in risk manager removed. |
| 2026-10-13 | **Reduce default per-trade risk to 2% (`DEFAULT_RISK_PCT = 0.02`).** | RULE | Risk audit & ruin probability | 15% per trade risked ~45% in 3 consecutive losses; 0.02 is defensible setting for small accounts and dynamic sizing. `EngineConfig.risk_pct` also lowered to 0.02. |
| 2026-10-13 | **Fix duplicate-fill bug and default backtest engine to `dedup_per_candle = True`.** Order deduplication keyed on `(strategy_magic, bar_time, direction)` enforced before order send, persisted to trade log and `loop_state.json` across restarts. | RULE | Live audit (duplicate fills 2026-08-25 06:23:47 / 06:24:44 -$27.81/-$27.77) | Eliminates duplicate fills on identical closed candles while aligning backtest simulations with live execution. |
| 2026-10-13 | **0.1 ATR stop permanently retired; all live legs use 0.5 ATR SL / 1.5 ATR TP.** | RULE | Live audit & cost analysis | Spread ($0.20–$0.30) + slippage consumes >60% of a 0.1 ATR (~$0.35) stop immediately upon entry, making 0.1 ATR stops physically non-executable. Validated 0.5 SL / 1.5 TP config in `portfolio_v5_6_leg.py`. |
| 2026-10-13 | **Authoritative live portfolio is Portfolio V5 (4-Leg Pruned Core)** (`TREND_PULLBACK_V5`, `BB_MEAN_REVERSION_V5`, `NVMR_TARGET_10_V5`, `FVG_NY_TIGHT_V5`). The 2 drag legs (`PDHLR_STRATEGY_V5` PF 0.795, `NY_LIQUIDITY_EXPANSION_V5` PF 0.953) are retired to `src/strategies/archive/retired_v5_legs.py`. | CONFIG | 4-leg core backtest: PF 1.141, Net +$4,495.43, reducing MaxDD by 32% and unlocking NVMR concurrency slots. Validated fingerprint `14b5467a4f969b25`. | README, REPO_GUIDE, and test_config_integrity unified on 4-leg core. |
| 2026-09-17 | **Enable Risk Rules** (`risk_rules.ENFORCE = True`). The sizing ladder, cascading daily/weekly caps, and consecutive-loss circuit breakers are now active. | RULE | Implementation Plan T1.1 (aug_5legs passed with laddered config on 2-leg FVG setup) | Protects capital during the $177 to $1000 run. See GROWTH_PATH.md. |
| 2026-09-17 | **Remove EMASTACK from `PORTFOLIO_V4`.** Live config is now the 2-leg FVG combination (FVGNYTight + FVGNYSweepOrVoid). | RULE | Owner decision (overruling the 09-11 risk-acceptance) | Three independent validations (HYP-069, HYP-073) proved EMASTACK dragged the portfolio into I.1/I.3/I.7 gate failures. 2-leg configuration is significantly safer. |
| 2026-09-11 | **Keep `PORTFOLIO_V4` at 3 legs** (EMASTACK + FVGNYTight + FVGNYSweepOrVoid) live as-is. EMASTACK's risk-adjusted drag and its cannibalisation of FVG_NY_TIGHT through the shared 6% breaker are **accepted** in exchange for London-session coverage. | RISK-ACCEPTED | HYP-069 (EMASTACK net-negative solo; 3-leg loses on both test windows where 2-leg does not) | Same category as HYP-048 — a conscious risk bet, not a finding that 3-leg is safe. If the account draws down the week of 09-11, this is the named cause. Closed unless new evidence. |
| 2026-09-09 | **Keep the D1 EMA20 direction gate.** Intraday-trend gates (H4-structure, M15-structure) are rejected. | RULE | HYP-067 (d1_ema20 the only variant solvent + shallow-DD on recent M1; "no gate" blows the account) | Re-confirms the 2026-09-08 HYP-065 reversal of HYP-048. The gate is a drawdown reducer that earns its keep in hard regimes. |
| 2026-09-09 | **Static ATR take-profit stays.** Structural / swing-pivot TP is rejected. | RULE | HYP-068 (lookahead-free structural TP marginally hurts every leg; the "PF 4.3" claim was vectorised-backtest lookahead) | `structural_tp` flag added to `BacktestEngine` (default off) as an A/B tool only. |
| 2026-09-09 | **Re-add `EMAStackLondonTight` to `PORTFOLIO_V4`** → 3 legs, for non-NY session coverage. | CONFIG | Owner call; London-coverage rationale | Superseded in effect by the 2026-09-11 risk-acceptance row above once HYP-069 quantified the cost. |
| 2026-09-09 | **Streak breakers wired to live closes, run in shadow** (`risk_rules.ENFORCE = False`). | PROCESS | HYP-053 (rulebook coded); `record_trade_result()` was never being called | State in `logs/risk_state.json` is now real. Enforcing waits on the laddered config being backtested + recorded. |
| 2026-09-08 | **`PORTFOLIO_V4` = 2 legs** (FVGNYTight + FVGNYSweepOrVoid). `FVGNYSweep` / `FVGNYVoid` removed as dead (0 trades, Highlander subsets). `FVGAsiaSweep` benched. | CONFIG | HYP-062, portfolio_v4 leg-trim | The 2-leg run == the old 4-leg run exactly. |
| 2026-09-08 | **Re-enable the D1 EMA20 gate** (reverses the 2026-09-03 "gate OFF"). | RULE | HYP-065 (trading FVG without the gate in high-vol Aug 2026 → terminal drawdown) | |
| 2026-09-07 | **Adopt the FVG liquidity filter** (`sweep_or_void`): only trade gaps with a preceding sweep or a gap > 0.5×ATR200. | CONFIG | HYP-059 / HYP-060 (filter beats plain FVG on drawdown + ruin in every session) | The filter is the edge; the unfiltered gaps it rejects are net-negative. |
| 2026-09-06 | **Starting capital = $100; first-phase per-trade risk explicitly accepted in writing.** | RISK-ACCEPTED | HYP-048 framing | Accepted as an edge/regime bet, not under Part III's 5–9%-per-trade framing. |
| 2026-09-06 | **2-year validation standard** (holdout 2025-01-01 → 2026-05-20), retire the "longer history" requirement (I.8). | PROCESS | Owner decision | |
| 2026-09-06 | **Config-integrity gate** — `main_loop` fingerprints its config on startup and refuses to trade unless that fingerprint is in `validation_ledger.json`. | RULE | Readiness roadmap IV.11 | Known weakness: the gate checks "recorded", not "passed I.1". |
| 2026-09-03 | **Trailing stops OFF, pyramiding OFF.** | RULE | `live_config_ab` (trail ON → PF 0.592, −$93.59, 89% DD) | Both were running live but were never in the validated backtest. |
| 2026-09-03 | **Max 2 concurrent positions** (was 3), **`MAX_TOTAL_VOLUME = 0.02`**. | RULE | `live_config_ab` (2 concurrent tested best) | Owner instruction. |
| 2026-09-03 | **External indicators (BigBeluga MS Trend Matrix, LuxAlgo SMC) are a human analysis lens, not bot inputs.** | DIRECTION | `direction_gate_ab`, `confluence_ab`, `exit_trail_ab` — all negative | `structure.py` kept as a reusable A/B tool. |
| 2026-09-02 | **Hard 0.01 lots per order**, enforced at `ExecutionHandler.send_order` (pyramid adds too). | RULE | Live sizing bug (0.02/0.03-lot positions on a ~$105 account) | The mission's core constraint. |
| 2026-09-02 | **Keep the D1 bias gate ON** (first A/B). | RULE | `d1_gate_ab` (gate ON PF 1.51 / +$702 vs OFF PF 1.09 / +$164) | Later flipped OFF (09-03), then back ON (09-08, HYP-065). |
| 2026-09-01 | **Deploy `PORTFOLIO_V4`** (originally 4 session-specialist legs) in `main_loop`. | CONFIG | Phase-3 full sweep | Declared dead 2026-09-03 (SYSTEM_FAULTS), then partially recovered via the FVG rework. |

---

## Open decisions (awaiting the owner)

Tracked here so they don't get lost. Also in `README.md` and `REPO_GUIDE.md §6`.

1. **The operating rulebook** (REAL_MONEY_READINESS Part II) — sizing ladder,
   cascading loss caps (weekly/monthly/peak — only the 6% daily exists in code),
   news blackout, profit ring-fencing, paper→live ramp. Still unwritten. This is
   the single biggest blocker to real money.
2. **[RESOLVED 2026-09-17] Streak breakers — flip `ENFORCE = True`?** Implemented as part of the Citadel-grade upgrade (T1.1). Circuit breakers are now active.
3. **Real-money go-live date.** 2026-09-30 is not viable — Part VII gate is far
   from passed (holdout fails on drawdown, rulebook unwritten). Re-baseline to
   milestone-gated.
4. **FVG take-profit / gap floor — now fully re-validated (HYP-073), still not
   go-live ready.** `combined_2leg` (TIGHT+SOV, 0.05% gap floor, SOV TP→3.5) is
   the first config ever to pass I.1 cleanly (PF 1.64, maxDD 31%, min $103) and
   I.7 (2× cost), but **fails I.3 Monte Carlo** — P(ruin) 6.2% on a bootstrap
   of its own 329-trade holdout (needs <1%). The gap filter's smaller, more
   concentrated sample makes the historical sequence look smoother than a
   resampled one is. Owner call: (a) treat as not ready and keep looking, or
   (b) accept the I.3 shortfall in writing (a RISK-ACCEPTED row, same shape as
   the EMASTACK decision) if going live on it anyway. Either way this candidate
   is a 2-leg config (no EMASTACK) — deploying it would reverse the 2026-09-11
   EMASTACK-keep decision, which is item 5 below.
5. **[RESOLVED 2026-09-17] EMASTACK removal.** The 3-leg configuration was proven to fail all three gates (I.1, I.3, I.7) worse than the 2-leg configuration (HYP-073). Owner decided to remove EMASTACK and run the 2-leg FVG config.
6. **Deeper M1 / tick history** — the broker terminal only serves M1 back to
   2026-05-29, so no clean pre-2026 out-of-sample window exists. Buy tick data
   (Dukascopy / Tickstory) or add a second feed. Blocks a real holdout — and
   specifically blocks getting I.3 to pass on `combined_2leg` (item 4), since a
   bigger out-of-sample trade count is the honest fix for its sequence-risk
   failure.
7. **Repo housekeeping** (REPO_GUIDE §7) — archive superseded runners, prune
   `research/runs/`, remove empty `src/` dirs. Low stakes.
