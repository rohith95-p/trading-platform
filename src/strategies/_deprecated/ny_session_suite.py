import numpy as np
from typing import Optional

from src.strategies.base_strategy import BaseStrategy, Signal, mt5
from src.research.market_study import atr as _atr, ema as _ema

class NYLondonSweepReversal(BaseStrategy):
    """
    Setup 3: NY London H/L Sweep
    Sweeps London session high/low, rejects back inside, displaces.
    """
    execute_immediately = True
    edge_trigger = False
    _min_bars = 250

    def __init__(
        self,
        penetration_atr: float = 0.15,
        displacement_body_atr: float = 0.3,
        sl_atr_mult: float = 1.3,
        tp_atr_mult: float = 2.5,
        session: tuple = (18.5, 20.5),
        magic: int = 91003,
        name: str = "NY_SWEEP_REV",
    ):
        self.penetration_atr = penetration_atr
        self.displacement_body_atr = displacement_body_atr
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.session = session
        self.magic = magic
        self.name = name

    def _in_london_killzone(self, ts: int) -> bool:
        hr = (int(ts) + 19800) % 86400 / 3600.0
        return 12.5 <= hr < 15.5

    def _in_ny_session(self, ts: int) -> bool:
        hr = (int(ts) + 19800) % 86400 / 3600.0
        a, b = self.session
        return a <= hr < b

    def evaluate(self, m15_rates: np.ndarray, m5_rates: Optional[np.ndarray] = None) -> Optional[Signal]:
        if m15_rates is None or len(m15_rates) < self._min_bars:
            return None

        t = m15_rates["time"].astype(np.int64)
        if not self._in_ny_session(t[-2]):
            return None

        h = m15_rates["high"].astype(float)
        l = m15_rates["low"].astype(float)
        c = m15_rates["close"].astype(float)
        o = m15_rates["open"].astype(float)
        
        atr_14 = _atr(m15_rates, 14)
        a = atr_14[-2]
        if not np.isfinite(a) or a <= 0:
            return None

        # 1. London Range Extraction
        london_high = -np.inf
        london_low = np.inf
        found_london = False
        
        in_london = False
        for i in range(len(m15_rates) - 3, -1, -1):
            if self._in_london_killzone(t[i]):
                in_london = True
                found_london = True
                london_high = max(london_high, h[i])
                london_low = min(london_low, l[i])
            elif in_london:
                break

        if not found_london:
            return None

        # 3. NY Sweep Detection (bar -2)
        bull_sweep = l[-2] < (london_low - self.penetration_atr * a)
        bear_sweep = h[-2] > (london_high + self.penetration_atr * a)

        if not (bull_sweep or bear_sweep):
            return None

        # 4. MSS / Rejection Confirmation + Displacement Strength
        body = abs(c[-2] - o[-2])
        has_displacement = body >= self.displacement_body_atr * a

        if bull_sweep and c[-2] > london_low and c[-2] > o[-2] and has_displacement:
            return Signal(direction=mt5.ORDER_TYPE_BUY, strategy_name=self.name, magic=self.magic, is_buy=True)
            
        if bear_sweep and c[-2] < london_high and c[-2] < o[-2] and has_displacement:
            return Signal(direction=mt5.ORDER_TYPE_SELL, strategy_name=self.name, magic=self.magic, is_buy=False)

        return None


