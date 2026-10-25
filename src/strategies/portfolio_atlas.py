# --- ATLAS PORTFOLIO (optimized for funded account evaluation) ---
# Two uncorrelated strategies for smooth equity curve:
#   1. AsianBreakoutV6 (7311): Intraday, London open breakout, tight stops
#   2. DonchianTrendV6 (7310): Daily, trend-following, wider stops
#
# Combined: ~4-6 trades/week (good for Atlas payout eligibility:
# 3+ days with >=0.5% profit per cycle).
#
# Risk per trade: 0.5% of account (enforced by Atlas rule engine).
# Max DD target: <6% (60% safety buffer on Atlas's 10% trailing DD).

from src.strategies.asian_breakout import AsianBreakoutV6
from src.strategies.momentum_strategies import DonchianTrendV6

PORTFOLIO = [AsianBreakoutV6, DonchianTrendV6]
