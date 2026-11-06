# PREREG: do these four legs have an edge at all? 18 years never used to pick them (2026-11-07)

**Owner's question, 2026-11-07:** "the strategies do not have a clear edge right now... why? Solve the issue."

**Why this test exists.** Every number this project has reported came from data that
was used to choose something. The four legs were selected by screening 48
strategies on DEV (2022-08..2024-06), TEST (2024-06..2026-01) and RECENT
(2026-07..2026-10); the stop and target multiples were then chosen by a
60-combination sweep on DEV+TEST and sanity-checked on RECENT. So PF 1.40 on TEST
and 1.81 on RECENT are in-sample for leg selection, and `research/DECISIONS.md`
marks nearly every live decision "post-hoc". There is, as of today, **no
out-of-sample evidence that this portfolio has an edge**, and that is the honest
state of the project, not a detail.

The archive reaches back to 2004-06. Nothing before 2022-08 has ever been used to
select, tune, filter or sanity-check these legs. It is therefore a true holdout —
18 years of it, roughly nine times the length of DEV.

**What runs.** The live four legs exactly as they trade
(`src/strategies/portfolio_atlas.py`: Asian Range Filtered 2.5/3.5, Asian
Breakout 3.0/5.0, London Momentum Tight 2.0/4.0, NY Session Reversal 2.5/4.5; D1
EMA20 gate on for all four), through `BacktestEngine` with
`live_parity_preset`, `m1_policy="skip"`, `realistic_ecn` costs, 0.02 lots, 3
concurrent, 3 per direction. The Atlas rule engine is **off**, so one early
drawdown cannot end a run and hide the rest of the record; Atlas survivability is
a separate question from whether an edge exists.

**Eras,** fixed before running, chosen as equal calendar blocks and not by
inspecting results:

| era | from | to |
|---|---|---|
| E1 | 2004-07-01 | 2008-01-01 |
| E2 | 2008-01-01 | 2012-01-01 |
| E3 | 2012-01-01 | 2016-01-01 |
| E4 | 2016-01-01 | 2020-01-01 |
| E5 | 2020-01-01 | 2022-08-01 |

**Reported per era, and pooled:** trades, net, profit factor, win rate, average
win, average loss, worst drawdown, trades per month, and the minute-bar coverage
the engine actually had (`bars_skipped_no_m1`, `exits_unchecked_no_m1`) so a thin
era cannot be mistaken for a good one.

**Dollar amounts are not comparable across eras** and will not be read as if they
were: lots are fixed at 0.02 while gold ran from $400 to $1,800 over these eras,
so ATR-sized stops are worth a fraction of today's in dollars. Profit factor and
win rate are the measures that carry across; net dollars are reported for
completeness only.

**The bar, set now:**

1. **Pass:** pooled profit factor >= 1.15 **and** at least 4 of the 5 eras
   individually above 1.00.
2. **Weak pass:** pooled PF >= 1.05 with at least 3 of 5 eras above 1.00 — an
   edge too small to carry costs and slippage reliably, and not something to put
   real money behind without more work.
3. **Fail:** anything else. In particular, a pooled PF below 1.00 means these
   legs do not have an edge and the 2024-2026 result was selection, not skill.

**Pre-committed consequence of a fail.** No attempt to rescue the result by
re-cutting eras, dropping a leg, adding a filter or re-tuning stops on this data —
that is precisely how the current portfolio was built. A fail means the honest
statement goes to the owner and the next step is a fresh search whose candidates
are chosen on 2004-2022 and judged on 2022-2026, the reverse of what was done.

**Known limitation, stated before seeing anything.** The pre-2022 minute bars come
from the third-party archive, which agrees with the broker's own candles to a
median 5 cents over 2022-2025 but cannot be checked at all before 2022, since the
broker's history does not reach there. Era coverage is reported alongside each
result for that reason.

Run: `python -I scripts/validation/eighteen_year_holdout.py`
