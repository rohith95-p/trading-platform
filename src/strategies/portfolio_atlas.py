# --- ATLAS PORTFOLIO (optimized for funded account evaluation) ---
# Three uncorrelated strategies for smooth equity curve:
#   1. AsianBreakoutV6 (7311): Asian range breakout at London open
#   2. DonchianTrendV6 (7310): Daily trend-following, wider stops
#   3. LondonMomentumV6 (7316): London/NY overlap trend continuation
#
# Backtested 2026-10-25: all three pass VALIDATE (PF>1.0) + HOLDOUT (PF>1.0).
# LondonMomentum adds ~130 trades/16mo at PF 1.20 in holdout.
#
# Risk per trade: 0.5% of account (enforced by Atlas rule engine).
# Max DD target: <6% (60% safety buffer on Atlas's 10% trailing DD).

from src.strategies.asian_breakout import AsianBreakoutV6
from src.strategies.momentum_strategies import DonchianTrendV6
from src.strategies.london_momentum import LondonMomentumV6

PORTFOLIO = [AsianBreakoutV6, DonchianTrendV6, LondonMomentumV6]
