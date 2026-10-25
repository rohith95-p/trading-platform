# Real-Money Readiness — Full Roadmap

*Draft for review — 2026-09-03, rohith-2. Author: Claude (Sonnet 5). Nothing here
is implemented yet; this is the complete list of what should be done before
portfolio_v4 trades real money, and the rules to run it by once it does.*

> **STATUS UPDATE 2026-09-06 — this document was abandoned mid-flight, not
> completed.** It was written ~10.5 hours *before* `SYSTEM_FAULTS.md` concluded
> the same day that portfolio_v4 has no real out-of-sample edge (4-year holdout
> PF 0.965), and it was never updated or marked superseded after that finding —
> it sat here looking current for 3 days while the underlying strategy was
> already known to be dead. See `docs/research/REAL_MONEY_READINESS_RATING_2026-09-06.md`
> for the full corrected scoring. Headline corrections since this was written:
> - **A real bug was found and fixed** (HYP-046/047): the 4-year holdout was
>   genuinely losing (PF 0.948) on the code that existed 09-03; one dedup fix to
>   `EMASTACK_LONDON_TIGHT` (not a re-tuned parameter) flipped it to PF 1.180.
>   There is now a real, if thin, edge to protect — the "no edge at all" verdict
>   is outdated, but PF 1.180 still misses this document's own I.1 pass bar
>   (>1.2) and its drawdown (83.9%) badly misses "never below 50% of start."
> - **III.2 below ("the direction gate is law") is no longer true.** The D1
>   gate is now deliberately OFF (HYP-048, owner decision, 2026-09-06),
>   accepting a named risk: the exact config that scores well on 2025-2026
>   (PF 1.245, $6.15/day) took the account to $4.50 (from $105.74) on 2022-2024
>   in the same backtest. This is a conscious bet on the recent regime, not a
>   validated-safe setting — Part III's framing needs to be read with that in
>   mind, not the original "gate is law, never override" language.
> - **A config-integrity gate now exists that this document doesn't mention**:
>   `src/core/system_config.py` + `src/core/validation_ledger.py`, wired into
>   `main_loop.py`'s startup — it fingerprints the live configuration and
>   refuses to trade anything that doesn't match a recorded backtest. This
>   closes part of the "frozen config" problem in III.3 mechanically instead of
>   relying on discipline alone. See Part IV's new IV.11 entry below.
> - **None of Part I's formal pass/fail gates have actually been cleared.**
>   Real testing happened this session (a pre/post-fix A/B, a 2022-2024 vs
>   2025-2026 out-of-sample check, a Monte Carlo ruin simulation), but it was
>   exploratory, not the pre-registered I.1-I.9 protocol below. See the rating
>   report for the honest per-item status.

---

## 0. Read this first — what "ready" and "consistent" actually mean

**The win rate is 24–30% by design, and that is correct.** These legs take a
small stop and aim for a target 2.25–4.0× larger. They lose ~7 trades in 10.
The edge is entirely in the size of the winners vs the losers (profit factor),
not in being right often.

Do **not** chase a higher hit rate. That is exactly what the trailing stop did
(win rate 29% → 53%, profit factor 1.58 → 0.59, account nearly wiped). "High
accuracy" in the everyday sense is a trap for this kind of system.

**"Consistent" here means:**
1. Positive expectancy that is *proven* to survive out-of-sample, cost stress,
   and bad market regimes — not just measured once on a lucky window.
2. Risk limits so hard that the worst realistic losing streak cannot end the
   account.
3. Zero discretion — the same rules produce the same trades every time,
   regardless of how anyone feels about the market.

Consistency is a property of the *process over hundreds of trades*, not of any
day or week. A day of +$3 / −$4 / flat is the system working.

---

## PART I — PROVE THE EDGE IS REAL

*This is the gate. If Part I does not pass, nothing else matters and real money
does not happen — regardless of the calendar.*

The current evidence for portfolio_v4 is **PF ≈ 1.5 on a single ~100-day window
(2026-05-21 → 08-29)** that was also the window the 4 legs were *selected* on.
That is a hypothesis, not proof. rohith-1 already found the 3 original live
strategies were statistically indistinguishable from random. The same bar must
be cleared here.

### I.1 Out-of-sample holdout test — HIGHEST PRIORITY

