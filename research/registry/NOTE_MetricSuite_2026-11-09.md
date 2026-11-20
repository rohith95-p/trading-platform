# Result — the owner's robustness list, run on the real records

Requested 2026-11-09: Monte Carlo, deflated Sharpe, Sortino, Omega, Calmar,
recovery factor, ablation. All were already implemented in this repo. **None had
ever been run**, and `scipy` was not installed, so
`src/research/metrics.deflated_sharpe_ratio` had never been executable and
`grep` confirms nothing had ever called it. Environment fixed to match
`requirements.txt` (`a5e844d`); raw numbers in
`full_metric_suite_2026-11-09.json`.

Source paper, supplied by the owner and read directly: **Bailey, D. H. and
López de Prado, M. (2014), "The Deflated Sharpe Ratio: Correcting for Selection
Bias, Backtest Overfitting and Non-Normality," Journal of Portfolio Management**
(SSRN 2460551) — the same paper this repo's implementation cites.

## Deflated Sharpe on the window that produced PF 1.41

Equation 2 inputs, all measured rather than assumed: per-trade SR 0.1409,
T = 269, skew 0.761, kurtosis 3.599, and `V[{SR_n}]` = **0.0199** taken from 21
real in-sample candidate Sharpes. (The function's own docstring warns that
leaving `sr_variance` at 1.0 is unfairly harsh — it gives 0.0000 everywhere. The
kinder measured input is used throughout.)

| independent trials N | SR_0 threshold | DSR |
|---|---|---|
| 1 | 0.0000 | **0.9923** |
| 2 | 0.0733 | 0.8775 |
| 3 | 0.1203 | 0.6384 |
| 4 | 0.1484 | 0.4485 |
| 10 | 0.2221 | 0.0812 |
| 21 | 0.2711 | 0.0125 |
| **48** (strategies actually screened) | 0.3189 | **0.0011** |
| 100 | 0.3570 | 0.0001 |

DSR falls below **0.95 at N = 2**, below **0.50 at N = 4**, below **0.05 at
N = 13**.

**This is the whole story of the project in one table.** Had exactly one strategy
been written and tested, PF 1.41 would have been real with 99.2% probability. It
took 48 to find it, and the probability is then **0.11%**.

**The sensitivity cuts in the strategies' favour and still does not save them.**
The paper notes (p.7) that N must be the number of *independent* trials and that
its Appendix 3 gives a method when trials are dependent — our trials are
correlated, so the effective N is below the raw count, which would *raise* DSR.
But the threshold is brutal: the effective number of independent trials would
have to be **2 or fewer** for the 1.41 to clear 0.95. Against 48 distinct
strategy rules plus a 60-cell parameter sweep plus everything in
`research/registry/`, no plausible correlation adjustment reaches an effective
N of 2.

**None of this touches the out-of-sample verdict.** DSR corrects an *in-sample*
number for selection. The 18-year PF 0.90 is a direct measurement and needs no
such correction — and its DSR is 0.0146 even at N = 1, so the out-of-sample
Sharpe is not significantly positive even treated as a single trial.

## Out-of-sample, 2,556 trades: every metric negative

| | |
|---|---|
| profit factor | 0.900 |
| win rate | 35.6% |
| expectancy | **−$0.513 / trade** |
| Sortino | −0.1042 |
| Calmar | −0.059 |
| Omega | 0.900 |
| recovery factor | −0.928 |
| Sharpe per trade | −0.0439 |
| skew / kurtosis | 0.727 / 4.777 |

As predicted before running: these are lenses on one P&L stream, and the stream
is negative. No value of any of them can make a losing system win.

(Non-normality is real here — skew 0.73, kurtosis 4.78 against a Normal's 0 and
3 — which is precisely why DSR carries both moments in its denominator.)

## Monte Carlo, 5,000 reshuffles

`prob_final_below_start` = **1.0**. Median final balance $3,688.65 from $5,000;
worst drawdown $2,312.86. **Every single ordering of those 2,556 trades ends
below the starting balance.** The losing is not in the sequence; it is in the
trades.

## Ablation — this kills the "filter out the bad trades" hope

| | |
|---|---|
| net | −$1,311.35 |
| drop the 5 **worst** trades | **−$1,078.35** |
| drop the 5 **best** trades | −$1,588.00 |
| top 3 wins as share of gross profit | **1.5%** |

Removing the five worst trades still loses a thousand dollars. The loss is spread
evenly across 2,556 trades, so there is no tail of disasters a filter could
remove. By contrast the in-sample window's top 3 trades are 8.1% of gross
profit — more concentrated, which is what a lucky sample looks like.

## The paper's criticism of my own method, recorded against myself

p.6, on the holdout method:

> "Holdout assesses the generality of a model as if a single trial had taken
> place, again ignoring the rise in false positives as more trials occur. If we
> apply the holdout method enough times (say 20 times for a 95% confidence
> level), false positives are no longer unlikely: They are expected."

This repo has used holdout windows repeatedly — 2016-2022 twice
(`entry_search` CONFIRM, `vol_timing` TEST), 2004-2016 once, the 18-year holdout
once, plus the October DEV/VALIDATE work. **Pre-registered holdouts are
necessary but, by this paper's argument, not sufficient.**

Repeated holdout use inflates false **positives**, so it does not threaten a
negative finding — the 0.90 stands. But it means that **had the entry search
produced a winner, this protocol would not have been enough to validate it.**
DSR on an honest effective-N would have been required on top. That is a real gap
in how this project has been run, and it is the paper's contribution to it.

Also noted for future use (p.10-11): the paper's answer to "how many trials
should one attempt" is the 1/e law of optimal choice — sample ~37% of the
theoretically justifiable configurations at random, then take the first that
beats all previous. A concrete cap on trials, which this project never had.

The paper's own conclusion describes this project exactly:

> "selection bias combined with backtest overfitting misleads investors into
> allocating capital to strategies that will systematically lose money."
