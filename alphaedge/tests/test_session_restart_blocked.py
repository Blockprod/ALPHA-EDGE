# ============================================================
# PROJECT      : ALPHAEDGE — Swing Trading Bot
# FILE         : alphaedge/tests/test_session_restart_blocked.py
# DESCRIPTION  : Verify shutdown_triggered persisted state blocks session restart
# AUTHOR       : ALPHAEDGE Dev Team
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-25
# ============================================================
"""ALPHAEDGE — Verify that a persisted shutdown_triggered=True blocks run_session()."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alphaedge.config.loader import AppConfig, IBConfig, TradingConfig
from alphaedge.engine.strategy import CoreModules, SwingStrategy
from alphaedge.utils.state_persistence import (
    DailyState,
    clear_daily_state,
    save_daily_state,
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _make_config() -> AppConfig:
    return AppConfig(
        ib=IBConfig(is_paper=True),
        trading=TradingConfig(pairs=["EURUSD"]),
    )


def _build_strategy() -> tuple[SwingStrategy, MagicMock]:
    """Return (strategy, mock_broker) — broker.connect is a tracked AsyncMock."""
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
            momentum_detector=MagicMock(),
            order_manager=MagicMock(),
            risk_manager=MagicMock(),
        )
        strategy = SwingStrategy(cfg)
        mock_broker = mock_broker_cls.return_value

    mock_broker.connect = AsyncMock(return_value=True)
    strategy._rt_feed.unsubscribe_all = AsyncMock()
    strategy._broker.disconnect = AsyncMock()
    strategy._executor.get_open_positions = AsyncMock(return_value=[])
    return strategy, mock_broker


@pytest.fixture(autouse=True)
def _cleanup_state_file() -> Generator[None, None, None]:
    """Clean up state file before/after each test."""
    clear_daily_state()
    yield
    clear_daily_state()


def _today_state(*, shutdown_triggered: bool) -> DailyState:
    return DailyState(
        date=date.today().isoformat(),
        starting_equity=10_000.0,
        trades_today=0,
        shutdown_triggered=shutdown_triggered,
    )


# ==================================================================
# Tests
# ==================================================================
class TestSessionRestartBlocked:
    """Verify kill switch persistence blocks session restarts."""

    def test_shutdown_triggered_blocks_restart(self) -> None:
        """run_session() must return immediately without calling broker.connect()."""
        strategy, mock_broker = _build_strategy()
        save_daily_state(_today_state(shutdown_triggered=True))

        asyncio.run(strategy._lifecycle.run_session())

        mock_broker.connect.assert_not_called()

    def test_shutdown_not_triggered_allows_restart(self) -> None:
        """run_session() must call broker.connect() when shutdown_triggered=False."""
        strategy, mock_broker = _build_strategy()
        save_daily_state(_today_state(shutdown_triggered=False))

        # connect() returns True but everything after is mocked — session will
        # proceed normally until it hits the first awaitable that isn't set up.
        # We intercept _init_session_pairs to stop early without error.
        async def _stop_early(
            _starting_equity: float,
            _live_equity: float,
            _persisted: object,
            _session_start: object,
        ) -> list[str]:
            return []

        strategy._lifecycle._init_session_pairs = _stop_early  # type: ignore[method-assign]
        strategy._executor.get_account_equity = AsyncMock(return_value=10_000.0)

        # Patch get_session_window_utc to avoid timezone dependency
        from datetime import UTC, datetime

        mock_window = (
            datetime(2026, 3, 25, 14, 30, tzinfo=UTC),
            datetime(2026, 3, 25, 15, 30, tzinfo=UTC),
        )
        with patch(
            "alphaedge.engine.session_lifecycle.get_session_window_utc",
            return_value=mock_window,
        ):
            asyncio.run(strategy._lifecycle.run_session())

        mock_broker.connect.assert_called_once()
