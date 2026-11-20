# Causal gold sweep / imbalance adaptation

Recorded before first execution, no parameter search; existing historical eras already inspected.
Source: https://github.com/baturdenada/gold-sweep-backtester ; reviewed raw swings.py,
sweeps.py, imbalance.py, simulate.py, trend.py, params.py on 2026-11-11.
Independent implementation of described concepts; no third-party code copied or executed.

Source audit: OB end_index identifies the pre-impulse candle, allowing find_entry to start
on the still-unfinished confirming impulse. Entry-bar-close EMA filters also use information
unavailable at an earlier limit fill. Entry-bar target credit can use a high/low preceding
the limit touch. The source does not model executable bid/ask, costs or a single account's
overlapping exposure. A favorable source headline cannot resolve these issues.

Fixed M15 XAUUSD adaptation, two arms: unfiltered and EMA20/50 trend, parameters from
source M15 preset: strict 3-neighbor pivots, OB search through sweep+3, FVG start through
sweep+4, gap >$1, stop buffer $.5, pending expiry sweep+12, target2R, .02 lots.
Pivots become usable only after all three right-neighbor closes; consumed on first break
or sweep. If both pivot types qualify, high takes precedence as in source.
For each sweep, use first direction-aligned OB (opposite-colored candle then reversal
candle), confirmed only after reversal candle closes. If no OB by end of search, use first
aligned FVG already confirmed, otherwise wait for first gap through the declared window.
All orders active from following bar. Trend uses the preceding completed close and EMA.
Long limits trigger on ask low; short limits on bid high.
No limit slippage; stops and market exits slip $.02, commission roundtrip $.07, observed
bar spread or $.26 fallback, and swap per realistic_ecn. Stop first on dual-touch bars.
For non-open limit fills, defer targets on entry bar: a favorable extreme might precede fill.

Account overlays added explicitly: one position, cancel competing orders on fill, one-day
UTC levels/orders, no new entries at/after22:45, flat first open at/after23UTC or next day.
All bar gaps cancel pending entries and reset unconfirmed structures; existing positions
exit at next available opening quote, with gap-aware stops thereafter. Day resets differ
from whole-history source behavior. These are implementation choices, not exact replication.

Three eras 2005–11, 2012–18, 2019–25, fixed settings. Store dates, risk ratios, MC trade-order
resampling and ablations. Trade-PF>=1.3 all eras required to advance to minute-level Atlas
equity/payout/news evaluation. M15 adverse-excursion path is unknown, no Atlas compliance
claim at screen stage. November 2026 holdout excluded. Both arms count as research trials.

Execution correction recorded after the first run, before rerun: a marketable resting limit
fills at the better executable opening quote, not its stale limit price. Recompute 2R from
that actual fill. This corrects an overly pessimistic fill assumption rather than changing
signal parameters. Old dated records sweep_raw/sweep_ema remain retained as superseded
fill diagnostics; corrected records have the _executable_open suffix and a separate JSON.
Opening quotes beyond an attached stop invalidate the proposed bracket and are skipped;
this is an activation-rejection assumption, not verified broker pending-order behavior.
Any passing candidate must test those cases against actual broker rules/ticks before promotion.
