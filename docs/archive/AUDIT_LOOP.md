# Audit Loop — bleeding / no-money hunt

Self-paced loop started 2026-09-03 (rohith-2, Thu). Goal: find and fix anything
that stops the system making money or causes it to bleed. **Research only** —
the frozen live config (0.01 lots, 0.02 cap, no trail/pyramid, D1 EMA20 gate, 4
legs) is untouched through the Thu/Fri evaluation. Nothing committed. Fixes are
surfaced here for the Saturday decision.

---

## Iteration 1 — 2026-09-03 09:26 IST

**Live bot:** healthy, flat, $135.76, heartbeat current. 2 trades in the last
12h (last night's FVG pair: +$4.70 / −$5.71). Nothing Thursday yet — the one
active leg (SQUEEZE_ASIA) only wanted longs into a bearish daily, all blocked.

**Backtests collected:**
- Gate refinements + BE-move: **done**. Every exit modification loses to the
  frozen fixed-TP config (3rd confirmation). Only `d1_proximity k=0.3` is a
  viable gate refinement (PF 1.42 vs 1.48, DD +1.6pp, +36 transition trades) —
  holdout test running.

**Problem hunted:** the spread gate is **global and static** (`MAX_SPREAD_POINTS
= 350` ≈ $0.35). It's applied once per loop with no knowledge of which leg is
about to trade:
- `FVG_NY_TIGHT` stop ≈ 0.5×ATR ≈ $5.50 → a $0.35 spread is **6.4% of the stop**
- `SQUEEZE_ASIA` stop ≈ 2.0×ATR ≈ $22 → the same spread is 1.6%

So the gate that's harmless for Asia is a real drag on FVG_NY — the weakest,
most-stopped leg. Related: FVG_NY fires on **any** 3-bar gap (no size filter),
and the isolated LuxAlgo test already showed a min-gap filter takes it from
PF 1.66 → 2.11.

**Candidate built:** `scripts/fvg_improve_ab.py` — the full portfolio with the
FVG leg wrapped to require a minimum gap size (0.03% / 0.05% / 0.10% of price,
or 0.5×ATR). Only the FVG leg changes. **Running.**

**Per-leg spread gate** — deferred to a later iteration (needs the engine's
spread check to be made leg-aware).

---

## Iteration 3 — 2026-09-03 ~10:10 IST

**Live bot:** alive through the brief offline, flat, $135.76, heartbeat current.
No trades (Asia leg still long-only into a bearish daily).

**Holdout proximity variant:** `d1_proximity k=0.3` on 4yr = PF **0.955**,
−$97, min $9 — the refinement doesn't rescue a system with no edge, as expected.

**`scripts/edge_by_period.py` — COMPLETE. Verdict: portfolio_v4 has no edge.**

| Period | PF | Net | Max DD |
|---|---|---|---|
| H2 2022 | 1.074 | +$70 | 44% |
| H1 2023 | 0.936 | −$58 | 75% |
| H2 2023 | 1.006 | +$4 | 75% |
| H1 2024 | 0.746 | −$96 | 93% |
| H2 2024 | 1.208 | +$306 | 23% |
| H1 2025 | 1.402 | +$690 | 33% |
| H2 2025 | 1.403 | +$834 | 80% |
| Jan–May 2026 | 0.894 | −$105 | **99.8%** |
| **May–Aug 2026 (SELECTION)** | **1.478** | +$843 | 21% |

The selection window is the **single best 6-month period in 4+ years**. Aggregate
PF 0.965. This is textbook selection bias: 90+ candidates screened, best-4-on-
one-window kept. **portfolio_v4 must not go to real money.**

Regime nuance: 2024H2–2025 genuinely worked (PF 1.2–1.4); 2023 and early 2026
were account-killers. But Jan–May 2026 (−99.8%) flipped to May–Aug 2026 (+PF
1.48) with no warning — regime shifts here are not visibly predictable.

**Next (iteration 4): regime filter test** — is there a volatility / macro
signal that would have turned the system OFF in the killer regimes? If not,
the answer is C: mechanical M15 gold entries don't carry an edge after costs.

---

## Iteration 2 — 2026-09-03 ~09:45 IST — ⚠️ MAJOR FINDING

### The frozen live config FAILS the 4-year holdout

`scripts/proximity_holdout.py`, baseline `d1_ema20` gate, portfolio_v4,
2022-06-15 → 2026-05-19 (M15 fidelity, no M1):

| | n | WR | PF | net | min balance | max DD |
|---|---|---|---|---|---|---|
| **in-sample** (100d, M1) | 330 | 29.7% | **1.478** | +$843 | — | 21.4% |
| **holdout** (4yr, M15) | 2109 | 22.0% | **0.965** | **−$96** | **$10.03** | **95.7%** |

The +$843 / PF 1.478 headline was on the single 100-day window the 4 legs were
**selected** on. Over 4 prior years the same config **loses money and draws the
account to $10.** This is exactly the failure mode `REAL_MONEY_READINESS.md`
Part I warned about, and echoes rohith-1's finding that the original strategies
sat on the random-entry null.

### ⚠️ CONFIRMED 09:49 IST — the failure is real, not a fidelity artifact
`logs/m15_control.log`: the in-sample window at **M15-only** gives PF **1.472**
(vs 1.478 with M1). Data resolution makes no difference. Therefore the holdout
PF 0.965 / −$96 / $10-min-balance is a genuine out-of-sample failure.
**portfolio_v4 is overfit to its 100-day selection window and has no edge before
it. Do not take it to real money on 2026-09-30.** All exit/gate/FVG tuning is
moot. Path forward: walk-forward re-selection from scratch, or accept that
mechanical M15 gold entries may not beat costs (2 independent research efforts
now point there).

### (original confound note, now resolved)
The in-sample runs use **M1** fills; the holdout only has **M15**. The engine's
coarse (M15) mode resolves any bar that touches both stop and target as
**stop-first** — a systematic penalty for a 24-30% WR tight-stop strategy.
`/tmp/m15_control.py` (→ `logs/m15_control.log`) re-runs the *in-sample* window
at **M15-only**:
- if it also collapses to ~PF 0.97 → the holdout number is a fidelity artifact,
  the strategy may still be fine, and we need true M1 holdout data.
- if it holds ~PF 1.4 → the strategy genuinely has no edge out-of-sample and
  **portfolio_v4 should not go to real money on Sept 30.**

### If the finding survives the confound check
The FVG filter and gate refinements become irrelevant — you don't tune a system
with no edge. The path forward would be: re-run the full candidate screen with
walk-forward + holdout from the start (no selection on a single window), or
accept that gold on this timeframe may not carry a mechanical edge at all.

---
