# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/tests/test_live_journal_outcome.py
# DESCRIPTION  : B-04-B — outcome and exit_reason fields in _on_trade_closed
# SCENARIO     : TP/SL filled IB trade → correct outcome + exit_reason recorded
# ============================================================
"""
B-04-B: outcome and exit_reason must never be 'unknown' when IB fill data
is available. Tests exercise _on_trade_closed with TP/SL IB trade mocks
carrying orderId, avgFillPrice, and fills.
"""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from alphaedge.config.loader import AppConfig
from alphaedge.engine.live_types import LiveTradeRecord
from alphaedge.engine.strategy import CoreModules, SwingStrategy
from alphaedge.utils.state_persistence import clear_daily_state

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _build_strategy() -> SwingStrategy:
    cfg = AppConfig()
    cfg.ib.is_paper = True
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
        mock_mods.return_value = CoreModules(
            momentum_detector=MagicMock(),
            order_manager=MagicMock(),
            risk_manager=MagicMock(),
        )
        return SwingStrategy(cfg)


def _make_ib_trade(*, order_id: int, avg_fill_price: float) -> MagicMock:
    """Minimal ib_insync Trade mock carrying orderId and avgFillPrice."""
    order = MagicMock()
    order.orderId = order_id

    order_status = MagicMock()
    order_status.avgFillPrice = avg_fill_price

    trade = MagicMock()
    trade.order = order
    trade.orderStatus = order_status
    trade.fills = []  # avgFillPrice is already set on orderStatus
    return trade


def _open_position(
    strategy: SwingStrategy,
    *,
    tp_order_id: int = 101,
    sl_order_id: int = 102,
    entry_price: float = 1.2500,
    direction: int = 1,
) -> None:
    """Seed a pair state as if a trade was entered."""
    state = strategy._init_pair_state("EURUSD")
    state.starting_equity = 10_000.0
    state.current_equity = 10_000.0
    state.is_position_open = True
    state._tp_order_id = tp_order_id
    state._sl_order_id = sl_order_id

    record = LiveTradeRecord(
        pair="EURUSD",
        direction=direction,
        entry_price=entry_price,
        fill_price=entry_price,
        stop_loss=entry_price - 0.0050,
        take_profit=entry_price + 0.0100,
        lot_size=0.01,
        sl_pips=50.0,
        spread_pips=0.2,
        exchange_rate=1.0,
        entry_time=datetime(2026, 4, 15, 13, 30, tzinfo=UTC),
    )
    state.live_record = record


@pytest.fixture(autouse=True)
def _cleanup() -> Generator[None, None, None]:
    yield
    clear_daily_state()


# ==================================================================
# Tests
# ==================================================================


class TestExitReasonTpHit:
    """TP child fill → exit_reason='tp_hit', outcome='win' or 'loss'."""

    @pytest.mark.asyncio()
    async def test_tp_fill_sets_tp_hit(self) -> None:
        """orderId matches _tp_order_id → exit_reason='tp_hit'."""
        strategy = _build_strategy()
        _open_position(
            strategy, tp_order_id=101, sl_order_id=102, entry_price=1.2500, direction=1
        )

        ib_trade = _make_ib_trade(order_id=101, avg_fill_price=1.2600)

        captured: list[LiveTradeRecord] = []
        with patch(
            "alphaedge.engine.session_lifecycle.append_live_trade_csv",
            side_effect=lambda r: captured.append(r),
        ):
            strategy._lifecycle._on_trade_closed("EURUSD", ib_trade)
            await asyncio.sleep(0.1)

        assert len(captured) == 1
        record = captured[0]
        assert record.exit_reason == "tp_hit"
        assert record.outcome == "win"
        assert record.exit_price == pytest.approx(1.2600)
        live_history = strategy.get_live_state()["trade_history"]
        assert len(live_history) == 1
        assert live_history[0]["pair"] == "EURUSD"
        assert live_history[0]["outcome"] == "win"

    @pytest.mark.asyncio()
    async def test_tp_fill_with_int_subtype_order_id(self) -> None:
        """orderId stored in state as int, ib_trade may carry compatible int."""
        strategy = _build_strategy()
        _open_position(
            strategy, tp_order_id=999, sl_order_id=1000, entry_price=1.0800, direction=1
        )

        # Simulate ib_insync returning a subclass of int for orderId
        class _IBInt(int):
            pass

        ib_trade = _make_ib_trade(order_id=_IBInt(999), avg_fill_price=1.0850)

        captured: list[LiveTradeRecord] = []
        with patch(
            "alphaedge.engine.session_lifecycle.append_live_trade_csv",
            side_effect=lambda r: captured.append(r),
        ):
            strategy._lifecycle._on_trade_closed("EURUSD", ib_trade)
            await asyncio.sleep(0.1)

        assert len(captured) == 1
        record = captured[0]
        assert record.exit_reason == "tp_hit", (
            f"Expected tp_hit, got {record.exit_reason!r} — int cast broken?"
        )


