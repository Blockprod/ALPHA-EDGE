# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/tests/test_strategy_gateway_dashboard_state.py
# DESCRIPTION  : Dashboard state must separate gateway health from broker session
# PYTHON       : 3.11.9
# ============================================================
"""Verify dashboard state does not report the gateway as down while waiting."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from alphaedge.config.loader import AppConfig
from alphaedge.engine.strategy import CoreModules, SwingStrategy


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
        mock_broker_cls.return_value.is_connected = False
        mock_broker_cls.return_value.uptime_seconds = 0
        mock_mods.return_value = CoreModules(
            momentum_detector=MagicMock(),
            order_manager=MagicMock(),
            risk_manager=MagicMock(),
        )
        return SwingStrategy(cfg)


def test_gateway_health_is_distinct_from_broker_connection() -> None:
    strategy = _build_strategy()

    strategy.set_gateway_health(gateway_connected=True, gateway_status="healthy")

    state = strategy.get_live_state()

    assert state["gateway_connected"] is True
    assert state["gateway_status"] == "healthy"
    assert state["ib_connected"] is False
