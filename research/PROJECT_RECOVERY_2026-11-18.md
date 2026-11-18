# Project recovery and evidence map — 18 November 2026

This is a recovery of the local repository at the beginning of finalization, not a new profitability backtest. The latest tracked commit at inspection was `1ee9f4d983e9e097bed6dcb0d2ff5fc3c3046a5f` (9 November 2026). A substantial later research working tree exists. A GitHub clone of that commit alone does not contain the complete local research record. No production configuration, broker connection, order or remote deployment was changed in this review.

## What was inspected

Read `.agents/AGENTS.md`, README, the decision log, the 1 November audit, the 11 November project review, the requested-period report, Genesis and Chandelier reports and selected underlying JSONs. Inspected the implementations of the eighteen-year test, signal-or-cost diagnostic, pre-registration checker, statistical primitives, startup checks, Atlas state persistence, watchdog, VPS updater, CI and test isolation. This is not a claim to have read every file or every previous conversation. Available conversation context was inherited in this chat; no private older chat retrieval was performed.

## The original portfolio failed its historical evaluation

Source: `research/registry/eighteen_year_holdout_2026-11-07.json`; runner: `scripts/validation/eighteen_year_holdout.py`; protocol: `research/registry/PREREG_EighteenYearHoldout_2026-11-07.md`.

| Historical cohort | Trades | Net USD | PF |
|---|---:|---:|---:|
| July 2004–December 2007 | 331 | -254.97 | 0.748 |
| 2008–2011 | 643 | -742.80 | 0.820 |
| 2012–2015 | 567 | 5.28 | 1.002 |
| 2016–2019 | 578 | -146.50 | 0.931 |
| January 2020–July 2022 | 437 | -172.36 | 0.944 |
| Pooled | 2,556 | -1,311.35 | 0.900 |

Every leg lost: AsianBreakout -$297.83 / PF0.216 /19 trades; AsianRangeFiltered -$224.13 / PF0.923 /651; LondonMomentumTight -$483.71 / PF0.901 /1,106; NYSessionReversal -$305.69 / PF0.937 /780. Rounded leg totals can differ a cent from pooled cash.

The runner creates a fresh engine/account for each era and pools realized trade P&L. Therefore pooled drawdown is a concatenated cash diagnostic, not an uninterrupted eighteen-year funded account. Historical M1 coverage has many partially populated candles even though no entirely missing candle was skipped in those eras. The name “holdout” describes its status when originally tested; it is now observed development information and cannot be reused as untouched evidence for a new model.

The source code computes PF as positive net cash divided by absolute negative net cash. Its failure is not simply a wrong PF formula. `signal_or_cost.py` preserves candidate entry timing, changes direction deterministically, and runs frictionless matched controls. Its saved verdict is that real direction does not beat the sampled control band. Controls change subsequent position occupancy, so they are diagnostic rather than perfectly identical realized trade sets. `bias_audit_2026-11-09.json` records target-first PF0.902 and adverse-gap PF0.892 versus baseline0.900: these conventions do not rescue profitability.

## Why attractive recent results do not qualify

The four legs were selected from 48 screened candidates and exit choices were fitted using modern data; the decision log explicitly records post-hoc choices. Corrected saved historical windows were DEV -$294.90 / PF0.658, TEST +$1,058 approximately / PF1.395, and RECENT +$790.14 / PF1.809. The DEV guard stopped new trading in May2023; it is not a full-window account result. The earlier DEV PF1.07 was not reproducible and was superseded. README still foregrounds favorable older headlines and must not be treated as a current evidence certificate.

The November2026 boundary remains protected by `load_master()` unless explicitly overridden. These existing reports do not prove the boundary has never been viewed by every external process or human; they establish the local declared policy. No November bars were loaded by this recovery.

## Research families already covered

| Family / evidence | Finding | Present status |
|---|---|---|
| Four original session legs | 2,556-trade older evaluation loses; direction diagnostic consistent with chance | Rejected as a real-money proposal |
| Twenty-one fixed trend, channel, range-expansion and mean-reversion candidates | Two Donchian survivors lose confirmation: PF0.823/149 trades and0.985/78 | Rejected; both also fail declared150-trade power gate |
| Volume search (latest tracked commit) | Commit records0 of8; magnitude information did not establish direction | Closed historical study; inspect full protocol before any revival |
| Stop, target, trailing and protector variants | Extensive selection history; no basis for arbitrary rescue optimization | Retain negative evidence and trial accounting |
| Original Genesis seven strategies and selector | No variant clears prior cross-era acceptance; reversal trigger and risk-rebasing defects | Archived research, no complete application parity or 2019–2026 proof |
| Chandelier/ZLSMA M1/M5, ordinary/Heikin-Ashi | Four variants lose in2013,2018 and2025; independent-provider2025 also loses | Rejected; separate audit unfinished |
| Turtle System2 | Wide long holds highly sensitive to funding; older eras fail; floating risk exceeds closed-cash risk | Not qualified for account deployment |
| Price-rule requested-date screens | Winners swap by era; only Forecast-to-Fill positive in both requested windows | Retrospective leads, not independent acceptance |
| COT, ETF flows, macro reaction, PAXG, miners, GVZ, auction and clock effects | Saved studies exist with heterogeneous vintages, coverage and methods | Must review individual protocols; positive small totals are not validation |

