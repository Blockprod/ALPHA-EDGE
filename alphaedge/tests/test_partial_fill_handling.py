# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/tests/test_partial_fill_handling.py
# DESCRIPTION  : B-05 — partial fill detection: cancel + no position
# SCENARIO     : partial fill cancels all legs; fill_status in CSV
# ============================================================
"""B-05 — Verify partial fill cancels all bracket legs and refuses position."""

from __future__ import annotations

import csv
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alphaedge.config.loader import AppConfig, IBConfig, TradingConfig
from alphaedge.engine.live_journal import CSV_HEADERS, append_live_trade_csv
from alphaedge.engine.live_types import LiveTradeRecord
from alphaedge.engine.strategy import CoreModules, SwingStrategy
from alphaedge.utils.state_persistence import clear_daily_state


# ------------------------------------------------------------------
# Minimal trade stub
# ------------------------------------------------------------------
class _MockTrade:
    """Minimal ib_insync Trade stub with configurable fill status."""

    def __init__(self, *, status: str = "Filled", remaining: float = 0.0) -> None:
        status_mock = MagicMock()
        status_mock.status = status
        status_mock.remaining = remaining
        status_mock.avgFillPrice = 1.2502
        self.orderStatus: Any = status_mock
        self.filledEvent: list[Any] = []
        self.order = MagicMock()
        self.order.orderId = 42


# ------------------------------------------------------------------
# Strategy builder (mirrors test_fill_verification.py)
# ------------------------------------------------------------------
def _make_config() -> AppConfig:
    cfg = AppConfig()
    cfg.ib = IBConfig(is_paper=True)
    cfg.trading = TradingConfig()
    cfg.trading.pairs = ["EURUSD"]
    return cfg


def _build_strategy() -> SwingStrategy:
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
            momentum_detector=MagicMock(),
            order_manager=order_mock,
            risk_manager=risk_mock,
        )
        strategy = SwingStrategy(_make_config())
    return strategy


def _make_signal() -> dict[str, Any]:
    return {
        "detected": True,
        "direction": 1,
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
# Tests — partial fill cancels position
# ==================================================================
class TestPartialFillCancelsPosition:
    """Partial fill (remaining > 0) must cancel all legs; no position opened."""

    @pytest.mark.asyncio()
    async def test_partial_fill_returns_false(self) -> None:
        """_execute_signal returns False when parent fill is partial."""
        strategy = _build_strategy()
        state = strategy._init_pair_state("EURUSD")
        state.starting_equity = 10000.0
        state.current_equity = 10000.0

        strategy._rt_feed.get_live_spread = AsyncMock(return_value=0.00008)
        strategy._rt_feed.get_mid_price = AsyncMock(return_value=1.25)

        # Partial fill: 500 units remaining out of 1000 requested
        parent = _MockTrade(status="Filled", remaining=500.0)
        sl_leg = _MockTrade(status="Submitted", remaining=0.0)
        tp_leg = _MockTrade(status="Submitted", remaining=0.0)
        strategy._executor.place_bracket_order = AsyncMock(
            return_value=[parent, tp_leg, sl_leg]
        )
        strategy._executor.cancel_all_orders = AsyncMock()

        result = await strategy._lifecycle._execute_signal(
            state, _make_signal(), 0.0001
        )

        assert result is False

    @pytest.mark.asyncio()
    async def test_partial_fill_position_not_opened(self) -> None:
        """Position state must not be set to open after a partial fill."""
        strategy = _build_strategy()
        state = strategy._init_pair_state("EURUSD")
        state.starting_equity = 10000.0
        state.current_equity = 10000.0

        strategy._rt_feed.get_live_spread = AsyncMock(return_value=0.00008)
        strategy._rt_feed.get_mid_price = AsyncMock(return_value=1.25)

        parent = _MockTrade(status="Filled", remaining=200.0)
        strategy._executor.place_bracket_order = AsyncMock(
            return_value=[parent, _MockTrade(), _MockTrade()]
        )
        strategy._executor.cancel_all_orders = AsyncMock()

        await strategy._lifecycle._execute_signal(state, _make_signal(), 0.0001)

        assert state.is_position_open is False
        assert state.trades_today == 0

    @pytest.mark.asyncio()
    async def test_partial_fill_triggers_cancel_all_orders(self) -> None:
        """cancel_all_orders must be called exactly once on partial fill."""
        strategy = _build_strategy()
        state = strategy._init_pair_state("EURUSD")
        state.starting_equity = 10000.0
        state.current_equity = 10000.0

        strategy._rt_feed.get_live_spread = AsyncMock(return_value=0.00008)
        strategy._rt_feed.get_mid_price = AsyncMock(return_value=1.25)

        parent = _MockTrade(status="Filled", remaining=1.0)
        strategy._executor.place_bracket_order = AsyncMock(
            return_value=[parent, _MockTrade(), _MockTrade()]
        )
        strategy._executor.cancel_all_orders = AsyncMock()

        await strategy._lifecycle._execute_signal(state, _make_signal(), 0.0001)

        strategy._executor.cancel_all_orders.assert_awaited_once()


# ==================================================================
# Tests — live journal fill_status column
# ==================================================================
class TestLiveJournalFillStatusColumn:
    """fill_status must appear in CSV headers and written rows."""

    def test_fill_status_in_csv_headers(self) -> None:
        """CSV_HEADERS must include fill_status column."""
        assert "fill_status" in CSV_HEADERS

    def test_fill_status_written_to_csv(self, tmp_path: Path) -> None:
        """append_live_trade_csv writes fill_status value to output file."""
        record = LiveTradeRecord(
            pair="EURUSD",
            direction=1,
            entry_price=1.2500,
            fill_price=1.2502,
            stop_loss=1.2450,
            take_profit=1.2600,
            lot_size=0.01,
            sl_pips=50.0,
            spread_pips=0.8,
            exchange_rate=1.0,
            entry_time=datetime(2026, 4, 14, 14, 30, tzinfo=UTC),
            exit_price=1.2600,
            exit_time=datetime(2026, 4, 14, 15, 0, tzinfo=UTC),
            pnl_pips=100.0,
            pnl_usd=10.0,
            outcome="win",
            exit_reason="tp_hit",
            fill_status="full",
        )

        with patch("alphaedge.engine.live_journal.LIVE_JOURNAL_DIR", str(tmp_path)):
            append_live_trade_csv(record)

        csv_file = tmp_path / "live_trades_2026-04-14.csv"
        assert csv_file.exists()
        with open(csv_file, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        assert rows[0]["fill_status"] == "full"