class TestExitReasonSlHit:
    """SL child fill → exit_reason='sl_hit', outcome='loss'."""

    @pytest.mark.asyncio()
    async def test_sl_fill_sets_sl_hit(self) -> None:
        """orderId matches _sl_order_id → exit_reason='sl_hit'."""
        strategy = _build_strategy()
        _open_position(
            strategy, tp_order_id=101, sl_order_id=102, entry_price=1.2500, direction=1
        )

        ib_trade = _make_ib_trade(order_id=102, avg_fill_price=1.2450)

        captured: list[LiveTradeRecord] = []
        with patch(
            "alphaedge.engine.session_lifecycle.append_live_trade_csv",
            side_effect=lambda r: captured.append(r),
        ):
            strategy._lifecycle._on_trade_closed("EURUSD", ib_trade)
            await asyncio.sleep(0.1)

        assert len(captured) == 1
        record = captured[0]
        assert record.exit_reason == "sl_hit"
        assert record.outcome == "loss"
        assert record.exit_price == pytest.approx(1.2450)


class TestExitReasonFallbacks:
    """Edge cases: no ib_trade, no match, fills fallback."""

    @pytest.mark.asyncio()
    async def test_no_ib_trade_outcome_unknown(self) -> None:
        """_on_trade_closed(pair) with no ib_trade → outcome='unknown' (harmless)."""
        strategy = _build_strategy()
        _open_position(strategy, tp_order_id=101, sl_order_id=102)

        captured: list[LiveTradeRecord] = []
        with patch(
            "alphaedge.engine.session_lifecycle.append_live_trade_csv",
            side_effect=lambda r: captured.append(r),
        ):
            strategy._lifecycle._on_trade_closed("EURUSD")  # no ib_trade
            await asyncio.sleep(0.1)

        assert len(captured) == 1
        record = captured[0]
        # Without ib_trade we cannot determine exit_reason — unknown is acceptable
        assert record.exit_reason == "unknown"
        assert record.outcome == "unknown"

    @pytest.mark.asyncio()
    async def test_fills_fallback_when_order_status_zero(self) -> None:
        """avgFillPrice=0 → fallback to fills[-1].execution.avgPrice."""
        strategy = _build_strategy()
        _open_position(
            strategy, tp_order_id=201, sl_order_id=202, entry_price=1.2500, direction=1
        )

        ib_trade = _make_ib_trade(order_id=201, avg_fill_price=0.0)
        # Provide fill execution as fallback
        fill_mock = MagicMock()
        fill_mock.execution.avgPrice = 1.2620
        ib_trade.fills = [fill_mock]

        captured: list[LiveTradeRecord] = []
        with patch(
            "alphaedge.engine.session_lifecycle.append_live_trade_csv",
            side_effect=lambda r: captured.append(r),
        ):
            strategy._lifecycle._on_trade_closed("EURUSD", ib_trade)
            await asyncio.sleep(0.1)

        assert len(captured) == 1
        record = captured[0]
        assert record.exit_price == pytest.approx(1.2620)
        assert record.outcome == "win"
        assert record.exit_reason == "tp_hit"
