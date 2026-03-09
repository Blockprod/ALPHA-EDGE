# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_slippage_integration.py
# DESCRIPTION  : Tests for slippage buffer integration in live flow (T2.6)
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-08
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: slippage integration tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alphaedge.config.constants import DEFAULT_MARKET_SLIPPAGE_PIPS
from alphaedge.config.loader import AppConfig, IBConfig, TradingConfig
from alphaedge.engine.strategy import CoreModules, FCRStrategy, StrategyState


# ------------------------------------------------------------------
# Helper
# ------------------------------------------------------------------
def _make_strategy() -> FCRStrategy:
    """Build a strategy with all externals mocked."""
    cfg = AppConfig(ib=IBConfig(is_paper=True), trading=TradingConfig())

    with (
        patch("alphaedge.engine.strategy.BrokerConnection") as mock_broker_cls,
        patch("alphaedge.engine.strategy.OrderExecutor"),
        patch("alphaedge.engine.strategy.HistoricalDataFeed"),
        patch("alphaedge.engine.strategy.RealtimeDataFeed"),
        patch("alphaedge.engine.strategy._import_core_modules") as mock_mods,
    ):
        mock_ib = MagicMock()
        handlers: list[Any] = []

        def _capture(self_event: Any, handler: Any) -> Any:
            handlers.append(handler)
            return self_event

        mock_ib.disconnectedEvent.__iadd__ = _capture
        mock_broker_cls.return_value.ib = mock_ib
        mock_mods.return_value = CoreModules(
            fcr_detector=MagicMock(),
            gap_detector=MagicMock(),
            engulfing_detector=MagicMock(),
            order_manager=MagicMock(),
            risk_manager=MagicMock(),
        )
        strategy = FCRStrategy(cfg)
    return strategy


