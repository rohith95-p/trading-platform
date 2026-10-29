# --- ATLAS PORTFOLIO (funded account evaluation + funded phase) ---
#   1. DonchianTrendV6 (7310): daily 10-day breakout, checked 06:15 IST
#   2. AsianRangeFilteredV6 (7320): Asian range breakout with range-size gate, 12:45 IST
#   3. AsianBreakoutV6 (7311): Asian range breakout without the gate, 12:45 IST
#   4. LondonMomentumTightV6 (7324): London/NY overlap continuation, 17:45 IST
#   5. NYSessionReversalV6 (7313): NY session sweep reversal
#
# 2026-10-29 M1 shared-cap confirm ($5K, 0.02 lots, live parity, risk rules on;
# scripts/research/atlas_candidate_study.py --confirm):
#   5-leg  PF 1.14 / 1.39 / 1.48 (DEV / TEST / RECENT), ~0.6 trades/day, ~half of days traded,
#          maxDD <= 5.6%, worst day -$92, no Atlas 10% / 5% breach.
#   3-leg  PF 1.43 / 1.52 / 0.91, ~0.2 trades/day.
# LondonMomentumV6 takes the same trades as the Tight variant; never run both.

from src.strategies.momentum_strategies import DonchianTrendV6
from src.strategies.asian_range_filtered import AsianRangeFilteredV6
from src.strategies.asian_breakout import AsianBreakoutV6
from src.strategies.london_momentum_tight import LondonMomentumTightV6
from src.strategies.ny_session_reversal import NYSessionReversalV6

PORTFOLIO = [DonchianTrendV6, AsianRangeFilteredV6, AsianBreakoutV6,
             LondonMomentumTightV6, NYSessionReversalV6]
