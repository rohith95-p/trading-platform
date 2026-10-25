# Phase 0 — Research Audit (2026-09-01)

Adversarial audit performed BEFORE any new strategy work, per the research
program's rule: *do not assume existing backtests are correct.*

**Headline: two findings invalidate or materially weaken prior conclusions,
one of them an error introduced during the 2026-08-31 "rohith phase 2" work.**

---

## CRITICAL FINDING 1 — The M1 sub-bar fidelity claim is false; prior results are inflated

### What was claimed
Every tier-2 result from 2026-08-31 (EMA_STACK survivability, the 10-candidate
screen, modified variants, no-Asia tests, the 27-cell session matrix) was
documented as running on "M1 sub-bar fidelity."

### What actually happened
All of those scripts called `load_bars(..., timeframes=("M15","M5","D1"))` —
**M1 was explicitly excluded.** The engine (`engine.py:537-540`) falls back to
treating an entire M15 bar as a single bar when M1 is absent: it slices M1 for
the next 900 seconds, finds nothing, increments `bars_without_m1`, and
substitutes `self.m15[i+1:i+2]` — the whole 15-minute bar as one unit.

### Measured impact
Same strategy (EMA_STACK), same config, same window (2026-05-21 → 2026-08-29),
only difference is whether M1 was loaded. Script: `scripts/audit_m1_fidelity.py`.

| Setup | Trades | WR | PF | Net P/L | End Bal | Ambiguous trades |
|---|---:|---:|---:|---:|---:|---:|
| WITHOUT M1 (what was actually run 2026-08-31) | 234 | 47.0% | **1.444** | +$866.61 | $972.35 | **184 (78.6%)** |
| WITH M1 (true sub-bar fidelity) | 200 | 42.5% | **1.160** | +$290.97 | $396.71 | 1 (0.5%) |

**Profit factor overstated by ~24%. Net profit overstated by ~3x.** 78.6% of
trades had their exit resolved by the coarse M15 heuristic rather than the
actual intrabar path.

### Consequence
Every performance figure in `docs/research/ROHITH_PHASE2_SURVIVABILITY.md` and
ledger entries HYP-025 through HYP-031 is **inflated by an unknown but material
amount** and must be treated as an upper bound, not a measurement. This includes
EMA_STACK's headline PF 1.319 / $105.74→$3,874.76 result.

**Status of EMA_STACK: not disproven, but its evidence is substantially weaker
than reported.** At true M1 fidelity over the only window we can verify, it
holds PF 1.160 on 200 trades — still positive, far less impressive.

---

## CRITICAL FINDING 2 — We cannot produce a high-fidelity backtest over the claimed windows

M1 data coverage is the binding limitation:

| Timeframe | Bars | First | Last |
|---|---:|---|---|
| M1 | 100,000 | **2026-05-20** | 2026-08-31 |
| M5 | 100,000 | 2025-04-02 | 2026-08-31 |
| M15 | 100,000 | 2022-06-07 | 2026-08-31 |
| H1 | 28,599 | 2021-10-27 | 2026-08-31 |
| H4 | 7,456 | 2022-01-02 | 2026-08-31 |
| D1 | 1,507 | 2021-10-27 | 2026-08-31 |

- The "in-sample" window (2025-04-03 → 2026-08-29) has M1 for only its last
  ~3.5 months (~20%).
- The "locked holdout" (2022-06-08 → 2025-04-02) has **no M1 at all** and no
  M5 either — it is M15-resolution only.

**Therefore: no result covering more than 2026-05-20 → 2026-08-31 can claim
execution-realistic fidelity.** Roughly 3.5 months is the true high-fidelity
research window, and that is a small sample for strategy validation.

Action required: attempt to extend the M1 cache via `scripts/fetch_history`
(brokers typically retain limited M1 history — if Exness caps it, this is a
permanent constraint that must be designed around, not wished away).

---

## Broker economics — verified from the live terminal, not assumed

Queried directly from Exness-MT5Trial11 on 2026-09-01:

| Property | Value |
|---|---|
| Symbol | XAUUSDm (XAUUSD does not exist on this server) |
| Contract size | 100 oz |
| Tick size / tick value | 0.001 / $0.10 per 1.00 lot |
| Point / digits | 0.001 / 3 |
| Min lot / lot step / max | **0.01 / 0.01** / 200.0 |
| **Broker stops level** | **0 (no minimum stop distance imposed)** |
| Freeze level | 0 |
| Current spread | 260 points = **$0.26** |
| Median historical spread (M15) | 200 points = **$0.20** |
| Leverage | 200 |
| Swap long / short | **−515.5 / 0.0** (mode 1) |
| Account balance / equity | $105.74 / $105.74 |
| Current price | 4427.84 / 4428.10 |

