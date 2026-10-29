"""
Critical configuration regression tests.

These tests MUST pass before any deployment. They catch configuration
drift that has caused production issues in the past.
"""
import pytest
from src.core import main_loop


class TestCriticalFlags:
    """Tests for flags that have caused production incidents."""
    
    def test_trailing_stops_must_be_disabled(self):
        """
        CRITICAL: Trailing stops are net-negative (PF 0.592, -$93.59).
        """
        from src.backtesting.engine import EngineConfig
        assert EngineConfig().enable_trailing is False, "ENABLE_TRAILING must be False in EngineConfig."
    
    def test_pyramiding_must_be_disabled(self):
        """
        CRITICAL: Pyramiding is net-negative (PF 0.592 with trail+pyramid on).
        """
        from src.backtesting.engine import EngineConfig
        assert EngineConfig().enable_pyramiding is False, "ENABLE_PYRAMIDING must be False in EngineConfig."
    
    def test_d1_gate_configuration(self):
        """
        D1 gate status is a deliberate choice with documented trade-offs.
        """
        from src.backtesting.engine import EngineConfig
        assert EngineConfig().enable_d1_bias_gate is True, "D1 gate configuration has changed."


class TestPositionLimits:
    """Tests for position sizing and exposure caps."""

    def test_fixed_lot_size_documented(self):
        """Current fixed lot size must match documentation."""
        from src.core.execution_handler import FIXED_LOT_SIZE

        assert FIXED_LOT_SIZE == 0.02, (
            f"FIXED_LOT_SIZE is {FIXED_LOT_SIZE}, expected 0.02. "
            "If changed, update REPO_GUIDE.md and README.md"
        )

    def test_max_total_exposure(self):
        """Maximum total volume must not exceed Atlas account limits."""
        from src.core.execution_handler import MAX_TOTAL_VOLUME

        assert MAX_TOTAL_VOLUME <= 0.10, (
            f"MAX_TOTAL_VOLUME is {MAX_TOTAL_VOLUME}. "
            "Values > 0.10 not validated for Atlas $5K accounts."
        )

    def test_max_concurrent_positions(self):
        """Concurrent position limit must match validated config (3) for Atlas portfolio."""
        from src.core.execution_handler import MAX_CONCURRENT_POSITIONS

        assert MAX_CONCURRENT_POSITIONS == 3, (
            f"MAX_CONCURRENT_POSITIONS is {MAX_CONCURRENT_POSITIONS}. "
            "Atlas portfolio validated with max_concurrent=3."
        )


class TestRiskControls:
    """Tests for risk management configuration."""
    
    def test_daily_loss_limit(self):
        """Daily loss limit must be configured."""
        from src.core.risk_manager import DAILY_LOSS_LIMIT_PCT
        
        assert DAILY_LOSS_LIMIT_PCT == 0.06, (
            f"DAILY_LOSS_LIMIT_PCT is {DAILY_LOSS_LIMIT_PCT}, expected 0.06 (6%)"
        )
    
    def test_risk_rules_enforcement_status(self):
        """
        Risk rules MUST be enforced to prevent bypassing circuit breakers.
        """
        from src.core import risk_rules
        
        assert getattr(risk_rules, 'ENFORCE', False) is True, "Circuit breakers must be enforced, not in shadow mode."

    def test_default_risk_pct(self):
        """P0-5: Default risk per trade must not exceed 2% (0.02)."""
        from src.core.risk_manager import DEFAULT_RISK_PCT
        assert DEFAULT_RISK_PCT <= 0.02, (
            f"DEFAULT_RISK_PCT is {DEFAULT_RISK_PCT}, expected <= 0.02 (2%)"
        )


class TestPortfolioConfiguration:
    """Tests for current live Atlas portfolio composition."""

    def test_portfolio_strategy_count(self):
        """Atlas portfolio must have exactly 5 strategies."""
        from src.strategies.portfolio_atlas import PORTFOLIO

        assert len(PORTFOLIO) == 5, (
            f"PORTFOLIO has {len(PORTFOLIO)} strategies, expected 5."
        )

    def test_portfolio_strategy_names(self):
        """Verify expected active strategies are in the Atlas portfolio."""
        from src.strategies.portfolio_atlas import PORTFOLIO

        strategy_names = {cls().name for cls in PORTFOLIO}
        expected = {
            'DONCHIAN_TREND_V6',
            'ASIAN_RANGE_FILTERED_V6',
            'ASIAN_BREAKOUT_V6',
            'LONDON_MOMENTUM_TIGHT_V6',
            'NY_SESSION_REVERSAL_V6',
        }

        assert strategy_names == expected, (
            f"Portfolio strategies: {strategy_names}, expected: {expected}"
        )

    def test_portfolio_magics_match_config(self):
        """All portfolio magics must be listed in ultra_magics.json."""
        import json, os
        from src.strategies.portfolio_atlas import PORTFOLIO

        cfg_path = os.path.join(os.path.dirname(__file__), "..", "config", "ultra_magics.json")
        with open(cfg_path) as f:
            allowed = set(json.load(f)["ultra_core_magics"])

        for cls in PORTFOLIO:
            inst = cls()
            assert inst.magic in allowed, (
                f"{inst.name} magic {inst.magic} not in ultra_magics.json"
            )

    def test_live_strategies_sl_atr_mult_floor(self):
        """Every live strategy's sl_atr_mult must be >= 1.0 (no micro-stops)."""
        from src.strategies.portfolio_atlas import PORTFOLIO
        for cls in PORTFOLIO:
            inst = cls()
            assert hasattr(inst, "sl_atr_mult"), f"{inst.name} missing sl_atr_mult"
            assert inst.sl_atr_mult >= 1.0, (
                f"{inst.name} has sl_atr_mult={inst.sl_atr_mult} < 1.0."
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
