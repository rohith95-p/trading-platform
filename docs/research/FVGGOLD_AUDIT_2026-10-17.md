# FvgGold EA audit (foeed/FvgGold-EA v2.01) - 2026-10-17

Verdict: **REJECT.** The headline claim (+48.7%, +$4,874 in 6 months at 0.01 lot) is arithmetically impossible for this EA's own rules, and no out-of-sample evidence of an edge exists in 4 years of XAUUSDm data.

Scope and method: source read via WebFetch only (raw.githubusercontent.com, GitHub commit pages); no code was cloned, installed or executed. Simulator: `scripts/research/fvggold_sim.py` (standalone, does not touch the main engine). Data: `research/data/XAUUSDm_{M15,H1,M1}.npy` (Exness trial feed, UTC, point 0.001, median spread ~$0.20-0.25, M15 2022-07-20 -> 2026-10-13, M1 only 2026-07-02 on). Nothing committed. Raw run output: scratchpad `fvg_out.txt/json` (reproduce with `venv\Scripts\python.exe -I scripts/research/fvggold_sim.py --out <json>`; ~5 min).

Caveat on the source read: WebFetch summarises through a small model and refuses verbatim dumps, so rules below are as reported by it, cross-checked by asking the same question from two angles (the MaxTrades/pending-order behaviour was asked twice). Re-read the .mq5 by eye before relying on any single line.

## 1. Exact rules (v2.01, main @ 2026-09-17)

| Item | Rule as coded |
|---|---|
| Execution | `OnTick`, every tick, no new-bar gate. FVG/OB scans use closed bars only (shift >=1). ATR(14) and H1 EMAs are read at shift 0 (forming bar; live values, not look-ahead). |
| FVG definition | For `i = 3 .. min(bars-3, MaxAgeBars+10)-1`: older = shift `i`, middle = `i-1` (its open time is the zone ID), newer = `i-2`. Bull: `low[newer] > high[older]` (top = low[newer], bottom = high[older]). Bear (only if not bull): `high[newer] < low[older]` (top = low[older], bottom = high[newer]). Wick gap only, no body requirement. Newest usable gap is detected on the first tick after the 3rd candle closes (age 2). |
| MinGapSize | `(top-bottom)/SYMBOL_POINT >= 25`. In price: $0.025 on a 3-digit XAUUSD (our feed) or $0.25 on a 2-digit one. Practically no filter at either value (median traded gap ~$1.23). |
| Age | `iBarShift(middle) in [2, 20]`. MinAgeBars=2 is a no-op (age >= 2 always). Zone is also pruned by wall-clock when `time < now - 20*900s` (effectively 19 bars). |
| Score (0-100, +20 OB) | `min(gap/ATR_M15(shift0),1)*30 + |body|/range(middle)*30 + 20*[type == H1 bias] + (1-age/20)*10 + 10*[bull: Bid<H1 EMA50 / bear: Bid>EMA50]`, +20 if OB confluence; rounded to 0.1. Must be `>= MinScoreFVG` (50). Re-scored every tick until it passes, then frozen. Max 120 with OB. |
| OB confluence | Impulse candle (shift 2..54) body >= 1.5 x ATR(shift0), preceded by an opposite-colour candle; OB = body of that prior candle, >= 10 points. Match if same-type OB overlaps the FVG or sits within 200 points ($0.20 on our feed) beyond it. OB only adds +20, never rejects (`UseOBFilter` name is misleading). |
| H1 bias | `+1` if EMA50(H1) > EMA200(H1), `-1` if <, both at shift 0. Price vs EMA is not used. Only FVGs with `type == bias` get orders. |
| Killzone (TimeGMT hour) | `7<=h<10` or `12<=h<21` (the "NY" window re-uses `KZ_OverlapStart`, so 12-21 is one contiguous window). `KZ_PreferOverlap=true` -> 12-16 only. Off: 10-12 and 21-07. |
| Order | Buy limit at `bottom + FVGBuffer/2` (bottom + $1.50), SL `bottom - FVGBuffer` (bottom - $3.00). Sell limit at `top - $1.50`, SL `top + $3.00`. SL distance is therefore a constant **$4.50**, TP **$6.75** (1.5R) whatever the gap size. No price rounding. |
| Placement gate | Buy skipped unless `ask - entry >= stopsLevel*point + spread` (so entry must be at least a spread below ask; sell mirrored). Skipped zones are retried every tick. Zone must be unmitigated: bull zone dies when `Bid < midpoint`, bear when `Ask > midpoint`. |
| Pending orders | `ORDER_TIME_GTC`, expiration 0. **Never cancelled** (no `OrderDelete` outside `CloseAtEOD`, which defaults to false). Not cancelled on mitigation, age-out or bias flip. |
| MaxTrades=1 | `CountMyPositions() + CountMyPending() >= MaxTrades` -> no new order. A stale unfilled pending order blocks the EA indefinitely (see 3). |
| Break-even | Every tick: long when `Bid - open >= 0.5*ATR_M15(shift0)` and `SL < open` -> `SL = open + 2 points` ($0.002); short mirrored with Ask. TP unchanged. No stops-level check, no spread allowance. |
| Daily loss limit | Server-day closed-deal P/L (profit+swap+commission) `<= -5.0` blocks NEW placements only; does not close positions or delete pending orders (so a pending order can still fill). Floating loss ignored. |
| Lot | `FixedLot=0.01` (1 oz on our spec). Risk-% sizing only if `FixedLot=0` (capped at min(0.10, 1% of balance), min-lot floor can exceed intended risk). |
| Spread | Only used in the placement `minDist` test. No max-spread filter; SL/TP are fixed price distances so a $0.20-0.25 spread is ~5% of risk on every trade. |
| Look-ahead / repaint | No future-bar access. Mild optimism by design: a gap is re-scored every tick until some tick passes the threshold (picks favourable Bid-vs-EMA / ATR instants), and a pruned zone can be re-detected and re-ordered later (the tag check only sees live orders/positions). Prune uses wall-clock `TimeCurrent`. |