Sources are in `research/registry/`, `research/results/requested_periods_2026-11-11/`, `research/results/genesis_2026-11-11/` and the external-strategy database. The latter labels its claims unverified; external headline PF is not our empirical evidence.

## Recovered requested-window results

These M15/coarser research screens are specifically below the repository's current M1-only execution standard. Keep them as hypothesis triage, not accepted execution backtests.

| Candidate | 2019–2024 PF / net | 2026 Jan1–Oct29 PF / net | Limitation |
|---|---|---|---|
| Forecast-to-Fill | 1.266 /+$922.49 | 1.278 /+$618.49 | Only13 recent trades; approximate execution; both below earlier1.30 threshold |
| Daily RSI2 | 1.558 /+$516.95 | 0.554 /-$424.32 |55 older and6 recent trades; reverses sign |
| Supertrend4H | 0.793 /-$1,530.57 | 3.582 /+$4,085.50 | Only26 recent trades; older period loses |
| RSI2R3 2H | 0.739 /-$934.37 | 2.201 /+$1,174.20 | Older period loses;36 recent trades |
| Original four legs, exact older replay | Portfolio -$144.74 /1,039 trades | +$790.14 /54 trades, Jul6–Oct29 only | Different gate chains; contributions are not standalone strategies |

The 2019–2024 window is aggregate six-year profit, not profitability every year. The2026 window ends before October30, not today or year-end. Small archived positive realized-cash allocations are not equivalent to start-flat/end-liquidated replays.

## What is reliable and what remains uncertain

Reliable within explicit scope: arithmetic identities independently checked on saved orders; deterministic strategy interfaces; closed-bar fixes; M1-only mode; provenance policies; test isolation; frozen-configuration tests; durable halt mechanism; useful metric and bootstrap primitives. “Reliable” here does not mean live-broker equivalence or perfect behavior under faults.

Known weak points: historical bid-only reconstruction; partial M1 coverage; mixed broker/archive series; stale financing assumptions; independent chart data not raw-tick reconciled; reused research dates; unknown total search count; heterogeneous research simulators; limited full-gate parity; no current account-specific Atlas contract; no live-deal reconciliation certificate.

Governance defect observed: `prereg_check.py` prints uncommitted pre-registration/result pairs as “not committed yet” but does not add them to `bad`; it can return success and print “every result was pre-registered first.” Same-commit pairs are weak but also return success. Its pass status is insufficient evidence of prior commitment. Existing uncommitted November11 protocols cannot retroactively become pre-registered by committing them now. New questions require their own dated committed protocol before outcome inspection.

Reporting defect observed: the Chandelier report lists `chandelier_zlsma_audit.json`, but that file is absent at inspection. Treat the auditor as unfinished; do not quote an independent zero-error audit for that study.

## Justified directions, without claiming a new edge

First separate predictable volatility from predictable direction. A volatility forecast can improve sizing or abstention without producing profitable directional entries. Inspect large-return continuation versus reversal using past-only volatility normalization, matched clock/volatility controls and nonoverlapping targets. Study session transitions using named local timezones and daylight-saving calendars rather than fixed UTC approximations. Macro features require release-time availability and vintage controls; price-discovery claims require the appropriate futures/spot timestamped quotes, which are not presently a free complete order-flow dataset.

All such discovery uses already observed history as exploratory data. Freeze only a small economically motivated comparison family, then test incrementally against matched controls and stress costs. A profitable retrospective conditional cell is not a selected strategy. The parent finalization checkpoint records new work after this baseline.

## Governance repair completed during finalization

The concrete uncommitted-record defect described above was repaired in `scripts/validation/prereg_check.py`. It now checks every result, rejects uncommitted/dirty protocol/result pairs, and requires the original protocol-addition commit to be a Git ancestor of the original result-addition commit rather than comparing editable wall-clock dates. Legacy same-commit records remain visibly WEAK for compatibility; `--strict-weak` rejects them. Twelve real-Git regression cases passed, including reverse dates and divergent branches. Registry check currently returns failure:14 verified,3 weak,12 failed. This is an honest governance result, not a failed trading calculation. The checker proves recorded original-file ancestry, not actual execution timing or compliance with all later protocol amendments.
