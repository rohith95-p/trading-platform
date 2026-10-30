"""
RiskManager -- THE INTELLIGENT HEART.

Zero hardcoded limits. Every single threshold scales with ATR(14).
  - Dynamic session multiplier (IST-based: 1.5x London/NY, 2.0x Asia)
  - Daily drawdown cap as a fraction of balance, including floating P/L
  - ATR-based SL/TP/trailing/consolidation
  - Pyramiding gate (add to winners at 0.5x ATR profit)
"""

import logging
import os
import numpy as np
import MetaTrader5 as _mt5
from typing import Any, Optional, Dict
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

mt5: Any = _mt5
log = logging.getLogger(__name__)

# IST offset
IST = timezone(timedelta(hours=5, minutes=30))

# ---------------------------------------------------------------------------
# ATR multipliers (never hardcoded dollar values)
# ---------------------------------------------------------------------------
TP_ATR_MULTIPLIER = 3.0         # TP = 3.0x ATR (always 1:2 R:R)
TRAIL_ACTIVATION_ATR = 0.7      # Trail activates at 0.7x ATR profit
TRAIL_DISTANCE_ATR = 0.3        # Trail distance = 0.3x ATR behind price
CONSOLIDATION_SHRINK_PCT = 0.30 # Close if ATR shrinks >30% over 3 candles
PYRAMID_THRESHOLD_ATR = 0.5     # Add to winner at 0.5x ATR profit

# ---------------------------------------------------------------------------
# Account-level risk
# ---------------------------------------------------------------------------
# CRIT-4: the daily loss limit used to be `1.5 * D1_ATR`, comparing account
# currency (P/L in USD) against a price quantity (USD per ounce). The two are
# dimensionally unrelated. With gold's daily ATR near $50 it evaluated to a flat
# -$75 regardless of account size: ~70% of a $105 account, 0.75% of a $10,000
# one. It is now a fraction of balance, which is what it was always meant to be.
DAILY_LOSS_LIMIT_PCT = 0.06     # Halt for the day after -6% of balance

# RISK PER TRADE. Backtesting on 17 months of broker data shows this is the
# single largest threat to the account: at 0.15 the minimum tradeable position
# on XAUUSDm already risks 15-20% of a $105 balance, and three losses in a row
# is roughly -45%. Lowered to 0.02 (2% per trade) per audit P0-5.
DEFAULT_RISK_PCT = 0.02

MAX_SPREAD_POINTS = 350         # ~$0.35 on XAUUSDm (digits=3, point=0.001)

# Canonical concurrent-position limit defined in ExecutionHandler (2 for small-account safety)
from src.core.execution_handler import MAX_CONCURRENT_POSITIONS

# Session definitions (IST hours)
# London Open (GOLDEN):   11:30 - 15:30 IST  -> mult 1.5
# NY Morning (GOOD):      17:30 - 21:30 IST  -> mult 1.5
# London-NY Overlap:      15:30 - 19:30 IST  -> mult 1.5
# Asia / Overnight:       21:30 - 11:30 IST  -> mult 2.0


@dataclass
class StopLevels:
    """Calculated stop-loss and take-profit levels."""
    sl: float
    tp: float
    sl_distance: float
    tp_distance: float
    trail_activation: float
    trail_distance: float
    atr: float
    session_multiplier: float


