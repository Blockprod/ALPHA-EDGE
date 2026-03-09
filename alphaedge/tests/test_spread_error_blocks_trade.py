# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_spread_error_blocks_trade.py
# DESCRIPTION  : Tests for P0-02 spread/mid_price None blocks trade
# AUTHOR       : ALPHAEDGE Dev Team
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-08
# ============================================================
"""ALPHAEDGE — Verify that None spread/mid_price blocks trade execution."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alphaedge.config.loader import AppConfig, IBConfig, TradingConfig
from alphaedge.engine.strategy import CoreModules, FCRStrategy


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _make_config() -> AppConfig:
    """Build a minimal AppConfig for tests."""
    return AppConfig(
        ib=IBConfig(is_paper=True),
        trading=TradingConfig(pairs=["EURUSD", "USDJPY"]),
    )


def _build_strategy() -> FCRStrategy:
    """Create FCRStrategy with mocked externals."""
    cfg = _make_config()
    with (
        patch("alphaedge.engine.strategy.BrokerConnection") as mock_broker_cls,
        patch("alphaedge.engine.strategy.OrderExecutor"),
        patch("alphaedge.engine.strategy.HistoricalDataFeed"),
        patch("alphaedge.engine.strategy.RealtimeDataFeed"),
        patch("alphaedge.engine.strategy._import_core_modules") as mock_modules,
    ):
        mock_ib = MagicMock()
        mock_ib.disconnectedEvent = MagicMock()
        mock_broker_cls.return_value.ib = mock_ib

        risk_mock = MagicMock()
        risk_mock.calculate_position_size.return_value = {
            "is_valid": True,
            "lot_size": 0.01,
            "pip_value": 0.10,
        }
        risk_mock.apply_slippage_buffer.return_value = 1.2400

        order_mock = MagicMock()
        order_mock.create_bracket_order.return_value = {
            "is_valid": True,
            "direction": 1,
            "entry_price": 1.2500,
            "stop_loss": 1.2400,
            "take_profit": 1.2700,
            "lot_size": 0.01,
        }
        order_mock.lots_to_units.return_value = 1000

        mock_modules.return_value = CoreModules(
            fcr_detector=MagicMock(),
            gap_detector=MagicMock(),
            engulfing_detector=MagicMock(),
            order_manager=order_mock,
            risk_manager=risk_mock,
        )
        strategy = FCRStrategy(cfg)
    return strategy


def _make_signal() -> dict[str, Any]:
    """Build a valid trade signal."""
    return {
        "detected": True,
        "signal": 1,
        "entry_price": 1.2500,
        "stop_loss": 1.2450,
        "take_profit": 1.2600,
        "risk_pips": 50.0,
    }


# ==================================================================
# Tests — get_live_spread returns None
# ==================================================================
class TestSpreadNoneBlocksTrade:
    """Verify that None from get_live_spread blocks trade execution."""

    @pytest.mark.asyncio()
    async def test_execute_signal_blocked_when_spread_none(self) -> None:
        """_execute_signal returns False when spread is None."""
        strategy = _build_strategy()
        state = strategy._init_pair_state("EURUSD")
        state.starting_equity = 10000.0
        state.current_equity = 10000.0

        # Mock get_live_spread to return None (IB error)
        strategy._rt_feed.get_live_spread = AsyncMock(return_value=None)
        strategy._rt_feed.get_mid_price = AsyncMock(return_value=1.2500)

        result = await strategy._lifecycle._execute_signal(
            state, _make_signal(), 0.0001
        )
        assert result is False
        assert state.is_position_open is False

    @pytest.mark.asyncio()
    async def test_check_spread_blocked_when_spread_none(self) -> None:
        """_check_spread_and_execute returns False when spread is None."""
        strategy = _build_strategy()
        state = strategy._init_pair_state("EURUSD")
        state.starting_equity = 10000.0
        state.current_equity = 10000.0

        strategy._rt_feed.get_live_spread = AsyncMock(return_value=None)

        result = await strategy._lifecycle._check_spread_and_execute(
            state, _make_signal(), 0.0001
        )
        assert result is False

    @pytest.mark.asyncio()
    async def test_check_spread_passes_when_spread_valid(self) -> None:
        """_check_spread_and_execute proceeds when spread is valid."""
        strategy = _build_strategy()
        state = strategy._init_pair_state("EURUSD")
        state.starting_equity = 10000.0
        state.current_equity = 10000.0

        # Valid spread = 0.00008 = 0.8 pips (below max_spread_pips=2.0)
        strategy._rt_feed.get_live_spread = AsyncMock(return_value=0.00008)
        strategy._rt_feed.get_mid_price = AsyncMock(return_value=1.2500)
        strategy._executor.place_bracket_order = AsyncMock(return_value=[])

        await strategy._lifecycle._check_spread_and_execute(
            state, _make_signal(), 0.0001
        )
        # get_live_spread is called in _check_spread_and_execute + _execute_signal
        assert strategy._rt_feed.get_live_spread.await_count >= 1


# ==================================================================
# Tests — get_mid_price returns None (P1-05 combined)
# ==================================================================
class TestMidPriceNoneBlocksTrade:
    """Verify that None from get_mid_price blocks trade for JPY pairs."""

    @pytest.mark.asyncio()
    async def test_execute_signal_blocked_when_mid_price_none_jpy(self) -> None:
        """_execute_signal returns False when mid_price is None on JPY pair."""
        strategy = _build_strategy()
        state = strategy._init_pair_state("USDJPY")
        state.starting_equity = 10000.0
        state.current_equity = 10000.0

        # Mock mid_price to return None (IB error)
        strategy._rt_feed.get_mid_price = AsyncMock(return_value=None)
        strategy._rt_feed.get_live_spread = AsyncMock(return_value=0.03)

        # pip_size for JPY = 0.01 (>= 0.001 → triggers mid_price fetch)
        result = await strategy._lifecycle._execute_signal(state, _make_signal(), 0.01)
        assert result is False
        assert state.is_position_open is False

    @pytest.mark.asyncio()
    async def test_execute_signal_skips_mid_for_non_jpy(self) -> None:
        """_execute_signal skips mid_price fetch for non-JPY pairs."""
        strategy = _build_strategy()
        state = strategy._init_pair_state("EURUSD")
        state.starting_equity = 10000.0
        state.current_equity = 10000.0

        strategy._rt_feed.get_mid_price = AsyncMock(return_value=None)
        strategy._rt_feed.get_live_spread = AsyncMock(return_value=0.00008)
        strategy._executor.place_bracket_order = AsyncMock(return_value=[])

        # pip_size=0.0001 < 0.001 → does NOT trigger mid_price
        await strategy._lifecycle._execute_signal(state, _make_signal(), 0.0001)
        strategy._rt_feed.get_mid_price.assert_not_awaited()
