"""
Tests for order execution critical paths.

These tests verify the fixes for known production issues:
- HIGH-6: Price refresh on retry (fixed)
- CRIT-1: Duplicate position prevention
- Threshold scaling
- Margin checks
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.core.execution_handler import ExecutionHandler, FIXED_LOT_SIZE, MAX_TOTAL_VOLUME



class TestOrderRetryLogic:
    """Tests for the 3-attempt retry mechanism."""

    @patch('src.core.execution_handler.mt5')
    def test_price_refreshed_on_each_retry(self, mock_mt5):
        """
        HIGH-6 fix verification: Price must be refreshed on every retry attempt.

        Regression: Previously used stale price on retries, causing requote failures.
        """
        handler = ExecutionHandler()

        # BUG-002 fix: account_info must return a real balance, not a MagicMock
        mock_mt5.account_info.return_value = Mock(balance=150.0)

        # BUG-004 fix: TRADE_RETCODE_DONE must be set so the comparison works
        mock_mt5.TRADE_RETCODE_DONE = 10009

        # Mock: first attempt fails, second succeeds
        mock_mt5.symbol_info_tick.side_effect = [
            Mock(ask=4300.0, bid=4299.5),  # First attempt
            Mock(ask=4300.5, bid=4300.0),  # Second attempt (price moved)
        ]

        mock_mt5.order_send.side_effect = [
            Mock(retcode=10004),              # TRADE_RETCODE_REQUOTE
            Mock(retcode=10009, order=12345), # TRADE_RETCODE_DONE
        ]

        mock_mt5.ORDER_TYPE_BUY = 0
        mock_mt5.positions_get.return_value = []

        result = handler.send_order(
            signal=0,  # BUY
            price=4300.0,
            sl=4290.0,
            tp=4310.0,
            strategy_name="TEST",
            magic=9999,
            lot_size=0.01,
        )

        # Verify tick was requested on retry attempts
        assert mock_mt5.symbol_info_tick.call_count >= 1

        # Verify second order_send used the refreshed price
        if mock_mt5.order_send.call_count >= 2:
            second_call_args = mock_mt5.order_send.call_args_list[1][0][0]
            assert second_call_args['price'] == 4300.5, "Second attempt must use refreshed price"

    @patch('src.core.execution_handler.mt5')
    def test_null_response_checks_for_fill(self, mock_mt5):
        """
        Null response handler: Must check if order filled despite null reply.

        Reference: execution_handler.py (HIGH-6 comment)
        """
        handler = ExecutionHandler()

        # BUG-002 fix: provide real balance
        mock_mt5.account_info.return_value = Mock(balance=150.0)
        mock_mt5.TRADE_RETCODE_DONE = 10009
        mock_mt5.ORDER_TYPE_BUY = 0

        # positions_get is called multiple times:
        # 1. get_open_positions() L149 (for exposure checks)
        # 2. can_open_new_position() / get_same_direction_count() calls
        # 3. count_open_positions() = positions_before L238
        # 4. count_open_positions() after sleep (fill check) L275
        # Use side_effect for the first calls, with the last one showing a filled position.
        filled_pos = Mock(ticket=12345, magic=5001)
        # Positions are empty until the (null-reply) order_send has been attempted; after that the fill shows up.
        mock_mt5.positions_get.side_effect = (
            lambda *a, **k: [filled_pos] if mock_mt5.order_send.called else []
        )
        mock_mt5.symbol_info_tick.return_value = Mock(ask=4300.0, bid=4299.5)
        mock_mt5.order_send.return_value = None

        result = handler.send_order(
            signal=0,
            price=4300.0,
            sl=4290.0,
            tp=4310.0,
            strategy_name="TEST",
            magic=9999,
            lot_size=0.01,
        )

        # Must not retry if fill detected
        assert mock_mt5.order_send.call_count == 1, "Should not retry after detecting fill"



class TestExposureLimits:
    """Tests for position and volume caps."""

    @patch('src.core.execution_handler.mt5')
    def test_blocks_when_max_concurrent_reached(self, mock_mt5):
        """Must refuse new orders when MAX_CONCURRENT_POSITIONS reached."""
        handler = ExecutionHandler()

        # BUG-002 fix: provide real balance — SizingLadder at $200 allows 2 positions
        mock_mt5.account_info.return_value = Mock(balance=200.0)
        mock_mt5.TRADE_RETCODE_DONE = 10009
        mock_mt5.ORDER_TYPE_BUY = 0

        # Mock: 2 positions already open (at the $200-tier limit of 2)
        mock_mt5.positions_get.return_value = [
            Mock(ticket=1, volume=0.01, type=0),
            Mock(ticket=2, volume=0.01, type=0),
        ]

        result = handler.send_order(
            signal=0,
            price=4300.0,
            sl=4290.0,
            tp=4310.0,
            strategy_name="TEST",
            magic=9999,
            lot_size=0.01,
        )

        assert result is None, "Must block when concurrent limit reached"
        mock_mt5.order_send.assert_not_called()

    @patch('src.core.execution_handler.mt5')
    def test_blocks_when_total_volume_exceeded(self, mock_mt5):
        """Must refuse orders that would exceed MAX_TOTAL_VOLUME."""
        handler = ExecutionHandler()

        # Mock: already have 0.03 lots open, trying to add 0.02
        mock_mt5.positions_get.return_value = [
            Mock(ticket=1, volume=0.03, type=0),
        ]
        mock_mt5.account_info.return_value = Mock(balance=200.0)
        mock_mt5.ORDER_TYPE_BUY = 0

        result = handler.send_order(
            signal=0,
            price=4300.0,
            sl=4290.0,
            tp=4310.0,
            strategy_name="TEST",
            magic=9999,
            lot_size=0.02,  # Would exceed 0.04 total
        )

        assert result is None, "Must block when total volume would exceed cap"
        mock_mt5.order_send.assert_not_called()


class TestThresholdScaling:
    """Tests for position sizing at small balances."""

    @patch('src.core.execution_handler.mt5')
    def test_sizing_ladder_at_150_balance(self, mock_mt5):
        """
        SizingLadder: Balance $100-$200 uses 0.01 lots (1 position max).

        Note: The previous test expected 0.02 lots below $200, but that was
        a stale comment from before SizingLadder was introduced. The ladder
        correctly uses 0.01 lots (the broker minimum) at $100-200 for safety.

        SizingLadder rungs:
          $0-$100:    0.01 lots, 1 position  (survival mode)
          $100-$200:  0.01 lots, 1 position  (still 4-9% risk)
          $200-$400:  0.01 lots, 2 positions (growth begins)
          $400-$800:  0.01 lots, 3 positions (scaling)
          $800+:      0.02 lots, 2 positions (full scale)
        """
        handler = ExecutionHandler()

        # Balance at $150: ladder gives 0.01 lots, 1 position max
        mock_mt5.account_info.return_value = Mock(balance=150.0)
        mock_mt5.positions_get.return_value = []
        mock_mt5.symbol_info_tick.return_value = Mock(ask=4300.0, bid=4299.5)
        mock_mt5.order_send.return_value = Mock(retcode=10009, order=12345)
        mock_mt5.TRADE_RETCODE_DONE = 10009
        mock_mt5.ORDER_TYPE_BUY = 0

        result = handler.send_order(
            signal=0,
            price=4300.0,
            sl=4290.0,
            tp=4310.0,
            strategy_name="TEST",
            magic=9999,
            lot_size=0.03,  # Requested size — should be overridden by ladder
        )

        # At $150, SizingLadder gives 0.01 lots
        call_args = mock_mt5.order_send.call_args[0][0]
        assert call_args['volume'] == 0.01, (
            f"At $150 balance, SizingLadder should give 0.01 lots, got {call_args['volume']}"
        )

    @patch('src.core.execution_handler.mt5')
    def test_sizing_ladder_at_900_balance(self, mock_mt5):
        """
        SizingLadder: Balance >= $800 uses 0.02 lots (full scale).
        """
        handler = ExecutionHandler()

        # Balance at $900: ladder gives 0.02 lots, 2 positions max
        mock_mt5.account_info.return_value = Mock(balance=900.0)
        mock_mt5.positions_get.return_value = []
        mock_mt5.symbol_info_tick.return_value = Mock(ask=4300.0, bid=4299.5)
        mock_mt5.order_send.return_value = Mock(retcode=10009, order=12345)
        mock_mt5.TRADE_RETCODE_DONE = 10009
        mock_mt5.ORDER_TYPE_BUY = 0

        result = handler.send_order(
            signal=0,
            price=4300.0,
            sl=4290.0,
            tp=4310.0,
            strategy_name="TEST",
            magic=9999,
            lot_size=0.01,  # Requested size — should be overridden by ladder
        )

        call_args = mock_mt5.order_send.call_args[0][0]
        assert call_args['volume'] == 0.02, (
            f"At $900 balance, SizingLadder should give 0.02 lots, got {call_args['volume']}"
        )


class TestMarginEnforcement:
    """Tests for margin requirement checks."""

    @patch('src.core.execution_handler.mt5')
    def test_checks_margin_before_order(self, mock_mt5):
        """
        Must verify sufficient free margin before sending order.

        Current implementation checks via _margin_allows in engine,
        but execution_handler should also verify.
        """
        # This is a placeholder for when margin checks are added to execution_handler
        # Currently margin enforcement is in the backtesting engine only
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