## 2. Code vs README / description discrepancies

1. **Defaults changed after the backtest numbers.** Commit `f6226d4` (2026-09-12, "align defaults with docs") changed `MinScoreFVG` 55 -> 50, `RiskRewardRatio` 2.0 -> 1.5, `KZ_PreferOverlap` true -> false. The v2.0 code (2026-07-20) that existed when the Jan-Jul 2026 test could have been run had different defaults, yet the README says the tested/"optimized" values are 50 / 1.5 / 3.0 (which are v2.01 values). No optimisation method or out-of-sample result is given.
2. **Same commit fixed two bugs that invalidate any earlier backtest.** (a) `TrackDailyPL` accumulated (`+=`) deal P/L on every tick, so after one losing close the $5 limit tripped within a tick and stayed tripped (a win inflated it the other way). (b) `ManagePositions()` (break-even) sat after the daily-limit/killzone early returns, i.e. was unreachable much of the time. So v2.0 backtests ran with a broken daily limit and mostly-disabled break-even; v2.01 behaves differently and has no published backtest.
3. README "buy limit slightly above the FVG bottom": entry is bottom + **$1.50**; for the 57% of gaps narrower than $1.50 the entry is above the gap top, outside the FVG. SL is also fixed at $4.50 regardless of gap size, which is not "opposite edge + buffer" in any size-aware sense.
4. README session list ("London 7-10, overlap 12-16, NY close ~21") reads as three windows; code runs 12-21 contiguous (overlap and NY are one window), and the `KZ_PreferOverlap` toggle that README lists as false turns on exactly the other setting v2.0 shipped with.
5. `UseOBFilter` does not filter; `MinAgeBars` does nothing; `MinGapSize` is in points (unit depends on broker digits) while `FVGBuffer` is in price units: the two are inconsistent and the README does not say which broker digits were used.
6. "Daily loss limit $5" does not stop trading, close positions or cancel orders. "MaxTrades 1" counts pending orders, which the docs do not mention (see 3).
7. File header says ATR-based TP; default is R:R TP. Pending orders are never cancelled; failed orders retry every tick; `hATR_htf` handle is not validated; `CloseAtEOD` only fires if a tick lands in the 21:55 minute.
8. **Internal arithmetic of the claim** (below): 3-month window "Apr-Jul" is 4 calendar months, "6-month Jan-Jul" is 7; the 64-trade/6-month vs 35-trade/3-month split implies 29 trades in Jan-Mar made +43.5% while 35 trades in Apr-Jul made +5.2%.

