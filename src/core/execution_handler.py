"""
ExecutionHandler -- THE GATEKEEPER.

No hardcoded trade limits. Unlimited wins, protected losses.
  - Daily drawdown cap (via RiskManager) is the ONLY hard limit
  - Pyramiding: adds to winners at 0.5x ATR profit (max 3 concurrent, 2 per side)
  - 3x retry logic on order_send failures
  - All timestamps logged in IST

PRODUCTION UPGRADES (2026-09-25):
  - PreTradeVeto: 6-layer risk gate before MT5 (NautilusTrader pattern)
  - SizingLadder: Account-based position sizing (replaces FIXED_LOT_SIZE)
  - Both are wired into send_order() for every trade
"""

import os
import time as _time
import logging
import MetaTrader5 as _mt5
from typing import Any, Optional, List
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

mt5: Any = _mt5
log = logging.getLogger(__name__)

# IST offset
IST = timezone(timedelta(hours=5, minutes=30))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SYMBOL = os.environ.get("ULTRA_SYMBOL", "XAUUSDm")

# These are fallback ceilings only; the live sizing comes from
# risk_rules.SIZING_LADDER via SizingLadder.get_sizing(balance).
MAX_CONCURRENT_POSITIONS = 3
MAX_SAME_DIRECTION_POSITIONS = 3
MAX_TOTAL_VOLUME = 0.06

ORDER_RETRY_COUNT = 3
ORDER_RETRY_DELAY_MS = 500

# DEPRECATED: Replaced by SizingLadder (2026-09-25)
# This value is no longer used. Position sizing now comes from sizing_ladder.get_sizing(balance).
FIXED_LOT_SIZE = 0.02

ORDER_DEVIATION_POINTS = 30


def _ist_now() -> str:
    """Return current IST time as a formatted string."""
    return datetime.now(IST).strftime("%I:%M:%S %p IST")


@dataclass
class TradeRecord:
    """Lightweight record of a trade we opened."""
    ticket: int
    strategy: str
    direction: str
    price: float
    sl: float
    tp: float
    atr: float
    session: str
    timestamp_ist: str
    lots: float = 0.0
    retcode: int = 10009  # TRADE_RETCODE_DONE: a record only exists for filled orders

    @property
    def order(self) -> int:
        """Alias so callers can read this like an MT5 OrderSendResult."""
        return self.ticket