> **STANDARD CHANGED 2026-09-06 (owner decision): 2-year scope, not 4-year.**
> Pre-2025 data is considered no longer representative of the current market
> environment and is excluded from the pass/fail decision. The 4-year holdout
> results remain on record (HYP-047: PF 1.180 post-fix) as context, but are no
> longer the gate.
>
> **The holdout window is `2025-01-01 -> 2026-05-20`.** This is deliberately
> *not* "all of 2025-2026": the 4 legs were selected on 2026-05-21 -> 08-29, so
> including that window would be scoring the strategy on its own training data.
> 16.5 months of genuinely unseen data, entirely inside the regime the owner
> considers representative, is the honest version of a 2-year standard.

- Run portfolio_v4 **exactly as frozen** (no parameter changes, no re-selection)
  on the holdout window above, at the live configuration (D1 gate OFF per
  HYP-048, live caps, fixed 0.01 lot).
- M15 fidelity is acceptable if M1 isn't available for that range — note the
  fill-model difference.
- **Pass condition:** combined PF > 1.2, max drawdown < 45%, account never below
  50% of start.
- If it fails: the legs are overfit to the selection window. Back to research.

### I.2 Walk-forward analysis
- Rolling windows: train 60d / test 20d / step 20d across all available history.
- On each *train* window, re-run the leg-selection sweep. On the *test* window,
  measure the selected portfolio.
- **Pass condition:** the same 3–4 leg *families* keep getting selected, and
  median test-window PF > 1.2.
- If each window selects different legs → the selection is fitting noise.

### I.3 Monte Carlo — trade-sequence bootstrap
- Take the actual per-trade P&L list. Resample with replacement 10,000×.
  Rebuild the equity curve each time.
- **Report distributions, not points:**
  - PF: 5th / 50th / 95th percentile
  - Max drawdown: 50th / 95th percentile
  - P(equity touches −25% / −50% / ruin)
  - P(a calendar month is negative)
  - Expected time to recover from a 20% drawdown
- **Pass condition:** 95th-percentile max drawdown < 40%; P(ruin at 0.01 lots) < 1%.

### I.4 Monte Carlo — parameter perturbation
- Jitter every threshold ±10–20%: ATR multipliers, session boundaries, EMA
  periods, gap-size thresholds, ADX cutoffs.
- Re-run the portfolio across the cloud of perturbed configs.
- **Pass condition:** PF stays > 1.2 across the whole cloud. If a 5% change to one
  parameter collapses PF, that parameter is overfit.

### I.5 Random-entry control — re-run per leg
- For each of the 4 legs: keep the exits and the session/time distribution,
  replace the *entry rule* with a random entry. Run 1,000×.
- **Pass condition:** the leg's real PF sits above the 95th percentile of its
  random distribution. A leg that doesn't clear this is deleted.

### I.6 Regime segmentation
- Slice every backtest by:
  - D1 trend: bull / bear / sideways
  - Volatility: ATR percentile quintiles
  - Structure: efficiency-ratio trending vs ranging
- Report PF and drawdown *per regime, per leg*.
- Use the result to decide whether legs should be gated by regime, not only by
  session. **Specifically: find where each leg bleeds and turn it off there.**

### I.7 Cost & slippage stress
- Re-run at 1×, 1.5×, 2×, 3× the modeled (spread + commission + slippage).
- Plot PF vs cost multiplier; record the **breakeven cost multiple**.
- **Model slippage on stops explicitly:** stop fills at `stop ± (0.5–1.0 ×
  spread)` adverse in normal conditions, worse on gap-throughs. The FVG_NY leg
  ($5.50 stop) is extremely sensitive to this.
- **Model spread as a function of time-of-day:** spread widens at session
  opens/closes and at broker rollover (~00:00 server time).
- **Pass condition:** PF > 1.2 at 2× modeled cost with realistic stop slippage.

### I.8 Longer history — RETIRED 2026-09-06 (owner decision)
- ~~Source Dukascopy multi-year tick data and re-run I.1-I.7 on it.~~
- **Dropped under the 2-year standard.** The explicit reasoning: pre-2025 gold
  behaviour is considered a different regime and not decision-relevant. This
  is a deliberate narrowing of the evidence base, and the cost of it is
  recorded honestly here rather than quietly dropped: the same live config
  (gate off) that passes on recent data produced **PF 0.654 / account down to
  $4.50** on 2022-2024. Choosing the 2-year standard means accepting that a
  regime like that would not be caught in advance by this test suite.

