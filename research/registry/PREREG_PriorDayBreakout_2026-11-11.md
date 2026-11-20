# Previous-day range breakout: public-rule adaptation

Recorded before this runner's first test; not a committed or independently registered protocol.
Source: https://github.com/allanninal/prior-day-breakout-pine (README rules accessed 2026-11-11).
Independent implementation of the described rule; no third-party source code copied.
The advertised presets are XAUEUR, not evidence for XAUUSD; repository test table contains TODO placeholders.

XAUUSD only, M15, fixed 0.02 lots (2 oz), target 2R, no parameter search.
Server clock is New York wall time plus seven hours, preserving the stated 17:00 NY day boundary across DST.
Prior available trading day high/low, maximum seven calendar days; exclude the initial potentially partial day.
First closed bar beyond each level consumes that side's signal for the day. Signal bar opens at/after 01:00;
enter only when flat, at the immediately following M15 open, on the same server day and before 20:00.
Require adjacent bars, avoiding fills across missing data. Stop at opposite previous-day extreme; target 2R
from executable entry including spread/slippage. Forced flat at first observed open at/after 23:00 or
the next server day if a data gap prevents it. Gap-aware stops; stop first on dual-touch bars.
Bid OHLC, constant per-bar observed spread with configured fallback, .02 price slippage each side,
realistic_ecn commission/swap. Same-bar stop/target path unknowable; count ambiguous bars explicitly.
M15 data cannot establish actual spread path or Atlas intraminute equity compliance.

Three already-inspected development eras: 2005-2011, 2012-2018, 2019-2025.
Report trade count, win rate, PF, expectancy, drawdown, Sortino/Omega/Calmar/recovery,
trade-order Monte Carlo and best/worst trade ablation. Save dated cash P&L for aligned search correction.
November 2026 holdout excluded. No claim of independent out-of-sample discovery or full Atlas validation.
Require PF >=1.3 in every era before spending effort on an account-policy/quote-level replay.
