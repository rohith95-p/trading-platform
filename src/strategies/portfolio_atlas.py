# --- ATLAS PORTFOLIO (optimized for funded account evaluation + funded phase) ---
# Two strategies chosen for maximum Atlas rule safety:
#   1. DonchianTrendV6 (7310): Daily trend-following, wider stops
#   2. AsianRangeFilteredV6 (7320): Filtered Asian range breakout
#
# Backtested 2026-10-25 across DEV/VALIDATE/HOLDOUT:
#   HOLDOUT: PF 1.49, MaxDD 1.76%, Worst Day 0.82%, 45 days to 3% target
#   Atlas eval (10% DD, 5% daily): PASS with 82% safety margin
#   Atlas funded (6% DD, 3% daily): PASS with 71% safety margin
#
# AsianRangeFiltered replaces basic AsianBreakout — same entry logic but
# with range filter (0.3%-1.6% of price) that eliminates worst setups.
# LondonMomentum removed: caused 6.00% MaxDD hitting the funded limit.

from src.strategies.momentum_strategies import DonchianTrendV6
from src.strategies.asian_range_filtered import AsianRangeFilteredV6

PORTFOLIO = [DonchianTrendV6, AsianRangeFilteredV6]