## 3. As-coded behaviour: the EA jams

Simulating the code literally (variant A: GTC pending, never cancelled, MaxTrades counts pending) from 2022-07-20: **32 trades, then nothing**. A buy limit at 1752.87 placed 2022-11-30 was never touched again (gold ran to 4,400+), and `MaxTrades=1` blocks every later order. This is a direct consequence of the rules above, not a modelling artefact, although in live use a trader would eventually notice and delete the order. It also means any multi-year or any regime-spanning backtest of the published code is mostly a single stale order.

Because the as-coded EA cannot be evaluated over 4 years, the validation below uses **variant B**: identical in every respect except a pending order is cancelled when its FVG ages out (20 bars). This is the minimal fix that makes the signal testable and is more favourable to the strategy than the code.

## 4. Reproducing the claim (0.01 lot, $10,000, defaults, fresh state at window start)

Arithmetic first, independent of any simulation. SL = $4.50, TP = $6.75 for every trade at 0.01 lot (1 oz = $1 per $1).

- Best possible: 64 trades all winning = 64 x 6.75 = **$432 (+4.3%)**. The claim is $4,874, i.e. $76 per trade = 17 R-multiples per trade; a single trade cannot make more than $6.75.
- At the claimed 45.3% win rate (29 W / 35 L): 29 x 6.75 - 35 x 4.5 = **+$38 (+0.38%)** before spread, swap and break-even effects. The claim is ~127x larger (it corresponds to about 1.3 lots, not 0.01).
- 3-month claim: 40% of 35 = 14 W / 21 L -> 94.5 - 94.5 = **$0**; the claim is +$520 ($14.9/trade, 2.2x the maximum possible win).
- Most "wins" are not wins: in our simulation (variant B, path) 731 of the 1,258 profit>0 exits (58%) are break-even scratches of +$0.002, and only 527 (22% of all trades) reached TP. A 45% "win rate" says nothing about profitability.

Simulator, same windows (n / win% / PF / net $ / maxDD $; fill-bar model noted):

| Window | Variant | n | win% | PF | Net $ | Max DD $ |
|---|---|---|---|---|---|---|
| Jan 1 - Jul 31 2026 | A as coded, fill-bar TP allowed (user spec) | 66 | 51.5 | 1.53 | +72 (+0.7%) | 25 |
| Jan 1 - Jul 31 2026 | A as coded, OHLC-path fill model | 81 | 39.5 | 0.80 | -45 | 86 |
| Jan 1 - Jul 31 2026 | B age-cancel, fill-bar TP allowed | 393 | 48.1 | 1.21 | +177 | 96 |
| Jan 1 - Jul 31 2026 | B age-cancel, OHLC-path | 333 | 35.1 | 0.65 | -338 | 349 |
| Apr 1 - Jul 31 2026 | A as coded, fill-bar TP allowed | 38 | 42.1 | 1.09 | +8 | 50 |
| Apr 1 - Jul 31 2026 | A as coded, OHLC-path | 48 | 31.2 | 0.56 | -63 | 77 |
| Apr 1 - Jul 31 2026 | B age-cancel, OHLC-path | 186 | 35.5 | 0.61 | -203 | 212 |
| Jan-Jul 2026, v2.0 defaults (55/RR2/overlap) | A, fill-bar TP allowed | 38 | 28.9 | 0.77 | -27 | 45 |

The as-coded variant lands near their trade count (66 vs 64) because the EA jams, but net P/L is -$45 to +$72, i.e. between -0.5% and +0.7%, not +48.7%. **The claim is not reproducible and is arithmetically implausible for the stated lot size.** Plausible explanations (unverified): the tester run used a much larger lot or contract size than 0.01, or the figures were not produced by this code. Using the 2-digit-point assumption (MinGapSize = $0.25) changes nothing material (Jan-Jul B-path PF 0.64).

## 5. Validation (variant B, all defaults pre-registered, no tuning)

Splits by fill time: DEV 2022-07..2024-12, VALIDATE 2025-01..2026-06, HOLDOUT 2026-07..2026-10-13 (the only period with M1 data). Start balance $10,000, 0.01 lot.

