# Ultra Core: deployment and edge-research plan

Prepared 11 November 2026. Planning only: no source, strategy, risk, account or deployment settings changed in this phase.

## Decision

Keep the software foundation. Repair its safety, experiment records and evaluation path before selecting a replacement strategy. Treat the current four legs as research baselines, with no claim to a deployable edge.

Overall engineering foundation: **6/10**. Research/evaluation credibility: **4/10**. Readiness to allocate money on the current strategy evidence: **2/10**. These are engineering judgments based on the reviewed paths, not measured percentages of correct code or probabilities of success. Ten would require reconciled production behavior and strong validation, not merely passing tests.

The previous review did not inspect every possible source line or certify security. It did run 513 passing tests and eight replays, independently checking arithmetic across 2,995 trades. Its confirmed findings are in REVIEW.md. Web research here checked relevant official documentation and primary research; it does not certify Atlas's private account settings or settle contradictions in its public pages.

## Scorecard

| System | /10 | Keep | Main work needed |
|---|---:|---|---|
| Folder and module organization | 7 | src/core, strategies, backtesting, atlas, research separation | Clear supported entry points; move dated study runners behind reproducible experiment manifests |
| Code maintainability | 6 | Explicit classes, signal interface, useful module boundaries | Remove stale claims, reduce shared mutable globals/import side effects and duplicated decision logic |
| Orchestration and candle handling | 6 | Feed repair, closed-bar logic, startup checks, locking | Fast independent risk supervision; deterministic timing and recovery tests |
| Order execution | 5 | Attached stops, account checks, retries, some null-reply protection | Durable order-intent lifecycle, partial/unknown outcomes, actual fills, broker-native sizing/preflight |
| Risk and state | 5 | Persistent halts, exposure caps, sizing floor, veto chain | Fail closed on state/evaluation failure; bind state to account; aggregate cash risk at stops |
| Atlas adapter | 4 | Pure rule engine, phase concept, documented rules | Account-specific confirmed rule version, exact official ledger plus separate internal buffers, payout lifecycle |
| Historical data and provenance | 5 | Central merge policy, individual manifests, cutoff | Real merged hashes, bid/ask ticks where needed, coverage eligibility and point-in-time features |
| Replay engine | 5 | M1 fills, D1 reconstruction, useful parity switches | End-boundary fix, same gate domain as live, continuous equity and state across windows |
| Cost and broker portability | 4 | Explicit spread/slippage/commission/swap | Measure Atlas terms/fills; financing schedules, currency conversion, dynamic costs and gap stress |
| Metrics and statistical inference | 3 | Useful metric primitives and bootstrap tools | Sortino, Calmar consistency, calendar returns, dependence-aware inference and correct interpretations |
| Experiment governance | 4 | Preregistrations, decisions, trial and holdout concepts | Immutable full-parameter records, source/data hashes, overlap-aware holdouts and complete candidate matrices |
| Strategy portfolio / demonstrated edge | 2 | Baselines and failure evidence | New economically motivated hypothesis; credible incremental net return versus matched controls |
| Tests | 7 | 513 passing behavioral/regression tests | Independent oracles, failure injection, boundary/property tests, Windows/MT5 integration |
| Monitoring and audit trail | 7 | Alerts, journal, heartbeat, reason-coded refusals | End-to-end signal/order/deal reconciliation, stale-state health, metrics on actual risk headroom |
| Packaging and deployment | 4 | Pinned direct packages and VPS runbooks | Clean locked environment, tested immutable release, targeted service control, rollback/restore drills |
| Documentation | 4 | Detailed incident and decision history | Replace superseded headline statistics; generated current-system facts and clearly labeled old research |
| Secrets and isolation | 5* | Local secrets excluded from Git, owned-position scoping | Dedicated trading account/process identity, secret redaction/rotation and artifact access review |

*Security score is provisional: no credential scan, penetration test or full dependency-security audit was performed. Do not average these scores into a safety percentage; a single critical execution defect can block deployment.

## What the profit factor means

PF = sum of positive net trade P&L / absolute sum of negative net trade P&L. Net means spread/fills, commission and financing have been accounted for with stated assumptions.

