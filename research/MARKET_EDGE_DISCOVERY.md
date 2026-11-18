# Market edge discovery — 2026-11-18

No qualified positive-expectancy strategy was established. This study distinguishes a detectable conditional effect from an executable trading advantage.

## Fixed atlas findings

The18 fixed exploratory comparisons use monthly bootstrap uncertainty and Bonferroni correction within this family. They do not erase prior searches or establish independence. November holdout remains untouched.

- Volatility clusters across intraday resolutions. This supports conditional risk forecasting, not a direction to buy or sell.
- Extreme M1 and M15 moves exhibit small next-bar reversal in each of the three historical era groups. M15 mean signed continuation is−0.359bps (reversal+0.359bps),95% interval[−0.556,−0.173]bps; adjusted centered-bootstrap p=.018, limited by999 draws. This may include bid bounce and source artifacts.
- H1 extreme continuation changes sign in the most recent era; H4 has only433 extreme observations, D1 only174. No dependable cross-regime directional conclusion follows.
- Macro same-row correlations are much stronger than most lagged correlations and lack certified information-availability timestamps. They do not authorize same-day forecast features.

## Economic hurdle

The same predetermined extreme thresholds were used for an approximate cost comparison. This is a descriptive reference-price movement, never an execution/backtest substitute.

| Resolution | Events | Mean reversal reference move $/oz | Mean modeled round-trip hurdle $/oz |
|---|---:|---:|---:|
| M1 | 398,154 | 0.01861 | 0.33479 |
| M15 | 34,985 | 0.05311 | 0.32288 |

Hurdle uses historical spread field or its explicit fallback, two assumed adverse slips and commission converted to price units. Zero archive spreads mean unavailable. Fees are repository ECN scenarios, not intended Atlas contract verification. Full candidate evaluation must additionally include fills, gap risk, ambiguity, financing, risk, account constraints and broker checks.

## Promotion decision

Neither fixed directional lead clears the reasonable-cost-margin gate in the atlas preregistration. They are not promoted into a newly fitted strategy. Volatility forecasting alone also fails the directional-alpha gate. No profitable strategy, Sharpe, DSR, PBO or payout rate is invented for a non-existent candidate.

## Falsifiable next directions

1. Publication-timed macro surprises with a causal post-release entry delay. Requires actual/revised release values and pre-release consensus with availability timestamps, not merely dates. Test matched event-time controls and exact bid/ask execution.
2. Volatility-aware abstention evaluated against an already positive independently confirmed signal. It must improve risk-adjusted net outcomes against matched exposure; it cannot create direction from a failed portfolio.
3. Cross-source replication of intraday reversal using synchronized observed bid/ask and noise-aware outcomes. If the effect disappears after using executable sides, reject it as nontradeable microstructure.

Each needs a separate committed candidate protocol before evaluation. Reusing examined2004–2026 data remains development; only prospectively frozen data can provide fresh confirmation. Reproduce with `venv/Scripts/python.exe -m scripts.research.market_edge_discovery`.
