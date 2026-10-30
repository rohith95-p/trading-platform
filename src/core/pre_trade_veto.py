"""
Pre-Trade Risk Veto Chain (adapted from NautilusTrader pattern).

Every order is vetted through multiple risk layers BEFORE it reaches MT5.
This is the single chokepoint that prevents any risk-violating trade.

Design: Each veto layer returns (allow: bool, reason: str).
First layer that returns False blocks the entire order.
"""

from typing import Tuple, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging

log = logging.getLogger(__name__)
IST = timezone(timedelta(hours=5, minutes=30))


@dataclass
class VetoDecision:
    """Result of pre-trade risk veto."""
    allow: bool
    reason: str
    layer: str  # Which veto layer made the decision
    
    def __str__(self):
        status = "APPROVED" if self.allow else "BLOCKED"
        return f"[{self.layer}] {status}: {self.reason}"


class PreTradeVeto:
    """
    Gate every order through all risk layers before MT5 sees it.
    
    Veto layers (checked in order):
    1. Position floor (minimum balance)
    2. Circuit breakers (consecutive losses, weekly/monthly caps)
    3. Concurrent position limits (from sizing ladder)
    4. Exposure caps (total volume)
    5. Macro overrides (visibility + logging)
    6. News blackout (high-impact events)
    
    Usage:
        veto = PreTradeVeto()
        decision = veto.check(signal, balance, open_positions, ...)
        if not decision.allow:
            log.warning(decision)
            return None  # Block the order
    """
    
    def __init__(self):
        self.position_floor = 50.0  # From sizing_ladder.py
    
    def check(
        self,
        signal_direction: str,  # "BUY" or "SELL"
        balance: float,
        open_positions: List,
        strategy_name: str,
        risk_manager,
        sizing_ladder,
        risk_rules_state,
        own_positions: Optional[List] = None,
    ) -> VetoDecision:
        """
        Run all veto layers. First failure blocks the order.
        
        Returns:
            VetoDecision with allow=True if all layers pass,
            or allow=False with the blocking reason.
        """
        
        # Layer 1: Position floor
        result = self._check_position_floor(balance)
        if not result.allow:
            return result
        
        # Layer 2: Circuit breakers (risk_rules.py)
        result = self._check_circuit_breakers(balance, risk_rules_state)
        if not result.allow:
            return result
        
        # Layer 3: Concurrent position limits (from sizing ladder)
        # Concurrency counts only Ultra Core's own positions; exposure (layer 4) counts every system's (account view).
        result = self._check_concurrent_limits(balance, open_positions if own_positions is None else own_positions, sizing_ladder)
        if not result.allow:
            return result
        
        # Layer 4: Exposure caps (total volume)
        result = self._check_exposure_caps(balance, open_positions, sizing_ladder)
        if not result.allow:
            return result
        
        # Layer 5: Macro overrides (make visible + logged)
        result = self._check_macro_override(signal_direction, strategy_name, risk_manager)
        if not result.allow:
            return result
        
        # Layer 6: News blackout (if enabled)
        result = self._check_news_blackout()
        if not result.allow:
            return result
        
        # All layers passed
        return VetoDecision(
            allow=True,
            reason="All risk layers passed",
            layer="PreTradeVeto"
        )
    
    def _check_position_floor(self, balance: float) -> VetoDecision:
        """Layer 1: Minimum balance to continue trading."""
        if balance < self.position_floor:
            return VetoDecision(
                allow=False,
                reason=f"Balance ${balance:.2f} below floor ${self.position_floor:.2f}",
                layer="PositionFloor"
            )
        return VetoDecision(allow=True, reason="Floor check passed", layer="PositionFloor")
    
    def _check_circuit_breakers(self, balance: float, risk_state) -> VetoDecision:
        """
        Layer 2: Consecutive losses, weekly/monthly caps.
        
        NOTE: This requires risk_rules.ENFORCE=True to actually block.
        When ENFORCE=False, this layer always passes (shadow mode).
        """
        from src.core import risk_rules
        
        if not risk_rules.ENFORCE:
            # Shadow mode - track but don't block
            return VetoDecision(
                allow=True, 
                reason="ENFORCE=False (shadow mode)",
                layer="CircuitBreakers"
            )
        
        # Check consecutive losses
        if risk_state.pause_until_ts > 0 and not risk_rules.streak_breakers_relaxed():
            import time
            if time.time() < risk_state.pause_until_ts:
                return VetoDecision(
                    allow=False,
                    reason=f"Consecutive-loss pause active (losses={risk_state.consecutive_losses})",
                    layer="CircuitBreakers"
                )
        
        # Check weekly cap
        if hasattr(risk_state, 'week_start_balance') and risk_state.week_start_balance > 0:
            week_loss_pct = (risk_state.week_start_balance - balance) / risk_state.week_start_balance
            if week_loss_pct >= 0.15:  # 15% weekly cap
                return VetoDecision(
                    allow=False,
                    reason=f"Weekly loss cap hit ({week_loss_pct*100:.1f}% >= 15%)",
                    layer="CircuitBreakers"
                )
        
        # Check monthly cap
        if hasattr(risk_state, 'month_start_balance') and risk_state.month_start_balance > 0:
            month_loss_pct = (risk_state.month_start_balance - balance) / risk_state.month_start_balance
            # demo-only relaxation (owner decision 2026-10-21): same switch as risk_rules, live loop + MT5-confirmed demo only
            if month_loss_pct >= 0.25 and not risk_rules.hard_halts_relaxed():  # 25% monthly cap
                return VetoDecision(
                    allow=False,
                    reason=f"Monthly loss cap hit ({month_loss_pct*100:.1f}% >= 25%)",
                    layer="CircuitBreakers"
                )
        
        return VetoDecision(allow=True, reason="No circuit breakers tripped", layer="CircuitBreakers")
    
    def _check_concurrent_limits(self, balance: float, open_positions: List, sizing_ladder) -> VetoDecision:
        """Layer 3: Maximum concurrent positions (from sizing ladder)."""
        _, max_concurrent, _ = sizing_ladder.get_sizing(balance)
        
        current_positions = len(open_positions)
        if current_positions >= max_concurrent:
            return VetoDecision(
                allow=False,
                reason=f"Concurrent limit reached ({current_positions}/{max_concurrent})",
                layer="ConcurrentLimit"
            )
        
        return VetoDecision(
            allow=True,
            reason=f"Concurrent positions OK ({current_positions}/{max_concurrent})",
            layer="ConcurrentLimit"
        )
    
    def _check_exposure_caps(self, balance: float, open_positions: List, sizing_ladder) -> VetoDecision:
        """Layer 4: Maximum total exposure (from sizing ladder)."""
        _, _, max_exposure = sizing_ladder.get_sizing(balance)
        
        current_exposure = sum(p.volume for p in open_positions)
        requested_lots, _, _ = sizing_ladder.get_sizing(balance)
        
        if current_exposure + requested_lots > max_exposure:
            return VetoDecision(
                allow=False,
                reason=f"Exposure cap exceeded ({current_exposure:.2f}+{requested_lots:.2f} > {max_exposure:.2f})",
                layer="ExposureCap"
            )
        
        return VetoDecision(
            allow=True,
            reason=f"Exposure OK ({current_exposure:.2f}/{max_exposure:.2f})",
            layer="ExposureCap"
        )
    
    def _check_macro_override(self, signal_direction: str, strategy_name: str, risk_manager) -> VetoDecision:
        """
        Layer 5: Make macro override visible.
        
        CRITICAL: This was previously SILENT. If strict_short_stops=true is active,
        all SHORT stops are rewritten to 1.0×ATR without any log entry.
        
        This layer doesn't block, but LOGS and ALERTS when override is active.
        """
        if signal_direction == "SELL" and risk_manager._strict_short_stops:
            # Override is active - make it visible
            log.warning(
                f"⚠️  MACRO OVERRIDE ACTIVE: {strategy_name} SHORT will use strict stops (1.0×ATR)"
            )
            
            # Send alert (if configured)
            try:
                from src.core import alerts
                alerts.send(
                    f"Macro override: {strategy_name} SHORT with strict stops",
                    severity=alerts.INFO,
                    context={'strategy': strategy_name, 'direction': signal_direction}
                )
            except Exception as e:
                log.error(f"Failed to send macro override alert: {e}")
            
            # Don't block, but make it visible
            return VetoDecision(
                allow=True,
                reason="MACRO OVERRIDE: strict SHORT stops active",
                layer="MacroOverride"
            )
        
        return VetoDecision(allow=True, reason="No macro override", layer="MacroOverride")
    
    def _check_news_blackout(self) -> VetoDecision:
        """
        Layer 6: News blackout (±15 minutes around tier-1 events).

        NOTE: This requires news_filter.ENABLE_NEWS_FILTER=True.
        """
        try:
            from src.core import news_filter

            if not news_filter.ENABLE_NEWS_FILTER:
                return VetoDecision(allow=True, reason="News filter disabled", layer="NewsBlackout")

            # Pass explicit now so the veto check and main loop check use the same instant.
            now_ist = datetime.now(IST)
            blocked, reason = news_filter.is_near_news_event(now=now_ist)
            if blocked:
                return VetoDecision(
                    allow=False,
                    reason=f"News blackout: {reason}",
                    layer="NewsBlackout"
                )

            return VetoDecision(allow=True, reason="No news event nearby", layer="NewsBlackout")

        except Exception as e:
            log.error(f"News filter check failed: {e}")
            # Fail open (allow trading) if news filter breaks
            return VetoDecision(allow=True, reason=f"News filter error: {e}", layer="NewsBlackout")


