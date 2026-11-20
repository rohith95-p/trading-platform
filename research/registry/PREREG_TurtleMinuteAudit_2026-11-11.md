# Turtle one-minute execution and sampled equity audit

Written before this runner's outputs. Keep the prior daily M15-derived FX-session
channels/N fixed; join them onto actual M1 quotes. No signal/parameter selection or tuning.
Both prior one/four-unit .02lot variants, eras2005–11,2012–18,2019–25, base project ECN
assumptions. Actual Atlas account not purchased, contract costs unverified. User confirmed
research-before-buying on2026-11-11. No paid data or live orders needed.

Replay core with60-second bar timestamps. Preserve actual per-unit fills, costs, funding,
basket records and minute-data hash. Incomplete M1 coverage/gaps remain visible; carry
positions across gaps with opening-price stops, not invented interpolated prices. M15
daily levels and M1 execution can originate from differing historical feeds. M1 is still
not tick data: same-minute path and intraminute spread unknown. Report this limitation.

Independently reconstruct equity at observed minute opening quotes. Count a new unit
only from the following minute, when its intraminute fill is known completed; a stopped
basket realizes at that minute's end. Include half-roundtrip entry commission and accrued
calendar funding while open, bid/ask mark, full fees/slippage after close. Append final
boundary liquidation. Marking at minute opens does not capture all floating extrema, so
sampled drawdown is not a proof of full intraminute compliance. Check ledger balance sum.

Separate raw unrestricted signal path from limited Access cash-flow scenarios. Each era
starts fresh$5000: evaluation5%daily/10%trailing equity,3%target when flat; funded3%daily/
6%trailing, hypothetical$100cash at90%split via existing AccessAccount waiting/day/
consistency/reanchor rules. Funding/fee inputs are scenarios, not verified Atlas pricing.
Stop funded diagnostic at first sampled -2%anchor floating loss because protector would
liquidate and invalidate subsequent unmodified trade path. Do not simulate past it or call
it a lifetime breach/complete protector implementation. No second-strike/split reduction,
all-calendar news deductions/min-hold profit deductions/activation fees modeled here.
Therefore no verified pass/payout probability or deployment eligibility may be claimed.

Report individual scenario statuses/timestamps, conditional cash payouts, raw sampled MTM
DD, trade metrics and coverage gaps. Failure is useful risk evidence; sampled survival is
not complete account validation. November2026 reserved holdout excluded.

Sizing extension recorded after the initial .02-lot audit, before its result: compare
.01-lot units by scaling fixed-path P&L, linear financing and commission by .5; spread/
slippage prices and all signal decisions unchanged. This is a diagnostic of a commonly
assumed minimum unit, not verified Atlas specifications. No search over position sizes
and no selection of better trades. Actual fills can differ with size/venue in live markets.

Phase-link extension before its outputs: additionally start a fresh funded $5000 account
at the evaluation's flat pass timestamp, resetting cash to5000 and discarding prior profits.
Assume instant activation, no activation fee/delay (optimistic, not real account issuance).
Only future baskets can count toward funded profit/days/payouts. Existing independent
phase scenarios remain for diagnostics and are not labelled evaluation-to-funded sequences.
