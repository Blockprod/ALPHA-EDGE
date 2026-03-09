# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_risk_check_interval.py
# DESCRIPTION  : Tests for adaptive risk check interval (T2.4)
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-08
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: adaptive risk check interval tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from alphaedge.config.constants import (
    RISK_CHECK_INTERVAL_IDLE,
    RISK_CHECK_INTERVAL_POSITION,
)
from alphaedge.config.loader import AppConfig, IBConfig, TradingConfig
from alphaedge.engine.strategy import CoreModules, FCRStrategy, StrategyState


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _build_strategy() -> FCRStrategy:
    """Build FCRStrategy with mocked externals."""
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
class TestAdaptiveRiskCheckInterval:
    """Verify interval constants and _has_open_position logic."""

    def test_idle_interval_is_30(self) -> None:
        """Without open positions, interval constant is 30 seconds."""
        assert RISK_CHECK_INTERVAL_IDLE == 30

    def test_position_interval_is_5(self) -> None:
        """With open positions, interval constant is 5 seconds."""
        assert RISK_CHECK_INTERVAL_POSITION == 5

    def test_has_open_position_false_when_idle(self) -> None:
        """No open positions → _has_open_position returns False."""
        strategy = _build_strategy()
        strategy._states = {
            "EURUSD": StrategyState(pair="EURUSD", is_position_open=False),
        }
        assert strategy._lifecycle._has_open_position() is False

    def test_has_open_position_true_when_active(self) -> None:
        """One pair has position → _has_open_position returns True."""
        strategy = _build_strategy()
        strategy._states = {
            "EURUSD": StrategyState(pair="EURUSD", is_position_open=True),
            "GBPUSD": StrategyState(pair="GBPUSD", is_position_open=False),
        }
        assert strategy._lifecycle._has_open_position() is True

    def test_has_open_position_empty_states(self) -> None:
        """No states → _has_open_position returns False."""
        strategy = _build_strategy()
        strategy._states = {}
        assert strategy._lifecycle._has_open_position() is False
