# --- ATLAS PORTFOLIO (optimized for funded account evaluation + funded phase) ---
# Three strategies: two Asian breakout variants + daily trend-following.
#   1. DonchianTrendV6 (7310): Daily trend-following, wider stops
#   2. AsianRangeFilteredV6 (7320): Filtered Asian breakout (tight range gate)
#   3. AsianBreakoutV6 (7311): Unfiltered Asian breakout (catches wider ranges)
#
# Backtested 2026-10-25 across DEV/VALIDATE/HOLDOUT:
#   HOLDOUT: PF 1.44, MaxDD 4.08%, Worst Day 2.33%, 45 days to 3% target
#   Atlas eval (10% DD, 5% daily): PASS with 59% safety margin
#   Atlas funded (6% DD, 3% daily): PASS with 32% safety margin
#
# AsianBreakout adds ~6 extra trades/month that AsianRangeFiltered skips
# (wider ranges that still break out). Slightly higher DD but more
# trade frequency for Atlas payout eligibility.

from src.strategies.momentum_strategies import DonchianTrendV6
from src.strategies.asian_range_filtered import AsianRangeFilteredV6
from src.strategies.asian_breakout import AsianBreakoutV6

PORTFOLIO = [DonchianTrendV6, AsianRangeFilteredV6, AsianBreakoutV6]
