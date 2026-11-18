# Historical Access lifecycle: real-engine engineering replay

18 November2026. **Result: INDETERMINATE because the first open position encounters incomplete minute coverage.** The evaluation cannot be certified as passed or failed over the requested window. Funded operation and payout opportunities were not reached. Actual requests, approvals, payments and user cash receipts are zero.

## Frozen question and implementation

Protocol `research/registry/PREREG_AccessLifecycle_2026-11-18.md` was committed as `da8e5a4` before measurement. Runner/coupling tests were committed as `5f358f8` before the actual historical replay. No strategy optimization or November holdout consumption occurred. The four original portfolio strategies and July6–October29 dates were already explored; this is engineering evidence, not independent strategy validation.

The `LifecycleEngine` subclasses the actual `BacktestEngine` only to enforce coverage refusal and bound the in-memory mark cache. Original strategy classes, entry/exit engine, costs and risk gates execute. Full configurations/hashes are in `summary.json`. Evaluation: starting$5,000, .02lot fixed, maximum3 positions, leverage100, D1 gate and live-parity internal gates on, profit-protector strategy off, explicit causal minute-open entry proxy (zero subminute interpolation). Funded would use a fresh$5,000 on strictly later data, leverage50 and the versioned provisional Access ledger rather than production's older rule helper.

The experimental ledger tracks percentage peak equity floors, actual/proven-flat UTC reset evidence,20% lifetime-best-day consistency, qualifying days and payout windows. The sole cashflow scenario would explicitly supply verified KYC plus instantaneous approval for eligible flat-only$100 trader-cash requests, with gross debit and re-anchoring. That favorable hypothetical approval is not a provider receipt. It never occurred in this replay. A pending request freezes account trading in the provisional API; zero-delay scenario settlement would resolve it before later orders.

## Observed outcome

| Field | Result |
|---|---:|
| Intended interval | July6 2026 inclusive–October30 exclusive |
| Replay stop | July6 2026,20:45 UTC |
| Stop reason | Existing open exposure entering an incomplete M1 block |
| Completed evaluation trades |0 |
| Open positions at stop |1 |
| Realized evaluation trade cash |$0 |
| Ledger balance |$5,000 |
| Last supported modeled net-liquidation equity |$5,046.844 |
| Highest supported sampled equity |$5,054.058 |
| Lowest supported sampled equity |$4,981.016 |
| Sampled peak-to-trough drawdown |$38.52 |
| Provisional daily floor |$4,750 |
| Provisional trailing floor at stop |$4,548.6522 |
| Ledger observation checks |2,490 |
| Engine opening/after-order/end marks |3,735 |
| Realized-cash reconciliation maximum error |$0 |
| Funded phase reached |No |
| Eligible funded requests / conditional settlements |Not reached /0 |
| Actual requests, approvals, receipts |0 |

PF, win rate, Sharpe, Sortino, R-expectancy and losing streaks are **not estimable from zero completed trades**. Do not translate them into zeros or favorable values. The positive floating amount was not realized profit, an evaluation pass or a withdrawal.

The block from20:45 through20:59 contains13 recorded M1 observations;20:58 and20:59 are absent. The pre-registered guard checks coverage before entering an incomplete15-minute block with exposure, so it stops at20:45. Even the13 present observations inside that block were not consumed by the declared account path. It did not interpolate missing prices, splice another provider, presume the market was safely closed, ignore exposure, or fabricate a Protector/stop liquidation. The reason for these missing observations is not independently established here.

`coverage_stop_forensics.json` records the raw present rows and missing timestamps. The descriptive probe was written after the stop was known; it changes no strategy rule or acceptance criterion. `evaluation_trades.json` is empty. No diagnostic end-of-data close was booked because the coverage guard raised before any artificial settlement. No UTC day boundary or first payout window was reached.

## Scope and uncertainty

- The intended full window was **not successfully simulated**. “Ran the replay” means the engineering pipeline ran and stopped honestly, not that an October29 account survived.
- The original portfolio's prior+$790 recent-sample result is a different, less restrictive historical calculation. It is not a substitute for this connected lifecycle path and does not establish current Access payouts.
- Minute opening/end marks and conservative OHLC envelopes remain below continuous tick evidence. Possible unobserved floor/Protector/margin intervention would halt rather than manufacture broker fills. Synthetic tests exercise those paths; none was reached historically before this coverage stop.
- The retrospectively known whole-block coverage eligibility rule is a declared diagnostic restriction, not a claim that a live bot knows which future minute quotes will be absent.
- Net-liquidation marks reserve modeled round-trip commission and accrue the project's financing assumption. Actual broker cash timing, Atlas contract, margin calculation, spread distribution and financing are unverified.
- Full news, short-hold profit deductions, inactivity, actual approval delays, KYC process and provider discretion are not completely implemented by this coupling. No full-rule compliance certificate follows.
- Public standard evaluation entry fee is$5; that external purchase expense is separate from the simulated$5,000 ledger. No account was bought here. Activation cost remains unverified, the funded stage was not reached, and no third-consecutive-payout entry refund could occur. No net customer-return claim is available from this truncated replay.

## Files and reproduction

From repository root:

```powershell
.\venv\Scripts\python.exe -m scripts.validation.access_lifecycle_20261118
.\venv\Scripts\python.exe -m scripts.validation.access_lifecycle_coverage_20261118
.\venv\Scripts\python.exe -m pytest tests/test_access_lifecycle_20261118.py tests/test_access_rules_20261118.py -q
```

`summary.json` and `evaluation.json` contain protocol/runner/ledger/engine hashes, the actual master-data hash, costs, config, termination, account floors and event records. `evaluation_observations.csv.gz` stores the observed checks with quote-stage labels and position counts. The engine retains only a small rolling mark cache, while streaming the account trace; it does not drop account observations from the trace.

Focused validation:43 coupling/provisional-ledger tests passed, including proven-flat multi-day resets, required exact midnight with exposure, flat evaluation pass, cash reconciliation, gross-versus-cash consistency eligibility, explicit conditional settlement, coverage refusal and intraminute rule uncertainty without invented closes. The parent checkpoint records the final full-suite result.

## Next executable requirement

Recover broker-coherent timestamped quotes for the exposed interval, determine whether the absent minutes are legitimate no-quote market closure or missing history, and verify the executable path on that same account/source. Do not repair it with forward-filled candles or an arbitrary provider's price series. Preserve this run as indeterminate even if later evidence supports a new versioned replay. Final deployment also still requires a genuinely qualifying strategy and account-specific rules.
