# Result — overlap window and time of day, live 4-leg portfolio (prereg 29e8b9b; script committed before the run)

Corrected engine, realistic_ecn costs, fixed 0.01 lot, D1 gate ON. Coarse 2022-08..2026-07 (DEV 2022-08..2024-12, VALIDATE 2025-01..2026-06) plus an M1-resolution check 2026-07-06..10-13. Raw: session_timing_result_2026-10-19.json. Coarse resolution flatters tight stops (PF 1.38 coarse vs 0.93 M1), so only comparisons between windows are meaningful.

## Q1 — Should the 15:30-17:30 IST overlap be traded? NO (keep the skip)
| Period | Whole portfolio, live (skip) | Whole portfolio, overlap allowed | Overlap-window trades alone |
|---|---|---|---|
| DEV | PF 0.77, net -$949 | PF 0.75, net -$1,116 | n=429, win 17%, PF 0.56, exp -0.36 R |
| VALIDATE | PF 1.00, net -$4 | PF 0.97, net -$223 | n=312, win 22%, PF 0.70, exp -0.11 R |
| DEV+VAL | PF 0.91, net -$954, max DD $1,267 | PF 0.88, net -$1,340, max DD $1,664 | n=741, PF 0.65, net -$394 |
| M1 (3 months) | PF 0.93 | PF 0.93 | n=56, PF 0.93, ~0 |
Decision rule failed (needs PF > 1 and positive expectancy in both halves): allowing the overlap adds 741 trades that lose $394 and raises max drawdown. The skip is correct. Today's +$7.48 overlap sell was a single winner, not a pattern.

## Q2 — Best hours (IST entry hour): no stable best hour exists
- Selected on DEV: hours 11, 13, 21. In VALIDATE 13 and 21 stayed positive (PF 1.33 and 1.58) but 11 did not; as a set they lose in the M1 run (n=66, PF 0.63).
- Benjamini-Hochberg across 16 hours: best adjusted p = 0.80. No hour is statistically stable (stable hours: none).
- Descriptive pattern: almost every hour with real sample size is negative in DEV. Worst: 12h (PF 0.61), 16h (PF 0.42 DEV), 17h (0.59 DEV, 0.50 VAL). The bot's actual trading hours 18-21 are the least bad (DEV PF 0.68-0.90, VALIDATE 0.88-1.58) but not reliably positive. Hours before 11:00 produce no trades (the legs are inactive then).
- By leg (VALIDATE PF): BB 1.11 (n=130), FVG-NY 1.04 (n=659), NVMR 0.94, TrendPullback 0.92 (n=1,481) — all weaker than 1.25, none stable across DEV and VALIDATE.

## Practical read (not a claim of edge)
Keep the overlap skip. If hours are to be restricted, the data supports AVOIDING 12:00-17:30 IST rather than favouring any hour; 18:00-21:30 is the least bad window, which is where the bot already trades. No timing choice turns the portfolio profitable: even with the best window the whole-portfolio PF at M1 is 0.93.
