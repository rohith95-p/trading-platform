# THE BUILD PLAN — a gold system that actually works

*2026-09-03, rohith-2. The definitive plan. Replaces every prior approach.*

**Context:** Exness (demo) is the **test bench** — live data, real execution,
fake money. It is not where real money goes. The only question that matters is
**does the strategy have a real edge.** Two systems have failed that question
(rohith-1's three strategies, rohith-2's portfolio_v4). This plan is built so the
same failure cannot happen a third time.

---

## PART A — Why the last two failed (and how this plan blocks it)

Both failed **identically**:
- A search over many rules picked the ones that scored best **on the data they
  were tested on.**
- That "winning" was luck that doesn't repeat. Tested on any other period, no edge.
- portfolio_v4: in-sample PF 1.48, 4-year holdout PF **0.965** (loses money).

The mechanism is called **overfitting / selection bias**, and it is the single
most common way trading systems die. It is defeated by four rules, below. They
are not negotiable and every step of this plan enforces them.

### The four unbreakable rules

| # | Rule | What it prevents |
|---|---|---|
| **1** | **Null first.** Before any strategy: measure buy-and-hold gold and random-entry. A strategy must beat both, risk-adjusted, or we stop. | Building a "system" that's worse than doing nothing. |
| **2** | **Pre-register.** Write the exact rule, exact parameters, exact pass/fail thresholds, and the kill criteria — *before* running the test. Run it **once**. Accept the result. | "Let me tweak it and re-run" — the exact move that overfits. |
| **3** | **Out-of-sample is the only verdict.** In-sample numbers get recorded but are **never** a reason to proceed. Proceeding requires passing on data the strategy never touched. | Believing a backtest that only saw its own training data. |
| **4** | **One hypothesis at a time, each with an economic reason.** No searching 90 rules. Each hypothesis names a *measured, published, or economically-grounded* phenomenon it exploits. | Turning noise into "strategies" by sheer number of attempts. |

---

## PART B — The phases

Each phase has a **gate**: a yes/no it must pass before the next phase starts.
No phase is skipped. No strategy is coded before Phase 2 exists.

### PHASE 0 — Data foundation
**Do:**
- Fetch the longest clean **D1** gold history obtainable (Exness only has ~4yr;
  supplement with Stooq / Dukascopy for a 15–20 year series). Also **H4**.
- Fetch D1 series for **DXY**, **10Y nominal yield (^TNX)**, **10Y real yield /
  TIPS**, **VIX**, **S&P 500** — the macro drivers.
- Data-integrity pass: no gaps, no zero/negative prices, no obvious bad prints,
  timezone aligned.

**Gate:** ≥ 10 years of clean D1 gold + at least DXY and yields aligned to it.
**Output:** `research/data/` extended; `scripts/fetch_history.py` updated.

---

### PHASE 1 — The market study + the null (GO / NO-GO for the whole project)
Measure, on the full history. **No strategy yet — just measurement.**

1. **Buy-and-hold gold:** CAGR, max drawdown, Sharpe, MAR (return/maxDD), worst
   calendar year, longest time underwater. *This is the bar.*
2. **Random D1 entry control:** 1,000 runs of a random long/short entry held N
   days. Distribution of PF and max-DD. *Any real strategy must sit outside the
   95th percentile of this.*
3. **Return autocorrelation**, lags 1–60 days. (M15 was ≈ 0. If D1 is also ≈ 0,
   that kills the momentum family.)
4. **Time-series momentum (the raw signal):** does the past 1/3/6/12-month
   return predict the next 1-month return? Regression, t-stat, by decade. *This
   is the most evidence-backed effect in commodity futures (Moskowitz-Ooi-
   Pedersen 2012) — test whether gold shows it.*
5. **DXY relationship:** rolling 30/60/90-day correlation. How stable? Does a DXY
   breakout lead gold?
6. **Real-yield relationship:** gold vs 10Y real yield — level and change.
7. **Volatility:** D1 ATR percentile distribution; do high-vol and low-vol
   regimes have different forward returns?
8. **Seasonality / calendar:** month, day-of-week, turn-of-month.
9. **Drawdown anatomy of gold itself:** how deep and how long are its own
   corrections? (Sets how wide a stop *has* to be.)

**Gate (GO):** at least **one** relationship is statistically real (t-stat > 2,
stable across decades) AND the random-entry control leaves room for an edge.
**Gate (NO-GO):** nothing beats random / everything is noise → gold has no simple
mechanical edge; escalate to the owner (different instrument, longer horizon, or
stop).
**Output:** `docs/research/D1_MARKET_STUDY.md` — every number, plots.

---

### PHASE 2 — The validation harness (built BEFORE any strategy)
Reusable modules. A strategy is fed in, a **verdict** comes out.

- **Walk-forward splitter:** e.g. train 2008–2015 → test 2016; +2016 → test
  2017; … → test 2026. Parameters chosen on train, measured on test, **never
  re-chosen after seeing test**.
- **Monte Carlo:** bootstrap the trade sequence 10,000× → PF distribution,
  50th/95th-pct max drawdown, P(ruin), P(losing year), expected recovery time.
