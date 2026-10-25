# Phase 6 — Execution-realistic backtester repairs (2026-09-01)

Four confirmed defects from `reports/PHASE_0_RESEARCH_AUDIT.md`, plus one new
measurement helper. Every change is additive and backward-compatible: a backtest
process already running on the old module image is unaffected, and every prior
call signature still works.

All broker numbers below are the live-queried values, not assumptions:
XAUUSDm, contract 100 oz, point 0.001, tick value $0.10/lot, volume_min/step
0.01, stops_level 0, leverage 200, swap_long −515.5 / swap_short 0.0 (mode 1),
server clock UTC+0.00, balance $105.74.

---

## Fix 1 — Overnight swap is now modelled, asymmetrically

**Was:** not modelled at all. Every backtest in this repo held longs across
nights for free.

**Now:** `CostModel` carries `swap_long_points` (−515.5), `swap_short_points`
(0.0), `enable_swap`, `rollover_hour_utc` (0.0, matching the UTC+0 server) and
an optional `triple_swap_weekday` (off by default — not verified on this
account). `CostModel.nights_held()` counts rollovers crossed; `CostModel.swap()`
converts points → price → account currency exactly as P&L is converted.
`BacktestEngine._close()` applies it: `net = gross − commission + swap`.
`Trade` gained `swap` and `nights_held` fields (both defaulted, so older
constructors still work), and the diagnostics carry `swap_paid` and
`swap_nights_charged`.

Arithmetic at 0.01 lot: `−515.5 × 0.001 × 100 × 0.01 = −$0.5155` per night for a
long; exactly `$0.00` for a short.

A new `SCENARIOS["observed_no_swap"]` exists so the size of this assumption can
be measured against `observed` rather than argued about.

**Tests:** `TestSwap` in `tests/unit/test_backtest_engine.py` — rollover
counting (intraday = 0 nights, 23:00→01:00 = 1 night, linearity, no negative
nights); the verified −$0.5155/night long rate and $0.00 short rate; a *flat*
long held two nights closing at −$1.031 net while an identical short closes at
exactly $0.00; and the off switch restoring the old behaviour.

**Expected direction of impact — measured, not guessed.** Replaying the swap
formula over two stored EMA_STACK trade sets:

| Run | Trades | Longs | Nights held | Net P/L | Swap owed | Swap as % of net |
|---|---:|---:|---:|---:|---:|---:|
| `stack_single_observed_t2s` | 1,420 | 885 | 219 | +$3,206.95 | **−$71.65** | 2.2% |
| `stack_single_observed_HOLDOUT` | 2,788 | 1,813 | 475 | +$648.74 | **−$147.43** | **22.7%** |

So the headline in-sample figures move only ~2%, but the holdout result loses
roughly **a fifth of its entire net profit** to financing that was never
charged. Note both runs compound, so swap scales with lot size — a strategy that
grows the account pays proportionally more. The structural conclusion stands
independently of the numbers: multi-day **longs** are now penalised and
multi-day **shorts** are not, so any future comparison of long-side against
short-side edge that predates this fix is biased in favour of longs.

---

## Fix 2 — Margin is now enforced

**Was:** only a `min_tradeable_balance` floor. The engine would happily hold
more concurrent positions than the account could fund.

**Now:** `EngineConfig` gained `leverage` (default 200.0), `enforce_margin`
(default True) and `margin_call_level_pct`. `BacktestEngine` gained
`margin_required(lots, price)` = `contract_size × price × lots / leverage`,
`used_margin()`, `floating_pl()` and `free_margin()` (equity-based, i.e.
including floating P&L, as MT5 computes it). `_open()` rejects an entry whose
margin exceeds free margin and counts it in `diag["entries_blocked_margin"]`.
The two duplicated floating-P&L loops in `_drawdown_breached` now call
`floating_pl()`.

**Tests:** `TestMargin` — `margin_required(0.01, 4428) == $22.14` exactly as the
audit derived; with position caps raised out of the way and $105.74 of balance,
**exactly four** 0.01-lot positions open and the fifth through tenth are
refused; the enforcement switches off cleanly; and a $20 floating loss reduces
free margin by exactly $20.

