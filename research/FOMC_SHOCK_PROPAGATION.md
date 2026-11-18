# FOMC normalized-shock propagation — experimental result

**No strategy is promoted.** This original project experiment produced small positive historical samples, but failed its declared sample-size, uncertainty and matched-direction evidence gates. Both eras were already explored by the broader project; neither is represented as independent confirmation. November2026 holdout was untouched.

## Inputs and economically observable information

The official [SF Fed USMPD](https://www.frbsf.org/research-and-insights/data-and-indicators/us-monetary-policy-event-study-database/) supplies statement calendar metadata. Its current download was updated30October2026 and contains retrospective market changes; those financial columns were excluded from features. The signal uses XAUUSD prices observed after the announcement, not a presumed advance policy surprise. Eastern timestamps were converted with America/New_York, preserving DST. The [Fed January2016 statement](https://www.federalreserve.gov/newsevents/pressreleases/monetary20160127a.htm) independently confirms14:00ET release timing.

Of79scheduled14:00statements in2016–2025,77had the full required13:00–15:59ET minute window.22March2023 and17September2025 were excluded for incomplete minute coverage. Exclusions are not harmless proof of performance on missing events. Source M15/M1 histories can come from different archive/broker feeds; spread fields often require the declared fallback.

The candidate follows the first30-minute gold response only when its absolute log movement exceeds twice a30-minute risk scale estimated from sixty pre-statement minute log(close/open) returns. It freezes that direction at14:30, waits until14:45, uses2/4ATR14stop/target on closedM15bars through the real RiskManager, and exits at15:45opening quote if still open. Fixed0.02lots; maximum1position; cash carries between events within each era, with$5000reset for the second era. A separate60second delay scenario enters14:46; no interpolation.

This schedule observes part of an ongoing press conference; its future content is unknown at entry. Avoiding the customary start-time news window does not verify the actual funded-calendar restrictions. The [Acosta et al. working paper](https://www.frbsf.org/wp-content/uploads/wp2025-30.pdf), revised27August2026, emphasizes the information contribution of press conferences. Its full text was accessible and introduction/methodology inspected; it does not establish a profitable XAUUSD continuation strategy. This reading did not change the frozen experiment.

## Every fixed experimental arm

| Era | Scenario | Arm | Trades | Net $ | PF | Win % | Sampled net-liquidation DD % |
|---|---|---|---:|---:|---:|---:|---:|
| 2016_2021 | base | candidate | 32 | 36.76 | 1.336 | 59.38 | 1.441 |
| 2016_2021 | base | unfiltered_follow | 47 | 70.82 | 1.407 | 57.45 | 1.692 |
| 2016_2021 | base | buy_control | 32 | 66.97 | 1.682 | 59.38 | 0.560 |
| 2016_2021 | base | sell_control | 32 | -14.70 | 0.899 | 40.62 | 1.505 |
| 2016_2021 | stress | candidate | 32 | 22.52 | 1.199 | 59.38 | 1.589 |
| 2016_2021 | stress | unfiltered_follow | 47 | 50.74 | 1.282 | 55.32 | 1.920 |
| 2016_2021 | stress | buy_control | 32 | 49.21 | 1.465 | 59.38 | 0.597 |
| 2016_2021 | stress | sell_control | 32 | -36.49 | 0.774 | 40.62 | 1.730 |
| 2016_2021 | delay60 | candidate | 32 | 22.40 | 1.195 | 59.38 | 1.525 |
| 2016_2021 | delay60 | unfiltered_follow | 47 | 49.04 | 1.272 | 55.32 | 1.971 |
| 2016_2021 | delay60 | buy_control | 32 | 54.65 | 1.539 | 59.38 | 0.764 |
| 2016_2021 | delay60 | sell_control | 32 | -4.72 | 0.966 | 40.62 | 1.606 |
| 2022_2025 | base | candidate | 15 | 26.59 | 1.268 | 53.33 | 1.098 |
| 2022_2025 | base | unfiltered_follow | 30 | 78.92 | 1.301 | 46.67 | 2.569 |
| 2022_2025 | base | buy_control | 15 | -82.41 | 0.4 | 40.0 | 2.268 |
| 2022_2025 | base | sell_control | 15 | 144.51 | 2.931 | 60.0 | 0.827 |
| 2022_2025 | stress | candidate | 15 | 19.47 | 1.192 | 53.33 | 1.127 |
| 2022_2025 | stress | unfiltered_follow | 30 | -32.89 | 0.896 | 43.33 | 2.766 |
| 2022_2025 | stress | buy_control | 15 | -89.01 | 0.364 | 40.0 | 2.375 |
| 2022_2025 | stress | sell_control | 15 | 139.43 | 2.822 | 60.0 | 0.843 |
| 2022_2025 | delay60 | candidate | 15 | 30.39 | 1.312 | 60.0 | 1.099 |
| 2022_2025 | delay60 | unfiltered_follow | 30 | 114.59 | 1.499 | 50.0 | 2.252 |
| 2022_2025 | delay60 | buy_control | 15 | -84.09 | 0.399 | 46.67 | 2.308 |
| 2022_2025 | delay60 | sell_control | 15 | 141.39 | 2.743 | 53.33 | 0.826 |

Costs: base uses the repository ECN scenario (historical spread or$0.26/oz fallback,20point adverse slip, commission$3.50/lot round trip); stress doubles spread and uses60point slip. These scenarios are not calibrated Atlas FOMC fills. Same-event buy/sell controls use identical geometry; their results cannot be cherry-picked into a new strategy after this test.

## Uncertainty, concentration and failure

Pooled candidate mean across47trades is$1.3480/trade, calendar-quarter block-bootstrap95%interval[-2.4313644811115793, 5.0869374396136235]. The interval contains0.1999fixed-seed draws do not create new market events.

- 2016_2021: expectancy$1.1488/trade and0.1552R; win59.38%. Matched balanced-direction advantage$0.3319/event,95%interval[-3.3562873655913146, 3.832713636363717], Bonferroni4p=1.0. Annual net: {'2016': 58.056000000001184, '2017': 36.24800000000074, '2018': -20.265999999999423, '2019': -21.351999999999173, '2020': -14.615999999999332, '2021': -1.3099999999994552}. Drop-best1 net$17.20; drop-best3 net$-18.73.
- 2022_2025: expectancy$1.7729/trade and0.1791R; win53.33%. Matched balanced-direction advantage$-0.2972/event,95%interval[-11.10703000000031, 9.892930208333109], Bonferroni4p=1.0. Annual net: {'2022': 13.134000000000377, '2023': 29.110000000000163, '2024': 10.093999999997067, '2025': -25.74400000000147}. Drop-best1 net$-11.54; drop-best3 net$-51.74.

| Predeclared condition | Passed? |
|---|---|
| sample_at_least_30_each_era | False |
| positive_net_and_pf_each_era | True |
| positive_pooled_mean_lower_ci | False |
| exceeds_direction_controls_each_era | False |
| sampled_dd_below_3_6pct_each_era | True |
| stress_and_delay_positive_pooled | True |
| drop_best_positive_pooled | True |

The later era has only15trades. Removing its best trade makes it negative; removing the best3makes both eras negative. Candidate frequency is about4.7trades/year across this sample, far from an everyday trading engine. The normalized-shock gate did not demonstrate reliable superiority to the unfiltered response or randomized direction controls. No revised threshold, opposite direction, different holding window or selected calendar subset is tested as a rescue.

JSON contains monthly/yearly/session/direction results, average wins/losses, R statistics, drawdown durations/recovery, sampled equity, weekday daily Sharpe/Sortino, distribution and Monte Carlo/ablation diagnostics. Weekday daily ratios include flat weekdays and are explicitly252annualized; raw trade Sortino is separate. Monte Carlo reshuffles an observed trade population and preserves its terminal cash: it is not a future profitability or Atlas breach probability. Full project search count/PBO matrix remains incomplete, so no precise DSR/PBO certification is invented. Unknown fees, actual slippage, news deductions, margin/protector policies and prospective fills preclude account qualification.

## Engineering verification and disclosed repair

Independent arithmetic/path audit checked654overlapping scenario trade records, found0mismatches and0ambiguous records. It independently reconstructs closed-history ATR14, entry-side prices, earliest M1stop/target or opening time-exit, commission, net and cash chain using the exact hashed master inputs. This certifies consistency with declared bar rules, not actual ticks, historical broker fills, or654independent observations.

The first harness run generated signals but no fills because a production night-window constant was imported before research24henvironment setup. Its invalid zero-fill output is retained as`fomc_shock_invalid_night_gate.json.gz`. A protocol amendment, early-process environment configuration and night-clock integration regression were committed before the valid replay. No valid fill results existed before that repair. All signal/threshold/exit parameters stayed fixed. Production code/settings remained unchanged.

## Reproducibility

- Protocol commits:`532351c`,`3471bf1`; disclosed bootstrap repair`9ea8322`.
- Runner:`scripts/research/fomc_shock_propagation.py`; run with`.\venv\Scripts\python.exe -m scripts.research.fomc_shock_propagation`.
- Independent audit:`.\venv\Scripts\python.exe -m scripts.validation.fomc_shock_audit`.
- Results:`research/results/finalization_2026-11-18/fomc_shock_propagation.json`; full equity records in same-name`.json.gz`, with archive hashes in the compact JSON.
- Source:`research/sources/fomc_usmpd_20261118/`; exact workbook hash pinned; calendar metadata committed. No retrospective rate/PCA/asset return is a signal feature.

The correct next step for this hypothesis is to retain it as an unqualified exploratory result. More trades can only come from a newly frozen prospective sample or a separately justified new mechanism; re-labeling controls or optimizing these eras would not supply independent evidence.