### I.9 Forward paper test — the final filter
- Freeze the config completely. Run on demo for a **minimum of 8 weeks**, no
  changes of any kind.
- Each week: compare live-demo results to what the backtest produces for that
  exact date range.
- **Pass condition:** live-demo PF within 20% of backtest PF, and no unexplained
  behaviour in the logs.

---

## PART II — CAPITAL & RISK RULES (the written rulebook)

*Every number below must be decided and fixed before go-live. No discretion.*

### II.1 The starting-capital decision
At 0.01 lots (broker minimum) with these tight stops, one trade risks **$5–9**.
On a $100 account that is **5–9% per trade** — far above the 1–2% norm. The first
~$100–300 of live trading is therefore the *structurally riskiest* phase of the
entire plan, and it does not get safer with time — it gets safer only with
balance.

Pick one, in writing:
- **(A)** Start with **$300–500** so 0.01 lots ≈ 1.5–3% per trade. Strongly
  preferred.
- **(B)** Use an **Exness Cent account** (`XAUUSDc`, 0.10 "lot" = the same $1
  notional) for the first phase, so sizing granularity is 10× finer.
- **(C)** Start at ~$100 on the Standard account and *explicitly accept* that the
  first weeks run at 5–9% risk per trade, with a hard 2-loss daily stop.

### II.2 Position-sizing ladder
Write the exact table. Example shape (fill in after Part I):

| Balance | Per-order lots | Max total exposure | ~Risk per trade |
|---|---|---|---|
| < $200 | 0.01 | 0.01 (one position only) | 4–9% |
| $200–400 | 0.01 | 0.02 | 2–4% |
| $400–800 | 0.01 | 0.03 | 1.5–2.5% |
| > $800 | 0.02 | 0.04–0.06 | 1.5–2% |

Sizing is a lookup against balance. It is never a judgement call. Changes to the
ladder require the full validation cycle.

### II.3 Loss caps (cascading)
- **Per-trade:** whatever the ATR stop gives at 0.01 lots. Not adjustable.
- **Daily:** early phase **3%** or **2 losing trades**, whichever first → halt
  new entries to midnight IST. Loosens to 6% above $400.
- **Weekly:** −15% from Monday's opening balance → halt for the week, mandatory
  review before resuming.
- **Monthly:** −25% from month-start balance → **full stop**, re-run Part I
  before resuming.
- **All-time peak:** −30% from the highest equity ever reached → **hard kill**,
  written post-mortem required before any restart.

### II.4 Circuit breakers (intraday)
- **3 consecutive losses** (any leg) → pause all new entries 4 hours.
- **5 consecutive losses** → stop for the day.
- **Spread spike** > per-leg max → that leg skips entries (already partly built;
  make the max per-leg, not global).
- **Unexpected account state** (balance jump, wrong login, margin call flag) →
  halt and alert.

### II.5 Profit protection
- At each milestone ($150, $200, $300, $500, then every $250), **ring-fence** a
  fixed fraction (e.g. 30%) of the gain — move it to a sub-account or withdraw.
  A later blowup then cannot erase all progress.
- **Never add external funds to a drawing-down account.** It earns its way back
  or it gets shut off. Adding money to a loser is how accounts die slowly.

### II.6 Leverage / margin
- Max margin utilization **20%**. At the sizing ladder above this is automatic,
  but write it as a hard check in the startup safety block.

---

## PART III — TRADING RULES & DISCIPLINE

### III.1 The bot trades, or nothing does
- **No manual entries. Ever.** Not "I see a great setup." The bot or nothing.
- **No manual management of open trades.** No moving stops, no early exits "to be
  safe," no letting it run past TP. (This was done on 2026-09-02 out of nerves —
  SL to 4308, TP to 4304. It should not have been. Those were not backtested
  actions and they inject discretion back into a system whose whole point is to
  remove it.)
- The **only** permitted manual action on a live position is the **kill switch**
  (III.6).