class RiskManager:
    """Fully dynamic, ATR-driven risk engine. Zero hardcoded dollar limits."""

    def __init__(self, symbol: str = "XAUUSDm"):
        self.symbol = symbol
        self._strict_short_stops = False
        self._load_macro_rules()

    # ------------------------------------------------------------------
    # Macro gating (reads DAILY_MARKET_ANALYSIS.md)
    # ------------------------------------------------------------------
    #
    # 2026-09-25 audit finding, addressed here: this used to match two loose
    # lowercased prose substrings anywhere in the file ("bullish macro
    # momentum" + "shorts must have strict, tight stops"), with no negation
    # or grammar handling -- a sentence discussing or rejecting that scenario
    # would trip it identically to an actual recommendation. It was also
    # loaded once at process start, so a same-day edit to a file literally
    # named "DAILY" market analysis had no effect until a restart, and the
    # resulting override was invisible to validation_ledger's config
    # fingerprint (system_config.py does not read this file) and to the
    # trade log (main_loop logs the strategy's own sl/tp multipliers, not
    # what calculate_atr_stops actually returned after this override fired).
    #
    # Fixed to require a single unambiguous marker line rather than prose
    # matching, and re-read on every call instead of once at import time, so
    # at minimum the trigger can't be accidentally tripped by discussion
    # text and an edit takes effect on the very next stop calculation.
    # Still not part of the fingerprinted config or the trade log -- that
    # requires threading the resulting flag through SystemConfig and
    # StopLevels, left as a follow-up rather than done silently here.
    MACRO_OVERRIDE_MARKER = "RISK_OVERRIDE: strict_short_stops=true"

    def _load_macro_rules(self):
        plan_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "docs", "plans", "DAILY_MARKET_ANALYSIS.md"
        )
        try:
            with open(plan_path, "r", encoding="utf-8") as f:
                content = f.read()
            triggered = self.MACRO_OVERRIDE_MARKER in content
            if triggered != self._strict_short_stops:
                status_str = "ENABLED" if triggered else "DISABLED"
                log.warning(
                    "⚠️  MACRO OVERRIDE: strict SHORT stops %s.",
                    status_str,
                )
                try:
                    from src.core import trade_log
                    trade_log.write("macro_override", strict_short_stops=triggered)
                except Exception:
                    pass
                # Phase 2.4: make the change visible through the alert channel
                # so the operator knows the override is active or has been cleared.
                try:
                    from src.core import alerts as _alerts
                    _alerts.send(
                        f"Macro override: strict SHORT stops {status_str}. "
                        f"Triggered by marker in DAILY_MARKET_ANALYSIS.md.",
                        severity=_alerts.INFO,
                        context={"source": "risk_manager._load_macro_rules"},
                    )
                except Exception:
                    pass  # Alert failure must never crash the risk manager
            self._strict_short_stops = triggered
        except FileNotFoundError:
            pass  # optional file; absent = no override (was a WARNING every scan)
        except Exception as e:
            log.warning(f"Could not parse macro analysis: {e}")


    def refresh_macro_rules(self):
        """Re-read the macro override marker. Call at the start of each scan."""
        self._load_macro_rules()

    # ------------------------------------------------------------------
    # ATR calculation
    # ------------------------------------------------------------------

    @staticmethod
    def calc_atr(rates: np.ndarray, period: int = 14) -> np.ndarray:
        """Compute ATR from a structured numpy rates array."""
        highs = rates["high"]
        lows = rates["low"]
        closes = rates["close"]
        high_low = highs - lows

        if len(closes) > 1:
            high_close = np.abs(highs[1:] - closes[:-1])
            low_close = np.abs(lows[1:] - closes[:-1])
            tr = np.maximum(high_low[1:], np.maximum(high_close, low_close))
            tr = np.insert(tr, 0, high_low[0])
        else:
            tr = high_low

        atr = np.full_like(tr, np.nan, dtype=float)
        if len(tr) >= period:
            atr[period - 1] = np.mean(tr[:period])
            for i in range(period, len(tr)):
                atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
        return atr

    @staticmethod
    def get_latest_atr(rates: np.ndarray, period: int = 14) -> Optional[float]:
        """Get the most recent valid ATR value."""
        atr = RiskManager.calc_atr(rates, period)
        valid = atr[~np.isnan(atr)]
        return float(valid[-1]) if len(valid) > 0 else None

    # ------------------------------------------------------------------
    # A. Session multiplier (IST-based)
    # ------------------------------------------------------------------

    @staticmethod
    def get_session_multiplier(ist_time: Optional[datetime] = None) -> float:
        """Return the ATR stop multiplier based on IST session.

        Returns 1.5 for London Open / NY / Overlap (11:30 - 21:30 IST).
        Returns 2.0 for Asia / Overnight (21:30 - 11:30 IST).
        """
        if ist_time is None:
            ist_time = datetime.now(IST)

        hour = ist_time.hour
        minute = ist_time.minute
        time_val = hour + minute / 60.0

        # 11:30 IST (11.5) to 21:30 IST (21.5) = London/NY sessions
        if 11.5 <= time_val < 21.5:
            return 1.5
        # Otherwise = Asia / Overnight
        return 2.0

    @staticmethod
    def get_session_name(ist_time: Optional[datetime] = None) -> str:
        """Return a human-readable session name."""
        if ist_time is None:
            ist_time = datetime.now(IST)
        hour = ist_time.hour
        minute = ist_time.minute
        tv = hour + minute / 60.0

        if 11.5 <= tv < 15.5:
            return "LONDON_OPEN"
        elif 17.5 <= tv < 21.5:
            return "NY_MORNING"
        elif 15.5 <= tv < 19.5:
            return "LONDON_NY_OVERLAP"
        else:
            return "ASIA_OVERNIGHT"

    @staticmethod
    def is_london_open(ist_time: Optional[datetime] = None) -> bool:
        """Check if we are in the London Open golden window (11:30-15:30 IST)."""
        if ist_time is None:
            ist_time = datetime.now(IST)
        tv = ist_time.hour + ist_time.minute / 60.0
        return 11.5 <= tv < 15.5

    # ------------------------------------------------------------------
    # B. Calculate ATR stops (session-aware)
    # ------------------------------------------------------------------

    def calculate_atr_stops(
        self,
        price: float,
        is_buy: bool,
        m15_rates: np.ndarray,
        multiplier: Optional[float] = None,
        tp_multiplier: Optional[float] = None,
    ) -> Optional[StopLevels]:
        """Calculate dynamic ATR-based SL, TP, trailing params.

        Returns a StopLevels dataclass with all calculated values.
        The multiplier is auto-detected from the current IST session if not provided.

        tp_multiplier: per-call override for the take-profit distance, same
        idea as `multiplier` for the stop. None (default) keeps the module
        constant `TP_ATR_MULTIPLIER` -- existing callers are unaffected.
        Added for portfolio strategies whose validated config uses a
        different TP than the shared default (rohith phase 3, 2026-09-01).
        """
        curr_atr = self.get_latest_atr(m15_rates)
        if curr_atr is None or curr_atr == 0:
            log.warning("ATR is None or 0, cannot calculate stops.")
            return None

        if multiplier is None:
            multiplier = self.get_session_multiplier()

        sl_dist = multiplier * curr_atr
        tp_dist = (tp_multiplier if tp_multiplier is not None else TP_ATR_MULTIPLIER) * curr_atr
        trail_activation = TRAIL_ACTIVATION_ATR * curr_atr
        trail_distance = TRAIL_DISTANCE_ATR * curr_atr

        # Tighten SHORT stops under macro gating
        if not is_buy and self._strict_short_stops:
            sl_dist = 1.0 * curr_atr
            tp_dist = 2.0 * curr_atr

        if is_buy:
            sl = price - sl_dist
            tp = price + tp_dist
        else:
            sl = price + sl_dist
            tp = price - tp_dist

        return StopLevels(
            sl=round(sl, 3),
            tp=round(tp, 3),
            sl_distance=round(sl_dist, 3),
            tp_distance=round(tp_dist, 3),
            trail_activation=round(trail_activation, 3),
            trail_distance=round(trail_distance, 3),
            atr=round(curr_atr, 3),
            session_multiplier=multiplier,
        )

    # ------------------------------------------------------------------
    # Position Sizing
    # ------------------------------------------------------------------

    def calculate_dynamic_lot_size(
        self, entry_price: float, sl_price: float, risk_pct: float = DEFAULT_RISK_PCT
    ) -> float:
        """Calculate the exact lot size based on account balance and SL distance.
        
        Args:
            entry_price: The expected entry price.
            sl_price: The calculated stop-loss price.
            risk_pct: The percentage of the account balance to risk (default 2%).
            
        Returns:
            The normalized lot size (clamped by broker limits).
        """
        account = mt5.account_info()
        balance = account.balance if account is not None else 100.0

        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info is None:
            return 0.01

        vol_min = float(symbol_info.volume_min)
        vol_max = float(symbol_info.volume_max)
        vol_step = float(symbol_info.volume_step)
        tick_size = float(symbol_info.trade_tick_size)
        tick_value = float(symbol_info.trade_tick_value)

        if tick_size == 0.0 or tick_value == 0.0:
            return vol_min

        risk_money = balance * risk_pct
        sl_distance = abs(entry_price - sl_price)
        ticks_at_risk = sl_distance / tick_size
        money_per_lot = ticks_at_risk * tick_value

        if money_per_lot <= 0:
            return vol_min

        raw_lots = risk_money / money_per_lot
        lots = round(raw_lots / vol_step) * vol_step
        
        # Clamp to broker limits
        final_lots = max(vol_min, min(lots, vol_max))

        if final_lots == vol_min and raw_lots < vol_min:
            log.warning(
                f"Lot size {raw_lots:.4f} is below broker min {vol_min}. "
                f"Risking more than {risk_pct*100:.1f}% of balance."
            )

        return round(final_lots, 2)

    # ------------------------------------------------------------------
    # C. Dynamic daily drawdown cap
    # ------------------------------------------------------------------

    def check_daily_drawdown(
        self,
        d1_rates: Optional[np.ndarray] = None,
        todays_pl: float = 0.0,
        floating_pl: float = 0.0,
        balance: Optional[float] = None,
    ) -> bool:
        """Check whether today's loss has breached the daily limit.

        Limit is DAILY_LOSS_LIMIT_PCT of account balance, and it counts open
        positions. The previous version compared account currency against a
        price-unit ATR (CRIT-4), ignored unrealised loss entirely, and returned
        True when the D1 fetch failed -- so it could sit at -40% floating and
        keep opening trades.

        Args:
            d1_rates: Unused; retained so existing call sites keep working.
            todays_pl: Realised P/L since midnight IST.
            floating_pl: Unrealised P/L on open positions.
            balance: Account balance; read from the terminal when omitted.

        Returns:
            True if trading may continue, False to shut down for the day.
        """
        if balance is None:
            account = mt5.account_info()
            if account is None:
                # Fail CLOSED. An unknown balance is not a licence to trade.
                log.error("account_info() unavailable -- halting trading for safety.")
                return False
            balance = float(account.balance)

        if balance <= 0:
            log.error(f"Balance is ${balance:.2f}. Halting.")
            return False

        total_pl = todays_pl + floating_pl
        daily_loss_limit = DAILY_LOSS_LIMIT_PCT * balance

        if total_pl < 0 and abs(total_pl) >= daily_loss_limit:
            log.warning(
                f"DAILY DRAWDOWN HIT: today's P/L ${total_pl:.2f} "
                f"(realised ${todays_pl:.2f} + floating ${floating_pl:.2f}) "
                f">= limit -${daily_loss_limit:.2f} "
                f"({DAILY_LOSS_LIMIT_PCT:.0%} of ${balance:.2f}). "
                f"SHUTTING DOWN until midnight IST."
            )
            return False

        log.debug(
            f"Drawdown check: total P/L=${total_pl:.2f}, "
            f"limit=-${daily_loss_limit:.2f}, "
            f"remaining=${daily_loss_limit - abs(min(total_pl, 0)):.2f}"
        )
        return True

    # ------------------------------------------------------------------
    # D. Pyramiding condition
    # ------------------------------------------------------------------

    def check_pyramid_condition(
        self, entry_price: float, current_price: float, atr: float, is_buy: bool
    ) -> bool:
        """Check if price has moved enough in profit to add a pyramid position.

        Condition: price moved >= 0.5 * ATR in the trade's direction.
        """
        threshold = PYRAMID_THRESHOLD_ATR * atr
        if is_buy:
            return current_price >= entry_price + threshold
        else:
            return current_price <= entry_price - threshold

    # ------------------------------------------------------------------
    # Trailing stop
    # ------------------------------------------------------------------

    def calculate_trailing_stop(
        self, position, curr_atr: float
    ) -> Optional[float]:
        """ATR-based step trailing stop. Moves in chunks to survive whipsaws."""
        activation = TRAIL_ACTIVATION_ATR * curr_atr
        trail = TRAIL_DISTANCE_ATR * curr_atr
        chunk_size = 0.5 * curr_atr  # Step chunk size

        if position.type == 0:  # ORDER_TYPE_BUY (int literal: works with MT5 stub in backtest)
            profit_dist = position.price_current - position.price_open
            if profit_dist > activation:
                ideal_sl = position.price_current - trail
                if position.sl == 0.0 or ideal_sl >= position.sl + chunk_size:
                    return round(ideal_sl, 3)
        elif position.type == 1:  # ORDER_TYPE_SELL
            profit_dist = position.price_open - position.price_current
            if profit_dist > activation:
                ideal_sl = position.price_current + trail
                if position.sl == 0.0 or ideal_sl <= position.sl - chunk_size:
                    return round(ideal_sl, 3)
        return None

    # ------------------------------------------------------------------
    # Consolidation exit
    # ------------------------------------------------------------------

    def should_exit_consolidation(self, rates: np.ndarray) -> bool:
        """Return True if ATR has shrunk >30% over the last 3 candles.

        MED-13: across 17 months and 1,688 backtested trades this never returned
        True, so it is presently dead code. It is also position-independent --
        if it ever did fire, main_loop would close every open position at once.
        Left in place rather than silently removed, but it should not be counted
        as an active risk control.
        """
        atr = self.calc_atr(rates)
        valid = atr[~np.isnan(atr)]
        if len(valid) < 4:
            return False
        atr_now = valid[-1]
        atr_3_ago = valid[-4]
        if atr_3_ago == 0:
            return False
        shrink = (atr_3_ago - atr_now) / atr_3_ago
        return bool(shrink > CONSOLIDATION_SHRINK_PCT)

    # ------------------------------------------------------------------
    # Spread filter
    # ------------------------------------------------------------------

    def is_spread_ok(self, max_spread: int = MAX_SPREAD_POINTS) -> bool:
        """Return True if the current spread is within acceptable limits."""
        info = mt5.symbol_info(self.symbol)
        if info is None:
            log.warning("symbol_info returned None for spread check")
            return False
        if info.spread > max_spread:
            log.info(f"Spread filter: {info.spread} > {max_spread}. Skipping.")
            return False
        return True
