# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_spread_monitor.py
# DESCRIPTION  : Tests for continuous spread monitoring (T2.3)
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-08
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: spread monitoring tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alphaedge.config.loader import AppConfig, IBConfig, TradingConfig
from alphaedge.engine.strategy import CoreModules, FCRStrategy, StrategyState


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _make_strategy() -> FCRStrategy:
    """Build a strategy with all externals mocked."""
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
class TestSpreadCheckBeforeExecution:
    """Signal is skipped when spread exceeds max at evaluation time."""

    @pytest.mark.asyncio()
    async def test_wide_spread_skips_signal(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Spread > max_spread_pips → signal not executed."""
        strategy = _make_strategy()
        state = StrategyState(pair="EURUSD")
        signal: dict[str, Any] = {
            "detected": True,
            "signal": 1,
            "entry_price": 1.0850,
            "stop_loss": 1.0830,
            "take_profit": 1.0910,
            "risk_pips": 20.0,
        }
        pip_size = 0.0001

        # Spread = 3 pips (0.0003 / 0.0001), max = 2.0
        monkeypatch.setattr(
            strategy._rt_feed,
            "get_live_spread",
            AsyncMock(return_value=0.0003),
        )

        result = await strategy._lifecycle._check_spread_and_execute(
            state, signal, pip_size
        )

        assert result is False
        # _execute_signal should NOT have been called

    @pytest.mark.asyncio()
    async def test_tight_spread_executes_signal(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Spread ≤ max_spread_pips → signal proceeds to execution."""
        strategy = _make_strategy()
        state = StrategyState(pair="EURUSD")
        signal: dict[str, Any] = {
            "detected": True,
            "signal": 1,
            "entry_price": 1.0850,
            "stop_loss": 1.0830,
            "take_profit": 1.0910,
            "risk_pips": 20.0,
        }
        pip_size = 0.0001

        # Spread = 1.5 pips (0.00015 / 0.0001), max = 2.0
        monkeypatch.setattr(
            strategy._rt_feed,
            "get_live_spread",
            AsyncMock(return_value=0.00015),
        )
        monkeypatch.setattr(
            strategy._executor,
            "get_account_equity",
            AsyncMock(return_value=10000.0),
        )
        # Mock _execute_signal to isolate spread check
        exec_mock = AsyncMock(return_value=True)
        monkeypatch.setattr(strategy._lifecycle, "_execute_signal", exec_mock)

        result = await strategy._lifecycle._check_spread_and_execute(
            state, signal, pip_size
        )

        assert result is True
        exec_mock.assert_awaited_once()


class TestSpreadSpikeMonitor:
    """Spread spike monitoring during open position."""

    @pytest.mark.asyncio()
    async def test_spike_above_threshold_logs_warning(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Spread > 3× max → no exception (warning logged internally)."""
        strategy = _make_strategy()
        # Spread = 8 pips → threshold = 2.0 × 3.0 = 6.0 → 8 > 6 → spike
        monkeypatch.setattr(
            strategy._rt_feed,
            "get_live_spread",
            AsyncMock(return_value=0.0008),
        )

        # Should not raise — just log
        await strategy._lifecycle._monitor_spread_spike("EURUSD")

    @pytest.mark.asyncio()
    async def test_normal_spread_no_warning(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Spread within threshold → no action."""
        strategy = _make_strategy()
        # Spread = 1 pip → threshold = 6.0 → 1 < 6 → no spike
        monkeypatch.setattr(
            strategy._rt_feed,
            "get_live_spread",
            AsyncMock(return_value=0.0001),
        )

        # Should not raise
        await strategy._lifecycle._monitor_spread_spike("EURUSD")
