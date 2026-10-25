# Phase 3 -- Genuine multi-strategy TP/SL in the backtest engine (2026-09-02)

## The gap (HYP-040)

`scripts/portfolio_merge_honest.py` (and the earlier per-session sweeps in
`scripts/phase3_worker.py`) validated portfolio_v4's four legs by running each
leg through its **own isolated** `engine.run([one_strategy], ...)` call --
`max_concurrent=1`, `max_same_direction=1`, its own `tp_atr_mult` /
`sl_atr_mult_override` set on the engine config -- then merging the resulting
trades chronologically onto one shared account in plain Python, applying the
6% daily-loss breaker manually.

That manual replay could not enforce the engine's real, shared
`_caps_allow` (`max_concurrent`, `max_same_direction`) or margin logic
(`_margin_allows`) *across* strategies, because each leg never knew the other
three existed. Two of the four legs (`fvg` NY and `range_rejection` NY) share
34.7% same-bar signal overlap, so the manual replay risked overstating the
portfolio's real PF/net$ by letting simultaneous entries through that a true
combined run's shared cap or margin check might have blocked.

## The fix

`EngineConfig` only ever carried one global `tp_atr_mult` / `sl_atr_mult_override`,
applied to every strategy in a run via `rm_mod.TP_ATR_MULTIPLIER` /
`_session_multiplier`. That's why the isolated-per-leg workaround existed at
all -- a single `engine.run([...])` call with multiple strategies had no way
to give each one its own stop/target.

`src/core/risk_manager.py`'s `calculate_atr_stops()` already gained a
`tp_multiplier: Optional[float] = None` parameter earlier the same night
(backward compatible: `None` keeps the module's `TP_ATR_MULTIPLIER`). And
`src/core/main_loop.py`'s live `_execute_signal` already reads
`getattr(strategy, "sl_atr_mult", None) or session_mult` /
`getattr(strategy, "tp_atr_mult", None)` per firing strategy and passes them
into `calculate_atr_stops`. The engine was the one place still stuck on the
single-global-override model.

**`src/backtesting/engine.py`** (`BacktestEngine._open`): added two optional
parameters, `sl_atr_mult` and `tp_atr_mult`, mirroring `main_loop`'s wiring
exactly:

```python
sl_mult = sl_atr_mult or session_mult
stops = rm.calculate_atr_stops(fill_price, is_buy, m15_view, sl_mult, tp_atr_mult)
```

The one call site in `run()` that opens a fresh entry now passes
`getattr(s, "sl_atr_mult", None)` / `getattr(s, "tp_atr_mult", None)` from the
firing strategy instance `s`. A strategy without these attributes gets
`None` for both, which reproduces the exact previous behaviour
(`session_mult` for SL, module `TP_ATR_MULTIPLIER` for TP) unchanged --
verified by test, see below.

The pyramiding path (`_pyramid` -> `_open`) was **left untouched**: it does
not pass `sl_atr_mult`/`tp_atr_mult`, matching `main_loop._check_pyramiding`,
which also calls `calculate_atr_stops` with only `session_mult` (no
per-strategy override) for a pyramid add. Reproducing that live asymmetry
faithfully, not "fixing" it, is in scope here -- portfolio_v4 runs with
pyramiding disabled anyway (see below).

Nothing in `src/core/main_loop.py` or `src/core/risk_manager.py` was
modified. `_make_risk_manager`, `_session_multiplier`, and every other engine
code path are unchanged.

## Tests added

`tests/unit/test_backtest_engine.py::TestPerStrategyExitGeometry` (4 new
tests, all passing):

1. `test_open_uses_the_strategys_own_multipliers_not_the_session_default` --
   unit level: `_open` given `sl_atr_mult=0.5, tp_atr_mult=2.5` on top of a
   `session_mult=1.5` produces a stop/target at 0.5x/2.5x ATR, not 1.5x/3.0x.
2. `test_strategy_without_the_attributes_keeps_the_session_default` --
   regression: omitting the new kwargs reproduces the exact old
   `session_mult` SL / module `TP_ATR_MULTIPLIER` TP.
3. `test_two_strategies_in_one_engine_run_each_get_their_own_stop` -- full
   `engine.run([tight, wide])` with two fake strategies (`sl/tp` 0.5/1.5 vs
   2.0/4.0) that both fire on the same bar: their resulting trades carry
   independently correct stop/target distances, proving neither strategy's
   geometry leaks onto the other's fill.
4. `test_third_strategy_without_attributes_is_unaffected_by_its_siblings` --
   a third, attribute-less strategy run alongside two attributed ones still
   gets plain session-default/global-TP geometry.

Result: `pytest tests/unit/test_risk_manager.py tests/unit/test_backtest_engine.py -q`
-> **54 -> 58 passed** (the 4 new tests), all green.
`pytest tests/unit/test_risk_manager.py tests/unit/test_backtest_engine.py tests/unit/test_research_sessions_atr.py -q`
-> **72 passed**.

**Pre-existing, unrelated issue found (not caused by this change, not
fixed):** running `tests/unit/test_backtest_engine.py` before
`tests/unit/test_risk_manager.py::TestDailyDrawdown::test_fails_closed_when_balance_is_unknown`
in the *same* pytest session makes that one test fail, because
`_make_risk_manager` patches `src.core.risk_manager.mt5` to the engine's stub
and nothing ever restores it -- a cross-test-file global-state leak that
predates tonight's per-strategy work (confirmed by isolating it to
`test_backtest_engine.py` + that one test with none of tonight's new code
involved). Order-independent (`test_risk_manager.py` before
`test_backtest_engine.py`, or either file alone) passes cleanly. Flagged
here rather than silently worked around; out of scope for this task since it
touches shared test-isolation behaviour, not the per-strategy TP/SL wiring.
`tests/unit/test_strategies.py`'s `TestMorningMomentum` failures are
unrelated: `src/strategies/morning_momentum.py` was deleted earlier tonight
(see `git status`) and its test file wasn't updated -- pre-existing, also
out of scope.