# Singleton instance
_veto = None

def get_veto() -> PreTradeVeto:
    """Get global veto instance."""
    global _veto
    if _veto is None:
        _veto = PreTradeVeto()
    return _veto


if __name__ == "__main__":
    # Test the veto chain
    from types import SimpleNamespace
    
    print("Testing PreTradeVeto chain...")
    print()
    
    veto = PreTradeVeto()
    
    # Mock objects
    class MockSizingLadder:
        @staticmethod
        def get_sizing(balance):
            if balance < 200:
                return (0.01, 1, 0.01)  # lots, max_concurrent, max_exposure
            else:
                return (0.01, 2, 0.02)
    
    class MockRiskManager:
        _strict_short_stops = False
    
    risk_state = SimpleNamespace(
        pause_until_ts=0,
        consecutive_losses=0,
        week_start_balance=0,
        month_start_balance=0
    )
    
    # Test 1: Normal case (should pass)
    print("Test 1: Normal case")
    decision = veto.check(
        signal_direction="BUY",
        balance=150.0,
        open_positions=[],
        strategy_name="TEST",
        risk_manager=MockRiskManager(),
        sizing_ladder=MockSizingLadder(),
        risk_rules_state=risk_state
    )
    print(decision)
    print()
    
    # Test 2: Below position floor (should block)
    print("Test 2: Below position floor")
    decision = veto.check(
        signal_direction="BUY",
        balance=40.0,
        open_positions=[],
        strategy_name="TEST",
        risk_manager=MockRiskManager(),
        sizing_ladder=MockSizingLadder(),
        risk_rules_state=risk_state
    )
    print(decision)
    print()
    
    # Test 3: Concurrent limit reached (should block)
    print("Test 3: Concurrent limit reached")
    mock_position = SimpleNamespace(volume=0.01)
    decision = veto.check(
        signal_direction="BUY",
        balance=150.0,
        open_positions=[mock_position],  # 1 position, limit is 1
        strategy_name="TEST",
        risk_manager=MockRiskManager(),
        sizing_ladder=MockSizingLadder(),
        risk_rules_state=risk_state
    )
    print(decision)
    print()
    
    # Test 4: Macro override (should pass but log)
    print("Test 4: Macro override active")
    rm_override = MockRiskManager()
    rm_override._strict_short_stops = True
    decision = veto.check(
        signal_direction="SELL",
        balance=150.0,
        open_positions=[],
        strategy_name="TEST",
        risk_manager=rm_override,
        sizing_ladder=MockSizingLadder(),
        risk_rules_state=risk_state
    )
    print(decision)
