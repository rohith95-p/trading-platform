# HYP-NY-FVG — Pre-Registration

*Written 2026-09-08, before any test was run. This document is locked. The
test runs once. The result is accepted. Revisions are recorded as new,
separately-dated hypotheses, never as edits to this file.*

This follows `D1_SYSTEM_PLAN.md`'s four unbreakable rules applied to **one**
strategy. It does **not** touch the live system — `PORTFOLIO_V4`,
`main_loop.py`, and the deployed config are untouched. All new code lives in
`scripts/validation/hyp_ny_fvg.py` and is self-contained.

---

## 1. The economic hypothesis (the "why", written before the numbers)

During the COMEX floor session — roughly **17:30–21:30 IST** (08:00–12:00 New
York) — scheduled US macro releases (08:30 ET data, 10:00 ET data) and the
metals pit open create bursts of one-directional order flow. That flow moves
price faster than resting liquidity can refill, leaving a **fair value gap
(FVG)**: a three-bar pattern where bar *i−2*'s high is strictly below bar *i*'s
low (bullish) or bar *i−2*'s low is strictly above bar *i*'s high (bearish).

The claim: **the displacement that creates the gap carries directional
information during this window** — the impulse continues often enough, and far
enough, that entering in the gap's direction with a tight stop and a wide
target is net-positive after real costs.

**Why this hypothesis and not another:**
- It names a *mechanism* (skipped resting liquidity during a known high-flow
  window), not a chart shape that "tends to work".
- It is time-and-place specific and that place is where 22 years of data say
  the structure is (`INTRADAY_MARKET_STUDY_22YR.md` §4: NY session = 44% of
  volume, 2× the range of Asia, widest bars 20:00–23:00 IST).
- It is the one component of the dead `portfolio_v4` that ever showed a
  measurable out-of-sample edge (`XAU-092` / `FVG_NY_TIGHT`, isolated PF 1.66,
  4-year holdout PF ~1.26 as part of the portfolio). This registration
  isolates it and tests it **alone, on a clean split it has never seen**.

**The failure mode being risked:** if NY gold flow is effectively random at
M15, the gaps are noise, price fills them and reverses as often as it
continues, and the tight stop simply pays spread on every entry. 22 years of
sub-50% M15 follow-through (`INTRADAY_MARKET_STUDY_22YR.md` §5) means this is
the *expected* outcome. A pass here would be genuinely surprising.

---

## 2. The exact rules (locked — no parameter is tuned after this line)

**Instrument / timeframe:** XAUUSDm, M15.

**Session filter:** enter only on bars whose fractional IST hour is in
`[17.5, 21.5)`. Rationale: 08:00–12:00 ET, the US-data-heavy part of the COMEX
day. This is `XAU-092`'s existing window — adopted, not searched.

**Entry signal (evaluated on the last closed bar, index −2 of the view):**
- **Bullish FVG:** `high[i-2] < low[i]` (strict, three-bar backward gap).
- **Bearish FVG:** `low[i-2] > high[i]`.
- No gap-size filter in the primary test. (A minimum-gap filter is a
  *secondary* pre-registration — §6 — because baking in the 0.05% value that
  prior exploratory work surfaced would be fitting to a number found by
  looking.)
