# --- ATLAS PORTFOLIO (funded account evaluation + funded phase) ---
#   1. AsianRangeFilteredV6 (7320): Asian range breakout with range-size gate, 12:45 IST
#   2. AsianBreakoutV6 (7311): Asian range breakout without the gate, 12:45 IST
#   3. LondonMomentumTightV6 (7324): London/NY overlap continuation, 17:45 IST
#   4. NYSessionReversalV6 (7313): NY session sweep reversal, 17:45-21:30 IST
#
# 2026-10-30 audit (M1 only, $5K, 0.02 lots, protector off, 24h, D1 gate on, Atlas guard, realistic ECN;
# scripts/validation/independent_audit_run.py), DEV / TEST / RECENT:
#   4-leg  PF 1.06 / 1.36 / 1.75, all windows +$1,687, 31% losing months.
#   5-leg  (+DonchianTrendV6 7310) PF 1.07 / 1.32 / 1.53, +$1,627, 38% losing months.
# DonchianTrendV6 removed 2026-10-30 (owner: "remove it if it's useless"): 89 trades, -$11, PF 0.98 on its own.
# LondonMomentumV6 takes the same trades as the Tight variant; never run both.

from src.strategies.asian_range_filtered import AsianRangeFilteredV6
from src.strategies.asian_breakout import AsianBreakoutV6
from src.strategies.london_momentum_tight import LondonMomentumTightV6
from src.strategies.ny_session_reversal import NYSessionReversalV6

PORTFOLIO = [AsianRangeFilteredV6, AsianBreakoutV6, LondonMomentumTightV6, NYSessionReversalV6]