**Intrabar ordering matters more than any edge.** On M15-only data a limit order that fills and reaches TP inside one bar cannot be ordered. 48% of fills happen in the placement bar. Three models were run:
- `on` (user spec: SL/TP walked from the fill bar, stop-first, TP allowed on the fill bar): optimistic.
- `off` (no TP/BE on the fill bar): pessimistic bound.
- `path` (TP/BE on the fill bar only if the bar's OHLC path allows it: bullish O-L-H-C for longs, bearish O-H-L-C for shorts): calibrated against M1 ground truth on the holdout. On the 2026-07-02+ period M1 truth gives net -$125 (n=162) while M15 `on` gives +$27 (n=170) and M15 `path` gives -$153 (n=154) and `off` -$169. `on` overstates by ~$150 per 160 trades; `path` is slightly pessimistic. The calibration used the holdout only to pick an execution-ordering model, not to tune any strategy parameter, but it is still a choice made after seeing that period.

| Model | Period | n | Win% | PF | E[R] | Net $ | Max DD $ (%) |
|---|---|---|---|---|---|---|---|
| path | DEV | 1293 | 60.2 | 0.84 | -0.052 | -300 | 363 (3.6) |
| path | VALIDATE | 908 | 44.9 | 0.81 | -0.099 | -403 | 468 (4.7) |
| path | HOLDOUT (M1) | 161 | 44.7 | 0.63 | -0.197 | -143 | 170 (1.7) |
| path | DEV+VAL | 2201 | 53.9 | 0.82 | -0.071 | -703 | 763 (7.6) |
| path | ALL | 2362 | 53.3 | 0.81 | -0.080 | -846 | 924 (9.2) |
| on | DEV | 1434 | 53.1 | 0.91 | -0.021 | -134 | 151 |
| on | VALIDATE | 1035 | 50.5 | 1.26 | +0.098 | +458 | 132 |
| on | HOLDOUT (M1) | 164 | 45.7 | 0.66 | -0.167 | -123 | 143 |
| on | DEV+VAL | 2469 | 52.0 | 1.10 | +0.029 | +324 | 151 |
| off | DEV+VAL | 2157 | 51.6 | 0.81 | -0.080 | -777 | 830 |

The only configuration with PF > 1 is the optimistic `on` model, and even there the edge is not stable: DEV 0.91, VALIDATE 1.26, HOLDOUT 0.66. Max single-trade $ is bounded (+6.75 / -4.50).

By year, `path` (PF): 2022 1.01, 2023 0.84, 2024 0.78, 2025 0.89, 2026 0.67. `on`: 0.76 / 0.91 / 0.95 / 1.19 / 1.12. By killzone (path): London 0.81, Overlap 0.79, NY-late 0.84. By score (path): 50-59 0.87, 60-69 0.76, 70+ 0.78 (higher score does not help). Long 0.81 vs short 0.81. Total swap paid -$47; gross price P&L -$799 (`path`); 910 of 2362 trades exit at break-even (731 exit at +$0.002, 179 exit below zero after gapping through the moved stop; mean -$0.17). ~46 trades/month.

Comparison: our FVG_NY_TIGHT_V5 over 2022-26 is PF ~0.97. FvgGold under the honest `path` model is worse (0.82 DEV+VAL); under the optimistic model it is 1.10 with the instability above. It is not an improvement and not a candidate to add to the portfolio.

### Cost stress (variant B, path)

| Scenario | DEV+VAL PF | DEV+VAL net $ | HOLDOUT PF |
|---|---|---|---|
| Base | 0.82 | -703 | 0.63 |
| Spread x2 | 0.75 | -1000 | 0.59 |
| +$0.30 slippage per fill (entry and exit) | 0.58 | -1636 | 0.48 |
| Spread x2 and +$0.30/fill | 0.53 | -1826 | 0.39 |
| Swap x3 (-$1.50/night long) | 0.80 | -797 | 0.63 |
| No swap | 0.83 | -673 | 0.63 |

At a $4.50 stop with a $0.20-0.25 spread plus any slippage, costs are 5-15% of risk per trade. Even the optimistic model goes to PF 1.00 (spread x2) and 0.71 (slippage) on DEV+VAL.

## 6. Component ablation (DEV+VAL only; holdout shown for information only)

Baseline path: PF 0.82 (n 2201). Baseline on: PF 1.10 (n 2469).

| Ablation | path: n / PF / net $ | on: n / PF / net $ | Reading |
|---|---|---|---|
| (a) no score filter | 2362 / 0.79 / -912 | 2643 / 1.01 / +51 | Score filter adds ~0.03 (path) to ~0.09 (on) PF; small, consistent sign, still < 1 on path |
| (b) no H1 trend filter | 2584 / 0.86 / -643 | 3035 / 1.15 / +558 | Trend filter **removes** PF (0.04 / 0.05); the EMA50/200 gate hurts |
| (c) no killzone | 3314 / 0.85 / -859 | 3810 / 1.06 / +288 | Killzone costs PF in path (0.82 vs 0.85), helps in on; no robust contribution |
| (d) no break-even | 1792 / 0.88 / -606 | 1889 / 1.08 / +396 | Break-even **removes** PF in path (0.82 vs 0.88) and is neutral in on (1.10 vs 1.08); its main visible effect is converting trades into +$0.002 scratches, which inflates the win rate |
| (e) market entry at formation | 3447 / 0.92 / -613 | 3447 / 0.92 / -613 | Order-independent (no fill-bar ambiguity). Limit entry is better than market only under the optimistic fill model; under path it is worse (0.82 vs 0.92) |
| (f) no OB bonus | 2187 / 0.82 / -713 | 2459 / 1.11 / +345 | No contribution |

No component shows a robust positive contribution across both fill models and all three periods. The only fairly clean result is market entry (0.92), the one variant not dependent on intrabar assumptions, and it is also a loser (HOLDOUT PF 1.29 on 235 trades is within noise and E[R] is still -0.027).

## 7. Caveats and what this does not show

- One feed (Exness trial, ~$0.20-0.25 spread). A tighter-spread broker would help, but costs are not what makes the claim impossible.
- Decisions are evaluated once per M15 bar open, not every tick; ATR(shift 0) is approximated by the last closed bar; OB state is approximated (current-ATR impulse test, current Bid vs OB edge). The EA's tick-level re-scoring would admit somewhat more trades at favourable instants. None of these can create the +17R/trade the claim needs.
- Fill-bar ordering is the dominant uncertainty (PF 0.81 to 1.10 on DEV+VAL by model). It is resolved only for 2026-07-02 onward via M1. I cannot rule out that a true tick replay of 2022-2026 sits between the `on` and `path` results; the evidence from the only period with ground truth is that it sits at `path` or below.
- Swap model approximate (UTC midnight crossings, Wed x3, longs only). Daily-limit uses UTC days, not broker server days. No commission assumed.
- Sample sizes are adequate (2,000+ trades) for PF to +-0.1, but the strategy is one regime-dependent family on one instrument; 4 years of mostly-rising gold. Not independently replicated on another instrument.
- v2.0 (the code of the claim's era) is not simulated with its daily-P/L bug; only its parameter defaults (55 / RR 2.0 / overlap-only) were run: B-path PF 0.85 DEV+VAL, 0.51 holdout.

## 8. Verdict

**REJECT.** (1) The claimed return cannot occur at 0.01 lot with a $4.50 stop / $6.75 target: the maximum conceivable profit of the stated trade count is 4.3%, and the stated win rates imply 0.38% and 0%. (2) The published code jams after a stale GTC pending order, so any long test is mostly a frozen EA. (3) After the minimal fix, the strategy shows PF 0.82 (honest fill model) to 1.10 (optimistic) on 2022-07..2026-06 and PF 0.63-0.66 out of sample on 2026-07+, with no robust contributing component, and it dies under a modest cost stress. (4) The README/code mismatches (defaults changed after the numbers, daily-P/L and break-even bugs fixed after the numbers) mean the published numbers do not correspond to the published code. Nothing here is evidence of profitability; do not add it to the portfolio.

If someone wants to keep an "awaiting" door open, the only way to re-open it is a tick-level MT5 tester run of the exact v2.01 file on this broker's history with a stated lot size, deposit, spread model and the saved report.