class NYContinuationBreakout(BaseStrategy):
    """
    Setup 4: NY Continuation Breakout
    London trends strongly, NY retraces slightly (30-70%) and forms an FVG, continues.
    """
    execute_immediately = True
    edge_trigger = False
    _min_bars = 250

    def __init__(
        self,
        min_london_move_atr: float = 0.8,
        sl_atr_mult: float = 1.0,
        tp_atr_mult: float = 2.5,
        session: tuple = (18.5, 21.5),
        magic: int = 91004,
        name: str = "NY_CONT",
    ):
        self.min_london_move_atr = min_london_move_atr
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.session = session
        self.magic = magic
        self.name = name

    def _in_london_killzone(self, ts: int) -> bool:
        hr = (int(ts) + 19800) % 86400 / 3600.0
        return 12.5 <= hr < 15.5

    def _in_ny_session(self, ts: int) -> bool:
        hr = (int(ts) + 19800) % 86400 / 3600.0
        a, b = self.session
        return a <= hr < b

    def evaluate(self, m15_rates: np.ndarray, m5_rates: Optional[np.ndarray] = None) -> Optional[Signal]:
        if m15_rates is None or len(m15_rates) < self._min_bars:
            return None

        t = m15_rates["time"].astype(np.int64)
        if not self._in_ny_session(t[-2]):
            return None

        h = m15_rates["high"].astype(float)
        l = m15_rates["low"].astype(float)
        c = m15_rates["close"].astype(float)
        o = m15_rates["open"].astype(float)

        atr_14 = _atr(m15_rates, 14)
        a = atr_14[-2]
        if not np.isfinite(a) or a <= 0:
            return None

        # 1. London Trend Direction
        london_high = -np.inf
        london_low = np.inf
        london_close = None
        london_open = None
        found_london = False
        
        in_london = False
        for i in range(len(m15_rates) - 3, -1, -1):
            if self._in_london_killzone(t[i]):
                if not in_london:
                    # First bar found going backwards = most recent London bar = session close
                    london_close = c[i]
                in_london = True
                found_london = True
                london_high = max(london_high, h[i])
                london_low = min(london_low, l[i])
                london_open = o[i]  # Overwrites to earliest London bar's open
            elif in_london:
                break

        if not found_london or london_open is None or london_close is None:
            return None

        london_range = london_high - london_low
        if london_range <= 0:
             return None

        london_bull = (london_close > london_open) and ((london_close - london_open) >= self.min_london_move_atr * a)
        london_bear = (london_close < london_open) and ((london_open - london_close) >= self.min_london_move_atr * a)

        if not (london_bull or london_bear):
            return None

        # 3. Pullback Check (bar -2)
        bull_pullback = False
        bear_pullback = False
        
        if london_bull:
            if c[-2] > london_low and c[-2] < (london_high - 0.30 * london_range) and c[-2] >= (london_high - 0.70 * london_range):
                bull_pullback = True
        elif london_bear:
            if c[-2] < london_high and c[-2] > (london_low + 0.30 * london_range) and c[-2] <= (london_low + 0.70 * london_range):
                bear_pullback = True

        if not (bull_pullback or bear_pullback):
            return None

        # 4. FVG Entry (within the pullback zone)
        # Check if the current bar (-2) completed an FVG in the direction of the trend
        # We need an FVG forming right now or recently mitigated during this pullback.
        # Simplify: Check if an FVG exists in the last 4 bars aligning with trend
        has_fvg = False
        
        # We check if an FVG formed ending at bar -2, -3, or -4
        for i in range(len(m15_rates) - 4, len(m15_rates) - 1):
             if london_bull and h[i-2] < l[i]:
                 has_fvg = True
                 break
             if london_bear and l[i-2] > h[i]:
                 has_fvg = True
                 break
                 
        if not has_fvg:
            return None

        if london_bull:
            return Signal(direction=mt5.ORDER_TYPE_BUY, strategy_name=self.name, magic=self.magic, is_buy=True)
        if london_bear:
            return Signal(direction=mt5.ORDER_TYPE_SELL, strategy_name=self.name, magic=self.magic, is_buy=False)
            
        return None


class NYPMReversal(BaseStrategy):
    """
    Setup 5: NY PM Micro-Reversal
    Late day profit-taking sweeps HOD/LOD, reverts to 50% of today's range.
    """
    execute_immediately = True
    edge_trigger = False
    _min_bars = 250

    def __init__(
        self,
        buffer_atr: float = 0.2,
        sl_atr_mult: float = 0.8,
        tp_atr_mult: float = 1.5,
        session: tuple = (20.0, 21.5),
        magic: int = 91005,
        name: str = "NY_PM_REV",
    ):
        self.buffer_atr = buffer_atr
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.session = session
        self.magic = magic
        self.name = name

    def _in_ny_pm_session(self, ts: int) -> bool:
        hr = (int(ts) + 19800) % 86400 / 3600.0
        a, b = self.session
        return a <= hr < b

    def _ist_date(self, ts: int) -> str:
        # Convert timestamp to IST date string for day grouping
        import datetime
        ist_dt = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)
        return ist_dt.strftime("%Y-%m-%d")

    def evaluate(self, m15_rates: np.ndarray, m5_rates: Optional[np.ndarray] = None) -> Optional[Signal]:
        if m15_rates is None or len(m15_rates) < self._min_bars:
            return None

        t = m15_rates["time"].astype(np.int64)
        if not self._in_ny_pm_session(t[-2]):
            return None

        h = m15_rates["high"].astype(float)
        l = m15_rates["low"].astype(float)
        c = m15_rates["close"].astype(float)
        
        atr_14 = _atr(m15_rates, 14)
        a = atr_14[-2]
        if not np.isfinite(a) or a <= 0:
            return None

        # 1. Day Range (HOD / LOD)
        current_date = self._ist_date(t[-2])
        hod = -np.inf
        lod = np.inf
        
        # Scan back to find HOD/LOD for the *current IST day* (before bar -2)
        for i in range(len(m15_rates) - 3, -1, -1):
            if self._ist_date(t[i]) == current_date:
                hod = max(hod, h[i])
                lod = min(lod, l[i])
            else:
                break
                
        if hod == -np.inf or lod == np.inf:
            return None

        # 3. Sweep + Rejection (bar -2)
        # HOD sweep short: high[-2] > hod (new HOD) AND close[-2] < hod - buffer_atr * ATR
        # LOD sweep long:  low[-2] < lod  (new LOD) AND close[-2] > lod + buffer_atr * ATR
        
        short_sweep = h[-2] > hod and c[-2] < (hod - self.buffer_atr * a)
        long_sweep = l[-2] < lod and c[-2] > (lod + self.buffer_atr * a)

        if short_sweep:
            return Signal(direction=mt5.ORDER_TYPE_SELL, strategy_name=self.name, magic=self.magic, is_buy=False)
            
        if long_sweep:
            return Signal(direction=mt5.ORDER_TYPE_BUY, strategy_name=self.name, magic=self.magic, is_buy=True)

        return None
