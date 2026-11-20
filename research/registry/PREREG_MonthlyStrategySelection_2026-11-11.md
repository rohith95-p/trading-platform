# Retrospective monthly strategy-selection diagnostic

Recorded before first execution; no parameter sweep. Underlying candidate universe was
discovered after observing these eras, so chronological calculations do not create untouched
out-of-sample evidence. This tests one fixed adaptation hypothesis; no deployment claim.
Selection-bias reference: https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf .

Input is the recovered aligned daily realized cash-P&L matrix. Use only eleven intraday
arms: auction_follow, auction_fade, cot_follow, cot_fade, orb_target_1, orb_target_2,
gld_creations, gold_iv_premium, miners_residual, paxg_flow, us_intraday_momentum.
Exclude multi-day Supertrend/GitHub VWAP arms and unverified session-flat arms. Selecting
multi-day trades on their exit dates could credit positions never entered. Intraday inputs
still inherit their original missing-bar coverage filters and public-data timing limitations.

2022 supplies warmup; evaluate January 2023 through December 2025 only. On the first
available business day of each month, rank arms on the latest 252 strictly earlier business
days. Require >=30 nonzero-P&L days, daily profit factor >=1.3 and positive Sharpe.
Pick largest mean / sample standard deviation, with lexical name tie break. Hold that arm
for the entire next month. If no eligible arm exists, remain flat. No shorting losing arms,
leverage, risk scaling or switching on today's result. Each arm retains its original .02 lot
costed cash P&L. Daily PF here is NOT trade PF and cannot satisfy the user's trade-PF gate.

Compare with equal allocation across the same arms (fractional notional diagnostic only)
and cash. Store every decision, per-day selected P&L, content hashes of input/protocol/code,
daily risk ratios and 5000 month-block bootstrap totals. Bootstrap loss fraction is conditional
on the observed monthly sample, not a future account-failure probability. No Atlas payout,
MTM equity, news eligibility or margin claim; any survivor needs actual trade/quote replay.
No November 2026 holdout input and no extension after seeing output. Count this selection
rule as an additional research trial. Positive results would justify further testing only.
