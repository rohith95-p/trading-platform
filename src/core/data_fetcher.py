"""
DataFetcher -- Centralised MT5 data access layer.

Fetches:
  - M15 OHLCV for strategy signals
  - D1 OHLCV for daily ATR drawdown cap
  - M5 tick_volume for volume confirmation
  - Live tick data (ask/bid/spread)
"""

import logging
import numpy as np
import MetaTrader5 as _mt5
from typing import Any, Optional, cast
from datetime import datetime, timezone, timedelta

mt5: Any = _mt5
log = logging.getLogger(__name__)

# IST offset
IST = timezone(timedelta(hours=5, minutes=30))


class DataFetcher:
    """Fetches OHLCV data and tick info from MetaTrader 5."""

    def __init__(self, symbol: str = "XAUUSDm", own_magics=None):
        self.symbol = symbol
        # Strategy view = these magics only; account view = everything (see src/core/scope.py).
        from src.core import scope
        self.own_magics = frozenset(own_magics) if own_magics is not None else scope.load_own_magics()

    # ------------------------------------------------------------------
    # Rate fetchers
    # ------------------------------------------------------------------

    def get_rates(self, timeframe: int, count: int) -> Optional[np.ndarray]:
        """Fetch the latest `count` candles for the given timeframe."""
        rates = mt5.copy_rates_from_pos(self.symbol, timeframe, 0, count)
        if rates is None or len(rates) < count:
            log.debug(f"get_rates({timeframe}, {count}): insufficient data")
            return None
        return cast(np.ndarray, rates)

    def get_m5_rates(self, count: int = 100) -> Optional[np.ndarray]:
        """Fetch M5 candles (used for volume confirmation)."""
        return self.get_rates(mt5.TIMEFRAME_M5, count)

    def get_m15_rates(self, count: int = 100) -> Optional[np.ndarray]:
        """Fetch M15 candles (primary strategy timeframe)."""
        return self.get_rates(mt5.TIMEFRAME_M15, count)

    def get_d1_rates(self, count: int = 20) -> Optional[np.ndarray]:
        """Fetch D1 candles (used for daily ATR drawdown cap)."""
        return self.get_rates(mt5.TIMEFRAME_D1, count)

    def get_rates_range(
        self, timeframe: int, start: datetime, end: datetime
    ) -> Optional[np.ndarray]:
        """Fetch candles between two UTC datetimes."""
        rates = mt5.copy_rates_range(self.symbol, timeframe, start, end)
        if rates is None or len(rates) == 0:
            return None
        return cast(np.ndarray, rates)

    # ------------------------------------------------------------------
    # Tick / price
    # ------------------------------------------------------------------

    def get_tick(self):
        """Return the latest tick (ask, bid, etc.)."""
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            log.warning(f"symbol_info_tick({self.symbol}) returned None")
        return tick

    def get_ask(self) -> Optional[float]:
        tick = self.get_tick()
        return tick.ask if tick else None

    def get_bid(self) -> Optional[float]:
        tick = self.get_tick()
        return tick.bid if tick else None

    def get_spread(self) -> Optional[int]:
        """Return the current spread in points."""
        info = mt5.symbol_info(self.symbol)
        return info.spread if info else None

    # ------------------------------------------------------------------
    # Positions & History
    # ------------------------------------------------------------------

    def get_positions(self) -> list:
        """ACCOUNT view of the symbol: every system's open positions on this symbol (any magic)."""
        positions = mt5.positions_get(symbol=self.symbol)
        return list(positions) if positions else []

    def get_own_positions(self) -> list:
        """STRATEGY view: only Ultra Core's positions (own magic allowlist) on this symbol."""
        return [p for p in self.get_positions() if p.magic in self.own_magics]

    def get_foreign_positions(self) -> list:
        """Positions on this symbol opened by any other system sharing the account."""
        return [p for p in self.get_positions() if p.magic not in self.own_magics]

    def get_account_floating_pl(self) -> float:
        """ACCOUNT view: floating P/L (profit + swap) of ALL open positions, all symbols, all magics."""
        positions = mt5.positions_get()
        return float(sum(p.profit + getattr(p, "swap", 0.0) for p in positions)) if positions else 0.0

    def get_todays_closed_pl(self, scope: str = "account") -> float:
        """Sum the P/L of all deals closed today (IST midnight to now).

        Feeds RiskManager.check_daily_drawdown() -- the 6% breaker -- so this
        must match the definition of "realised P/L" used everywhere else in
        the codebase (main_loop._record_closed_trades / _check_vi3_tripwire),
        which include swap and commission. This previously summed only
        deal.profit, letting the breaker under-count today's loss by any
        commission/swap on today's closed deals (2026-09-25 audit).
        """
        now_ist = datetime.now(IST)
        midnight_ist = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
        midnight_utc = midnight_ist.astimezone(timezone.utc)

        deals = mt5.history_deals_get(midnight_utc, datetime.now(timezone.utc))
        if deals is None:
            return 0.0

        # scope="account" (default, used by the daily-loss gate): every exit deal on the account, any symbol/magic.
        # scope="strategy": only this symbol and Ultra Core's own magics (per-strategy attribution).
        total_pl = 0.0
        for deal in deals:
            # entry=1 means closing a position (exit deal)
            if deal.entry != 1:
                continue
            if scope == "strategy" and not (deal.symbol == self.symbol and deal.magic in self.own_magics):
                continue
            total_pl += deal.profit + deal.swap + deal.commission
        return total_pl