class ExecutionHandler:
    """Manages order execution with dynamic gating. No hardcoded trade caps."""

    def __init__(self, symbol: str = SYMBOL, risk_manager=None):
        """
        Initialize execution handler.
        
        Args:
            symbol: Trading symbol
            risk_manager: RiskManager instance (needed for PreTradeVeto)
        """
        self.symbol = symbol
        self.risk_manager = risk_manager
        
        # Import PreTradeVeto and SizingLadder
        from src.core.pre_trade_veto import get_veto
        from src.core.sizing_ladder import SizingLadder
        
        self.veto = get_veto()
        self.sizing_ladder = SizingLadder
        from src.core import scope
        self.own_magics = scope.load_own_magics()

    # ------------------------------------------------------------------
    # Position queries
    # ------------------------------------------------------------------

    def get_open_positions(self) -> list:
        """ACCOUNT view of the symbol (every system's positions): used for exposure/margin checks."""
        positions = mt5.positions_get(symbol=self.symbol)
        return list(positions) if positions else []

    def get_own_positions(self) -> list:
        """STRATEGY view: only Ultra Core's own magic numbers: used for position counts and attribution."""
        return [p for p in self.get_open_positions() if p.magic in self.own_magics]

    def count_open_positions(self) -> int:
        return len(self.get_own_positions())

    def get_same_direction_count(self, is_buy: bool) -> int:
        positions = self.get_own_positions()
        target_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
        return sum(1 for p in positions if p.type == target_type)

    def can_open_new_position(self) -> bool:
        """Max concurrent positions (leverage guard)."""
        return self.count_open_positions() < MAX_CONCURRENT_POSITIONS

    # ------------------------------------------------------------------
    # Order execution with retry
    # ------------------------------------------------------------------

    def send_order(
        self,
        signal: int,
        price: float,
        sl: float,
        tp: float,
        strategy_name: str,
        magic: int,
        lot_size: float,
        atr: float = 0.0,
        session: str = "",
        is_pyramid: bool = False,
    ) -> Optional[TradeRecord]:
        """Execute a market order on MT5 with 3x retry logic.

        PRODUCTION UPGRADES (2026-09-25):
          1. SizingLadder: lot_size parameter is IGNORED; size comes from balance
          2. PreTradeVeto: 6-layer risk gate vetoes every order before MT5
          
        Gates applied here:
          - Position floor ($50 minimum balance)
          - Circuit breakers (consecutive losses, weekly/monthly caps)
          - Concurrent position limits (from sizing ladder)
          - Exposure caps (from sizing ladder)
          - Macro override visibility (strict short stops)
          - News blackout (if enabled)
        """
        # Get current account info
        account = mt5.account_info()
        if account is None:
            log.error("Failed to get account info")
            return None
        
        balance = account.balance
        open_positions = self.get_open_positions()
        
        # SIZING LADDER: Get position size from balance (ignores lot_size parameter)
        try:
            lot_size, max_concurrent, max_exposure = self.sizing_ladder.get_sizing(balance)
            log.info(
                f"[{strategy_name}] SizingLadder: ${balance:.2f} → {lot_size:.2f} lots "
                f"(max {max_concurrent} positions, {max_exposure:.2f} total exposure)"
            )
        except ValueError as e:
            # Below position floor
            log.error(f"[{strategy_name}] BLOCKED by SizingLadder: {e}")
            print(f"[{_ist_now()}] BLOCKED: {e}")
            return None
        
        # PRE-TRADE VETO: Run all risk layers
        if self.risk_manager is None:
            log.warning("RiskManager not set - PreTradeVeto will run in degraded mode")
            # Create a mock risk manager for veto
            from types import SimpleNamespace
            mock_rm = SimpleNamespace(_strict_short_stops=False)
            risk_manager = mock_rm
        else:
            risk_manager = self.risk_manager
        
        # Get risk_rules state
        try:
            from src.core import risk_rules
            risk_state = risk_rules.load_state()
        except Exception as e:
            log.warning(f"Could not load risk_rules state: {e}")
            from types import SimpleNamespace
            risk_state = SimpleNamespace(
                pause_until_ts=0,
                consecutive_losses=0,
                week_start_balance=0,
                month_start_balance=0
            )
        
        is_buy = signal == mt5.ORDER_TYPE_BUY
        signal_direction = "BUY" if is_buy else "SELL"
        
        veto_decision = self.veto.check(
            signal_direction=signal_direction,
            balance=balance,
            open_positions=open_positions,
            own_positions=self.get_own_positions(),
            strategy_name=strategy_name,
            risk_manager=risk_manager,
            sizing_ladder=self.sizing_ladder,
            risk_rules_state=risk_state,
        )
        
        if not veto_decision.allow:
            log.warning(f"[{strategy_name}] {veto_decision}")
            print(f"[{_ist_now()}] VETO: {veto_decision.reason}")
            return None
        
        log.info(f"[{strategy_name}] PreTradeVeto: {veto_decision.reason}")
        
        # Legacy checks (now redundant with PreTradeVeto, but kept for safety)
        if not self.can_open_new_position():
            log.warning(
                f"[{strategy_name}] BLOCKED: Max {MAX_CONCURRENT_POSITIONS} "
                f"concurrent positions. Wait for one to close."
            )
            print(f"[{_ist_now()}] BLOCKED: Max concurrent positions reached")
            return None

        # Hard exposure ceiling check (now redundant, but kept as secondary safety)
        open_volume = sum(p.volume for p in open_positions)
        if open_volume + lot_size > max_exposure + 1e-9:
            log.warning(
                f"[{strategy_name}] BLOCKED: open volume {open_volume:.2f} + "
                f"{lot_size:.2f} would exceed cap {max_exposure:.2f} lots."
            )
            print(f"[{_ist_now()}] BLOCKED: exposure cap reached")
            return None

        if self.get_same_direction_count(is_buy) >= MAX_SAME_DIRECTION_POSITIONS:
            log.warning(
                f"[{strategy_name}] BLOCKED: Max {MAX_SAME_DIRECTION_POSITIONS} "
                f"same-direction positions reached."
            )
            print(f"[{_ist_now()}] BLOCKED: Max same-direction positions reached")
            return None

        direction = "BUY" if is_buy else "SELL"
        label = f"PYRAMID {direction}" if is_pyramid else direction

        positions_before = self.count_open_positions()

        # Retry logic: 3 attempts with 500ms delay.
        for attempt in range(1, ORDER_RETRY_COUNT + 1):
            # HIGH-6: refresh the price on every attempt. Resubmitting the same
            # stale price after a requote can only fail again, or fill somewhere
            # the caller never intended.
            tick = mt5.symbol_info_tick(self.symbol)
            if tick is not None:
                price = tick.ask if is_buy else tick.bid

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": lot_size,
                "type": signal,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": ORDER_DEVIATION_POINTS,
                "magic": magic,
                "comment": f"{strategy_name}{'_PYR' if is_pyramid else ''}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            res = mt5.order_send(request)

            if res is None:
                # HIGH-6: None means "no reply", NOT "no fill". The server may
                # have accepted the order. Retrying blindly here is how one
                # signal becomes two positions. Check before retrying.
                log.error(
                    f"[{strategy_name}] order_send returned None "
                    f"(attempt {attempt}/{ORDER_RETRY_COUNT}) -- outcome unknown, verifying"
                )
                _time.sleep(ORDER_RETRY_DELAY_MS / 1000.0)
                if self.count_open_positions() > positions_before:
                    log.warning(
                        f"[{strategy_name}] order DID fill despite the null reply. "
                        f"Not retrying."
                    )
                    print(f"[{_ist_now()}] RECOVERED: {strategy_name} filled after null reply")
                    return None
                continue

            if res.retcode == mt5.TRADE_RETCODE_DONE:
                record = TradeRecord(
                    ticket=res.order,
                    strategy=strategy_name,
                    direction=label,
                    price=price,
                    sl=sl,
                    tp=tp,
                    atr=atr,
                    session=session,
                    timestamp_ist=_ist_now(),
                    lots=lot_size,
                )

                # Keep flat string for logs
                log_msg = f"[{strategy_name}] {label} @ {price:.3f} | SL: {sl:.3f} | TP: {tp:.3f} | ATR: {atr:.3f} | Session: {session} | Lots: {lot_size:.2f} | Open: {self.count_open_positions()}/{max_concurrent}"
                log.info(log_msg)
                print(f"[{_ist_now()}] >> {log_msg}")
                
                from src.core import trade_alerts
                trade_alerts.entry(strategy_name, is_buy, lot_size, getattr(res, "price", 0) or price,
                                   sl, tp, res.order, self.symbol)
                return record

            else:
                log.error(
                    f"[{strategy_name}] Order FAILED (attempt {attempt}/{ORDER_RETRY_COUNT}): "
                    f"{res.comment} (code {res.retcode})"
                )
                if attempt < ORDER_RETRY_COUNT:
                    _time.sleep(ORDER_RETRY_DELAY_MS / 1000.0)

        print(f"[{_ist_now()}] FAILED: {strategy_name} after {ORDER_RETRY_COUNT} retries")
        from src.core import alerts
        alerts.send(f"Order rejected by MT5: {strategy_name}", alerts.WARN,
                    context={"tries": ORDER_RETRY_COUNT},
                    action="Nothing if it is a one-off. If it repeats, check MT5 'Algo Trading' is on.")
        return None

    # ------------------------------------------------------------------
    # Position modification (trailing stop)
    # ------------------------------------------------------------------

    def modify_sl(self, ticket: int, new_sl: float, tp: float, symbol: str) -> bool:
        """Modify the stop-loss of an existing position."""
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "symbol": symbol,
            "sl": new_sl,
            "tp": tp,
        }
        res = mt5.order_send(request)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            log.info(f"Trailing stop: #{ticket} SL -> {new_sl:.3f}")
            print(f"[{_ist_now()}] TRAIL: #{ticket} SL -> {new_sl:.3f}")
            return True
        return False

    # ------------------------------------------------------------------
    # Position closure
    # ------------------------------------------------------------------

    def close_position(self, position) -> bool:
        """Close an open position (for consolidation exit)."""
        close_type = (
            mt5.ORDER_TYPE_SELL
            if position.type == mt5.ORDER_TYPE_BUY
            else mt5.ORDER_TYPE_BUY
        )
        tick = mt5.symbol_info_tick(position.symbol)
        if tick is None:
            return False

        price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": position.volume,
            "type": close_type,
            "position": position.ticket,
            "price": price,
            "deviation": ORDER_DEVIATION_POINTS,
            "magic": position.magic,
            "comment": "consolidation_exit",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        res = mt5.order_send(request)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            log.info(f"Consolidation exit: closed #{position.ticket} @ {price:.3f}")
            print(f"[{_ist_now()}] CLOSED: #{position.ticket} (consolidation) @ {price:.3f}")
            return True
        return False
