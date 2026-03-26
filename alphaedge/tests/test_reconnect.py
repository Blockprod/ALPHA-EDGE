# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_reconnect.py
# DESCRIPTION  : Tests for IB disconnect recovery (T2.1)
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-08
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: IB reconnection tests."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alphaedge.config.loader import AppConfig, IBConfig, TradingConfig
from alphaedge.engine.broker import BrokerConnection
from alphaedge.engine.strategy import CoreModules, StrategyState, SwingStrategy


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _make_config(pairs: list[str] | None = None) -> AppConfig:
    """Build a minimal AppConfig for tests."""
    return AppConfig(
        ib=IBConfig(is_paper=True),
        trading=TradingConfig(pairs=pairs or ["EURUSD"]),
    )


# ------------------------------------------------------------------
# Helper to build an SwingStrategy with mocked externals
# ------------------------------------------------------------------
def _build_strategy(
    config: AppConfig | None = None,
) -> SwingStrategy:
    """Create SwingStrategy with mocked broker, feeds, and modules."""
    cfg = config or _make_config()
    with (
        patch("alphaedge.engine.strategy.BrokerConnection") as mock_broker_cls,
        patch("alphaedge.engine.strategy.OrderExecutor"),
        patch("alphaedge.engine.strategy.HistoricalDataFeed"),
        patch("alphaedge.engine.strategy.RealtimeDataFeed"),
        patch("alphaedge.engine.strategy._import_core_modules") as mock_modules,
    ):
        # Provide a mock IB instance with a disconnectedEvent list
        mock_ib = MagicMock()
        mock_ib.disconnectedEvent = MagicMock()
        mock_broker_cls.return_value.ib = mock_ib
        mock_modules.return_value = CoreModules(
            momentum_detector=MagicMock(),
            order_manager=MagicMock(),
            risk_manager=MagicMock(),
        )
        strategy = SwingStrategy(cfg)
    return strategy


# ==================================================================
# Tests
# ==================================================================
class TestDisconnectTriggersReconnect:
    """Verify that IB disconnect fires the reconnect handler."""

    def test_disconnect_event_wired(self) -> None:
        """disconnect handler is registered through BrokerConnection."""
        cfg = _make_config()
        with (
            patch("alphaedge.engine.strategy.BrokerConnection") as mock_broker_cls,
            patch("alphaedge.engine.strategy.OrderExecutor"),
            patch("alphaedge.engine.strategy.HistoricalDataFeed"),
            patch("alphaedge.engine.strategy.RealtimeDataFeed"),
            patch("alphaedge.engine.strategy._import_core_modules") as mock_mods,
        ):
            mock_ib = MagicMock()
            mock_broker_cls.return_value.ib = mock_ib
            mock_mods.return_value = CoreModules(
                momentum_detector=MagicMock(),
                order_manager=MagicMock(),
                risk_manager=MagicMock(),
            )
            strategy = SwingStrategy(cfg)

        mock_broker_cls.return_value.add_disconnect_handler.assert_called_once_with(
            strategy._lifecycle._on_ib_disconnect
        )

    def test_broker_rebinds_disconnect_handlers_on_client_reset(self) -> None:
        """Custom disconnect handlers survive IB client replacement."""

        class _Event:
            def __init__(self) -> None:
                self.handlers: list[Any] = []

            def __iadd__(self, handler: Any) -> _Event:
                self.handlers.append(handler)
                return self

        class _IBStub:
            def __init__(self) -> None:
                self.errorEvent = _Event()
                self.disconnectedEvent = _Event()

            def isConnected(self) -> bool:  # noqa: N802
                return False

        with patch("alphaedge.engine.broker.IB", side_effect=[_IBStub(), _IBStub()]):
            broker = BrokerConnection(IBConfig(is_paper=True))
            handler = MagicMock()

            broker.add_disconnect_handler(handler)
            first_client = cast(_IBStub, broker.ib)
            broker._on_disconnect()
            rebound_client = cast(_IBStub, broker.ib)

        assert handler in first_client.disconnectedEvent.handlers
        assert handler in rebound_client.disconnectedEvent.handlers

    @pytest.mark.asyncio()
    async def test_disconnect_calls_reconnect(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_on_ib_disconnect schedules _handle_reconnection."""
        strategy = _build_strategy()
        reconnect_mock = AsyncMock(return_value=True)
        monkeypatch.setattr(strategy._broker, "reconnect", reconnect_mock)
        monkeypatch.setattr(
            strategy._executor, "get_open_positions", AsyncMock(return_value=[])
        )
        monkeypatch.setattr(
            strategy._executor, "get_open_orders", AsyncMock(return_value=[])
        )
        monkeypatch.setattr(strategy._rt_feed, "subscribe", AsyncMock())

        await strategy._lifecycle._handle_reconnection()

        reconnect_mock.assert_awaited_once_with(max_retries=3)
        assert strategy._reconnecting is False


class TestReconnectSuccessReconciles:
    """Verify position reconciliation on successful reconnect."""

    @pytest.mark.asyncio()
    async def test_position_state_synced(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """After reconnect, StrategyState reflects actual IB positions."""
        strategy = _build_strategy(_make_config(["EURUSD", "GBPUSD"]))

        # Pre-populate states
        state_eur = StrategyState(pair="EURUSD", is_position_open=False)
        state_gbp = StrategyState(pair="GBPUSD", is_position_open=True)
        strategy._states = {"EURUSD": state_eur, "GBPUSD": state_gbp}

        # Mock IB returning only EURUSD with an open position
        mock_pos = MagicMock()
        mock_pos.contract = MagicMock()
        mock_pos.contract.pair = "EURUSD"
        mock_pos.position = 10000

        monkeypatch.setattr(strategy._broker, "reconnect", AsyncMock(return_value=True))
        monkeypatch.setattr(
            strategy._executor,
            "get_open_positions",
            AsyncMock(return_value=[mock_pos]),
        )
        monkeypatch.setattr(
            strategy._executor, "get_open_orders", AsyncMock(return_value=[])
        )
        monkeypatch.setattr(strategy._rt_feed, "subscribe", AsyncMock())

        await strategy._lifecycle._handle_reconnection()

        # EURUSD should now show position open (was False → True)
        assert state_eur.is_position_open is True
        # GBPUSD should now show position closed (was True → False)
        assert state_gbp.is_position_open is False


class TestReconnectFailureShutdown:
    """Verify shutdown on reconnect failure."""

    @pytest.mark.asyncio()
    async def test_shutdown_on_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Failed reconnect sets _shutdown_requested = True."""
        strategy = _build_strategy()
        monkeypatch.setattr(
            strategy._broker, "reconnect", AsyncMock(return_value=False)
        )

        await strategy._lifecycle._handle_reconnection()

        assert strategy._shutdown_requested is True
        assert strategy._reconnecting is False
