# Result — 18-year holdout: the four live legs have no demonstrated edge

Pre-registered in `PREREG_EighteenYearHoldout_2026-11-07.md`, committed in
`499e306` before the test ran. Bar, eras, metrics and the consequence of a fail
were all fixed in advance.

**Verdict: FAIL.**

## What ran

The live four legs exactly as they trade — Asian Range Filtered 2.5/3.5, Asian
Breakout 3.0/5.0, London Momentum Tight 2.0/4.0, NY Session Reversal 2.5/4.5,
D1 EMA20 gate on for all four — through `BacktestEngine` with
`live_parity_preset`, `m1_policy="skip"`, `realistic_ecn` costs, 0.02 lots, 3
concurrent. Atlas rule engine off, so no early drawdown could end a run and hide
the rest of the record.

On 2004-07 to 2022-08: eighteen years, **2,556 trades**, none of it ever used to
select, tune or sanity-check these legs.

| era | trades | net $ | PF | win % | avg win | avg loss | worst DD | trades/mo |
|---|---|---|---|---|---|---|---|---|
| E1 2004-2008 | 331 | −254.97 | **0.75** | 31.1 | 7.35 | −4.44 | 254.97 | 7.9 |
| E2 2008-2012 | 643 | −742.80 | **0.82** | 34.5 | 15.27 | −9.82 | 886.39 | 13.4 |
| E3 2012-2016 | 567 | +5.28 | **1.00** | 38.1 | 12.79 | −7.86 | 309.52 | 11.8 |
| E4 2016-2020 | 578 | −146.50 | **0.93** | 35.8 | 9.50 | −5.70 | 247.43 | 12.0 |
| E5 2020-2022 | 437 | −172.36 | **0.94** | 37.3 | 17.67 | −11.14 | 375.89 | 14.1 |
| **pooled** | **2,556** | **−1,311.35** | **0.90** | **35.6** | 12.91 | −7.94 | 1,412.91 | |

Eras above PF 1.00: **1 of 5**, and that one is 1.00 to two decimals.

Per leg, pooled over the 18 years — **all four negative**:

| leg | trades | net $ | PF | win % |
|---|---|---|---|---|
| Asian Range Filtered | 651 | −224.13 | 0.92 | 40.4 |
| London Momentum Tight | 1,106 | −483.71 | 0.90 | 32.0 |
| NY Session Reversal | 780 | −305.69 | 0.94 | 37.2 |
| Asian Breakout | 19 | −297.83 | 0.22 | 21.1 |

Data quality: **zero** candles without minute bars and **zero** exits resolved
without them, in every era. The result is not an artefact of thin data.

## What it means

The portfolio's profit factor is **0.90 over 2,556 trades**. That is not a
regime story and not noise. The per-era numbers — 0.75, 0.82, 1.00, 0.93, 0.94 —
are strikingly stable around 0.90, which is the signature of a systematic small
negative expectancy, not of an edge that comes and goes.

The arithmetic says the same thing. Average win $12.91 against average loss
$7.94 is a reward-to-risk of 1.63, so these settings need a **38.0%** win rate
to break even. The legs deliver **35.6%**, consistently, across every era. They
are about two and a half points short of paying for themselves, and costs are
the difference.

So PF 1.40 on TEST and 1.81 on RECENT were **selection, not skill**. Those legs
were chosen by screening 48 strategies on exactly that data, and the stop and
target multiples were then fitted on it too. Picking the best of 48 on one sample
and reporting its performance on the same sample measures the search, not the
strategy. `research/DECISIONS.md` has said "post-hoc" against nearly every row
since 2026-10-29; this result is what that word was warning about.

The 2026-11-03..06 live losses, three stops out of four trades, are **not**
evidence of anything — 44% of four-trade runs lose three or more at a 42% win
rate. They are consistent with this result but far too few to show it. The
18-year test is the evidence.

## Consequences, as pre-committed

No era is re-cut, no leg dropped, no filter added and no stop re-tuned on this
data. That is how the current portfolio was built and it is what produced a
false positive.

1. **This portfolio must not be connected to real money.** There is no
   out-of-sample evidence it makes money, and 18 years of it says the opposite.
2. The Atlas evaluation plan is on hold until a candidate exists that passes a
   test like this one *before* going live, not after.
3. The demo may keep running as an infrastructure test — the execution path,
   alerts, journal and guards are worth exercising — but it is no longer a
   rehearsal for a funded account, and its P&L is not evidence either way.
4. The next search picks candidates on **2004-2022** and judges them on
   **2022-2026**, the reverse of what was done, so the judging data has never
   touched selection. Pre-registered before it runs.

## What was actually learned, and is worth keeping

- The execution stack is now sound and observable: minute-data honesty in the
  engine, one bar source, the broker measured at startup, the feed self-repairing,
  sixteen gates auditable in one command, and the holdout enforced in code.
- The research machinery works. This test is the first thing this project has
  run that could have failed, was set up to fail honestly, and did.
