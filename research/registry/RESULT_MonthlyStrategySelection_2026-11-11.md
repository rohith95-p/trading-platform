# Monthly strategy rotation: failed diagnostic

Reproducible runner: scripts/research/monthly_strategy_selection.py
Protocol: PREREG_MonthlyStrategySelection_2026-11-11.md
Outputs: monthly_strategy_selection.json and monthly_strategy_selection_daily.csv.

One fixed rule selected among eleven intraday candidates each month using only the previous
252 business days. Eligibility required 30 active P&L days, daily PF >=1.3, positive Sharpe;
largest Sharpe selected, otherwise cash. These parameters were recorded before execution,
not optimized after seeing output. Candidate research itself used these historical periods:
this is retrospective causal selection, not untouched forward validation.

| Evaluation year | Net USD | Daily PF | Active days |
|---|---:|---:|---:|
| 2023 | 31.92 | 1.099 | 58 |
| 2024 | -214.88 | .461 | 39 |
| 2025 | -127.69 | .598 | 5 |
| All | -310.65 | .701 | 102 |

783 business days, 45 profitable active days, annualized daily Sharpe -.540, Sortino -.722,
realized-balance maximum drawdown $380.47 (7.56%), recovery -.816, Calmar -.270.
18 months remained cash; eight selected PAXG flow, eight COT fade, one GLD creations and
one miners residual. Equal allocation to all eleven also lost $301.86, daily PF .700.
Equal allocation is a fractional-notional research control, not broker lot-feasible execution.

5000 resamples of the 36 observed monthly blocks give total-net percentiles 2.5/50/97.5:
-$743.66 / -$298.11 / +$39.03. 95.16% of those conditional resamples lose money; this is
not a prediction of future loss probability. The interval includes zero and supports no
positive-return claim. No thresholds were changed after observing these results.

Daily PF and active-day profitability differ from individual-trade PF and win rate. Maximum
drawdown excludes floating losses. No Atlas pass, rule compliance or payout claim follows.
Selecting multi-day strategies by exit-day P&L would create unearned position profits; those
arms were excluded. Intraday screens retain their original data quality/coverage caveats.
The protocol, runner and exact input matrix hashes are saved with every monthly decision.
November 2026 holdout remains unused. This is an additional selection experiment beyond
the sixteen recovered underlying arms; those sixteen are not the complete historical search.

Validation: future-outcome mutations cannot change prior/month-start choices; ties resolve
deterministically; no eligible arm means cash; nonchronological input is rejected.
Conclusion: do not promote this fixed rotation rule and do not tune it on the same outcome.
