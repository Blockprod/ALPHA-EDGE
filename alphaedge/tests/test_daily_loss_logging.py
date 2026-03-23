# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_daily_loss_logging.py
# DESCRIPTION  : Tests for daily loss kill-switch log severity
# PYTHON       : 3.11.9
# ============================================================
"""Verify daily loss shutdown emits a critical log entry."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alphaedge.config.loader import AppConfig, IBConfig, TradingConfig
from alphaedge.engine.strategy import CoreModules, FCRStrategy, StrategyState


def _build_strategy() -> FCRStrategy:
    cfg = AppConfig(ib=IBConfig(is_paper=True), trading=TradingConfig())
    with (
        patch("alphaedge.engine.strategy.BrokerConnection") as mock_broker_cls,
        patch("alphaedge.engine.strategy.OrderExecutor"),
        patch("alphaedge.engine.strategy.HistoricalDataFeed"),
        patch("alphaedge.engine.strategy.RealtimeDataFeed"),
        patch("alphaedge.engine.strategy._import_core_modules") as mock_mods,
    ):
        mock_ib = MagicMock()
        mock_ib.disconnectedEvent = MagicMock()
        mock_ib.disconnectedEvent.__iadd__ = lambda self, _handler: self
        mock_broker_cls.return_value.ib = mock_ib
        mock_mods.return_value = CoreModules(
            fcr_detector=MagicMock(),
            gap_detector=MagicMock(),
            engulfing_detector=MagicMock(),
            order_manager=MagicMock(),
            risk_manager=MagicMock(),
        )
        return FCRStrategy(cfg)


class TestDailyLossLogging:
    @pytest.mark.asyncio()
    async def test_daily_loss_breach_logs_critical(self) -> None:
        strategy = _build_strategy()
        strategy._states = {
            "EURUSD": StrategyState(
                pair="EURUSD",
                starting_equity=10000.0,
                current_equity=9600.0,
            )
        }
        strategy._check_risk = AsyncMock(
            return_value={
                "limit_breached": True,
                "daily_pnl_pct": -4.0,
                "reason": "daily_loss_limit",
            }
        )
        strategy._alert_manager.send_async = AsyncMock(return_value=None)
        strategy._executor.cancel_all_orders = AsyncMock(return_value=None)

        with patch(
            "alphaedge.engine.session_lifecycle.logger.critical"
        ) as critical_log:
            await strategy._lifecycle._check_daily_loss_shutdown()

        critical_log.assert_called_once()
        assert strategy._shutdown_requested is True
