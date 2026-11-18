# Access lifecycle: provider-calendar engineering sensitivity

18 November2026. **Under the explicitly assumed Exness summer calendar, evaluation passes; funded continuation loses and then becomes indeterminate before its first payout window.** This is a descriptive engineering sensitivity on previously explored dates, not an independently qualified strategy or an Atlas-account pass certificate. The primary no-calendar indeterminate result is preserved separately.

## Result

| Phase | Calendar-assumed status | Closed trades | Realized net | PF | End closed balance | End time UTC |
|---|---|---:|---:|---:|---:|---|
| Evaluation | Flat3% target reached | 9 | +$184.754 | 2.359 | $5,184.754 | July23 13:06 |
| Fresh funded | Indeterminate at unverified active/close-only quote gap | 12 | -$193.523 | 0.473 | $4,806.477 | August18 22:00 |

Funded starts July23 13:15 on later data with a fresh$5,000 and leverage50; evaluation used leverage100. Evaluation profit is not credited as spendable funded cash. No eligible request or conditional settlement occurs. **Actual payments and user cash receipts: zero.** The assumed first funded payout window would open August20 13:15, after this run's stopping point.

Evaluation wins5/9, average win$64.1442, average loss-$33.99175, expectancy+$20.5282 per close. Funded wins3/12, average win$57.812, average loss-$40.77322, expectancy-$16.12692. These small selected-period samples cannot support a durable-edge conclusion. Sampled maximum net-liquidation drawdown is$153.965 evaluation /$196.865 funded; these are minute marks with conservative envelope refusal, not tick-certified risk figures.

## What the new evidence explains

The official Exness notice updated3 November2026 distinguishes summer regular closure and close-only periods. We applied its then-current XAUUSD summer table retrospectively to July–October as an **assumption**, because an account-specific historical schedule for every date has not been obtained. This is Exness evidence, not Atlas's instrument calendar. [Official notice](https://get.exness.help/hc/en-us/articles/31342732737180-Trading-Hours-Update-End-of-US-Daylight-Saving-Time-01-Nov-2026)

The initial July6 block's absent20:58/20:59 minutes fall inside that published closure. This scenario consumes all13 actual observed20:45–20:57 minutes, retains open exposure through the scheduled closure without synthetic marks, and uses the first actual reopening quote for gap-stop handling. It blocks new positions in close-only periods. The primary result did not have this schedule evidence and remains unchanged.

The source manifests identify XAUUSDm on `Exness-MT5Trial11`; both the base cache and later October snapshot content hashes match their declared array hashes. Actual first/last epoch timestamps reconcile with the declared UTC coverage. No new live-terminal/timezone check occurred. Source metadata verifies the supplied cache identity, not historical market-hours contracts or actual Atlas executable prices.

## Remaining stop

August18 22:00–22:03 M1 observations are absent, while the assumed calendar expects close-only/open quoting from part of that interval. The account is flat. The frozen calendar-only protocol nevertheless requires refusal for unexpected active/close-only gaps, so it stops rather than silently broadening the calendar or inventing holiday exceptions. Its historical balance is$4,806.477, provisional daily floor$4,774.83955, trailing floor$4,703.14148 and peak$5,003.342. No forced close or Protector event is manufactured.

This does not prove those absent minutes had trades or that a real account would breach. It establishes the limit of this particular calendar-only scenario. A separate, predeclared proof of flatness and impossibility of strategy entries could potentially support a more limited continuation; no such exception was retroactively inserted here.

## Execution, reset and accounting evidence

- No M15 price fills: engine `bars_without_m1` is0 in both phases. The internal `coarse` coverage flag allows real partial M1 arrays to be walked, but the subclass never returns None: wholly scheduled-closed blocks return empty arrays and execute no iterations. It cannot fall back to M15 prices.
- Evaluation has15 scheduled partial blocks,13 recognized closed-gap transitions,2 exact00UTC exposed resets and15 proven-flat cash resets. Funded has23 partial blocks,18 closed-gap transitions,1 exact exposed midnight reset and25 proven-flat resets.
- All actual quotes are retained; close-only entry blocks observed0. Synthetic tests demonstrate the close-only refusal and adverse gap-stop fill at the real next quote rather than the requested stop. Historical gapped-stop count0 is not independent evidence of real broker slippage.
- Engine/ledger cash reconciliation stays within numerical tolerance. Explicit conditional approval remains a favorable scenario assumption; no request became eligible here, so no settlement assumption affected this path.
- Public rule definitions, actual contract/financing, news/short-trade deductions, inactivity, approval delay and fee limitations remain those of the primary report. Standard external$5 evaluation payment is separate; activation price is unknown. Evaluation profit is not a payout.

## Provenance and reproduction

Protocol `PREREG_AccessProviderCalendar_2026-11-18.md`: commit`465ae18`, before evaluation. Runner/tests implementation: `0f27901`, before measurement. Rule profile is the separately versioned provisional public-access ledger; production settings and November holdout remain untouched.

```powershell
.\venv\Scripts\python.exe -m scripts.validation.access_provider_calendar_20261118
.\venv\Scripts\python.exe -m pytest tests/test_access_provider_calendar_20261118.py tests/test_access_lifecycle_20261118.py tests/test_access_rules_20261118.py -q
```

`summary.json` records exact configurations, costs, source and implementation hashes, schedule-source metadata and all phase events. Per-phase JSON/trade files and compressed observation traces retain complete declared outcomes.63 focused tests pass. No account was purchased, no actual order/request was submitted, no production strategy/rule level changed, and no result here authorizes real-money deployment.
