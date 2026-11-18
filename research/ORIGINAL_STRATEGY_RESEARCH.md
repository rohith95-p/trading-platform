# Original strategy research — 2026-11-18

## Selection result

**No candidate qualifies for promotion from the current evidence.** No new strategy was routed to production. No fabricated PF, DSR, PBO, account-pass probability or payout rate is substituted for missing strategy validation.

## Mechanism-first work actually performed

The separately committed MarketAtlas protocol tests return distributions and three fixed conditional effects at six resolutions, rather than choosing indicators. Actual inputs include6,887,193 M1 observations and514,712 M15 observations through the declared master loader. November2026 onward prices were excluded. Existing histories remain explored data.

The primary observations are volatility persistence and a small negative next-return response to extreme M1/M15 moves. Extreme is precisely `abs(log(C_t/C_previous)) > 2*RMS(previous60 valid adjacent returns)`. Current and forward returns must span exactly one declared interval. The reference fade direction is the negative sign of the extreme return. This is a falsifiable statistical mechanism, not an implemented tradable strategy.

The reference movement after extreme moves averages about **$0.01861/oz for M1 and $0.05311/oz for M15**. The corresponding modeled round-trip friction hurdles average **$0.33479/oz and $0.32288/oz**. Even the historical reference effect does not cover the stated friction scenario. The separate `economic_hurdle.json` is explicitly **not a backtest**: it neither creates fills nor applies paths, exposure, stops, financing or account rules.

Because the predeclared promotion condition includes an executable-cost margin, neither direction hypothesis advances. Selecting a high-price era, more extreme threshold, attractive hour or exit geometry afterward would be a new comparison, not confirmation. Volatility predictability alone does not choose a profitable direction. No indicator combination or parameter sweep was used to manufacture a candidate.

## Candidate specification gate

For a hypothesis that actually clears this screen, freeze inputs/availability, direction, timestamp, stops/targets, max holding, sizing and exposure, before any candidate evaluation. Compare against matched-time random direction, fixed-direction exposure, unfiltered and volatility-only controls. Use BacktestEngine with corrected chronology and strict M1 coverage; record contract/cost/model hashes. Investigate parameter neighborhoods only on development history; count every trial. Release requires prospective or genuinely unseen evidence, after-cost uncertainty and complete account-rule stress.

The existing November holdout is reserved. It was not spent merely to produce an answer. There is no new independent evaluation period created by renaming old eras.

## Existing candidates

Recovered portfolio, Genesis, public-rule and macro studies are catalogued in PROJECT_RECOVERY_2026-11-18.md and STRATEGY_VALIDATION_REPORT.md. Some show favorable subperiods; none is upgraded by an engineering repair. Corrected engine defaults differ materially from archived runs, so archived profitability is not current-engine certification.

## Scientifically justified next candidates

1. Conditional volatility as an abstention/risk forecast, evaluated against matched volatility and calendar controls, using independently aligned bid/ask data. It is not a directional alpha claim.
2. Post-announcement information digestion using source release timestamps and point-in-time actual-versus-consensus surprises, with entry after known spreads recover. Existing scheduled dates alone cannot reproduce the required features.
3. Spot–futures price discovery only after synchronized executable futures/spot observations exist. Free bars and quote-volume proxies do not establish aggressor flow or cross-market tradeability.

No new costly data subscription or provider account was purchased. No order-book architecture was added. These research gates are recorded so the next session can distinguish a justified experiment from another arbitrary search.

## Completed follow-up experiments

| Mechanism | Observation | Decision |
| --- | --- | --- |
| Reversal after an extreme signed return on separate Dukascopy bid/ask quotes | 2025 next-quote mean losses of $0.677/oz on M1 and $0.665/oz on M15. All 18 friction cases lost money. | Reject both horizons. [Replication](QUOTE_SIDE_REPLICATION.md) |
| Delayed dollar and yield agreement during New York hours | Net average $0.0015/oz over 2,755 sessions, with a loss in the middle era. The 95% interval for advantage over buying the same dates crosses zero. | Failed before strategy construction. [Registered result](registry/RESULT_DelayedMacroAgreement_2026-11-18.md) |
| Propagation of the first half-hour gold move after a scheduled FOMC statement | The engine recorded 32 and 15 base-case trades in the two eras. Both samples gained, but removing the later era's best trade reverses its sign. | Reject promotion. Sample size, matched controls and uncertainty failed the frozen criteria. [All 24 comparisons](FOMC_SHOCK_PROPAGATION.md) |
