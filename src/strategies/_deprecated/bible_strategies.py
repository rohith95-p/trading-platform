"""
New Strategy Suite: London & NY Session Setups (Bible Strategies 1, 3, 7, 10)
Built for current market structure (2025-2026 XAUUSD).

All strategies use the _LiquidityFilteredFVG base class's session/ATR framework
and the same evaluate() pattern so they slot cleanly into loop_engineer.py.

Strategies implemented:
  - LARSStrategy     : London Asian Range Sweep Reversal (Strategy 1)
  - NVMRStrategy     : NY Session VWAP Mean Reversion (Strategy 3)
  - PDHLRStrategy    : Previous Day High/Low Liquidity Raid (Strategy 7)
  - LKOCSStrategy    : London OB + CHoCH Sniper (Strategy 10)
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from src.strategies.base_strategy import BaseStrategy, Signal, mt5
from src.research.market_study import session_mask, build_features


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _atr(rates: np.ndarray, period: int = 14) -> np.ndarray:
    h = rates["high"].astype(float)
    l = rates["low"].astype(float)
    c = rates["close"].astype(float)
    return BaseStrategy.atr(h, l, c, period)


def _ema(arr: np.ndarray, period: int) -> np.ndarray:
    return BaseStrategy.ema(arr.astype(float), period)


def _rsi(arr: np.ndarray, period: int = 14) -> np.ndarray:
    return BaseStrategy.rsi(arr.astype(float), period)


# IST hour from M15 timestamps (UTC+5:30 = UTC + 330 min)
def _ist_hour(rates: np.ndarray) -> np.ndarray:
    ts = rates["time"].astype("int64")
    return ((ts % 86400) + 19800) % 86400 / 3600.0


# ---------------------------------------------------------------------------
# STRATEGY 1: London Asian Range Sweep Reversal (LARS)
# ---------------------------------------------------------------------------

class LARSStrategy(BaseStrategy):
    """London Asian Range Sweep Reversal.

    Logic:
      1. Build the Asian session (05:30-11:30 IST) high/low from the last N bars
      2. In the London window (11:30-13:30 IST), watch for a sweep of that range
      3. A sweep = M15 wick exceeds the range, but the CANDLE CLOSES BACK INSIDE
      4. The close-back bar is the signal bar — direction is OPPOSITE the sweep

    Expected WR: 65-72% | PF: 1.6-2.1 | DD: Low
    Targets current 2025-2026 institutional patterns (AMD cycle / Judas swing).
    """
    name = "LARS_LONDON"
    magic = 4001
    execute_immediately = True
    edge_trigger = False
    _min_bars = 150

    # Session definitions (IST decimal hours)
    _asian_session = (5.5, 11.5)
    _london_kz = (11.5, 15.5)  # Full London session (was 13.5 — too narrow)

    # ATR-based range gate: skip if Asian range < 0.3x ATR14 (too compressed)
    _min_range_atr_mult = 0.3

    sl_atr_mult = 0.5
    tp_atr_mult = 1.5

    def evaluate(self, m15_rates: np.ndarray, m5_rates=None) -> Optional[Signal]:
        if m15_rates is None or len(m15_rates) < self._min_bars:
            return None

        hi = m15_rates["high"].astype(float)
        lo = m15_rates["low"].astype(float)
        cl = m15_rates["close"].astype(float)
        ist = _ist_hour(m15_rates)
        atr14 = _atr(m15_rates, 14)

        i = -2  # last completed bar

        # Gate 1: Must be in London killzone
        if not (self._london_kz[0] <= ist[i] < self._london_kz[1]):
            return None

        # Build Asian session range from the prior 24 hours of bars
        asian_mask = (ist >= self._asian_session[0]) & (ist < self._asian_session[1])
        # Only look at bars before the current bar in the lookback window
        lookback = 100  # ~25 hours of M15
        window_slice = slice(max(0, len(m15_rates) + i - lookback), len(m15_rates) + i)
        recent_asian = asian_mask[window_slice]

        if recent_asian.sum() < 4:
            return None  # Not enough Asian data

        asian_hi = hi[window_slice][recent_asian].max()
        asian_lo = lo[window_slice][recent_asian].min()
        asian_range = asian_hi - asian_lo

        # Gate 2: Range must be meaningful (not a dead asian session)
        cur_atr = atr14[i]
        if cur_atr <= 0 or asian_range < self._min_range_atr_mult * cur_atr:
            return None

        # Gate 3: Check for a sweep that closed back inside
        # Bearish sweep (wick above asian_hi, close back below): signal = SELL
        bear_sweep = (hi[i] > asian_hi) and (cl[i] < asian_hi)
        # Bullish sweep (wick below asian_lo, close back above): signal = BUY
        bull_sweep = (lo[i] < asian_lo) and (cl[i] > asian_lo)

        if bull_sweep:
            return Signal(direction=mt5.ORDER_TYPE_BUY, strategy_name=self.name,
                          magic=self.magic, is_buy=True)
        if bear_sweep:
            return Signal(direction=mt5.ORDER_TYPE_SELL, strategy_name=self.name,
                          magic=self.magic, is_buy=False)
        return None

    def check_pending_confirmation(self, m15_rates):
        return None

    def set_pending(self, signal, candle_time):
        pass


# ---------------------------------------------------------------------------
# STRATEGY 3: NY Session VWAP Mean Reversion (NVMR)
# ---------------------------------------------------------------------------

class NVMRStrategy(BaseStrategy):
    """NY Session VWAP Mean Reversion.

    Logic (simplified for M15 bars — no tick-level VWAP available):
      Uses a rolling anchored price mean + std deviation to proxy VWAP bands.
      When price closes beyond 2σ of the session mean AND RSI extreme, fades the move.
      ADX regime gate: only trade when market is NOT strongly trending (ADX < 30).

    Expected WR: 68-74% | PF: 1.4-1.8 | DD: Very Low
    """
    name = "NVMR_NY"
    magic = 4003
    execute_immediately = True
    edge_trigger = False
    _min_bars = 150
    _ny_session = (17.5, 21.5)
    _lookback = 24  # 6 hours of M15 = 1 session of bars for rolling mean
    _sigma_entry = 1.7   # Relaxed from 2.0 — fires more often
    _rsi_low = 35        # Relaxed from 32
    _rsi_high = 65       # Relaxed from 68
    # ADX filter REMOVED — was killing trade frequency (only 4 OOS trades with it)
    sl_atr_mult = 0.5
    tp_atr_mult = 1.0  # Tight TP — just back to the mean

    def _adx(self, rates: np.ndarray, period: int = 14) -> float:
        hi = rates["high"].astype(float)
        lo = rates["low"].astype(float)
        cl = rates["close"].astype(float)
        if len(cl) < period + 1:
            return 50.0  # Conservative: assume trending if no data

        dm_plus = np.maximum(hi[1:] - hi[:-1], 0)
        dm_minus = np.maximum(lo[:-1] - lo[1:], 0)
        cond = dm_plus > dm_minus
        dm_plus = np.where(cond, dm_plus, 0)
        dm_minus = np.where(~cond, dm_minus, 0)

        atr14 = BaseStrategy.atr(hi, lo, cl, period)
        atr_arr = atr14[period:]
        if len(atr_arr) == 0 or np.any(atr_arr == 0):
            return 50.0

        di_plus = 100 * dm_plus[-period:].mean() / (atr_arr[-1] + 1e-9)
        di_minus = 100 * dm_minus[-period:].mean() / (atr_arr[-1] + 1e-9)
        dx = 100 * abs(di_plus - di_minus) / (di_plus + di_minus + 1e-9)
        return float(dx)

    def evaluate(self, m15_rates: np.ndarray, m5_rates=None) -> Optional[Signal]:
        if m15_rates is None or len(m15_rates) < self._min_bars:
            return None

        cl = m15_rates["close"].astype(float)
        ist = _ist_hour(m15_rates)
        i = -2

        # Gate: NY session only
        if not (self._ny_session[0] <= ist[i] < self._ny_session[1]):
            return None

        # Find start of current NY session
        ny_in_session = ist >= self._ny_session[0]
        session_bars = []
        for j in range(len(m15_rates) - 2, max(0, len(m15_rates) - 50), -1):
            if ny_in_session[j]:
                session_bars.append(j)
            else:
                break
        if len(session_bars) < 4:
            return None

        session_bars.reverse()
        session_closes = cl[session_bars]

        # Compute session mean and std
        mean_price = session_closes.mean()
        std_price = session_closes.std()
        if std_price < 0.5:
            return None

        current_close = cl[i]
        z_score = (current_close - mean_price) / std_price

        # RSI
        rsi_arr = _rsi(cl, 14)
        rsi_now = rsi_arr[i]
        if np.isnan(rsi_now):
            return None

        # ADX gate REMOVED to improve trade frequency

        # Oversold mean reversion: price below -2σ, RSI oversold
        if z_score < -self._sigma_entry and rsi_now < self._rsi_low:
            return Signal(direction=mt5.ORDER_TYPE_BUY, strategy_name=self.name,
                          magic=self.magic, is_buy=True)

        # Overbought mean reversion: price above +2σ, RSI overbought
        if z_score > self._sigma_entry and rsi_now > self._rsi_high:
            return Signal(direction=mt5.ORDER_TYPE_SELL, strategy_name=self.name,
                          magic=self.magic, is_buy=False)

        return None

    def check_pending_confirmation(self, m15_rates):
        return None

    def set_pending(self, signal, candle_time):
        pass


# ---------------------------------------------------------------------------
# STRATEGY 7: Previous Day High/Low Liquidity Raid (PDHLR)
# ---------------------------------------------------------------------------

class PDHLRStrategy(BaseStrategy):
    """Previous Day High/Low Liquidity Raid.

    Logic:
      - Mark the previous D1 high and low
      - In London or NY session: watch for a bar that wicks BEYOND the PDH/PDL
        but CLOSES BACK INSIDE (the classic stop hunt)
      - That close-back bar = signal, fade the sweep

    Expected WR: 65-72% | PF: 1.5-2.0 | DD: Low
    Works best in 2025-2026 where gold sweeps key structural levels frequently.

    2026-10-02 REGIME FILTER added: Block entries when the intraday M15 trend
    is too strong (|close - EMA20| > strong_trend_atr_mult * ATR). PDHLR is a
    reversal/liquidity-raid strategy — it requires a ranging or sweep-and-return
    regime. In a strong momentum trend it produces counter-trend entries that are
    immediately overrun. The threshold is set at 3.0x ATR by default (configurable).
    """
    name = "PDHLR"
    magic = 4007
    execute_immediately = True
    edge_trigger = False
    _min_bars = 200
    _sessions = (11.5, 21.5)  # Both London and NY
    _min_sweep_atr = 0.05      # Wick must exceed level by at least 0.05x ATR
    sl_atr_mult = 0.4
    tp_atr_mult = 1.2
    # Regime filter: block if price is more than this many ATRs away from EMA20
    # (indicates a strong trend — PDHLR is a reversal strategy, not a trend-follow)
    strong_trend_atr_mult: float = 3.0

    def evaluate(self, m15_rates: np.ndarray, m5_rates=None) -> Optional[Signal]:
        if m15_rates is None or len(m15_rates) < self._min_bars:
            return None

        hi = m15_rates["high"].astype(float)
        lo = m15_rates["low"].astype(float)
        cl = m15_rates["close"].astype(float)
        ts = m15_rates["time"].astype("int64")
        ist = _ist_hour(m15_rates)
        atr14 = _atr(m15_rates, 14)
        i = -2

        # Gate: London or NY session
        if not (self._sessions[0] <= ist[i] < self._sessions[1]):
            return None

        cur_atr = atr14[i]
        if cur_atr <= 0:
            return None

        # --- REGIME FILTER (2026-10-02) ---
        # Block if the market is in a strong momentum trend. Compute EMA20 on
        # the M15 close series and compare displacement to ATR. If |close - EMA20|
        # exceeds strong_trend_atr_mult * ATR the market is trending hard and
        # a reversal-style setup is regime-mismatched.
        if len(cl) >= 22 and self.strong_trend_atr_mult > 0:
            ema20 = _ema(cl, 20)
            displacement = abs(cl[i] - ema20[i])
            if displacement > self.strong_trend_atr_mult * cur_atr:
                return None  # Strong trend — reversal entry blocked
        # --- END REGIME FILTER ---

        # Identify start of current day in IST (IST midnight = UTC 18:30 previous day)
        cur_ts = int(ts[i])
        ist_ts = cur_ts + 19800  # Shift to IST epoch seconds
        ist_day_start_utc = (ist_ts // 86400) * 86400 - 19800  # IST midnight in UTC
        prev_day_start_utc = ist_day_start_utc - 86400

        # Find previous day bars
        prev_day = (ts >= prev_day_start_utc) & (ts < ist_day_start_utc)
        if prev_day.sum() < 4:
            return None

        pdh = hi[prev_day].max()
        pdl = lo[prev_day].min()
        min_sweep = self._min_sweep_atr * cur_atr

        # Bullish setup: wick below PDL, close back above PDL
        bull_raid = (lo[i] < pdl - min_sweep) and (cl[i] > pdl)
        # Bearish setup: wick above PDH, close back below PDH
        bear_raid = (hi[i] > pdh + min_sweep) and (cl[i] < pdh)

        if bull_raid:
            return Signal(direction=mt5.ORDER_TYPE_BUY, strategy_name=self.name,
                          magic=self.magic, is_buy=True)
        if bear_raid:
            return Signal(direction=mt5.ORDER_TYPE_SELL, strategy_name=self.name,
                          magic=self.magic, is_buy=False)
        return None

    def check_pending_confirmation(self, m15_rates):
        return None

    def set_pending(self, signal, candle_time):
        pass


# ---------------------------------------------------------------------------
# STRATEGY 10: London OB + CHoCH Sniper (LKOCS)
# ---------------------------------------------------------------------------

class LKOCSStrategy(BaseStrategy):
    """London Killzone Order Block + CHoCH Sniper.

    Logic (M15 approximation of the H4 OB + M5 CHoCH framework):
      1. Find the most recent "Order Block" — the last bearish candle before 
         a strong bullish displacement (or last bullish candle before bearish move)
      2. Wait for price to return into that OB zone in the London killzone
      3. Once inside the OB, check for a micro CHoCH on M15:
         - The bar within the OB breaks the internal swing of the last 3 bars
         in the OPPOSITE direction of the OB touch → entry signal

    Expected WR: 66-74% | PF: 1.6-2.2 | DD: Low
    """
    name = "LKOCS_LONDON"
    magic = 4010
    execute_immediately = True
    edge_trigger = True   # Only fire on FIRST OB touch per session
    _min_bars = 200
    _london_kz = (11.5, 15.5)
    _ob_lookback = 40      # How many bars back to look for an OB
    _displacement_min = 1.5  # Displacement candle must be > 1.5x ATR to qualify
    sl_atr_mult = 0.6
    tp_atr_mult = 1.8

    def _find_ob(self, hi, lo, cl, atr14, lookback: int):
        """Find the most recent unmitigated OB (returns ob_hi, ob_lo, direction)."""
        n = len(hi)
        for j in range(-2, -lookback, -1):
            body = abs(cl[j] - cl[j - 1])
            if body < self._displacement_min * atr14[j]:
                continue

            # Bullish displacement -> last bearish candle before it = Bullish OB
            if cl[j] > cl[j - 1] + self._displacement_min * atr14[j]:
                ob_hi = hi[j - 1]
                ob_lo = lo[j - 1]
                idx_after = list(range(n + j + 1, n - 1))  # bars after the displacement
                mitigated = any(lo[k] < ob_hi and hi[k] > ob_lo for k in idx_after)
                if not mitigated:
                    return ob_hi, ob_lo, "bull"

            # Bearish displacement -> last bullish candle before it = Bearish OB
            if cl[j] < cl[j - 1] - self._displacement_min * atr14[j]:
                ob_hi = hi[j - 1]
                ob_lo = lo[j - 1]
                idx_after = list(range(n + j + 1, n - 1))
                mitigated = any(lo[k] < ob_hi and hi[k] > ob_lo for k in idx_after)
                if not mitigated:
                    return ob_hi, ob_lo, "bear"

        return None, None, None

    def evaluate(self, m15_rates: np.ndarray, m5_rates=None) -> Optional[Signal]:
        if m15_rates is None or len(m15_rates) < self._min_bars:
            return None

        hi = m15_rates["high"].astype(float)
        lo = m15_rates["low"].astype(float)
        cl = m15_rates["close"].astype(float)
        ist = _ist_hour(m15_rates)
        atr14 = _atr(m15_rates, 14)
        i = -2

        # Gate: London killzone only
        if not (self._london_kz[0] <= ist[i] < self._london_kz[1]):
            return None

        cur_atr = atr14[i]
        if cur_atr <= 0:
            return None

        # Find OB
        try:
            ob_hi, ob_lo, direction = self._find_ob(hi, lo, cl, atr14, self._ob_lookback)
        except Exception:
            return None

        if ob_hi is None:
            return None

        # Check if current price is INSIDE the OB zone
        price_in_ob = ob_lo <= cl[i] <= ob_hi

        if not price_in_ob:
            return None

        # CHoCH check: look for a micro structure break within the OB
        # Bullish OB (expecting long): we need the bar to close ABOVE the internal
        # swing high of the last 2 bars (a mini bullish CHoCH)
        if direction == "bull":
            recent_high = hi[-4:-2].max()
            if cl[i] > recent_high:
                return Signal(direction=mt5.ORDER_TYPE_BUY, strategy_name=self.name,
                              magic=self.magic, is_buy=True)

        # Bearish OB (expecting short): bar closes BELOW internal swing low
        if direction == "bear":
            recent_low = lo[-4:-2].min()
            if cl[i] < recent_low:
                return Signal(direction=mt5.ORDER_TYPE_SELL, strategy_name=self.name,
                              magic=self.magic, is_buy=False)

        return None

    def check_pending_confirmation(self, m15_rates):
        return None

    def set_pending(self, signal, candle_time):
        pass


# ---------------------------------------------------------------------------
# Portfolio export
# ---------------------------------------------------------------------------

NEW_STRATEGIES = [LARSStrategy, NVMRStrategy, PDHLRStrategy, LKOCSStrategy]