- **Cost/slippage stress:** run at 1× / 2× / 3× (spread + commission + stop
  slippage).
- **Regime segmentation:** PF and DD per regime (bull/bear/chop, vol quintiles,
  rate-rising/falling).
- **Parameter perturbation:** ±20% on every threshold; the result must be stable
  across the cloud, not a spike.
- **The scorecard:** one function → `SURVIVES` / `DIES` with all numbers and the
  specific test(s) failed.
- **Pre-registration template:** the form every hypothesis fills out before it runs.

**Gate:** the harness reproduces a known result (run portfolio_v4 through it, it
must return `DIES` with PF ≈ 0.965 on the holdout).
**Output:** `src/research/validation/` + `docs/research/VALIDATION_PROTOCOL.md`.

---

### PHASE 3 onward — Hypotheses, one at a time
For each hypothesis:

1. **Pre-register** (fill the template): the phenomenon it exploits · the
   economic reason it persists · the exact entry rule (round numbers) · the exact
   exit rule · position sizing · the pass thresholds · the **kill criteria**
   (what result means "abandon this", decided *now*).
2. **Code it** as a single clean strategy.
3. **Run it through the harness once.**
4. `SURVIVES` → Phase 4 (paper). `DIES` → write the post-mortem in the ledger,
   move to the next hypothesis. **No tweaking and re-running.**

**Candidate hypotheses, in priority order** (finalised after Phase 1):
- **H1 — Time-series momentum.** Gold above its N-day moving average *and*
  past-N-month return positive → hold long; flat or short otherwise. Exit on the
  MA or a volatility stop. *Rationale: the most robust documented futures effect;
  Phase 1 confirms if gold has it.*
- **H2 — Dollar regime.** DXY breaks a multi-month range → take gold the opposite
  way; hold while the DXY trend persists. *Rationale: gold is priced in USD; a
  sustained dollar move mechanically moves gold.*
- **H3 — Real-yield trend.** 10Y real yield trending down → gold long bias.
  *Rationale: gold is a zero-yield asset competing with real yields.*
- **H4 — Volatility breakout.** D1 range compresses to an N-month low → trade the
  breakout with an ATR stop. *Rationale: volatility clusters; compression
  precedes expansion.*

Expect **most to fail.** Testing 10–20 hypotheses to find 1–2 survivors is
normal and correct. A phase that ends in `DIES` is the process working.

---

### PHASE 4 — Paper trading the survivor
- Freeze the strategy completely. Run on **Exness demo** for **≥ 8 weeks**, zero
  changes.
- Weekly: compare live-demo results to what the backtest produces for that exact
  date range.
- **Gate:** live-demo performance within 20% of backtest, no unexplained
  behaviour in the logs.

---

### PHASE 5 — Real deployment (only after Phase 4 passes)
- Choose the real broker/instrument whose minimum size fits the capital (there
  are many with far finer granularity than Exness Standard — this is an easy
  problem once a validated edge exists).
- Write the operating rulebook: sizing ladder, loss caps (daily/weekly/monthly/
  peak), circuit breakers, the kill switch, the review cadence, the shut-down
  criteria.
- Start at minimum size. Scale only on balance, never on a good feeling.

---

## PART C — What "done" looks like

A strategy that has, in this exact order:
1. Beaten buy-and-hold gold on Sharpe **and** MAR, over 10+ years.
2. Been **positive in every out-of-sample walk-forward window.**
3. Survived 2× modelled costs with PF still > 1.2.
4. Survived Monte Carlo: P(ruin) < 1%, 95th-pct max drawdown < 35%.
5. Then **matched its backtest over 8 weeks of live paper trading.**

Only then does real money enter the conversation.

---

## PART D — Honest expectations (read this on the hard days)

- **Most hypotheses will fail.** That is not failure — it is the filter doing
  its job. The last two systems failed *because there was no filter.*
- **Timeline is weeks to months of research, not days.** Every shortcut is
  exactly what broke the last two attempts.
- **It is possible the honest answer is "no simple mechanical edge exists on
  daily gold."** If we get there rigorously, that is a real result — and the
  options are a different instrument, a longer horizon, or a
  fundamentals-driven process. We will not paper over it with a curve fit again.
- **The demo bot keeps running** on the old (dead) system until the first
  survivor is ready. It costs nothing and risks nothing.

---

## PART E — What carries over, what's archived

**Keep:** `src/core/resilience.py` · `src/backtesting/engine.py` (add D1 mode) ·
`src/research/market_study.py`, `structure.py` · the execution/risk plumbing ·
the A/B harness pattern.

**Archived (dead):** portfolio_v4 + all 4 legs · ema_stack / trend_sniper_sar /
supertrend_ema / luxalgo_fvg · `src/research/candidates.py` (the 90-rule library)
· all rohith-2 tuning scripts (`scripts/archive/rohith2_deadend/`).

**Rewrite when the survivor exists:** `main_loop.py`, `DAILY_BATTLE_PLAN.md`.

---

## NEXT ACTION

**Phase 0 — extend the data.** Then Phase 1 — the market study. That first study
is the GO/NO-GO for everything. Say the word and it starts.
