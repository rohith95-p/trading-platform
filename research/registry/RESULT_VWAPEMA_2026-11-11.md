# VWAP / EMA real-bar screens: no promotion

Paper: https://ssrn.com/abstract=6650958 ; author paper mirrored at
https://www.scribd.com/document/1063631287/ssrn-6650958 .
GitHub strategy: https://github.com/mrZtrader68/gc-strategies/blob/main/vwap_regime_strategy.py
The paper's methodology uses assumed outcome probabilities, not actual historical trade replay.
Its headline result is therefore not evidence of a historically realised edge. Published
summary and bucket arithmetic also differ: see vwap_paper_arithmetic.json and its reproducible runner.

| Core mechanism | Period | Trades | Win % | PF | Net USD |
|---|---|---:|---:|---:|---:|
| GitHub | 2005–11 | 5466 | 16.7 | .831 | -2603.31 |
| GitHub | 2012–18 | 5797 | 16.8 | .784 | -3404.43 |
| GitHub | 2019–25 | 6055 | 18.3 | .932 | -1787.00 |
| Stricter paper-inspired | 2005–11 | 181 | 24.3 | .798 | -158.46 |
| Stricter paper-inspired | 2012–18 | 223 | 30.9 | 1.146 | 107.24 |
| Stricter paper-inspired | 2019–25 | 277 | 32.9 | 1.065 | 102.83 |

No era/arm clears PF 1.3. More recent stricter core has only 277 trades over seven years,
not evidence of profitable daily participation. Two ambiguous M15 bars across that arm
resolve stop first. P&L includes spread, slippage, commission and swap at fixed .02 lots.
Full metrics in vwap_ema.json; dated series included in recovered search report (16 arms).
Source thresholds were fixed before this run, but all eras were previously inspected in
other studies; none is pristine out-of-sample evidence. November 2026 was not accessed.

This evaluates core rules with tick-volume VWAP, not true consolidated traded volume.
Omitted paper news overrides, partial exits, varying position sizing and daily-cap policy
prevent calling it a full paper replication or Atlas account simulation. The exact changes
and limitations are listed in PREREG_VWAPEMA_2026-11-11.md. Results reject promotion of
these implemented candidates; they do not establish that every possible VWAP variant fails.

Four deterministic tests verify indicator prefix invariance, session VWAP reset and
next-open long/short EMA exits with executable spread. No live configuration changed.
