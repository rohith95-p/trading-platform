# Strategy validation report — 18 November 2026

## Decision at recovery

**No previously researched strategy currently has sufficient evidence for promotion to a profitable live system.** Some historical samples are positive. Engineering checks and PF arithmetic do not establish future positive expectancy. This report assesses the recovered evidence; newly completed finalization experiments must be appended with their actual protocol and artifacts before changing the decision.

## Evidence hierarchy

1. Observed broker-demo deals and reproducible signal/fill reconciliation: operational evidence, currently incomplete.
2. Frozen candidate judged once on previously unseen coherent quotes with account-realistic constraints: required acceptance evidence, not established for a current candidate.
3. Chronological walk-forward rules on already explored history: useful conditional evidence, subject to project-level model selection.
4. Replayed old rules on repeatedly inspected dates: retrospective screen only.
5. External marketing, forum statistics or code comments: unverified hypotheses only.

The original 2004–2022 portfolio test was independent of its selection when first run. Now that it influenced the research plan, it is not an untouched test for newly designed rules. The November1 onward holdout remains restricted. Prospective demo observations cannot be manufactured before the November22 deadline; calendar time is a real validation constraint.

## Historical verdicts and qualifications

See `PROJECT_RECOVERY_2026-11-18.md` for exact source files and numerical tables. Original portfolio: PF0.900, -$1,311.35,2,556 trades; every leg negative. Favorable modern periods were involved in selection. First Donchian confirmation: PF0.823/149 trades; second PF0.985/78. Genesis variants do not pass their cross-era gate. Chandelier/ZLSMA loses after observed bid/ask costs on a separate2025 provider; its separate auditor did not complete. Forecast-to-Fill's requested-period PF1.266 and1.278 exceed a possible1.20 screening threshold but do not establish acceptance and are below the earlier1.30 preference.

Do not silently lower an old acceptance threshold to convert an observed loser into a pass. The new mission permits1.20 as a screen only; new final acceptance criteria must be committed before running that comparison.

## Required metric coverage

| Metric group | Existing capability / evidence | Outstanding requirement for a final candidate |
|---|---|---|
| Net cash, PF, expectancy, win rate, average win/loss | Implemented and checked on selected saved records | Rerun under final version and actual executable prices; include zero-loss undefined cases |
| R expectancy | Available in some research paths | Initial cash risk fixed at entry, costs and partials attributed consistently; no rebasing after break-even |
| Sharpe / Sortino | Trade-based diagnostics and daily-cash studies exist | Calendar-time marked equity returns, explicit frequency, downside target and annualization; account cashflows separated |
| Maximum DD, duration, recovery | Closed-balance outputs common; selected minute-open liquidation diagnostics exist | Continuous bid/ask floating-equity path, account floors, duration and recovery including unrecovered ending DD |
| Monthly/yearly, sessions, sides, regimes | Several outputs exist separately | One complete consistent candidate matrix, coverage masks and fixed regime definitions |
| Loss streak / concentration / ablation | Helpers and Genesis/Chandelier analyses exist | Dependence-aware distributions, top-trade deletion and calendar-cluster concentration |
| Costs / slippage / delay | Fixed scenario and sensitivity tools exist | Empirical demo spread/fill distributions where available, adverse gap and delay scenarios, funding by actual contract |
| Monte Carlo | Permutations and bootstrap helpers exist | Explain conditioning and block design; permutation preserves final cash and cannot estimate future profit probability |
| DSR / expected maximum SR | `src/research/metrics.py` implemented | Same-frequency SR variance and honest trial-count sensitivity; total historical research count unknown |
| Bonferroni / hypothesis testing | Function exists | Correct complete intended family, dependence-aware uncertainty, exploratory discoveries labeled |
| Probability of Backtest Overfitting | Not established by recovered headline reports | Complete aligned candidate-by-time return matrix and declared valid chronological/CSCV design, or mark unavailable |
| Strategy correlation / portfolio risk | Individual and shared contributions saved | Simultaneous marked returns, overlap, shared failures and weights chosen solely in development |
| Account-rule and payout probability | Limited `src/backtesting/access.py` lifecycle exists | Verified current phase-specific rules, continuous equity, exact eligibility/deductions/fees/withdrawal floors |
| Confidence / sample sufficiency | Existing IID/month bootstrap sensitivity | Effective sample size, economic minimum effect, power before selection;13 or26 trades cannot support broad certainty |

Undefined metrics must remain undefined with a reason. A no-trade candidate is not a100%-win strategy; a period without source coverage is not a zero-return observation. No-loss PF is not a verified infinite edge.

## Why the current payout evidence is incomplete

A $100 profit trigger is not sufficient for a real eligible payout. Evaluation must pass first; funded capital, eligibility days, consistency, payout windows, split, deductions, approval and floor movement must then be simulated. Existing cashflow code is a limited declared model, not an account-specific Atlas certificate. A withdrawal transfers cash out of equity and changes future risk headroom; it cannot erase preceding losses or improve underlying predictive expectancy. Payouts and residual equity must be reported jointly with fees and breach probability, without cherry-picking surviving paths.

## Acceptance sequence for a new candidate

- Commit its mechanism, deterministic features and timestamps, fixed comparison family, past-only fit schedule, data/cost versions, development/evaluation dates and failure conditions.
- Verify numerical inputs and coverage eligibility. Use `BacktestEngine`/`load_master` with M1 execution; do not promote coarse-bar scratch-simulator results.
- Compare net outcomes with random-direction matched-entry, unconditional exposure, session-only and volatility-only controls as appropriate. Correct for the complete disclosed comparison family.
- Check prefix causality, independent execution accounting, delayed entry, adverse quote/stop fills, funding, parameter neighborhood and exceptional-trade dependence.
- Evaluate continuous capital feasibility at minimum lot and actual account constraints. Low closed-cash DD cannot substitute for floating DD.
- Only candidates clearing their frozen bar can consume a justified one-time independent evaluation or prospective demo period. Preserve every rejection.
- No passing candidate means abstention and further bounded research, not fabricated completion.

## Reproduction status

This recovery reads and cross-checks saved sources; it does not rerun every historical experiment or certify all old JSONs. Full-suite results for the current worktree and any repaired execution behavior belong in `../docs/FINALIZATION_STATUS.md` and `../docs/BACKTEST_REALITY_AUDIT.md`. No new holdout was consumed here. Real-money readiness remains **not established**.
