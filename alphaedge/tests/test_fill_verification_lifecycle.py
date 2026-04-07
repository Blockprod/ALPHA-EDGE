# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/tests/test_fill_verification_lifecycle.py
# DESCRIPTION  : Tests for P0-01/02/03/04 fill verification improvements
# AUTHOR       : ALPHAEDGE Dev Team
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-04-06
# ============================================================
"""
P0 fill-verification lifecycle tests.

Covers the new polling-based fill confirmation (P0-01), slippage guard
(P0-02), fill_status field (P0-03), and SL/TP child-order callbacks (P0-04).
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alphaedge.config.loader import AppConfig, IBConfig, TradingConfig
from alphaedge.engine.strategy import CoreModules, SwingStrategy
from alphaedge.utils.state_persistence import clear_daily_state

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_trade(
    *,
    status: str = "Filled",
    remaining: float = 0.0,
    avg_fill: float | None = None,
) -> MagicMock:
    """Build a minimal ib_insync Trade mock with configurable orderStatus."""
    trade = MagicMock()
    trade.filledEvent = MagicMock()
    trade.filledEvent.__iadd__ = lambda self, _h: self

    os_mock = MagicMock()
    os_mock.status = status
    os_mock.remaining = remaining
    os_mock.avgFillPrice = avg_fill  # None → _record_fill uses entry_price fallback
    trade.orderStatus = os_mock
    return trade


def _build_strategy() -> SwingStrategy:
    cfg = AppConfig()
    cfg.ib = IBConfig(is_paper=True)
    cfg.trading = TradingConfig()
    cfg.trading.pairs = ["EURUSD"]

    with (
        patch("alphaedge.engine.strategy.BrokerConnection") as mock_broker_cls,
        patch("alphaedge.engine.strategy.OrderExecutor"),
        patch("alphaedge.engine.strategy.HistoricalDataFeed"),
        patch("alphaedge.engine.strategy.RealtimeDataFeed"),
        patch("alphaedge.engine.strategy._import_core_modules") as mock_mods,
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

        mock_mods.return_value = CoreModules(
            momentum_detector=MagicMock(),
            order_manager=order_mock,
            risk_manager=risk_mock,
        )
        return SwingStrategy(cfg)


def _signal() -> dict[str, Any]:
    return {
        "detected": True,
        "direction": 1,
        "entry_price": 1.2500,
        "stop_loss": 1.2450,
        "take_profit": 1.2600,
        "risk_pips": 50.0,
    }


@pytest.fixture(autouse=True)
def _cleanup() -> Generator[None, None, None]:
    yield
    clear_daily_state()


# ==================================================================
# P0-03 — fill_status field in LiveTradeRecord
# ==================================================================
class TestFillStatusTracking:
    """fill_status field reflects the actual IB fill type."""

    @pytest.mark.asyncio()
    async def test_full_fill_sets_status_full(self) -> None:
        """orderStatus.remaining == 0 → fill_status='full'."""
        strategy = _build_strategy()
        state = strategy._init_pair_state("EURUSD")
        state.starting_equity = 10000.0
        state.current_equity = 10000.0

        strategy._rt_feed.get_live_spread = AsyncMock(return_value=0.00008)
        strategy._rt_feed.get_mid_price = AsyncMock(return_value=1.25)

        trade = _make_trade(status="Filled", remaining=0.0)
        strategy._executor.place_bracket_order = AsyncMock(return_value=[trade])

        result = await strategy._lifecycle._execute_signal(state, _signal(), 0.0001)

        assert result is True
        assert state.live_record is not None
        assert state.live_record.fill_status == "full"

    @pytest.mark.asyncio()
    async def test_partial_fill_sets_status_partial(self) -> None:
        """orderStatus.remaining > 0 → fill_status='partial', trade still opens."""
        strategy = _build_strategy()
        state = strategy._init_pair_state("EURUSD")
        state.starting_equity = 10000.0
        state.current_equity = 10000.0

        strategy._rt_feed.get_live_spread = AsyncMock(return_value=0.00008)
        strategy._rt_feed.get_mid_price = AsyncMock(return_value=1.25)

        trade = _make_trade(status="Filled", remaining=200.0)
        strategy._executor.place_bracket_order = AsyncMock(return_value=[trade])

        result = await strategy._lifecycle._execute_signal(state, _signal(), 0.0001)

        assert result is True
        assert state.live_record is not None
        assert state.live_record.fill_status == "partial"
        assert state.is_position_open is True


# ==================================================================
# P0-01 — Order rejection detection
# ==================================================================
class TestOrderRejection:
    """Rejected bracket orders must abort execution and cancel all children."""

    @pytest.mark.asyncio()
    @pytest.mark.parametrize("status", ["Cancelled", "Inactive", "ApiCancelled"])
    async def test_rejected_order_returns_false(self, status: str) -> None:
        """Any IB rejection status prevents position opening."""
        strategy = _build_strategy()
        state = strategy._init_pair_state("EURUSD")
        state.starting_equity = 10000.0
        state.current_equity = 10000.0

        strategy._rt_feed.get_live_spread = AsyncMock(return_value=0.00008)
        strategy._rt_feed.get_mid_price = AsyncMock(return_value=1.25)
        strategy._executor.cancel_all_orders = AsyncMock()

        trade = _make_trade(status=status)
        strategy._executor.place_bracket_order = AsyncMock(return_value=[trade])

        result = await strategy._lifecycle._execute_signal(state, _signal(), 0.0001)

        assert result is False
        assert state.is_position_open is False
        assert state.trades_today == 0
        strategy._executor.cancel_all_orders.assert_awaited_once()

    @pytest.mark.asyncio()
    async def test_fill_timeout_cancels_bracket(self) -> None:
        """IB_FILL_TIMEOUT_SECONDS exceeded → cancel + return False."""
        strategy = _build_strategy()
        state = strategy._init_pair_state("EURUSD")
        state.starting_equity = 10000.0
        state.current_equity = 10000.0

        strategy._rt_feed.get_live_spread = AsyncMock(return_value=0.00008)
        strategy._rt_feed.get_mid_price = AsyncMock(return_value=1.25)
        strategy._executor.cancel_all_orders = AsyncMock()

        # Trade whose status never becomes "Filled"
        trade = _make_trade(status="PreSubmitted")
        strategy._executor.place_bracket_order = AsyncMock(return_value=[trade])

        with patch(
            "alphaedge.engine.session_lifecycle.IB_FILL_TIMEOUT_SECONDS",
            0.01,
        ):
            result = await strategy._lifecycle._execute_signal(state, _signal(), 0.0001)

        assert result is False
        assert state.is_position_open is False
        strategy._executor.cancel_all_orders.assert_awaited_once()


# ==================================================================
# P0-02 — Slippage guard
# ==================================================================
class TestSlippageGuard:
    """Excessive entry slippage is recorded; trade still opens (warn-only)."""

    @pytest.mark.asyncio()
    async def test_excessive_slippage_still_opens_trade(self) -> None:
        """Guard logs WARNING but does NOT abort the trade."""
        strategy = _build_strategy()
        strategy._config.trading.max_entry_slippage_pips = 1.0  # tight threshold
        state = strategy._init_pair_state("EURUSD")
        state.starting_equity = 10000.0
        state.current_equity = 10000.0

        strategy._rt_feed.get_live_spread = AsyncMock(return_value=0.00008)
        strategy._rt_feed.get_mid_price = AsyncMock(return_value=1.25)

        # avgFillPrice = 1.2510 → slippage = 10 pips >> threshold of 1.0
        trade = _make_trade(status="Filled", remaining=0.0, avg_fill=1.2510)
        strategy._executor.place_bracket_order = AsyncMock(return_value=[trade])

        result = await strategy._lifecycle._execute_signal(state, _signal(), 0.0001)

        assert result is True
        assert state.live_record is not None
        assert state.live_record.slippage_pips == pytest.approx(10.0)
        assert state.is_position_open is True

    @pytest.mark.asyncio()
    async def test_slippage_within_threshold_records_correctly(self) -> None:
        """Slippage below threshold: fill_price and slippage_pips are correct."""
        strategy = _build_strategy()
        strategy._config.trading.max_entry_slippage_pips = 3.0
        state = strategy._init_pair_state("EURUSD")
        state.starting_equity = 10000.0
        state.current_equity = 10000.0

        strategy._rt_feed.get_live_spread = AsyncMock(return_value=0.00008)
        strategy._rt_feed.get_mid_price = AsyncMock(return_value=1.25)

        # avgFillPrice = 1.2501 → slippage = 1.0 pip (< threshold)
        trade = _make_trade(status="Filled", remaining=0.0, avg_fill=1.2501)
        strategy._executor.place_bracket_order = AsyncMock(return_value=[trade])

        result = await strategy._lifecycle._execute_signal(state, _signal(), 0.0001)

        assert result is True
        assert state.live_record is not None
        assert state.live_record.fill_price == pytest.approx(1.2501)
        assert state.live_record.slippage_pips == pytest.approx(1.0)
        assert state.live_record.fill_status == "full"


# ==================================================================
# P0-04 — SL/TP child order callbacks
# ==================================================================
class TestChildOrderCallbacks:
    """SL and TP child orders must have filledEvent callbacks registered."""

    @pytest.mark.asyncio()
    async def test_child_orders_register_filled_callback(self) -> None:
        """_record_fill registers _on_trade_closed on trades[1:]."""
        strategy = _build_strategy()
        state = strategy._init_pair_state("EURUSD")
        state.starting_equity = 10000.0
        state.current_equity = 10000.0

        strategy._rt_feed.get_live_spread = AsyncMock(return_value=0.00008)
        strategy._rt_feed.get_mid_price = AsyncMock(return_value=1.25)

        parent_trade = _make_trade(status="Filled", remaining=0.0)

        tp_callbacks: list[Any] = []
        sl_callbacks: list[Any] = []

        tp_trade: MagicMock = MagicMock()
        tp_trade.filledEvent.__iadd__ = lambda self, cb, _bag=tp_callbacks: (
            _bag.append(cb) or self
        )

        sl_trade: MagicMock = MagicMock()
        sl_trade.filledEvent.__iadd__ = lambda self, cb, _bag=sl_callbacks: (
            _bag.append(cb) or self
        )

        strategy._executor.place_bracket_order = AsyncMock(
            return_value=[parent_trade, tp_trade, sl_trade]
        )

        result = await strategy._lifecycle._execute_signal(state, _signal(), 0.0001)

        assert result is True
        assert len(tp_callbacks) == 1, (
            "TP child must have exactly one filledEvent callback"
        )
        assert len(sl_callbacks) == 1, (
            "SL child must have exactly one filledEvent callback"
        )

    @pytest.mark.asyncio()
    async def test_tp_sl_order_ids_stored_in_state(self) -> None:
        """_record_fill stores TP and SL orderId values in StrategyState."""
        strategy = _build_strategy()
        state = strategy._init_pair_state("EURUSD")
        state.starting_equity = 10000.0
        state.current_equity = 10000.0

        strategy._rt_feed.get_live_spread = AsyncMock(return_value=0.00008)
        strategy._rt_feed.get_mid_price = AsyncMock(return_value=1.25)

        parent_trade = _make_trade(status="Filled", remaining=0.0)

        tp_trade: MagicMock = MagicMock()
        tp_trade.order.orderId = 1001
        tp_trade.filledEvent.__iadd__ = lambda self, _h: self

        sl_trade: MagicMock = MagicMock()
        sl_trade.order.orderId = 1002
        sl_trade.filledEvent.__iadd__ = lambda self, _h: self

        strategy._executor.place_bracket_order = AsyncMock(
            return_value=[parent_trade, tp_trade, sl_trade]
        )

        await strategy._lifecycle._execute_signal(state, _signal(), 0.0001)

        assert state._tp_order_id == 1001
        assert state._sl_order_id == 1002