### III.2 The direction gate — status changed 2026-09-06, read carefully
- **As of 2026-09-06 the D1 gate is deliberately OFF** (HYP-048), reversing the
  framing below. This was an explicit owner decision to weight the 2025-2026
  regime over 2022-2024, made with the full evidence on the table: gate-off
  scores better on 2025-2026 (PF 1.245, $6.15/day) but took the account from
  $105.74 to $4.50 on 2022-2024 in the identical config; gate-on survived that
  period (min balance $39.18) at a lower $/day. **This is a named, accepted
  risk, not a validated-safe setting** — if conditions revert toward
  2022-2024-style behavior after real money is live, this is the specific
  exposure being carried. Re-litigating this decision daily is not useful; but
  "no overriding it, ever" (the original framing below) no longer describes
  the system's actual configuration, and anyone reading this document should
  know that before assuming the gate is protecting anything right now.
- Original 2026-09-03 rationale, kept for context: the D1 EMA20 bias gate
  decides direction. On 2026-09-02 a blocked long (FVG_NY BUY at ~4378) would
  have stopped out on the very next candle — the gate was right and the
  hindsight-perfect entry was a fantasy.
- Open question for research (not a live override): the 20-day EMA is *slow* and
  held a stale bias through a full intraday reversal. Test faster variants
  (EMA10, H4 close, intraday EMA20 cross) — see Part V. (Tested 2026-09-06:
  `d1_proximity` k=0.3/k=0.5 variants both did *worse* than plain `d1_ema20` on
  the 4-year holdout — PF 0.859/0.897, both cratering to ~$7 minimum balance.
  Don't switch to proximity gating based on this evidence.)

### III.3 One frozen config
- After Part I passes, the config is **frozen**. Any change requires:
  hypothesis → backtest → holdout → 4-week paper test → written entry in
  `RESEARCH_LEDGER.md` → deploy.
- **No hot-patching a live bot.** (Done tonight because the running config was
  net-negative; it should be a once-a-quarter event, always logged, never
  routine.)

### III.4 Session discipline
- Trust the session gates. No extending a session because it "looks good."
- No entries in the **last 15 minutes** of a leg's session (not enough runway).

### III.5 News blackout
- Maintain a hardcoded list of high-impact events (US CPI, NFP, FOMC decision +
  presser, PCE, PPI, GDP, ISM, Fed Chair speeches, Jackson Hole, major
  geopolitical scheduled events).
- **No new entries from −15 min to +15 min** around each. Existing positions are
  left to their stops.
- Refresh the list on the 1st of every month from an economic calendar.

### III.6 The kill switch
- A `STOP` file in the project root. The loop checks for it every scan. If
  present: close all positions at market, halt, alert, do not resume until the
  file is removed *and* a reason is logged.
- Tested before go-live: create the file mid-trade, confirm flat + halted +
  alerted within one scan.

### III.7 Operator discipline (the human)
- **Check the bot twice a day** (morning, evening). Not more. Over-monitoring
  leads to over-intervening.
- **Do not watch ticks.** The expectancy plays out over hundreds of trades.
- **Red day:** the system working as designed. Do nothing.
- **Green day:** the system working as designed. Do nothing. Do not increase size.
- **Do not take it personally.** The market is not doing anything *to you*.
- Keep a one-page "why I built this and how it works" note. Re-read it on bad days.

---

## PART IV — RESILIENCE & OPERATIONS

*A bot that silently dies at 3 a.m. is worse than no bot.*

> **Status 2026-09-03 (rohith-2):** IV.2, IV.3, IV.5, IV.7 and the kill switch
> (III.6) are **implemented and tested** — `src/core/resilience.py`, hooked into
> `main_loop._run_guarded()`. `scripts/watchdog.py` exists (IV.1) but is not
> auto-started and has **no alert channel** yet. IV.4 (external heartbeat
> monitor), IV.6 (weekend/rollover/maintenance), IV.8 (structured logging) and
> IV.9 (daily report) are still to do.
>
> **Status 2026-09-06 addendum:** watchdog (IV.1) has no awareness of
> `protect_profit.py` and nothing monitors watchdog itself -- a real single
> point of failure in the chain, confirmed by direct code audit, not just
> unfinished. `logs/trade_ledger.jsonl` (meant to back IV.8/VI.4) is dead code
> -- nothing currently writes to it. A new item, **IV.11**, was built and
> verified this session and should be treated as part of this Part going
> forward.

### IV.1 Watchdog + auto-restart
- A separate supervisor (Windows Task Scheduler entry, or a tiny `watchdog.py`)
  that checks `main_loop` is alive every 60 s, restarts it on death, and
  **alerts** (Telegram bot / push / email) on every restart with the last 50 log
  lines.

### IV.2 MT5 reconnection
- Current behaviour: if the MT5 terminal drops, `copy_rates_from_pos` returns
  `None`, the loop hits `continue`, and it spins forever — no trades, no error,
  no alert.
- Fix: after 3 consecutive `None` fetches, call `mt5.shutdown()` + re-`initialize()`.
  Alert if reconnect fails 3×.

### IV.3 State persistence
- Write `last_fired_candle` and the open-position → magic map to a JSON file each
  scan. Reload on startup so a restart mid-candle cannot re-fire a signal.

### IV.4 Heartbeat + external monitor
- Touch `logs/heartbeat` with a timestamp every scan. A separate cheap monitor
  (phone cron, UptimeRobot on a pushed status file, etc.) alerts if it goes
  stale > 3 min.

### IV.5 Startup safety block
On every start, refuse to run unless ALL pass:
- symbol resolves and is tradeable
- spread is within sane bounds
- `account_info().login` matches the expected account number
- balance within an expected range (catches wrong-account connection)
- `trade_allowed` is True (catches investor-password connection — error 10017)
- AutoTrading enabled (catches error 10027)

### IV.6 Broker realities
- **Maintenance window:** Exness has a short daily maintenance window. Detect
  "market closed" / "trade disabled" and pause gracefully instead of retry-spamming.
- **Weekend:** gold gaps on Sunday open. Decide and document: **close all
  positions Friday ~21:00 IST**, no positions held over the weekend.
- **Rollover:** spreads balloon around 00:00 server time. No entries in that
  ±10 min window.

### IV.7 Single-instance guard
- Lockfile (`logs/main_loop.lock` with PID). Refuse to start a second instance.
  (The "two processes" scare on 2026-09-02 was a venv launcher stub, not a real
  double-run — but a real double-run is a genuine risk and this prevents it.)

### IV.8 Logging
- Structured JSON lines, rotated daily, retained 90 days.
- Log: every signal (fired / blocked / deduped + reason), every order (full
  request + full response), every SL/TP set, every gate decision, every
  exception with stack trace, every reconnect, every breaker trip.
- Goal: any trading day can be fully reconstructed from the log alone.

### IV.9 Daily auto-report
- 23:30 IST cron: trades today, P&L, balance vs plan, current drawdown, error
  count, bot uptime %, any breaker trips. Delivered to the operator.

### IV.10 Backups
- Repo is in git (done). Additionally: daily export of the MT5 account statement
  and the trade ledger to a dated file; weekly off-machine copy.

### IV.11 Config-integrity gate — NEW, built and verified 2026-09-06
- `src/core/system_config.py` fingerprints every value that changes a backtest
  result (lot size, exposure caps, trailing/pyramiding/D1-gate flags, every
  strategy's session/SL/TP/dedup settings) into one comparable snapshot, from
  either the live modules or a backtest run.
- `src/core/validation_ledger.py` (`research/validation_ledger.json`) records
  which exact configurations have actually been backtested and with what
  result. `main_loop.py` checks its live fingerprint against this ledger at
  startup and **refuses to trade a configuration nobody has validated**,
  naming the exact field that drifted.
- This exists because of a real, repeated failure pattern this project kept
  hitting: exposure caps raised in `execution_handler.py` without the backtest
  that "validated" portfolio_v4 ever being re-run against the new caps; a
  strategy bugfix silently changing what an unrelated holdout script tested;
  `EngineConfig`'s own defaults quietly reproducing already-fixed live bugs.
  Verified working: seeded with the current live config's real backtest
  result, then confirmed it correctly blocks a simulated revert of the
  HYP-046 fix with the exact drifted field named.
- **Not yet done**: `BacktestEngine` runs still don't auto-record into the
  ledger — that step is still manual (`validation_ledger.record(...)`), which
  means a backtest can be run, discussed, and never registered. This is the
  next real gap in this specific piece.

---

## PART V — STRATEGY IMPROVEMENTS (validate each before applying)

### V.1 On the table now
- **FVG size filter.** LuxAlgo test 2026-09-03: minimum ~$4.4 gap → PF 1.66 →
  2.11, max drawdown 28.5% → 19.6%, on ~half the trades. Validate on the
  holdout, then apply.
- **Faster D1 gate.** A/B EMA10 / H4 close / intraday EMA20 cross vs the current
  D1 EMA20. Pick by holdout PF. The current gate is too slow on reversal days.

### V.2 Exit research (currently the weakest-researched layer)
- Per leg, on the holdout: fixed TP (current) vs trail-after-1.5×ATR vs
  partial-at-2×ATR-then-runner vs ATR Chandelier vs time-stop-at-N-bars.
- The current fixed TP multiples were chosen on the *training* window.
- Also test: move stop to breakeven after +1×ATR (note: this can *hurt* by
  killing winners at BE — measure, don't assume).

### V.3 Regime & volatility gating
- Skip or halve size when ATR percentile > 90th (stops meaningless) or < 10th
  (targets unreachable).
- From I.6: turn each leg off in the regime where it bleeds.

### V.4 Per-leg spread gate
- FVG_NY ($5.50 stop) should reject entries at a spread that SQUEEZE_ASIA ($22
  stop) tolerates. Replace the single global `MAX_SPREAD_POINTS` with a per-leg
  value scaled to its stop distance.

### V.5 Leg-correlation check
- FVG_NY and RANGEREJECTION_NY trade the same session, often the same direction.
  Measure their trade-level correlation. If high, they are one bet at 2× size,
  not diversification — and `max_same_direction` should be 1, not 2.

### V.6 Account-level anti-martingale
- After a green week, allow the *upper* end of the sizing ladder; after a red
  week, the *lower* end. Systematic, bounded, not discretionary.

### V.7 What NOT to add
- No new strategies. No new indicators. No new timeframes. No fundamental-data
  pipeline. The research is explicit that over-filtering kills these systems and
  there are already enough entries. The missing piece is *proof*, not *more
  system*.

---

## PART VI — MONITORING, REVIEW & LEARNING

### VI.1 Weekly review (every Sunday)
- Actual vs backtest-expected for the week, per leg.
- Drawdown vs limits.
- **Rule-adherence audit:** did any manual intervention happen? Why? (The answer
  should almost always be "no".)
- Log it in a running `docs/trade_logs/WEEKLY_REVIEW.md`.

### VI.2 Monthly deep review
- Re-run the full backtest with the last month's live data appended.
- Has live PF diverged from backtest PF? By how much?
- If live is materially worse (see tripwire) for **2 consecutive months** →
  halt, re-run Part I.

### VI.3 The divergence tripwire (quantitative, not a feeling)
- Track rolling 30-trade PF from live results.
- **If it drops below 1.0 → pause new entries, investigate before resuming.**
- **If it drops below 0.8 → full stop, treat as edge decay, re-validate.**

### VI.4 Automated trade journal
- Every trade recorded with: leg, session, entry/exit, P&L, MFE, MAE, and what
  the backtest expected for that setup family. Builds the dataset for VI.2 and
  future research.

### VI.5 Edge-decay awareness
- All edges decay as they get crowded or as the regime that produced them ends.
- Quarterly: explicitly ask "is this still working, and is there a reason it
  might stop?" Plan for the day it stops, not just the day it works.

---

## PART VII — THE GO-LIVE GATE

*Real money does not start until every box is checked. The 2026-09-30 date is a
target, not a deadline that overrides this list.*

> **Honest status as of 2026-09-06** — see `REAL_MONEY_READINESS_RATING_2026-09-06.md`
> for full detail per item. Checked = actually done and verifiable; ✗ = not
> done; ~ = partial / done informally, not to this document's original bar.

**Edge (Part I):**
- [✗] Holdout test: PF > 1.2, drawdown < 45%, never below 50% of start — **fails as specified**: best measured result (post-fix, D1 gate ON, 4yr) is PF 1.180 (misses >1.2) with 83.9% max drawdown and min balance $39.18 (63% down, misses "never below 50% of start")
- [✗] Walk-forward: stable leg selection, median test PF > 1.2 — not done; calendar 6-month chunking (`edge_by_period.py`) was re-run and shows PF swinging 0.86-1.51 by period, not the pre-registered walk-forward protocol
- [✗] Monte Carlo: 95th-pct drawdown < 40%, P(ruin) < 1% — **run this session, fails badly**: P(ruin within 100 trades) = 42.3% even under the optimistic stats regime
- [ ] Parameter perturbation: PF > 1.2 across the ±20% cloud — not done
- [ ] Every leg clears its random-entry control on out-of-sample data — not re-done post-fix (historical HYP-020 found random-entry scored inside the same range as every real strategy pre-fix)
- [ ] Cost stress: PF > 1.2 at 2× cost with stop-slippage modeled — not done this session (engine uses one "realistic" cost scenario throughout)
- [ ] Long-history (Dukascopy) test covers ≥ 1 bear market and 1 chop period — not done; all testing this session stayed on the same Exness-sourced data
- [ ] 8+ week forward paper test, live-demo PF within 20% of backtest — not done; bot has been stopped, not paper-trading

**Rules (Parts II–III):**
- [~] Starting capital decided; if ~$100, first-phase risk accepted in writing — $100 confirmed, risk explicitly accepted in writing (HYP-048), but as an edge/regime bet, not this section's 5-9%-per-trade framing specifically
- [✗] Sizing ladder table filled in and coded as a balance lookup — not built; still fixed 0.01 lot regardless of balance
- [✗] All loss caps (daily/weekly/monthly/peak) decided and coded — only daily (6%) exists in code; weekly/monthly/peak are still just this document's prose
- [✗] Circuit breakers coded and unit-tested — not built (no consecutive-loss pause/stop)
- [✗] Profit ring-fencing schedule decided — not built
- [✗] News blackout list built and wired in — not built
- [✗] The rulebook is a single finished document — this document itself was abandoned mid-flight for 3 days; corrected 2026-09-06 but still not a finished, current rulebook

**Resilience (Part IV):**
- [~] Watchdog + auto-restart + alert — exists, restart logic present, but alert is a `print()` stub (no real channel), and watchdog doesn't monitor `protect_profit.py` nor is it itself monitored
- [x] MT5 reconnect — implemented (`resilience.py`, reconnect after 3 failed fetches)
- [x] Kill switch — implemented (STOP file); not re-tested mid-trade this session
- [x] Startup safety block — implemented; **extended 2026-09-06** with the config-integrity gate (IV.11)
- [✗] Structured logging + daily auto-report live — not built; `trade_ledger.jsonl` is dead code, `main_loop.log` is plain text
- [✗] Weekend flatten + rollover skip + maintenance-window handling coded — not built

**Operations:**
- [ ] One dry-run week where the operator follows the rulebook by hand to confirm
      it is actually followable — not done
- [x] Broker: master password, AutoTrading on, correct account verified — confirmed working this session (real MT5 deal history pulled successfully)
- [ ] "Kill criteria" document written — the conditions for shutting this down
      permanently — not written

---

## PART VIII — POST-LIVE OPERATIONS

- **Week 1–2:** minimum size regardless of what the ladder allows. Check daily.
  Intervene never (kill switch only).
- **First negative month:** mandatory halt + review. Do not "push through."
- **Monthly:** re-validate with live data appended (VI.2).
- **Quarterly:** full re-validation; assess edge decay (VI.5).
- **Scaling:** move up the sizing ladder only on balance, never on a good feeling.
- **The account is disposable.** If it blows the −30% peak kill, it is done —
  post-mortem, then decide from scratch whether to restart. It never gets a
  top-up.

---

## APPENDIX — EXPLICITLY DO NOT

- Do not optimise parameters to raise backtest PF (that *is* overfitting).
- Do not add strategies, indicators, or timeframes.
- Do not override the bot's direction based on a macro view.
- Do not move stops or targets on open trades.
- Do not add funds to a drawing-down account.
- Do not skip the holdout because training results look good.
- Do not go live on 2026-09-30 if the Part VII gate is not 100% passed.
- Do not run this on money you need for anything else.
- Do not confuse a high win rate with a good system — for this system they are
  opposites.

---

## PRIORITY ORDER (if time is short)

1. **I.1 Holdout test** — one script, one day. Go/no-go on everything.
2. **I.3 Monte Carlo bootstrap** — turns "35% drawdown" into a real worst case.
3. **II — write the rulebook** — it is the mission's actual deliverable.
4. **IV.1 + IV.2 + IV.6 watchdog / reconnect / kill switch** — stop the bot from
   dying silently.
5. **I.7 cost & slippage stress** — is PF 1.5 real or an artifact of optimistic
   fills?
6. **I.9 8-week paper test** — the clock on this starts the day the config
   freezes, so freeze early.
7. Everything else.
