# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
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

from alphaedge.config.loader import AppConfig, IBConfig, TradingConfig
from alphaedge.engine.strategy import CoreModules, FCRStrategy
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
        Path("alphaedge_daily_state.json").write_text(
            "not valid json",
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
        strategy._executor.get_account_equity = AsyncMock(
            return_value=9400.0,
        )
        strategy._hist_feed.fetch_m5_pre_session = AsyncMock(
            return_value=[],
        )
        strategy._hist_feed.fetch_bars = AsyncMock(
            return_value=[],
        )
        strategy._rt_feed.on_bar = MagicMock()
        strategy._rt_feed.subscribe = AsyncMock()
        strategy._rt_feed.unsubscribe_all = AsyncMock()
        strategy._broker.disconnect = AsyncMock()
        strategy._executor.get_open_positions = AsyncMock(
            return_value=[],
        )

        # Patch is_session_active to immediately end
        with patch(
            "alphaedge.engine.session_lifecycle.is_session_active",
            return_value=False,
        ):
            await strategy.run_session()

        # starting_equity should be the PERSISTED value, not live
        state = strategy._states.get("EURUSD")
        assert state is not None
        assert state.starting_equity == 9500.0
        assert state.trades_today == 2