One existing test (`TestCaps::test_concurrent_and_direction_caps`) now passes
`enforce_margin=False`, because at HEAD's 15% risk sizing the *second* position
is genuinely unfundable — the caps test should test caps, and margin is covered
separately.

**Expected direction of impact:** strictly reduces trade count and therefore
gross P&L in both directions. Prior results configured `max_concurrent=3`, which
the audit already flagged as sitting at the edge rather than inside the limit —
but at HEAD's compounding 15% sizing, lots grow well past 0.01, so the true
binding constraint bites much earlier than "4 positions". Expect visible
divergence from prior results in any run using `sizing_mode="live"`; runs at
`sizing_mode="fixed"`/0.01 lot with `max_concurrent=3` should be nearly
unchanged, since 3 × $22.14 = $66.42 fits inside $105.74.

---

## Fix 3 — Session wraparound masking

**Was:** three near-identical private copies of `_session_mask`, disagreeing
with each other. `src/research/screener.py` and
`scripts/tier2_screen_survivors.py` computed `(h >= a) | (h < b − 24.0)` in the
wrap branch. For a session written `(21.5, 11.5)` that branch was **never
reached at all**: `b = 11.5 ≤ 24` sent it down the plain path
`(h >= 21.5) & (h < 11.5)`, which is empty for every bar — an overnight session
silently screened *zero* bars, and the screen reported the resulting trade count
as if it were the market's answer. `scripts/tier2_session_matrix.py` had a
different copy that handled `(21.5, 11.5)` but broke on the `(21.5, 26.5)`
spelling used by `market_study.SESSIONS`.

**Now:** one canonical implementation, `src/research/market_study.session_mask`,
which handles **both** spellings (`b > 24` normalises to a clock hour; `b < a`
wraps) and the `(0, 24)` all-day case. `screener._session_mask`,
`tier2_screen_survivors._session_mask` and `tier2_session_matrix._session_mask`
are now thin delegates, so the copies cannot drift again.
`market_study.session_of` also routes through it.

`scripts/phase3_tight_stop_search.py` also contains a masking helper but is
owned by other work and was **not** touched — it only implements the non-wrap
branch, so it is safe for the sessions it currently uses but would need the same
delegation before any overnight session is passed to it.

**Tests:** `TestSessionMaskWraparound` in
`tests/unit/test_research_sessions_atr.py` — a `(21.5, 11.5)` session now
includes 00:00, 02:00 and 11:00 bars (the half that was dropped); the old buggy
expression is pinned as selecting nothing, so a regression is unambiguous; both
spellings of the same window produce identical masks; ordinary non-wrapping
sessions are byte-identical to before, so no already-correct result moves;
`screener._session_mask` is proved to agree with the canonical one; and every
half-hour of the day is covered by exactly one entry of `SESSIONS`.

**Expected direction of impact:** no prior published result changes, because no
candidate in `src/research/candidates.py` uses a wraparound session — the bug
was latent. It would have silently corrupted the overnight/LATE-session research
Phase 2 intends to run.

---

## Fix 4 — `sl_atr_mult_override` verified wired

The override resolution was inlined in `run()`. It is now
`BacktestEngine._session_multiplier(rm, ist)` — same behaviour, but reachable
from a test rather than buried mid-loop.

**Tests:** `TestSlAtrOverride` — with no override, 13:00 IST resolves to the
live London multiplier 1.5; with `sl_atr_mult_override=0.5` it resolves to 0.5;
a 0.5 multiplier produces a stop distance that is **half** the 1.0 multiplier's,
to within one tick; and end to end, an engine configured with the override
opens a position whose stop sits at exactly `0.5 × ATR` from entry.

