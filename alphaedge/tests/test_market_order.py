# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_market_order.py
# DESCRIPTION  : Tests for Market entry bracket order (T2.5)
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-08
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: market order bracket tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from alphaedge.config.constants import (
    DEFAULT_MARKET_SLIPPAGE_PIPS,
    DEFAULT_SLIPPAGE_PIPS,
)


# ------------------------------------------------------------------
# Helper
# ------------------------------------------------------------------
def _build_executor() -> tuple[Any, list[Any]]:
    """Build an OrderExecutor with mocked broker, return (executor, placed)."""
    from alphaedge.engine.broker import BrokerConnection, OrderExecutor

    with patch.object(BrokerConnection, "__init__", lambda self, *a, **kw: None):
        broker = BrokerConnection.__new__(BrokerConnection)
        mock_ib = MagicMock()
        object.__setattr__(broker, "_ib", mock_ib)
        object.__setattr__(broker, "_throttler", MagicMock())

        placed: list[Any] = []

        def _capture(contract: Any, order: Any) -> MagicMock:
            placed.append(order)
            return MagicMock()

        mock_ib.placeOrder = MagicMock(side_effect=_capture)

        executor = OrderExecutor(broker)
        return executor, placed


# ==================================================================
# Broker bracket order tests
# ==================================================================
class TestMarketEntryBracket:
    """Verify bracket order uses MarketOrder entry with correct children."""

    def test_parent_is_market_order(self) -> None:
        """Entry parent should be a MarketOrder, not LimitOrder."""
        executor, placed = _build_executor()
        executor._submit_bracket(
            contract=MagicMock(),
            action="BUY",
            quantity=1000,
            take_profit=1.0900,
            stop_loss=1.0800,
        )

        assert len(placed) == 3
        assert type(placed[0]).__name__ == "MarketOrder"

    def test_children_types_and_linking(self) -> None:
        """TP should be LimitOrder, SL should be StopOrder, both linked."""
        executor, placed = _build_executor()
        executor._submit_bracket(
            contract=MagicMock(),
            action="SELL",
            quantity=500,
            take_profit=1.0700,
            stop_loss=1.0900,
        )

        parent, tp_child, sl_child = placed[0], placed[1], placed[2]

        assert type(tp_child).__name__ == "LimitOrder"
        assert type(sl_child).__name__ == "StopOrder"

        # Children linked to parent
        assert tp_child.parentId == parent.orderId
        assert sl_child.parentId == parent.orderId

    def test_transmit_flags(self) -> None:
        """Parent and TP: transmit=False, SL (last): transmit=True."""
        executor, placed = _build_executor()
        executor._submit_bracket(
            contract=MagicMock(),
            action="BUY",
            quantity=1000,
            take_profit=1.0900,
            stop_loss=1.0800,
        )

        assert placed[0].transmit is False
        assert placed[1].transmit is False
        assert placed[2].transmit is True

    def test_reverse_action_applied(self) -> None:
        """Children should use the reverse action of the parent."""
        executor, placed = _build_executor()
        executor._submit_bracket(
            contract=MagicMock(),
            action="BUY",
            quantity=1000,
            take_profit=1.0900,
            stop_loss=1.0800,
        )

        # Parent is BUY → children are SELL
        assert placed[0].action == "BUY"
        assert placed[1].action == "SELL"
        assert placed[2].action == "SELL"


# ==================================================================
# Backtest slippage tests
# ==================================================================
class TestBacktestMarketSlippage:
    """Verify backtest spread cost includes market slippage component."""

    def test_market_slippage_constant_exists(self) -> None:
        """DEFAULT_MARKET_SLIPPAGE_PIPS should be defined and positive."""
        assert DEFAULT_MARKET_SLIPPAGE_PIPS > 0

    def test_combined_slippage_greater_than_base(self) -> None:
        """Combined slippage should exceed base slippage alone."""
        combined = DEFAULT_SLIPPAGE_PIPS + DEFAULT_MARKET_SLIPPAGE_PIPS
        assert combined > DEFAULT_SLIPPAGE_PIPS