The corrected PF calculations reproduced: DEV 0.658, TEST 1.395, RECENT 1.809, historical pooled 0.900. Their arithmetic is not all false. Their use as a forecast is unsupported because choices were made while inspecting the favorable modern periods, the pipeline has known defects, and the long sample uses imperfect historical data and assumed costs. Fixing a formula or bug requires a versioned rerun; it does not imply that the corrected strategy will become profitable.

The old five-era result resets account state between eras. It is neither a single uninterrupted 18-year account nor an Atlas pass/payout simulation. Its negative P&L is evidence against this tested portfolio; it does not prove that gold has no tradeable predictability. Dependence-aware uncertainty also matters: this review's pooled month-block expectancy interval was [-$1.024,+$0.006], narrowly including zero.

## Atlas verification before capital deployment

Planning assumption: Access CFD program on MT5, with $5,000 used only for examples. Exact account size, phase, account identifier, server, signed agreement, add-ons and displayed dashboard rules must be captured before implementing final limits.

The Access page currently lists evaluation/funded trailing equity limits of 10%/6%, daily limits 5%/3%, and a 3% evaluation target. Funded qualification includes three >=0.5% days and a payout-cycle best-day limit, with a size-dependent exception. MT5 funded leverage is stated as 1:50. These program values are inputs to verify, not a substitute for an account contract. [Access](https://help.atlasfunded.com/access)

Use the following rule distinctions in the design:

| Topic | Public evidence checked | Planned treatment |
|---|---|---|
| Access total drawdown | Specific drawdown page: peak equity multiplied by one minus limit | Exact official floor, including unrealized peaks, tracked separately from our earlier internal stop. [Source](https://help.atlasfunded.com/max-drawdown) |
| Daily anchor | Specific daily page: equity at 00:00 UTC; general rules page: prior-day high | Record conflict; reconcile signed account/dashboard/support evidence. Do not hardcode either as universally settled. [Specific page](https://help.atlasfunded.com/daily-loss), [general page](https://www.atlasfunded.com/trading-rules) |
| News | Funded profit deductions for opening or closing in restricted windows; evaluation treated differently | Exact phase-aware accounting; fresh account-specific calendar; model deductions even for SL/TP executions. [Source](https://help.atlasfunded.com/news-trading) |
| Short holding periods | Funded profitable closes under 3 minutes lose their profit; losing trades remain losses | Simulate deductions rather than suppress emergency exits. Strategy horizon must be compatible. [Source](https://help.atlasfunded.com/short-trades) |
| Protector | Specific page: funded floating-loss threshold, strike count and lifetime split reduction | Preserve event/strike state across restarts; reconcile conflicting general-page wording before deployment. [Source](https://help.atlasfunded.com/atlas-protector) |
| Profit split | Profit-split help page and Terms give different defaults | Use actual contract and payout screen; carry conservative alternatives in economics until resolved. [Help](https://help.atlasfunded.com/profit-split), [Terms](https://www.atlasfunded.com/terms) |
| EA permission | Platforms help allows EAs; Terms includes approval wording | Obtain account-specific written resolution; no assumption that the conflict is already closed. [Platforms](https://help.atlasfunded.com/platforms), [Terms](https://www.atlasfunded.com/terms) |
| Instrument concentration | General rules page says the old one-sided rule was removed | Remove false official labeling if confirmed for account; an internal concentration limit can remain explicit. [Source](https://www.atlasfunded.com/trading-rules) |
| Payout eligibility | Closed-profit days and consistency differ from hard account breaches | Separate eligibility, deductions, strikes and permanent breaches as different state transitions. [Eligibility](https://help.atlasfunded.com/payout-eligibility), [consistency](https://help.atlasfunded.com/consistency) |

No messages to Atlas were sent. Rule reconciliation is an explicit future input, not a request for permission to continue the present planning task.

There should be two ledgers: (1) the exact account rules and official account events; (2) our strategy's deliberately tighter exposure, daily stop and safety reserve. This makes it possible to see whether an order was rejected by Atlas or by us. A local conservative stop is recoverable under policy; an actual firm breach is not fixed by restarting at midnight.

## Stage 1 — engineering and safety repair

Do these before a capital-enabled release. Continue independent historical diagnostic work only where its outputs remain clearly labeled.

| ID | Defect or required improvement | Acceptance evidence |
|---|---|---|
| S01 | Risk evaluation exceptions and unreadable state can permit continuation | Inject corrupt/missing/stale state and exceptions: zero new orders, visible halt, existing risk handled by declared fail-safe policy |
| S02 | Atlas state can restart fresh after corruption or phase mismatch | State bound to account/server/program/initial balance/phase; reconcile from authoritative history; no invented lower peak or clean strike count |
| S03 | News monitor maps missing/failed data to an empty event list and does not validate calendar age on use | Separate EMPTY_VALID from UNKNOWN/STALE/ERROR, validity horizon, clock checks, bounded retries; missing calendar blocks new funded exposure |
| S04 | Broker differences currently warn; several calculations assume Exness contract, USD and fixed leverage | Enforce an approved broker profile; use account-currency profit/margin calculations, volume steps, stop/freeze levels and supported fill mode |
| S05 | Null/partial/ambiguous execution cannot be reconciled by position count alone | Persist an intent ID before send; reconcile matching orders/deals/positions; handle partials and actual fills; no blind duplicate resend |
| S06 | Risk projection uses fallback lots/approximations before executor selects actual lots | Compute one final executable order specification, stop loss in account currency, aggregate risk of every open position and correlated exposure, then revalidate after repricing |
| S07 | Risk supervision shares the minute scan and can be delayed by slow work | Independent faster risk path and latency measurements; SL/TP verified at broker; test signal-loop hang, disconnection and gap scenarios. No claim that software can prevent all gap losses |
| S08 | Rule implementation differs from documented account formula and applies stricter rules across phases without separate labels | Account-specific fixtures for exact rules, plus independently named internal buffers; reproduce both paths in replay |
| S09 | Cash-risk helper is 100x wrong for cached gold contract | Contract-aware oracle cases across gold/FX/indices; display and decision values agree; no hardcoded universal contract size |
| S10 | Broad updater stops every Python process, copies latest master in place, changes dependencies, then restarts | Pinned release artifact, dedicated service/PID control, staged environment, smoke test, atomic switch, verified rollback; runtime files preserved |

MT5 supplies account-currency [profit](https://www.mql5.com/en/docs/python_metatrader5/mt5ordercalcprofit_py) and [margin](https://www.mql5.com/en/docs/python_metatrader5/mt5ordercalcmargin_py) estimators and [order preflight](https://www.mql5.com/en/docs/python_metatrader5/mt5ordercheck_py). Preflight does not guarantee a fill. Partial completion has its own [server return code](https://www.mql5.com/en/docs/constants/errorswarnings/enum_trade_return_codes). The implementation must reconcile server truth rather than assume one successful Python call equals one completed order.

## Stage 2 — trustworthy replay, statistics and records

| ID | Work | Acceptance evidence |
|---|---|---|
| Q01 | Fix END_OF_DATA to use the final simulated timestamp and executable side of the quote | Boundary probe becomes regression test; zero future exits with a larger preloaded dataset; genuine truncation invariance |
| Q02 | Hash merged arrays, broker specification and transformations | Different bars/spec/merge policy yield different IDs; equivalent builds produce same ID |
| Q03 | Preserve immutable logical experiment and execution-attempt records | Full strategy parameters, code revision, config, rules, data, costs, seeds, purpose and timestamp; identical reruns do not inflate choices; changed choices cannot overwrite prior records |
| Q04 | Track holdout intervals and provenance across every supported loader | Overlap detection works after renaming a window; feature selection, model/threshold fitting and data repair decisions are recorded |
| Q05 | Save time-indexed returns and equity for every candidate | Common calendar alignment with explicit zeros/missingness; no index-of-trade correlation; retain full exposure and outcome timestamps |
| Q06 | Correct Sortino and harmonize Calmar/annualization | Independent target-zero examples and calendar-return examples; realized and mark-to-market drawdown separately labeled |
| Q07 | Integrate one standard report into all supported research runs | Every result gets costs, net expectancy/PF with intervals, calendar returns, drawdown, concentration, trial accounting and data-quality flags; unavailable statistics fail visibly |
| Q08 | Qualify DSR and trial-dependence estimates | Actual candidate return matrices and measured SR dispersion; raw/effective-trial sensitivities; no claim that DSR is probability of profitability; do not treat eigenvalue entropy as a universally exact trial count |
| Q09 | Separate resampling questions | Permutations for order-sensitive risk, block bootstrap for uncertainty, full replay for adaptive sizing/risk gates; rerun selection under null controls when estimating search-level luck |
| Q10 | Replace invented latency haircut with delayed execution replay | Entry moved through actual historical quotes; recompute stops/risk/fills and subsequent occupancy; compare delays with observed scan/fill timing |
| Q11 | Fix stale audit paths and independent checker case mismatch | Auditor consumes exact run ID/path, fresh output and data hash, independently checks both sides and costs |
| Q12 | One decision domain for replay and live | Golden event stream yields matching signals, refusals, final lots, intended orders and account-rule transitions; differences explained by measured execution |
| Q13 | Account continuity and floating equity | Carry state/positions across chronological scoring windows, including unrealized peaks and boundary positions; explicit reset experiments labeled separately |
| Q14 | Cost/coverage realism | Bid/ask ticks where available; reject unsupported precision; report partial minutes, source mismatch, spread imputation, financing/rollover/currency assumptions and stress variants |
| Q15 | Repair CI and environment without rewriting history | Clean install + pip check + Linux and Windows tests; MetricSuite labeled retrospective diagnostic or exempted by explicit category, never fabricated backdated preregistration |

Use chronological outer walk-forward tests for development choices, with an inner fitting/selection stage when needed. Exclude training labels/exposures overlapping the evaluation boundary and define an appropriate gap for the actual forecast horizon. Do not randomly shuffle time-series training/test rows. Preserve account continuity while excluding a fold's warmup from its scored return.

Cross-validation and resampling describe robustness on available data; they do not make the heavily inspected 2022–2026 history unseen again. CSCV/PBO can be a supplementary search-overfitting diagnostic where its assumptions fit, not a replacement for chronological deployment simulation. [PBO paper](https://carmamaths.org/resources/jon/backtest2.pdf)

DSR addresses selection and non-normality under stated assumptions, and requires an honest view of the trials. Use it as supporting evidence, not a universal 0.95 magic certificate. A search-wide bootstrap or SPA test can compare the declared candidate family with benchmarks without pretending one lucky winner was the only test. [DSR](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf), [Hansen SPA](https://www.tandfonline.com/doi/abs/10.1198/073500105000000063)

## Stage 3 — replacement-strategy research

Do not start by sweeping the old four strategies' stop/target values or adding every indicator in the library. A replacement begins with an explicit economic or market-mechanism hypothesis, a usable information set, a holding horizon and a reason its gross expected advantage could exceed execution and financing costs.

Proposed first research batch: **at most two families, at most four deliberately justified variants per family**. This is a planning budget, not a completed preregistration or a claim that eight tests reset past trial counts. Log all human and automated variants. Close a failed batch instead of changing the pass criterion after seeing its outcome.

| Priority | Hypothesis | Why investigate | Main falsification / dependency |
|---|---|---|---|
| 1 | Gold's response to already-observed dollar/rate changes varies by macro state and has delayed continuation or correction | Adds information beyond XAU OHLC; gold/real-rate relationships have economic grounding | Association is not a forward signal. Test lagged prediction and incremental net P&L against price-only and contemporaneous-factor benchmarks. Existing DXY/yield work must first be mapped to avoid repeating it |
| 2 | Post-release adjustment persists after the funded news restriction and an execution buffer have expired | A defined information arrival can supply a mechanism and measurable comparison group | Need accurate release times and genuinely available surprises/market reactions; discard if advantage occurs only inside the restricted window, within quick closes, or before realistic execution |
| Conditional later | Diversified slower trend/carry or cross-market relative value on permitted instruments | A single gold-only strategy need not be the best commercial constraint | Only if universe expansion is accepted and account costs/permissions justify it; requires a multi-symbol risk/replay model. Published futures evidence does not validate a gold CFD implementation |
| Conditional later | COMEX traded-volume/flow information beyond broker tick counts | Different measurement from the failed tick-volume candidates | Data cost/licensing, latency, futures roll/basis and venue-transfer tests; reject anything dependent on stale-quote exploitation or prohibited short-horizon behavior |

These are hypotheses, not strategies with a known edge. Macro rates/price relationships can be contemporaneous rather than exploitable forecasts; the Chicago Fed analysis is motivation, not a buy/sell rule. [Gold research](https://www.chicagofed.org/publications/chicago-fed-letter/2021/464)

Data must record observed_at, available_at and ingested_at. Revised macro series must use the information version available at decision time; FRED supports real-time/vintage periods. Daily releases must not be treated as intraday live feeds. [FRED/ALFRED](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html)

COT information is usually published Friday for Tuesday positions. Any positioning hypothesis must enter after actual publication, with holiday delays respected; it is not Tuesday intraday knowledge. [CFTC](https://www.cftc.gov/MarketReports/CommitmentsofTraders/AbouttheCOTReports/index.htm)

CME offers historical trades and order-book data, but this is only a data feasibility option. Do not purchase expensive depth history before checking the hypothesis, coverage, permitted use and whether expected payout economics can support the cost. [CME data](https://www.cmegroup.com/market-data/real-time-and-historical-data.html)

Matched controls should preserve relevant session, side distribution, exposure, entry opportunities and exit geometry. Add always-long, always-short, no-trade and price-only baselines where meaningful. Use multiple suitable controls rather than proclaiming a fixed-barrier fair-coin win-rate formula universally valid for gaps, time exits and path-dependent prices. Verify controls are not accidentally given extra information or different feasible trading opportunities.

Before final forward evaluation, freeze the candidate, features, exits, sizing, gates, cost assumptions, trial accounting, endpoints and minimum meaningful net edge. No interim tuning on forward outcomes. A changed candidate starts a new explicitly tracked forward experiment; price data after a past calendar date are not automatically clean if they have already informed choices.

## Evidence gates for a candidate

The initial suggested historical screen is net PF >=1.15 at baseline costs, nonnegative expected net return under a declared realistic adverse-cost scenario, and better performance than its matched controls. This is a pragmatic screening margin, not an academic universal threshold. Report its CI and concentration rather than allowing the number alone to approve a candidate.

Capital promotion requires the preregistered primary effect to survive the chosen dependence and multiplicity treatment; a lower confidence bound on net expectancy above zero or a declared economically meaningful threshold; multiple chronological windows without a single unplanned regime carrying the entire finding; parameter-neighborhood stability; and a completed locked forward endpoint. A model genuinely designed for one regime must be tested for the ability to identify that regime using past information and for the cost of false activation.

No universal requirement of exactly 1,000 trades, 100 trades or 90 days. Size the experiment for the minimum effect that would pay for its risks and operating cost. Illustration using this portfolio's historical per-trade dollar SD of $11.69: detecting a $1 mean net advantage at one-sided 5% significance and 80% power needs roughly 846 IID observations under a simple normal approximation. Dependence, model selection and changing regimes can increase this requirement. At 12 trades/month that is about 70.5 months, and at 50/month about 16.9 months. This is not a sample-size estimate for an unbuilt strategy; it explains why 40 or 100 trades alone cannot prove a small edge.

Predetermined interim reviews may monitor safety and execution. If they are used to accept/reject alpha early, use a prespecified sequential testing procedure with controlled error, rather than repeatedly checking an ordinary confidence interval until it looks favorable.

## Stage 4 — Atlas survival and payout economics

Run two reports on the frozen candidate: unconstrained net trading behavior and the exact deployable constrained system. If account gates alter the trades, the constrained system's edge must be evaluated too. Do not optimize passing probability first and call the resulting leverage an edge.

Simulate complete paths through evaluation, activation, funded operation, payout eligibility, withdrawals, floor adjustments, protector strikes, profit deductions and permanent breach. Include fees and realistic time to payout. Use continuous account state, mark-to-market paths and correlated daily/weekly blocks; reapply gates, volume rounding, costs and sizing on every resampled path. A shuffle of closed-trade profits is insufficient.

Required outputs over declared horizons, such as 90/180/365 days:

* Probability of reaching evaluation target before breach, with uncertainty and sensitivity.
* Probability of first payout and repeat payouts, conditional and unconditional on passing.
* Time-to-pass, time-to-payout, no-payout probability and downside cash-loss distribution.
* Daily/equity/Protector breaches, short-hold/news deductions and consistency delays by cause.
* Expected and stressed net cash received after entry, activation, reset, VPS and data costs.
* Effects of withdrawal on remaining risk headroom and subsequent eligibility.

Commercial objective: E[cash payouts actually received] minus E[all fees and operating costs], subject to acceptable loss probability and time commitment. Account notional is not withdrawable personal wealth. Atlas describes a simulated trading environment with real payout rewards; economic analysis must model that arrangement rather than pretend the displayed $5,000 belongs to the trader. [Disclosure](https://help.atlasfunded.com/platforms)

Provisional small-account sizing experiment: 0.10–0.25% initial balance planned risk per trade, <=0.50% aggregate open planned loss, <=0.75% internal daily loss, with tighter limits when firm headroom or stress scenarios require them. On $5,000 those amounts are $5–$12.50 per trade, $25 aggregate and $37.50/day. These are conservative starting hypotheses to test, not validated final settings or a guarantee against gaps. Include commissions, financing and gap/slippage reserves. If minimum lot size makes the structurally justified stop too expensive, skip the trade; do not tighten the stop to force it into budget. Reject infeasible strategies rather than force frequency to satisfy payout days.

Use capital, current firm-floor headroom, correlated adverse moves and instrument minimum volume together. Do not escalate after losses, assume opposite gold positions cancel all tail risk, or raise risk just to print a >=0.5% qualifying day.

## Stage 5 — deployment and forward observation

1. **Offline engineering gate:** all confirmed critical defects closed; clean dependency resolution; Linux and Windows tests; independent rule/arithmetic oracles; immutable data/run/report lineage; reviewed account rules.
2. **Shadow gate:** actual intended broker feed, no orders, identical versioned decision domain; every signal gets a traceable execution/refusal reason. Unexplained discrepancies block progression.
3. **Operational demo gate:** orders allowed only on the explicitly selected demo account; verify fills/stops, partial and unknown replies, reconnects, midnight boundaries, restarts, backups and rollback. Ten complete market sessions and 100 order opportunities may be an initial operational check, not proof of alpha; do not manufacture trades to meet it.
4. **Statistical/economic gate:** frozen endpoint achieved, suitable uncertainty/multiplicity treatment, constrained-system expectancy credible, estimated payout economics positive within a declared fee budget. If evidence is inconclusive, remain in research/demo.
5. **Limited capital gate:** only after the prior gates and account-rule resolution, use the smallest feasible planned exposure and a bounded total fee budget. Set a predeclared suspension policy for drift, cost excess, missing state, unexplained execution or firm-rule changes. Never escalate merely because a calendar deadline arrived.

Predeclare measurable slippage, acknowledgement, data-age and risk-monitor latency tolerances after measuring the actual broker. No unsupported universal guarantee such as 'zero misses' or a fixed subsecond response should be asserted before measurement. Safety-critical failures should have deterministic refusal/reconciliation outcomes even though network outages and market gaps remain possible.

## Folder and code evolution

Keep the existing package layout. Introduce a small shared domain for risk/entry decisions, account-rule snapshots and execution events incrementally; do not build a second live engine or a distributed microservice platform. Prefer dataclasses/typed interfaces and an explicit clock/config dependency over import-time environment reads and monkeypatching globals.

Within existing research directories, distinguish immutable dataset manifests, experiment specifications, per-run records and rendered reports. Large licensed data can live in versioned external storage with hashes and access control; code and manifests stay in Git. Dated result artifacts are legitimate history; dated scripts with silently hardcoded input paths should become thin invocations of supported runners.

Keep archived strategies isolated from runtime imports, consolidate duplicated configuration, document ownership of every persisted state file, and generate the current strategy/rule/config summary from the release manifest. Keep the old incident record but mark superseded profitability statements explicitly. A code-quality cleanup must not silently alter strategy behavior.

For state and order intents, choose atomic validated snapshots plus append-only events, or a small transactional database such as SQLite for a single-writer host after design review. Requirements matter more than the storage brand: durable commits, account binding, idempotent recovery, consistency checks, backups and tested restore.

## Definition of completion

Engineering work is complete when its acceptance evidence passes and the operator can reproduce a release, stop it safely, reconcile it and restore it. Edge discovery is complete only if a frozen candidate passes its declared evidence and account-economic gates. It may produce no qualifying candidate. That is a valid result, not a reason to lower the bar.

The next implementation tranche should be S01–S09 and Q01–Q05, followed by metric/report parity and deployment repair. Strategy research can proceed only after the relevant data, record and inference dependencies are trustworthy. No implementation is authorized by this planning document alone; the current user request explicitly asked to plan first.
