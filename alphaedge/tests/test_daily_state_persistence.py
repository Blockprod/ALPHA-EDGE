# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/tests/test_daily_state_persistence.py
# DESCRIPTION  : Tests for P0-03 daily state persistence
# AUTHOR       : ALPHAEDGE Dev Team
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-08
# ============================================================
"""ALPHAEDGE — Verify daily loss state persists across restarts."""

from __future__ import annotations

from collections.abc import Generator
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import alphaedge.utils.state_persistence as _state_mod
from alphaedge.config.loader import AppConfig
from alphaedge.engine.strategy import CoreModules, SwingStrategy
from alphaedge.utils.state_persistence import (
    DailyState,
    clear_daily_state,
    load_daily_state,
    save_daily_state,
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _make_config() -> AppConfig:
    cfg = AppConfig()
    cfg.ib.is_paper = True
    cfg.trading.pairs = ["EURUSD"]
    return cfg


def _build_strategy() -> SwingStrategy:
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
    # Make async cleanup methods awaitable for robustness under test ordering
    strategy._rt_feed.unsubscribe_all = AsyncMock()
    strategy._broker.disconnect = AsyncMock()
    strategy._executor.get_open_positions = AsyncMock(return_value=[])
    return strategy


@pytest.fixture(autouse=True)
def _cleanup_state_file() -> Generator[None, None, None]:
    """Ensure state file is cleaned up before and after each test."""
    clear_daily_state()  # Setup: guarantee clean slate
    yield
    clear_daily_state()  # Teardown: remove any state written by this test


# ==================================================================
# Tests — DailyState round-trip
# ==================================================================
class TestDailyStateRoundTrip:
    """Verify save/load of DailyState."""

    def test_save_and_load(self) -> None:
        state = DailyState(
            date=date.today().isoformat(),
            starting_equity=10000.0,
            trades_today=2,
            shutdown_triggered=False,
            open_pairs=["EURUSD"],
        )
        save_daily_state(state)
        loaded = load_daily_state()
        assert loaded is not None
        assert loaded.starting_equity == 10000.0
        assert loaded.trades_today == 2
        assert loaded.shutdown_triggered is False
        assert loaded.open_pairs == ["EURUSD"]
        assert loaded.last_update_utc != ""

    def test_load_returns_none_for_different_day(self) -> None:
        state = DailyState(
            date="2020-01-01",
            starting_equity=10000.0,
            trades_today=1,
            shutdown_triggered=True,
        )
        save_daily_state(state)
        loaded = load_daily_state()
        assert loaded is None  # Different day → reset

    def test_load_returns_none_when_no_file(self) -> None:
        loaded = load_daily_state()
        assert loaded is None

    def test_load_handles_corrupt_file(self) -> None:
        Path(_state_mod.STATE_FILE).write_text(
            "not valid json",
            encoding="utf-8",
        )
        loaded = load_daily_state()
        assert loaded is None

    def test_load_rejects_invalid_schema(self) -> None:
        Path(_state_mod.STATE_FILE).write_text(
            (
                '{"date": "' + date.today().isoformat() + '", '
                '"starting_equity": "oops", '
                '"trades_today": 1, '
                '"shutdown_triggered": false}'
            ),
            encoding="utf-8",
        )

        loaded = load_daily_state()

        assert loaded is None

    def test_load_rejects_invalid_open_pairs(self) -> None:
        Path(_state_mod.STATE_FILE).write_text(
            (
                '{"date": "' + date.today().isoformat() + '", '
                '"starting_equity": 10000.0, '
                '"trades_today": 1, '
                '"shutdown_triggered": false, '
                '"open_pairs": ["EURUSD", 42]}'
            ),
            encoding="utf-8",
        )

        loaded = load_daily_state()

        assert loaded is None


# ==================================================================
# Tests — Shutdown persistence blocks restart
# ==================================================================
class TestShutdownBlocksRestart:
    """Verify bot refuses to start after kill-switch same day."""

    @pytest.mark.asyncio()
    async def test_run_session_refused_after_shutdown(self) -> None:
        """run_session returns immediately if shutdown was persisted."""
        # Persist a shutdown state for today
        save_daily_state(
            DailyState(
                date=date.today().isoformat(),
                starting_equity=10000.0,
                trades_today=3,
                shutdown_triggered=True,
            )
        )

        strategy = _build_strategy()
        # Mock connect to track if it's called (it shouldn't be)
        strategy._broker.connect = AsyncMock(return_value=True)

        await strategy.run_session()

        # connect should NOT have been called
        strategy._broker.connect.assert_not_awaited()


# ==================================================================
# Tests — Persist after trade + shutdown
# ==================================================================
class TestPersistAfterTrade:
    """Verify _persist_daily_state writes correct data."""

    def test_persist_writes_file(self) -> None:
        strategy = _build_strategy()
        state = strategy._init_pair_state("EURUSD")
        state.starting_equity = 10000.0
        state.trades_today = 1
        strategy._global_trades_today = 1
        state.is_position_open = True

        strategy._lifecycle._persist_daily_state()

        loaded = load_daily_state()
        assert loaded is not None
        assert loaded.trades_today == 1
        assert loaded.starting_equity == 10000.0
        assert loaded.open_pairs == ["EURUSD"]
        assert loaded.shutdown_triggered is False

    def test_persist_with_shutdown_flag(self) -> None:
        strategy = _build_strategy()
        state = strategy._init_pair_state("EURUSD")
        state.starting_equity = 10000.0
        state.trades_today = 2

        strategy._lifecycle._persist_daily_state(shutdown=True)

        loaded = load_daily_state()
        assert loaded is not None
        assert loaded.shutdown_triggered is True


class TestRestoredEquityOnRestart:
    """Verify starting_equity is preserved on restart."""

    @pytest.mark.asyncio()
    async def test_equity_restored_from_state(self) -> None:
        """run_session uses persisted starting_equity."""
        save_daily_state(
            DailyState(
                date=date.today().isoformat(),
                starting_equity=9500.0,
                trades_today=2,
                shutdown_triggered=False,
            )
        )

        strategy = _build_strategy()
        strategy._broker.connect = AsyncMock(return_value=True)
        strategy._broker.refresh_account_funds = AsyncMock()
        strategy._executor.get_account_equity = AsyncMock(
            return_value=9400.0,
        )
        strategy._hist_feed.fetch_bars = AsyncMock(
            return_value=[],
        )
        strategy._rt_feed.on_bar = MagicMock()
        strategy._rt_feed.subscribe = AsyncMock()
        strategy._rt_feed.unsubscribe_all = AsyncMock()
        strategy._broker.disconnect = AsyncMock()
        strategy._broker.stop_heartbeat = AsyncMock()
        strategy._executor.get_open_positions = AsyncMock(
            return_value=[],
        )

        # Patch _wait_for_session_open to skip the real-time wait loop,
        # then patch is_session_active so the monitoring loop exits immediately.
        with (
            patch.object(
                strategy._lifecycle,
                "_wait_for_session_open",
                new=AsyncMock(),
            ),
            patch(
                "alphaedge.engine.session_lifecycle.is_session_active",
                return_value=False,
            ),
            patch(
                "alphaedge.engine.session_lifecycle.ensure_gateway_ready",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            await strategy.run_session()

        # starting_equity should be the PERSISTED value, not live
        state = strategy._states.get("EURUSD")
        assert state is not None
        assert state.starting_equity == 9500.0
        assert state.trades_today == 2