## The real portfolio_v4 run

`scripts/portfolio_merge_honest.py` and `scripts/phase3_worker.py` are
unchanged (per instructions -- no modification to the earlier work, this is
an independent one-off script in the scratchpad). A new one-off script ran
`PORTFOLIO_V4`'s four classes through **one genuine
`engine.run([...])`** call:

```python
cfg = EngineConfig(
    symbol="XAUUSDm", starting_balance=105.74, sizing_mode="fixed",
    fixed_lots=0.01, dedup_per_candle=True,
    daily_loss_limit_mode="balance_pct", daily_loss_limit_pct=0.06,
    history_bars=900, warmup_bars=950,
    enable_pyramiding=False, enable_consolidation_exit=False, enable_trailing=False,
)
strategies = [cls() for cls in PORTFOLIO_V4]
res = eng.run(strategies, start_ts=_ts("2026-05-21"), end_ts=_ts("2026-08-29"))
```

`enable_pyramiding`/`enable_consolidation_exit`/`enable_trailing` were turned
off to match the assumptions every leg was actually validated under
(`scripts/phase3_worker.py` sets all three off in the per-leg sweep that
produced the numbers in `docs/research/PHASE3_FULL_SWEEP_RESULTS.md`) --
leaving them on would have confounded "does the real concurrent-position/
margin cap change the result" with "does adding pyramiding/trailing change
the result," two different questions. `max_concurrent`/`max_same_direction`
were left at the engine's real production defaults (3/2), **not** each
individual leg's isolated `max_concurrent=1` -- that's exactly the cap this
run exists to test, applied here for the first time across all four
strategies sharing one account inside the actual engine loop rather than in
a post-hoc Python replay.

First attempt used the engine's live-fidelity defaults for pyramiding/
trailing/consolidation-exit (all on) as a sanity check and produced a clearly
broken result (PF 0.592, net -$94, max_dd 89%, `entries_blocked_margin`
6,090) -- pyramiding retried the same blocked entry every M1 bar for as long
as a position sat past the pyramid threshold, which is expected engine
behaviour but not what portfolio_v4's legs were validated against. Rerun
with the matched (pyramiding/trailing/consolidation-exit off) config below is
the reported result.

### Result: true engine-enforced run vs. the manual-replay estimate

