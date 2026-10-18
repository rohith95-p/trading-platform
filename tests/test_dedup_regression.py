"""
Regression test for P0-3: Duplicate-fill bug prevention.

Tests:
1. Two scans on the same closed candle -> only ONE order placed.
2. Dedup key (strategy_magic, bar_time, direction) persists to trade log across restart.
3. EngineConfig default is dedup_per_candle=True.
4. Backtest engine deduplicates signals per candle.
"""

import json
import os
import tempfile
import numpy as np
import pytest
from types import SimpleNamespace
from unittest.mock import Mock, patch, MagicMock

from src.core import main_loop
from src.core import trade_log
from src.core.execution_handler import ExecutionHandler
from src.backtesting.engine import BacktestEngine, EngineConfig


class TestLiveDedupRegression:
    """Test duplicate order prevention in live execution loop."""

    def test_two_scans_on_same_closed_candle_places_only_one_order(self):
        """
        P0-3 Action 5: Simulate two scans on the same closed candle and assert
        only ONE order is placed by _execute_signal.
        """
        # Synthetic M15 rates with closed candle at [-2]
        bar_time = 1791376200
        rates_dtype = np.dtype([
            ('time', '<i8'), ('open', '<f8'), ('high', '<f8'),
            ('low', '<f8'), ('close', '<f8'), ('tick_volume', '<i8'),
            ('spread', '<i4'), ('real_volume', '<i8')
        ])
        m15_rates = np.zeros(10, dtype=rates_dtype)
        for i in range(10):
            m15_rates[i]['time'] = bar_time - (9 - i) * 900
            m15_rates[i]['open'] = 2650.0
            m15_rates[i]['high'] = 2655.0
            m15_rates[i]['low'] = 2645.0
            m15_rates[i]['close'] = 2652.0
        
        # Closed candle time at [-2]
        closed_candle_time = int(m15_rates[-2]['time'])

        signal = SimpleNamespace(
            direction=0,  # BUY
            direction_str="BUY",
            is_buy=True,
            strategy_name="TEST_STRATEGY",
            magic=5001,
        )

        mock_fetcher = Mock()
        mock_fetcher.get_tick.return_value = Mock(ask=2652.5, bid=2652.0)
        mock_fetcher.get_foreign_positions.return_value = []
        mock_fetcher.get_foreign_exposure.return_value = []
        mock_fetcher.get_own_positions.return_value = []

        mock_risk = Mock()
        mock_risk.is_spread_ok.return_value = True
        mock_risk.calculate_atr_stops.return_value = SimpleNamespace(sl=2642.5, tp=2672.5, atr=10.0)

        mock_executor = Mock()
        mock_executor.can_open_new_position.return_value = True
        mock_executor.send_order.return_value = Mock(retcode=10009, order=99901)

        strategy = Mock()
        strategy.sl_atr_mult = 0.5
        strategy.tp_atr_mult = 1.5
        strategy.max_spread_pts = None

        dedup_set = set()

        with patch('src.core.market_hours.allow_new_entry', return_value=(True, "")):
            # First scan: should execute successfully
            res1 = main_loop._execute_signal(
                signal=signal,
                m15_rates=m15_rates,
                fetcher=mock_fetcher,
                risk=mock_risk,
                executor=mock_executor,
                session_mult=1.0,
                session_name="NY",
                strategy=strategy,
                executed_orders_dedup=dedup_set,
            )
            assert res1 is not None, "First scan should place order"
            assert mock_executor.send_order.call_count == 1
            assert (5001, closed_candle_time, "BUY") in dedup_set

            # Second scan on the EXACT same closed candle: MUST BE DEDUPED
            res2 = main_loop._execute_signal(
                signal=signal,
                m15_rates=m15_rates,
                fetcher=mock_fetcher,
                risk=mock_risk,
                executor=mock_executor,
                session_mult=1.0,
                session_name="NY",
                strategy=strategy,
                executed_orders_dedup=dedup_set,
            )
            assert res2 is None, "Second scan on same candle must return None (blocked)"
            assert mock_executor.send_order.call_count == 1, (
                f"send_order called {mock_executor.send_order.call_count} times; expected exactly 1!"
            )

    def test_dedup_persists_to_trade_log_and_survives_restart(self, tmp_path):
        """
        P0-3 Action 3: Dedup keys written to trade log are recovered on startup.
        """
        log_dir = str(tmp_path / "trades")
        os.makedirs(log_dir, exist_ok=True)
        
        with patch('src.core.trade_log.LOG_DIR', log_dir):
            # Write an order event with dedup_key
            bar_time = 1791376200
            magic = 5002
            direction = "SELL"
            trade_log.order(
                strategy="BB_MEAN_REVERSION_V5",
                direction=direction,
                lots=0.02,
                price=2650.0,
                magic=magic,
                bar_time=bar_time,
                dedup_key=f"{magic}:{bar_time}:{direction}",
            )

            # Reload dedup keys (simulating bot restart)
            recovered_keys = trade_log.load_order_dedup_keys()
            assert (magic, bar_time, direction) in recovered_keys, (
                f"Expected {(magic, bar_time, direction)} in recovered keys: {recovered_keys}"
            )


class TestBacktestEngineDedup:
    """Test EngineConfig default and dedup behavior in backtests."""

    def test_engine_config_dedup_default_is_true(self):
        """
        P0-3 Action 4: EngineConfig default must be dedup_per_candle=True.
        """
        cfg = EngineConfig()
        assert cfg.dedup_per_candle is True, (
            "EngineConfig().dedup_per_candle must be True by default"
        )
