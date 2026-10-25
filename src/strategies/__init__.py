"""Strategy package.

ACTIVE (live in main_loop via portfolio_atlas.py):
  DonchianTrendV6 (7310) — daily breakout with EMA50 trend filter
  AsianRangeFilteredV6 (7320) — Asian breakout with range filter
  AsianBreakoutV6 (7311) — unfiltered Asian breakout

ARCHIVED: All prior strategies (V4/V5 legs, failed London/NY candidates)
  saved in src/strategies/archive/ and src/strategies/_deprecated/.
"""

from src.strategies.base_strategy import BaseStrategy, Signal

__all__ = [
    "BaseStrategy",
    "Signal",
]
