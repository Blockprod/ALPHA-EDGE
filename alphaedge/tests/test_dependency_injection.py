# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_dependency_injection.py
# DESCRIPTION  : Tests for dependency injection in FCRStrategy (T2.8)
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-08
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: dependency injection tests."""
# pylint: disable=no-member  # MagicMock modules have dynamic members

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from alphaedge.config.loader import AppConfig, IBConfig, TradingConfig
from alphaedge.engine.strategy import CoreModules, FCRStrategy, StrategyState


def _mock_modules() -> CoreModules:
    """Build a CoreModules with all MagicMock modules."""
    return CoreModules(
        fcr_detector=MagicMock(),
        gap_detector=MagicMock(),
        engulfing_detector=MagicMock(),
        order_manager=MagicMock(),
        risk_manager=MagicMock(),
    )


def _mock_broker() -> MagicMock:
    """Build a mock BrokerConnection with required attributes."""
    broker = MagicMock()
    broker.ib = MagicMock()
    broker.ib.disconnectedEvent = MagicMock()
    broker.ib.disconnectedEvent.__iadd__ = lambda self, h: self
    return broker


# ==================================================================
# Tests
# ==================================================================
class TestDependencyInjection:
    """Verify FCRStrategy accepts injected dependencies."""

    def test_accepts_injected_broker(self) -> None:
        """FCRStrategy should use injected broker instead of creating one."""
        cfg = AppConfig(ib=IBConfig(), trading=TradingConfig())
        broker = _mock_broker()
        modules = _mock_modules()

        strategy = FCRStrategy(
            cfg,
            broker=broker,
            core_modules=modules,
        )

        assert strategy._broker is broker

    def test_accepts_injected_feeds(self) -> None:
        """FCRStrategy should use injected feeds."""
        cfg = AppConfig(ib=IBConfig(), trading=TradingConfig())
        broker = _mock_broker()
        modules = _mock_modules()
        hist = MagicMock()
        rt = MagicMock()

        strategy = FCRStrategy(
            cfg,
            broker=broker,
            historical_feed=hist,
            realtime_feed=rt,
            core_modules=modules,
        )

        assert strategy._hist_feed is hist
        assert strategy._rt_feed is rt

    def test_accepts_injected_core_modules(self) -> None:
        """FCRStrategy should use injected CoreModules."""
        cfg = AppConfig(ib=IBConfig(), trading=TradingConfig())
        broker = _mock_broker()
        modules = _mock_modules()

        strategy = FCRStrategy(
            cfg,
            broker=broker,
            core_modules=modules,
        )

        assert strategy._modules is modules

    @pytest.mark.asyncio()
    async def test_execute_signal_with_injected_deps(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Full signal execution should work with all injected mocks."""
        cfg = AppConfig(ib=IBConfig(), trading=TradingConfig())
        broker = _mock_broker()
        modules = _mock_modules()
        rt_feed = MagicMock()

        strategy = FCRStrategy(
            cfg,
            broker=broker,
            realtime_feed=rt_feed,
            core_modules=modules,
        )

        state = StrategyState(pair="EURUSD", starting_equity=10000.0)
        signal: dict[str, Any] = {
            "detected": True,
            "signal": 1,
            "entry_price": 1.0850,
            "stop_loss": 1.0830,
            "take_profit": 1.0910,
            "risk_pips": 20.0,
        }

        # Configure mocks
        rt_feed.get_mid_price = AsyncMock(return_value=0.0)
        rt_feed.get_live_spread = AsyncMock(return_value=0.00010)
        monkeypatch.setattr(
            strategy._executor,
            "get_account_equity",
            AsyncMock(return_value=10000.0),
        )

        modules.risk_manager.calculate_position_size.return_value = {
            "is_valid": True,
            "lot_size": 0.10,
            "risk_amount": 100.0,
        }

        def _mock_slippage(
            stop_loss: float,
            direction: int,
            slippage_pips: float,
            pip_size: float,
        ) -> float:
            buffer = slippage_pips * pip_size
            return stop_loss - buffer if direction == 1 else stop_loss + buffer

        modules.risk_manager.apply_slippage_buffer.side_effect = _mock_slippage

        modules.order_manager.create_bracket_order.return_value = {
            "is_valid": True,
            "direction": 1,
            "entry_price": 1.0850,
            "stop_loss": 1.0830,
            "take_profit": 1.0910,
            "lot_size": 0.10,
            "risk_pips": 20.0,
            "reward_pips": 60.0,
        }
        modules.order_manager.lots_to_units.return_value = 1000

        mock_trade = MagicMock()
        mock_trade.filledEvent = MagicMock()
        mock_trade.filledEvent.__iadd__ = lambda self, h: self
        mock_trade.filledEvent.wait = AsyncMock()
        place_mock = AsyncMock(return_value=[mock_trade])
        monkeypatch.setattr(strategy._executor, "place_bracket_order", place_mock)

        result = await strategy._lifecycle._execute_signal(state, signal, 0.0001)

        assert result is True
        assert state.trades_today == 1
        assert state.is_position_open is True
        place_mock.assert_awaited_once()