(The tolerance is one tick, not floating-point: `calculate_atr_stops` rounds
stops to the symbol's 3 digits, so exact halving is only recoverable to $0.001.)

**Expected direction of impact:** none on prior results — the config was dead,
so every prior run used the live session default (1.5 / 2.0) regardless of what
the manifest recorded. Any prior run whose manifest shows a non-null
`sl_atr_mult_override` did **not** actually apply it and must be re-run.

---

## Addition — `time_of_day_atr`

New function in `src/research/market_study.py`. Computes ATR conditioned on
hour-of-day alongside the flat 24h ATR, returning per-bucket ATR, sample counts,
a `bucket_ratio` correction factor (bucket ATR ÷ overall mean ATR) and a per-bar
`atr_tod` series. Bucket width is configurable (60 min → 24 buckets, 15 min → 96,
one per M15 bar of the day); buckets thinner than `min_samples` return NaN
rather than a fabricated average, and the per-bar series falls back to the flat
ATR there.

**Rationale (Andersen & Bollerslev):** intraday volatility follows a strong,
stable diurnal pattern. A flat 24h ATR is therefore *systematically* too wide in
quiet hours — the stop sits far beyond any plausible adverse move, so losers are
maximally expensive — and too tight in active hours, where the stop sits inside
routine noise and winners are stopped out before they work. That is a bias with
a known sign, not noise, and every `k × ATR` stop in this project inherits it.

**Nothing calls it.** Existing behaviour is untouched by construction; a test
asserts `flat_atr` is bit-identical to `atr()`.

**Tests:** `TestTimeOfDayAtr` — on synthetic bars with a known 3:1 diurnal cycle
it recovers the pattern and puts the active-hour ratio above 1.0 and the
quiet-hour ratio below 1.0 (i.e. it reproduces the stated direction of the
bias); bucket counts follow `bucket_minutes`; thin buckets are NaN and fall back
to flat; a bucket width that does not tile 1440 minutes raises. Note the
measured active/quiet ratio comes back at ~1.5 rather than 3.0 — ATR14 is a
trailing 14-bar Wilder average smeared across a 16-bar active window, which is
itself part of why a flat trailing ATR cannot track a diurnal cycle.

---

## Test run

```
venv/Scripts/python.exe -m pytest tests/unit/test_backtest_engine.py \
    tests/unit/test_research_sessions_atr.py tests/unit/test_risk_manager.py \
    tests/unit/test_strategies.py -q
→ 71 passed, 1 failed
```

24 tests in `test_backtest_engine.py` (10 new), 14 new in
`test_research_sessions_atr.py`. A full-run smoke test confirms `run()` still
completes end to end and that `leverage` / `enforce_margin` are captured in the
result manifest.

### Unresolved failures

**`test_risk_manager.py::TestDailyDrawdown::test_fails_closed_when_balance_is_unknown`
— pre-existing, not caused by this work.** Verified failing at the same
assertion *before* any Phase 6 edit. It lives in `src/core/risk_manager.py`,
which is live trading code owned by other work, so it was left alone. It asserts
`check_daily_drawdown(todays_pl=0.0)` returns False when balance is unknown; the
current implementation returns True (fails *open*, not closed). Worth flagging:
the test name says the intended behaviour is fail-closed, so either the
implementation or the test is wrong, and on live money the fail-open direction
is the dangerous one.

`pytest tests/unit` as a whole cannot be collected: 19 test modules import
`src.simulation`, `src.connectors`, `src.auth` and similar packages that do not
exist in this repo. Pre-existing dead tests from an earlier project, unrelated
to Phase 6.

---

## Files changed

| File | Change |
|---|---|
| `src/backtesting/costs.py` | swap fields, `nights_held`, `swap`, `observed_no_swap` scenario |
| `src/backtesting/engine.py` | swap applied in `_close`; `Trade.swap`/`nights_held`; margin config + `margin_required`/`used_margin`/`floating_pl`/`free_margin`; margin check in `_open`; `_session_multiplier` extracted |
| `src/research/market_study.py` | canonical `session_mask`; `session_of` routed through it; new `time_of_day_atr` |
| `src/research/screener.py` | `_session_mask` delegates to canonical |
| `scripts/tier2_screen_survivors.py` | same delegation (fixes the wrap bug) |
| `scripts/tier2_session_matrix.py` | same delegation (fixes the `b > 24` spelling) |
| `tests/unit/test_backtest_engine.py` | +`TestSwap`, +`TestMargin`, +`TestSlAtrOverride` |
| `tests/unit/test_research_sessions_atr.py` | new file |

Untouched as instructed: `src/core/main_loop.py`, `src/core/execution_handler.py`,
`src/core/risk_manager.py`, `scripts/phase3_tight_stop_search.py`, and the
reports owned by other work.
