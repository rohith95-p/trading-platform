# Are the live stop/target sizes the best? (2026-10-30)

Live 4-leg setup (daily gate on, protector off, 24h, 0.02 lots, Atlas guard, realistic ECN costs), M1 bars only.
Step 1, `scripts/validation/sltp_sweep.py`: replays the real entries with 60 stop/target combinations per strategy
(stop 1.0–4.0 x ATR, target 1.5–8.0 x ATR). The replay reproduces the engine's own trades (560/561 to the cent).
Combinations were picked on DEV + TEST; RECENT (2026-07 to 2026-10) was kept unseen.
Step 2: full-engine confirm of the candidates (trade limits and Atlas guard included).

| Candidate | DEV | TEST | RECENT (unseen) | All: net | PF | Max DD | Losing months |
|---|---|---|---|---|---|---|---|
| **Live** (ARF 2.0/3.5, London 2.0/4.0) | +$101 | +$856 | +$730 | +$1,687 | 1.34 | $298 | 31% |
| Asian Range Filtered stop 2.5 ATR | +$134 | +$1,095 | +$790 | **+$2,020** | **1.42** | $356 | 29% |
| London Momentum stop 2.5 / target 8.0 ATR | +$220 | +$1,355 | **−$116** | +$1,458 | 1.27 | $401 | 38% |
| Both | +$262 | +$1,520 | +$730 | +$2,512 | 1.46 | $463 | 34% |

Asian Breakout (22 trades) is too rare to tune; NY Session Reversal is already at the best of its grid.
Verdict: only the Asian Range Filtered stop at 2.5 ATR improves every window including the unseen one; the London
change fails on unseen data. Each ARF loss gets ~25% bigger (stop $40 instead of $32 at 0.02 lots).