- Direction: bullish FVG → BUY, bearish FVG → SELL.
- The backtest engine executes on the **open of the next bar**. No confirmation
  queue (matches `XAU-092`'s `execute_immediately`).

**Position management:**
- **0.01 lots, fixed, always.** One position at a time (`max_concurrent = 1`).
  No pyramiding, no adding.
- **Stop loss:** `0.5 × ATR(14)` from fill.
- **Take profit:** `2.5 × ATR(14)` from fill.
- **No trailing stop, no breakeven move** (net-negative in every prior test —
  `SYSTEM_FAULTS.md` §1).
- **Time stop:** none beyond the engine's own runway; a position runs until SL
  or TP. (The engine does not force session-close exits; this matches how
  `XAU-092` was validated. Recorded as a known deviation from the "flat by
  22:00" intuition.)
- **Daily loss breaker:** 6% of balance, then no new entries until 00:00 IST.
- **D1 EMA20 bias gate:** **OFF** for the primary test. Rationale: the gate has
  mixed evidence (`SYSTEM_FAULTS.md` §2 — it inverts at turning points) and
  adding it makes this a test of *two* things. The raw FVG edge is tested
  first. Gate-on is a secondary registration (§6).

**Sizing / account for the survivability test:** $100 starting balance,
0.01 lots, 1 position. Ruin = equity ever touches $20 (−80%).

---

## 3. Data split (defined now, enforced by the script)

Source: the Kaggle 22-year M15 import (`KAGGLE_IMPORT`, 2004→2026-02-27).
Retail feed, synthetic spread — costs are modelled by the engine's `realistic`
scenario, not read from the data.

| Bucket | Window | Rule |
|---|---|---|
| **In-sample** | 2015-01-01 → 2020-12-31 | May be inspected freely. Numbers from here are **never** a reason to proceed. |
| **Holdout** | **2021-01-01 → 2023-12-31** | The verdict. Run **once**, all six gates, then this file's result section is written and frozen. |
| **Never-touch** | 2024-01-01 → 2026-02-27 | Run **once**, and **only** after a decision to go live has been made on the holdout result. Final confirmation. |

Pre-2015 excluded: 2004–2005 data is unreliable (`INTRADAY_MARKET_STUDY_22YR.md`
data-health note); 2008–2014 is arguably a different microstructure regime. The
2015→ window is the modern electronic market.

The holdout (2021–2023) is deliberately a **hard** period for gold —
consolidation and the 2022 drawdown, not a melt-up. A strategy that only works
in trending regimes should fail gate 5 here, and that is the point.

---

## 4. Pass / fail gates (all six evaluated on the holdout, in one run)

**Core gates** (a failure here kills the hypothesis):

| # | Gate | Threshold |
|---|---|---|
| **1** | **Beats random entry** | holdout PF `>` 1.30 **and** `>` the 95th percentile of the random-entry PF distribution (same session, same SL/TP geometry, random bar + random direction, ≥1000 iterations) |
| **3** | **Survivable** | Monte Carlo (10 000 bootstrap resamples of the holdout trade sequence): **P(equity touches $20) < 1%** and 95th-percentile max drawdown `<` 40%, at $100 / 0.01 lot / 1 position |
| **5** | **Regime-robust** | net profit `> 0` **and** PF `> 1.0` in **each** calendar year 2021, 2022, 2023 — not just in aggregate |

**Robustness gates** (a failure here means revise-and-re-register, not
necessarily dead):

| # | Gate | Threshold |
|---|---|---|
| **2** | **Beats buy-and-hold, risk-adjusted** | strategy annualised Sharpe (daily equity changes) `>` 0.69, **or** MAR (annualised return / max DD) `>` 0.26 |
| **4** | **Not knife-edge** | SL and TP multipliers scaled by ×0.8, ×0.9, ×1.1, ×1.2 — worst-case PF across all four `>` 1.15 |
| **6** | **Survives real costs** | re-run at 2× the modelled spread + slippage — PF `>` 1.15 |

**Overall verdict:** PASS only if **all six** clear. The script prints a table
and writes `research/validation/hyp_ny_fvg_holdout.json`.

---

## 5. What each outcome means (kill criteria, defined now)

- **All six pass** → proceed to the 8-week paper test (§7). Record in
  `validation_ledger.json` and `RESEARCH_LEDGER.md` as HYP-NY-FVG PASS.
- **Gate 1 fails** → the FVG displacement carries no information in NY.
  **Hypothesis dead. No revision.** Move to the D1 macro path
  (`D1_SYSTEM_PLAN.md` DXY lead/lag).
- **Gates 1 & 5 pass, gate 3 fails** → edge is real, bet size is not. Revise:
  Cent account / smaller effective size is a *sizing* change, not a rule
  change. Re-register the sizing and run the **never-touch** window once.
- **Any of 2 / 4 / 6 fails** (with 1, 3, 5 passing) → one documented revision
  allowed; it counts as a new hypothesis and is tested on **never-touch**, which
  is then burned.
- **Gate 2 alone fails** → recorded, not automatically fatal — beating
  buy-and-hold gold risk-adjusted is a high bar and a fixed-lot micro strategy
  is a different risk object. The go/no-go leans on 1, 3, 5.

The holdout is run **once**. "Adjust the rule and re-run the holdout" is
forbidden — it is the exact mechanism that killed the last two systems.

---

## 6. Secondary pre-registrations (only opened if the primary is revised)

Registered now so they cannot be presented later as fresh ideas:

- **6a — minimum gap size:** require the FVG to span `≥ 0.04%` of price. One
  value, chosen now, informed by prior exploratory work. Tested on never-touch
  only.
- **6b — D1 EMA20 gate ON:** the primary rules, plus only trade in the
  direction of D1 close vs D1 EMA20. Tested on never-touch only.

Each may be used **once**, and only under the §5 revision paths.

---

## 7. Paper test (only if §4 passes)

8 weeks, demo account, live data, real time. Runs as a **standalone signal
logger** (`scripts/hyp_ny_fvg_paper.py`) that records what the hypothesis would
do — it does **not** place orders and does **not** enter `main_loop`. The live
`PORTFOLIO_V4` bot is unaffected.

Pass condition (pre-registered): realised paper PF within **0.30** of the
holdout PF, no execution surprises (fills, spread spikes, data-gap None-returns)
that the backtest did not model.

---

## 8. Go-live (only if §7 passes)

1. Run the **never-touch** window (2024→2026) once as final confirmation.
2. Deploy at 0.01 lots, 1 position, smallest real account.
3. **Live kill criterion (pre-registered):** stop and re-evaluate if live max
   drawdown exceeds **1.5×** the holdout's max drawdown, or after **6
   consecutive losing weeks**.
4. Write the operating rulebook (sizing floor, early-loss caps, the paper→live
   ramp) — the item `README.md` still lists as unwritten.

---

*Locked 2026-09-08. Result section appended below by the single holdout run —
nothing above this line changes.*

---

# RESULT — holdout run 2026-09-08 (locked)

**One run. `research/validation/hyp_ny_fvg_holdout.json`. Not re-run.**

## Headline — holdout 2021-01-01 → 2023-12-31

| metric | value |
|---|---|
| trades | 663 |
| win rate | 13.9% |
| profit factor | **0.833** |
| net | **−$92.97** on $100 |
| avg win / avg loss | +$5.05 / −$0.98 |
| min balance | $7.03 (effectively blown by mid-2022) |
| max drawdown | 95.6% |

## Gates — 0 of 6 passed (all three core gates failed)

| # | gate | result | pass? |
|---|---|---|---|
| 1 | beats random entry | PF 0.833 vs random p95 **0.70**, floor **1.30** | **FAIL** |
| 2 | beats buy-and-hold, risk-adj | Sharpe −0.76, MAR −0.62 | **FAIL** |
| 3 | survivable | P(ruin) **70.4%**, 95th-pct maxDD 185% | **FAIL** |
| 4 | not knife-edge | worst off-base PF 0.73 (whole cloud < 0.84) | **FAIL** |
| 5 | regime-robust | 2021 −$75 (PF 0.86), 2022 −$18 (PF 0.32), 2023 dead | **FAIL** |
| 6 | survives 2× cost | PF 0.59 | **FAIL** |

In-sample (2015–2020, inspected before the run) was consistent: PF 0.487,
−$95, account blown. The strategy fails in both periods, not just one.

## What this means

Per section 5: **gate 1 failed → the hypothesis is dead. No revision. The
secondary registrations (6a min-gap, 6b D1 gate) are NOT opened** — they were
conditional on gates 3/5 passing with only a robustness gap, which did not
happen.

**Nuance worth recording:** the FVG signal is not *pure* noise — real PF 0.833
beats the random-entry distribution (p50 0.566, p95 0.70), so a fresh
three-bar gap in the NY session does carry a little directional information.
But "a little information" is not an edge: it is nowhere near enough to pay for
a 0.5×ATR stop on a 24-hour instrument. Random entry in this exact
session + geometry also loses badly (p50 PF 0.57), because the tight stop
bleeds regardless of why you entered. The 0.5/2.5 geometry that made
`FVG_NY_TIGHT` look good on its 2026 selection window does not survive a clean
2021–2023 holdout.

## Next action

The intraday-FVG line is closed. Move to `D1_SYSTEM_PLAN.md` — measure the
DXY→gold **lead/lag** regression on D1 (the one pre-registered hypothesis in
that plan not yet tested). That single regression decides Phase 1 GO / NO-GO.

*Result locked 2026-09-08. This hypothesis is retired.*
