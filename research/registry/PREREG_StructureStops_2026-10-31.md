# PREREG: structure-based stops and targets (2026-10-31)

**Question (owner):** would stops placed at market structure (beyond the last swing high/low, or the other side of
the range the trade broke out of), with targets as a multiple of that risk, beat the live ATR-multiple stops?

**Data and entries:** the real entries of the live 4-leg setup (`research/results/audit_2026-10-30/trades_no_donchian.json`,
gate on, protector off, 0.02 lots; Asian Range Filtered replayed with its live 2.5 ATR stop as the baseline).
Exits replayed on raw M1 bars with the engine's costs (bar spread, 20-point stop slippage, $3.50/lot commission,
long swap) and the Friday 22:30 IST close. Entries are fixed; lot size stays 0.02 (so dollar risk per trade varies).

**Variants (fixed before running, no additions):**
- `swingN_kR` for N in {4, 8, 16} closed M15 bars before entry and k in {1.5, 2.0, 3.0}:
  stop 0.1 ATR beyond the lowest low (buy) / highest high (sell) of those N bars; target = k x stop distance.
- `range_kR` (Asian Range Filtered and Asian Breakout only) for k in {1.0, 1.5, 2.0}:
  stop 0.1 ATR beyond the opposite side of that day's Asian range (00:00-06:00 UTC); target = k x stop distance.
- Every structure stop distance is clamped to [0.5, 4.0] x ATR (too tight = noise, too wide = runaway risk).

**Choose on:** DEV + TEST (2022-08 -> 2026-02, M1 bars only, data hole excluded).
**Judge on:** RECENT (2026-07 -> 2026-10), unseen for this choice.

**Pass bar, per strategy:** the best DEV+TEST variant replaces that strategy's live stops only if
(1) DEV+TEST net > live, (2) RECENT net >= live, and (3) DEV+TEST max drawdown <= 1.2 x live.
Anything else: keep the live ATR stops. A pass is then confirmed with the full engine before any live change,
and it does not go live during the freeze week.