### Derived facts that matter

**1. Risk arithmetic at 0.01 lot is exactly $1 per $1 of stop distance.**
0.01 lot × 100 oz = 1 oz, so a $10 stop = $10 risk. Clean and unavoidable.

**2. The broker imposes NO minimum stop distance (stops_level = 0).**
This contradicts any assumption that wide stops are forced by the broker.
Tight stops are *technically* permitted — whether they are *statistically*
valid is a separate question Phase 1 must answer, not the broker.

**3. Margin caps concurrent positions at ~4.**
Margin per 0.01 lot = (1 oz × $4,428) / 200 = **$22.14**. With $105.74 free
margin, the account supports **4 concurrent 0.01-lot positions maximum** before
margin exhaustion — and that assumes zero floating loss. The previously
requested "max 3 concurrent trades" sits right at the edge of this limit, not
comfortably inside it. **This constraint was not documented anywhere in prior
research.**

**4. Long positions carry a real overnight cost; shorts do not.**
Swap long −515.5 points/lot/night = **−$0.52 per night per 0.01 lot**; swap
short is 0.0. Any strategy holding longs multi-day bleeds ~0.5% of this account
per night. This asymmetry structurally favours shorts for multi-day holds and
was never modelled in any backtest to date.

**5. Volatility has more than doubled across the data window.**
Mean true range: **4.67** across the full M15 history vs **10.03** over the
last 500 bars. Price ranged 1,616 → 5,586, currently 4,428.

**Implication:** historical backtests contain long stretches where a 1.5×ATR
stop risked only ~$7 (6.6% of a $105 account). At *today's* volatility the same
rule risks ~$15 (14.2%). **Prior survivability results are therefore optimistic
about present-day conditions** — the account was being risked at roughly half
today's rate for much of the test period.

---

## Architecture / what can be reused

| Component | Verdict |
|---|---|
| `src/backtesting/engine.py` | **Reusable, with the M1 caveat.** Calls the real `RiskManager`; models spread, slippage, dedup, daily loss breaker, margin floor. Ambiguity resolved stop-first (conservative *within* a bar) but the M15 fallback still inflates results overall, per Finding 1. |
| `src/backtesting/costs.py` | Reusable. Observed-spread + slippage scenarios exist. |
| `src/research/candidates.py` | Reusable as a *library* (120 candidates), but all its published results are tier-1 approximations and non-authoritative. |
| `src/research/screener.py` | **Contains a bug**: `_session_mask` wraparound branch computes `ist_hour < b - 24.0`, which is never true for a session like (21.5, 11.5) — wraparound sessions silently lose their post-midnight half. Not triggered by the non-wrapping sessions used so far, but it will silently corrupt any overnight-session research. **Must fix before Phase 2.** |
| `src/core/risk_manager.py` | Reusable; note `sl_atr_mult_override` in `EngineConfig` is **declared but never wired to anything** — dead config that silently does nothing. |
| Prior tier-2 results (2026-08-31) | **Do not trust.** Inflated per Finding 1. Re-run with M1 where data permits. |
| Prior tier-1 screen results | Approximations only; already shown to mis-rank (XAU-120 ranked #11 then failed completely in tier-2). |

---

## Environment finding — duplicate process spawning

Every Python launch in this environment spawns **twice** (once via
`venv/Scripts/python.exe`, once via the global `Python311` install), reproduced
3x with different launch methods. Two `main_loop.py` processes have been running
concurrently since 2026-08-31 20:50:35 as a result.

**Risk:** duplicate live order submission — the same failure class the ledger
already recorded once (HYP-010, a duplicate fill doubled a live loss to
−$55.58). Must be resolved before any live deployment.

---

## What must NOT be trusted going forward

1. Any performance figure produced before 2026-09-01 (pre-dates Finding 1).
2. Any result covering periods without M1 data, if it claims execution realism.
3. Any wraparound-session result produced via `screener.py` (masking bug).
4. Any survivability conclusion that does not account for the ATR doubling.
5. Any multi-day-hold result for long positions (swap never modelled).

## What must be rebuilt

1. Re-run every surviving candidate WITH M1, restricted to 2026-05-20 onward.
2. Fix `screener.py` session wraparound masking.
3. Add swap modelling to the cost model (asymmetric: longs only).
4. Add margin-cap enforcement (max ~4 concurrent 0.01 lots at current price).
5. Attempt to extend M1 history; if impossible, formally accept ~3.5 months as
   the maximum high-fidelity validation window and design the program around it.

---

*Phase 0 completed 2026-09-01. Evidence: `scripts/audit_m1_fidelity.py`,
live MT5 terminal query, `research/data/*.manifest.json`.*