# ==================================================================
# Tests
# ==================================================================
class TestSlippageBufferInExecuteSignal:
    """Verify apply_slippage_buffer is called during signal execution."""

    @pytest.mark.asyncio()
    async def test_sl_widened_by_slippage_buffer_buy(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """BUY signal: SL should be lowered by market slippage buffer."""
        strategy = _make_strategy()
        state = StrategyState(pair="EURUSD")
        pip_size = 0.0001

        signal: dict[str, Any] = {
            "detected": True,
            "signal": 1,
            "entry_price": 1.0850,
            "stop_loss": 1.0830,
            "take_profit": 1.0910,
            "risk_pips": 20.0,
        }

        # Mock dependencies
        monkeypatch.setattr(
            strategy._rt_feed, "get_mid_price", AsyncMock(return_value=0.0)
        )
        monkeypatch.setattr(
            strategy._rt_feed,
            "get_live_spread",
            AsyncMock(return_value=0.00010),
        )
        monkeypatch.setattr(
            strategy._executor,
            "get_account_equity",
            AsyncMock(return_value=10000.0),
        )

        # risk_manager (module 4) — real-ish apply_slippage_buffer
        risk_mod = strategy._modules.risk_manager
        risk_mod.calculate_position_size.return_value = {
            "is_valid": True,
            "lot_size": 0.10,
            "units": 1000,
            "risk_amount": 100.0,
        }
        original_sl = 1.0830

        def _mock_apply_slippage(
            stop_loss: float,
            direction: int,
            slippage_pips: float,
            pip_size: float,
        ) -> float:
            buffer = slippage_pips * pip_size
            if direction == 1:
                return stop_loss - buffer
            return stop_loss + buffer

        risk_mod.apply_slippage_buffer.side_effect = _mock_apply_slippage

        # order_manager (module 3)
        order_mod = strategy._modules.order_manager
        order_mod.create_bracket_order.return_value = {
            "is_valid": True,
            "direction": 1,
            "entry_price": 1.0850,
            "stop_loss": original_sl,
            "take_profit": 1.0910,
            "lot_size": 0.10,
            "risk_pips": 20.0,
            "reward_pips": 60.0,
        }
        order_mod.lots_to_units.return_value = 1000

        # Executor place_bracket_order with fillable trades
        mock_trade = MagicMock()
        mock_trade.filledEvent = MagicMock()
        mock_trade.filledEvent.__iadd__ = lambda self, h: self
        mock_trade.filledEvent.wait = AsyncMock()
        place_mock = AsyncMock(return_value=[mock_trade])
        monkeypatch.setattr(strategy._executor, "place_bracket_order", place_mock)

        result = await strategy._lifecycle._execute_signal(state, signal, pip_size)

        assert result is True
        # Verify apply_slippage_buffer was called
        risk_mod.apply_slippage_buffer.assert_called_once_with(
            stop_loss=original_sl,
            direction=1,
            slippage_pips=DEFAULT_MARKET_SLIPPAGE_PIPS,
            pip_size=pip_size,
        )

        # Verify the widened SL was passed to place_bracket_order
        call_kwargs = place_mock.call_args
        expected_sl = original_sl - (DEFAULT_MARKET_SLIPPAGE_PIPS * pip_size)
        assert abs(call_kwargs.kwargs["stop_loss"] - expected_sl) < 1e-10

    @pytest.mark.asyncio()
    async def test_sl_widened_by_slippage_buffer_sell(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SELL signal: SL should be raised by market slippage buffer."""
        strategy = _make_strategy()
        state = StrategyState(pair="EURUSD")
        pip_size = 0.0001

        signal: dict[str, Any] = {
            "detected": True,
            "signal": -1,
            "entry_price": 1.0850,
            "stop_loss": 1.0870,
            "take_profit": 1.0790,
            "risk_pips": 20.0,
        }

        monkeypatch.setattr(
            strategy._rt_feed, "get_mid_price", AsyncMock(return_value=0.0)
        )
        monkeypatch.setattr(
            strategy._rt_feed,
            "get_live_spread",
            AsyncMock(return_value=0.00010),
        )
        monkeypatch.setattr(
            strategy._executor,
            "get_account_equity",
            AsyncMock(return_value=10000.0),
        )

        risk_mod = strategy._modules.risk_manager
        risk_mod.calculate_position_size.return_value = {
            "is_valid": True,
            "lot_size": 0.10,
            "units": 1000,
            "risk_amount": 100.0,
        }
        original_sl = 1.0870

        def _mock_apply_slippage(
            stop_loss: float,
            direction: int,
            slippage_pips: float,
            pip_size: float,
        ) -> float:
            buffer = slippage_pips * pip_size
            if direction == 1:
                return stop_loss - buffer
            return stop_loss + buffer

        risk_mod.apply_slippage_buffer.side_effect = _mock_apply_slippage

        order_mod = strategy._modules.order_manager
        order_mod.create_bracket_order.return_value = {
            "is_valid": True,
            "direction": -1,
            "entry_price": 1.0850,
            "stop_loss": original_sl,
            "take_profit": 1.0790,
            "lot_size": 0.10,
            "risk_pips": 20.0,
            "reward_pips": 60.0,
        }
        order_mod.lots_to_units.return_value = 1000

        mock_trade = MagicMock()
        mock_trade.filledEvent = MagicMock()
        mock_trade.filledEvent.__iadd__ = lambda self, h: self
        mock_trade.filledEvent.wait = AsyncMock()
        place_mock = AsyncMock(return_value=[mock_trade])
        monkeypatch.setattr(strategy._executor, "place_bracket_order", place_mock)

        result = await strategy._lifecycle._execute_signal(state, signal, pip_size)

        assert result is True
        # Verify the widened SL was passed to place_bracket_order
        call_kwargs = place_mock.call_args
        expected_sl = original_sl + (DEFAULT_MARKET_SLIPPAGE_PIPS * pip_size)
        assert abs(call_kwargs.kwargs["stop_loss"] - expected_sl) < 1e-10


class TestReconnectBackoff:
    """Verify reconnect uses exponential backoff with jitter."""

    @pytest.mark.asyncio()
    async def test_reconnect_exponential_backoff(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """reconnect() should sleep with exponential delay + jitter."""
        from alphaedge.engine.broker import BrokerConnection

        with patch.object(BrokerConnection, "__init__", lambda self, *a, **kw: None):
            broker = BrokerConnection.__new__(BrokerConnection)
            mock_ib = MagicMock()
            mock_ib.isConnected.return_value = True
            object.__setattr__(broker, "_ib", mock_ib)
            object.__setattr__(broker, "_connected", False)

            # All connect attempts fail
            monkeypatch.setattr(broker, "connect", AsyncMock(return_value=False))
            monkeypatch.setattr(broker, "disconnect", AsyncMock())

            with (
                patch(
                    "alphaedge.engine.broker.asyncio.sleep",
                    new_callable=AsyncMock,
                ) as mock_sleep,
                patch(
                    "alphaedge.engine.broker.random.uniform",
                    return_value=0.5,
                ),
            ):
                result = await broker.reconnect(max_retries=3)

            assert result is False
            assert mock_sleep.await_count == 3
            # Exponential: 2^1+0.5=2.5, 2^2+0.5=4.5, 2^3+0.5=8.5
            calls = [c.args[0] for c in mock_sleep.await_args_list]
            assert calls == [2.5, 4.5, 8.5]

    @pytest.mark.asyncio()
    async def test_reconnect_delay_capped_at_30s(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Delay should be capped at 30 seconds even for high attempt."""
        from alphaedge.engine.broker import BrokerConnection

        with patch.object(BrokerConnection, "__init__", lambda self, *a, **kw: None):
            broker = BrokerConnection.__new__(BrokerConnection)
            mock_ib = MagicMock()
            mock_ib.isConnected.return_value = True
            object.__setattr__(broker, "_ib", mock_ib)
            object.__setattr__(broker, "_connected", False)

            monkeypatch.setattr(broker, "connect", AsyncMock(return_value=False))
            monkeypatch.setattr(broker, "disconnect", AsyncMock())

            with (
                patch(
                    "alphaedge.engine.broker.asyncio.sleep",
                    new_callable=AsyncMock,
                ) as mock_sleep,
                patch(
                    "alphaedge.engine.broker.random.uniform",
                    return_value=0.5,
                ),
            ):
                result = await broker.reconnect(max_retries=6)

            assert result is False
            calls = [c.args[0] for c in mock_sleep.await_args_list]
            # 2^5+0.5=32.5 → capped to 30, 2^6+0.5=64.5 → capped to 30
            assert all(d <= 30.0 for d in calls)
