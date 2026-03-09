# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_graceful_shutdown.py
# DESCRIPTION  : Tests for P1-01 SIGINT/SIGTERM graceful shutdown
# AUTHOR       : ALPHAEDGE Dev Team
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-08
# ============================================================
"""ALPHAEDGE — Verify graceful shutdown sets flags and persists state."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from alphaedge.config.loader import AppConfig, IBConfig, TradingConfig
from alphaedge.engine.strategy import CoreModules, FCRStrategy
from alphaedge.utils.state_persistence import clear_daily_state, load_daily_state


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _make_config() -> AppConfig:
    return AppConfig(
        ib=IBConfig(is_paper=True),
        trading=TradingConfig(pairs=["EURUSD"]),
    )


def _build_strategy() -> FCRStrategy:
    cfg = _make_config()
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
        mock_modules.return_value = CoreModules(
            fcr_detector=MagicMock(),
            gap_detector=MagicMock(),
            engulfing_detector=MagicMock(),
            order_manager=MagicMock(),
            risk_manager=MagicMock(),
        )
        strategy = FCRStrategy(cfg)
    return strategy


@pytest.fixture(autouse=True)
def _cleanup_state_file() -> Generator[None, None, None]:
    yield
    clear_daily_state()


# ==================================================================
# Tests
# ==================================================================
class TestGracefulShutdownMethod:
    """Verify graceful_shutdown() sets flags correctly."""

    @pytest.mark.asyncio()
    async def test_sets_shutdown_flag(self) -> None:
        strategy = _build_strategy()
        assert strategy._shutdown_requested is False

        await strategy.graceful_shutdown()

        assert strategy._shutdown_requested is True

    @pytest.mark.asyncio()
    async def test_persists_state_on_shutdown(self) -> None:
        strategy = _build_strategy()
        state = strategy._init_pair_state("EURUSD")
        state.starting_equity = 10000.0
        state.trades_today = 1

        await strategy.graceful_shutdown()

        loaded = load_daily_state()
        assert loaded is not None
        assert loaded.trades_today == 1

    @pytest.mark.asyncio()
    async def test_idempotent_multiple_calls(self) -> None:
        """Calling graceful_shutdown twice doesn't crash."""
        strategy = _build_strategy()
        strategy._init_pair_state("EURUSD")

        await strategy.graceful_shutdown()
        await strategy.graceful_shutdown()

        assert strategy._shutdown_requested is True


class TestGracefulShutdownHasMethod:
    """Verify the method exists and is async."""

    def test_method_exists(self) -> None:
        strategy = _build_strategy()
        assert hasattr(strategy, "graceful_shutdown")
        assert asyncio.iscoroutinefunction(strategy.graceful_shutdown)
