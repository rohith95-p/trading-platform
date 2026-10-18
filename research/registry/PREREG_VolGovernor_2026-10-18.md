# Pre-registration — Volatility-regime risk governor (a risk overlay, NOT a profit claim)

Frozen 2026-10-18 BEFORE any replay was computed. It consumes no directional trial number; it asks one question: does the regime tell us anything about WHEN the (already falsified) strategies lose?

## The governor (deterministic, fail-closed; src/core/vol_regime.py)
- Feature: ATR(14, Wilder) on H1 bars built from M15 (complete UTC hours only), taken at the last CLOSED H1 bar before the decision time. ATR percentile = rank of that value among the previous 1,440 H1 ATR values (about 60 trading days, current value excluded). Fewer than 720 prior values -> regime UNKNOWN.
- Regimes: **EVENT** (within 30 min before to 60 min after an event in research/events/usd_high_impact_2022_2026.csv) -> allowed=false, mult 0. Else **HIGH** (percentile > 85) mult 0.5; **LOW** (< 25) mult 0.5; **NORMAL** (25..85) mult 1.0. UNKNOWN or missing input -> allowed=false (fail closed).
- Applies to ENTRIES only: a trade's P&L is scaled by the multiplier in force at its entry (fill) time; blocked trades contribute 0. Nothing is retuned.

## Replay sets (existing, previously falsified strategies; used only as test material)
1. FvgGold B/path (scripts/research/fvggold_sim.py, as in the audit), entries 2022-09-01..2026-10-13, entry time = fill time.
2. Trial #640 trades (research/registry/regime_trend_result_2026-10-18.json) — already exclude events.
3. Trial #641 trades (33; reported but NOT part of the pass decision: too few).
Trades before the percentile warm-up are dropped from BOTH arms.

## Metrics
Per set, baseline vs governed: trades kept, net P&L, max drawdown, Calmar = net / max drawdown, worst day, CVaR(5%) of trade P&L, and expectancy per regime (NORMAL / LOW / HIGH / EVENT) with trade counts.

## Placebo (the key control)
A multiplier set that merely trades less looks better on drawdown. So: keep the SAME counts of trades in each multiplier bucket (blocked / 0.5 / 1.0) but assign them to randomly chosen trades, 5,000 shuffles (seed 641). The governor is credited only if its Calmar exceeds the 95th percentile of the placebo Calmar.

## Pass rule (falsification gate)
The governor is "useful" only if, in BOTH replay sets 1 and 2: governed Calmar > baseline Calmar AND governed Calmar > the placebo 95th percentile. Otherwise the regime carries no information about these strategies' losses and the governor is only a generic exposure reducer (can still be used as a blunt safety cap, not credited as an edge or as an improvement). Regime-level expectancies are reported descriptively; no regime is promoted to a trading rule.
No threshold, window or multiplier may be changed after the replay.
