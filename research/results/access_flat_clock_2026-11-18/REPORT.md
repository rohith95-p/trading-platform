# Access lifecycle: final proven-flat / inert-clock sensitivity

18 November2026. **The frozen four-leg portfolio can pass the selected evaluation sample under the provider-calendar assumption, but its subsequent funded sample loses and generates no eligible$100 payout. Full-window continuation remains indeterminate.** No actual payment, account purchase or production change occurred.

## Corrected final result

| Phase | Result | Closed trades | Net after modeled costs | PF | Closed balance | Last supported observation UTC |
|---|---|---:|---:|---:|---:|---|
| Evaluation | Flat target pass | 9 | +$184.754 | 2.359 | $5,184.754 | July23 13:06 |
| Fresh funded | Indeterminate at a gap failing the frozen proof | 19 | -$174.327 | 0.681 | $4,825.673 | September7 18:28 |

The engine detects the unsupported continuation at September7 22:01. That is the stopping/detection time, **not a quote observation for which the account was marked**. Its last supported mark is18:28, after the last observed18:27 minute. No intervening prices or account path were invented.

Funded starts July23 13:15 with fresh$5,000, leverage50; evaluation used100. Evaluation winnings are not transferable trader cash. The first provisional funded payout window opens August20 13:15 and is reached by this sensitivity, but funded closed cash remains below the profit anchor. **Eligible requests0, hypothetical settlements0, actual receipts0.** No favorable approval assumption ever affects this path.

Funded wins6/19, average win$61.90467, average loss-$41.98115 and expectancy-$9.17511 per close. Its sampled maximum liquidation drawdown is$220.949, minimum sampled liquidation equity$4,782.393, peak$5,003.342. Last recorded provisional floors are daily$4,708.96491 and trailing$4,703.14148. These refer to the last supported ledger state, not certification of unobserved later prices. Nineteen trades on selected dates are insufficient for general predictive conclusions, and the historical older portfolio evidence already failed.

## What was allowed, and why

Protocol`PREREG_AccessFlatClock_2026-11-18.md` was committed`0711785` before this sensitivity. Source hashes freeze the actual four strategy files, selector/base and engine/coupling clock code. Their hard signal-bar clocks are Asia07:00, London12:00 and NY12:00–15:45UTC. They are immediate edge triggers with no pending-confirmation path. Engine reevaluation precedes entries within a block and caches clear across discontinuities.

The final exception requires zero positions both before/now, no intervening closed-event/order activity, no pending payout/pyramiding/delay, a conservative same-day16:30–23:45 interval, a noncandidate actual M15 view, and a valid real broker M15 aggregate for **every unexplained minute**. Available M1 observations are never dropped. Missing candidate bars and unknown first-of-day feature origins are not waived.

This proves the August18 22:00–22:03 unquoted interval inert for these fixed rules while flat. It keeps all11 available22:04–22:14 observations. The fully accepted unknown-gap trace contains those4 minutes. Per-block proofs additionally identify2 absent18:28/18:29 minutes and1 absent22:00 minute on September7, but the larger gap fails before continuation, so those partial-block checks do not establish an accepted whole-gap path. They must not be reported as a successful155-minute waiver.

## Why the final gap is still unsupported

On September7 the observed source stops at18:27 and resumes at22:01. The broader interval contains151 minutes unexplained by the assumed regular calendar. The M15 aggregate history for several affected off-clock blocks is also absent. The protocol requires those aggregates to preserve the information used by later indicators/features. A flat account removes immediate position risk, but it does not reconstruct missing signal history. The proof therefore refuses at the first returning observation. No holiday schedule or broader exception was fitted after seeing this result.

This sensitivity retains the original declared Exness summer-calendar assumption from the official November3 notice. It is not account-specific historical confirmation or Atlas trading hours. [Official schedule source](https://get.exness.help/hc/en-us/articles/31342732737180-Trading-Hours-Update-End-of-US-Daylight-Saving-Time-01-Nov-2026)

## Implementation correction and preserved evidence

The initial implementation (`5e73e2a`) accidentally validated only the destination M15 aggregate across a gap. Independent review caught this before finalizing: it had incorrectly advanced beyond September7 and reported23 funded closes, -$129.529, through a September13 stop. Those figures **do not satisfy the frozen aggregate-preservation requirement** and are superseded. The initial outputs remain under `initial_implementation_superseded/` with an explicit reason file and original hashes.

Commit`4c14aeb` fixes the proof for every affected aggregate and adds a regression deleting off-clock M15/M1 history while retaining a destination bar. This corrects implementation to match the existing protocol; it changes no strategy, calendar boundary or acceptance criterion. The actual replay was rerun. The19-trade result in the top-level JSON/report is the corrected final evidence. The three prior primary/calendar/initial-implementation artifacts remain distinguishable; no unfavorable result was erased.

## Accounting and execution verification

`trace_accounting_check.json` independently checks the recorded cash identities, chronological timestamps, observed floors, marked peak/trailing formula, sampled drawdown and evaluation-flat target condition. It reconciles19 funded closes to$4,825.673 and88,795 observation rows, alongside37,394 evaluation observations. This is a cash/trace audit, not an independent indicator reconstruction or real-tick replay.

No M15 price fills occur (`bars_without_m1=0`). Scheduled-closed intervals return empty arrays and generate no prices; real partial arrays preserve each available quote. Synthetic tests cover close-only refusal, gap stops at the observed adverse reopening quote, missing candidate minutes/bars, missing off-clock aggregates, source-lock changes and every off-clock signal label for the real four strategies.77 focused tests pass. Exact/proven-flat midnight reset requirements, conservative rule-intervention envelopes and all provisional-ledger limitations remain.

## Limits and reproduction

These dates/strategies were previously explored. This is an engineering continuation sensitivity, not an independent edge qualification or a completed October29 account path. Actual Atlas contract/financing, complete news/short-trade deductions, margin-close fills, inactivity, KYC, actual approval delays and fees remain unverified. Standard external evaluation payment$5 is separate from$5,000 account cash; activation fee is unknown. No third-consecutive-payout refund or user cashflow occurs.

```powershell
.\venv\Scripts\python.exe -m scripts.validation.access_flat_clock_20261118
.\venv\Scripts\python.exe -m scripts.validation.access_lifecycle_accounting_check_20261118
.\venv\Scripts\python.exe -m pytest tests/test_access_flat_clock_20261118.py tests/test_access_provider_calendar_20261118.py tests/test_access_lifecycle_20261118.py tests/test_access_rules_20261118.py -q
```

The source lock must match before replay. Summary, phase JSON/trades, streamed compressed marks, proof events, source hashes and superseded initial files are saved here. No further exception should be added to this frozen sensitivity after inspecting outcomes. Recovery of coherent source quotes/aggregate history or genuinely documented historical holiday evidence would require a separate versioned investigation. The current strategy is not qualified for real money or reliable payouts.