| Metric | Manual replay (doc) | **Real `engine.run()`** | Delta |
|---|---:|---:|---:|
| PF | 1.512 | **1.479** | -0.033 (-2.2%) |
| Net $ | $703 | **$844** | **+$141 (+20%)** |
| Min balance | $106 | **$105.74** | ~flat (never dipped below start, same as claimed) |
| Max drawdown | 35.0% | **22.8%** | **-12.2pp, much shallower** |
| Trades | ~255 (sum of isolated legs) | 331 | +76 |
| End balance | -- | $949.68 | -- |

Per-leg trade counts, isolated (from the doc) vs. inside the real combined
run:

| Leg | Isolated | Combined (real) |
|---|---:|---:|
| SQUEEZE_ASIA | 49 | 86 |
| EMASTACK_LONDON_TIGHT | 70 | 113 |
| FVG_NY_TIGHT | 110 | 111 |
| RANGEREJECTION_NY_TIGHT | 26 | 21 |

Diagnostics from the real run: `entries_blocked_caps=3064`,
`entries_blocked_d1_bias=4710`, `entries_blocked_margin=0`,
`daily_shutdowns=15`, `duplicate_entries=124`.

### Interpretation -- does the real cap reduce the HYP-040 overstatement?

**Not in the direction HYP-040 feared.** The real, shared `max_concurrent=3`/
`max_same_direction=2` cap across all four legs did fire heavily
(`entries_blocked_caps=3064`), but the net effect on the headline numbers was
mildly *positive*, not negative: net$ is 20% higher and max drawdown is 12
points shallower than the manual-replay estimate, with PF essentially
unchanged (within 2%).

The mechanism: each isolated per-leg backtest that produced the
docs/research numbers used an artificially tight `max_concurrent=1` /
`max_same_direction=1` *for that one strategy alone* (`phase3_worker.py`).
The real portfolio doesn't share that restriction -- the shared cap is 3
concurrent / 2 same-direction *across all four strategies combined*. That
lets SQUEEZE_ASIA and EMASTACK_LONDON_TIGHT each take more trades than their
own isolated backtest ever allowed (a strategy can now hold a same-direction
add or a second signal that its own `max_concurrent=1` run would have
rejected), while FVG_NY_TIGHT and RANGEREJECTION_NY_TIGHT -- the two legs
HYP-040 flagged for 34.7% same-bar overlap -- see roughly flat-to-lower
trade counts (111 vs 110, 21 vs 26) because the shared cap does bind between
them when they fire together. Those two effects mostly offset in aggregate;
the net$ increase comes from the extra trades in the ASIA/LONDON legs, and
the drawdown improvement comes from the daily-loss breaker now interacting
with genuinely shared-account equity/margin bookkeping inside the real loop
instead of a manually replayed approximation of it.

**Bottom line: the manual replay's PF/net$ were not overstated by the
missing concurrent-position cap -- they were, if anything, mildly
understated on net$ and drawdown, because the per-leg isolated backtests
that fed it used a tighter-than-real per-leg concurrency limit that the real
shared cap doesn't reproduce.** The true, fully engine-enforced portfolio_v4
result is **PF 1.479, net $844, min balance $105.74 (never dropped below
the $105.74 start), max drawdown 22.8%** over 2026-05-21 to 2026-08-29 --
still the strongest validated portfolio result of the research effort, and
better on two of three headline metrics than what the manual-replay
workaround reported.

## Caveats carried forward

- Single ~100-day window, no holdout -- unchanged from portfolio_v4.py's own
  caveat.
- `entries_blocked_d1_bias=4710` is large relative to `signals_generated=2499`
  because the D1 bias gate is checked on every M1-cadence loop tick a cached
  signal is still live, not once per signal -- expected engine behaviour
  (`enable_d1_bias_gate=True` is the engine's live-fidelity default and was
  not touched here), not a new finding.
- This run, like the manual replay, is a screening-level result: it uses the
  real engine loop end-to-end for the first time for this portfolio, but the
  underlying entry rules and per-leg parameters are exactly the ones already
  documented in `docs/research/PHASE3_FULL_SWEEP_RESULTS.md` and
  `src/strategies/portfolio_v4.py` -- nothing about the trading logic itself
  changed.
