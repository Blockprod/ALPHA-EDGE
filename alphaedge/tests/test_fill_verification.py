# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_fill_verification.py
# DESCRIPTION  : Tests for P1-02 bracket fill verification
# AUTHOR       : ALPHAEDGE Dev Team
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-08
# ============================================================
"""ALPHAEDGE — Verify bracket fill is checked before state update."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alphaedge.config.loader import AppConfig, IBConfig, TradingConfig
from alphaedge.engine.strategy import CoreModules, FCRStrategy
from alphaedge.utils.state_persistence import clear_daily_state


class _FilledEvent:
    """
    Minimal ib_insync-style event stub.

    Supports:
    - ``event += callback`` (ib_insync callback registration)
    - ``await event.wait()`` (asyncio-style one-shot wait)
    """

    def __init__(self, *, preset: bool = True) -> None:
        self._callbacks: list[Any] = []
        self._asyncio_event = asyncio.Event()
        if preset:
            self._asyncio_event.set()  # resolves immediately

    def __iadd__(self, cb: Any) -> _FilledEvent:
        self._callbacks.append(cb)
        return self

    async def wait(self) -> None:
        await self._asyncio_event.wait()


class _MockTrade:
    """
    Minimal ib_insync Trade stub.

    Using a plain Python class (not ``MagicMock``) ensures that
    ``trade.filledEvent += cb`` goes through ``object.__setattr__``,
    never triggering ``MagicMock``'s ``MagicProxy`` creation which
    would accidentally create an unawaited ``_FilledEvent.wait`` coroutine.
    """

    def __init__(self, fill_event: _FilledEvent) -> None:
        self.filledEvent = fill_event


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _make_config() -> AppConfig:
    return AppConfig(
        ib=IBConfig(is_paper=True),
        trading=TradingConfig(pairs=["EURUSD"]),
    )


def _build_strategy() -> FCRStrategy:
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
        strategy = FCRStrategy(_make_config())
    return strategy


def _make_signal() -> dict[str, Any]:
    return {
        "detected": True,
        "signal": 1,
        "entry_price": 1.2500,
        "stop_loss": 1.2450,
        "take_profit": 1.2600,
        "risk_pips": 50.0,
    }


@pytest.fixture(autouse=True)
def _cleanup_state_file() -> Generator[None, None, None]:
    yield
    clear_daily_state()


# ==================================================================
# Tests
# ==================================================================
class TestEmptyTradesReturned:
    """Verify _execute_signal returns False when no trades placed."""

    @pytest.mark.asyncio()
    async def test_empty_trades_blocks_execution(self) -> None:
        strategy = _build_strategy()
        state = strategy._init_pair_state("EURUSD")
        state.starting_equity = 10000.0
        state.current_equity = 10000.0

        strategy._rt_feed.get_live_spread = AsyncMock(return_value=0.00008)
        strategy._rt_feed.get_mid_price = AsyncMock(return_value=1.25)
        strategy._executor.place_bracket_order = AsyncMock(return_value=[])

        result = await strategy._lifecycle._execute_signal(
            state, _make_signal(), 0.0001
        )

        assert result is False
        assert state.is_position_open is False
        assert state.trades_today == 0


class TestFillTimeoutCancels:
    """Verify fill timeout triggers cancel and returns False."""

    @pytest.mark.asyncio()
    async def test_timeout_cancels_bracket(self) -> None:
        strategy = _build_strategy()
        state = strategy._init_pair_state("EURUSD")
        state.starting_equity = 10000.0
        state.current_equity = 10000.0

        strategy._rt_feed.get_live_spread = AsyncMock(return_value=0.00008)
        strategy._rt_feed.get_mid_price = AsyncMock(return_value=1.25)

        mock_trade = _MockTrade(_FilledEvent(preset=False))  # never resolves → timeout
        strategy._executor.place_bracket_order = AsyncMock(
            return_value=[mock_trade],
        )
        strategy._executor.cancel_all_orders = AsyncMock()

        async def _timeout_and_close(coro: Any, *args: Any, **kwargs: Any) -> None:
            # Close the coroutine so CPython does not emit
            # "coroutine was never awaited" when it is GC'd.
            coro.close()
            raise TimeoutError

        with patch(
            "alphaedge.engine.session_lifecycle.asyncio.wait_for",
            _timeout_and_close,
        ):
            result = await strategy._lifecycle._execute_signal(
                state, _make_signal(), 0.0001
            )

        assert result is False
        assert state.is_position_open is False
        strategy._executor.cancel_all_orders.assert_awaited_once()


class TestSuccessfulFill:
    """Verify successful fill sets position open."""

    @pytest.mark.asyncio()
    async def test_filled_trade_sets_position_open(self) -> None:
        strategy = _build_strategy()
        state = strategy._init_pair_state("EURUSD")
        state.starting_equity = 10000.0
        state.current_equity = 10000.0

        strategy._rt_feed.get_live_spread = AsyncMock(return_value=0.00008)
        strategy._rt_feed.get_mid_price = AsyncMock(return_value=1.25)

        mock_trade = _MockTrade(_FilledEvent(preset=True))
        strategy._executor.place_bracket_order = AsyncMock(
            return_value=[mock_trade],
        )

        result = await strategy._lifecycle._execute_signal(
            state, _make_signal(), 0.0001
        )

        assert result is True
        assert state.is_position_open is True
        assert state.trades_today == 1
