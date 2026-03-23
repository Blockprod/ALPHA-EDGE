# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_broker_margin_safety.py
# DESCRIPTION  : Tests for fail-closed margin checks
# AUTHOR       : ALPHAEDGE Dev Team
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-22
# ============================================================
"""ALPHAEDGE — Verify broker margin checks fail closed."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from alphaedge.config.loader import IBConfig
from alphaedge.engine.broker import BrokerConnection, OrderExecutor


class TestBrokerMarginSafety:
    """Verify account summary failures block order submission."""

    def test_margin_check_blocks_when_available_funds_missing(self) -> None:
        broker = BrokerConnection(IBConfig(is_paper=True))
        broker.ib.accountSummary = MagicMock(return_value=[])
        executor = OrderExecutor(broker)

        allowed = executor._check_margin(quantity=1000, entry_price=1.10)

        assert allowed is False


class TestBrokerErrorPolicies:
    """Verify explicit broker error policies remain fail-closed."""

    @pytest.mark.asyncio()
    async def test_connect_timeout_is_classified_and_counted(self) -> None:
        broker = BrokerConnection(IBConfig(is_paper=True))
        broker.ib.connectAsync = AsyncMock(side_effect=TimeoutError)

        result = await broker.connect()

        assert result is False
        assert broker._consecutive_failures == 1

    @pytest.mark.asyncio()
    async def test_place_bracket_runtime_failure_returns_empty(self) -> None:
        broker = BrokerConnection(IBConfig(is_paper=True))
        broker.ib.isConnected = MagicMock(return_value=True)
        broker.ib.placeOrder = MagicMock(side_effect=RuntimeError("ib boom"))
        executor = OrderExecutor(broker)
        executor._throttler.acquire = AsyncMock(return_value=None)
        executor._check_margin = MagicMock(return_value=True)

        trades = await executor.place_bracket_order(
            pair="EURUSD",
            direction=1,
            quantity=1000,
            entry_price=1.10,
            stop_loss=1.09,
            take_profit=1.12,
        )

        assert trades == []

    @pytest.mark.asyncio()
    async def test_get_account_equity_raises_on_invalid_numeric_value(self) -> None:
        broker = BrokerConnection(IBConfig(is_paper=True))
        broker.ib.isConnected = MagicMock(return_value=True)
        broker.ib.accountSummary = MagicMock(
            return_value=[MagicMock(tag="NetLiquidation", value="not-a-number")]
        )
        executor = OrderExecutor(broker)
        executor._throttler.acquire = AsyncMock(return_value=None)

        with pytest.raises(ValueError):
            await executor.get_account_equity()

    def test_margin_check_blocks_on_summary_exception(self) -> None:
        broker = BrokerConnection(IBConfig(is_paper=True))
        broker.ib.accountSummary = MagicMock(side_effect=RuntimeError("boom"))
        executor = OrderExecutor(broker)

        allowed = executor._check_margin(quantity=1000, entry_price=1.10)

        assert allowed is False
