# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_strategy_p2_05.py
# DESCRIPTION  : P2-05 — state persistence wired to SL/TP fills + startup reconcile
# ============================================================
"""P2-05: persist state on trade close, reconcile positions at startup."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alphaedge.config.loader import AppConfig, IBConfig, TradingConfig
from alphaedge.engine.strategy import CoreModules, FCRStrategy
from alphaedge.utils.state_persistence import clear_daily_state, load_daily_state


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _make_config(pairs: list[str] | None = None) -> AppConfig:
    return AppConfig(
        ib=IBConfig(is_paper=True),
        trading=TradingConfig(pairs=pairs or ["EURUSD"]),
    )


def _build_strategy(pairs: list[str] | None = None) -> FCRStrategy:
    cfg = _make_config(pairs)
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
def _cleanup_state() -> Generator[None, None, None]:
    clear_daily_state()
    yield
    clear_daily_state()


# ==================================================================
# Tests — SL/TP fill persists state
# ==================================================================
class TestPersistOnTradeClosed:
    """Verify _on_trade_closed persists state after resetting is_position_open."""

    @pytest.mark.asyncio()
    async def test_persist_called_after_close(self) -> None:
        """_persist_daily_state is called when a position closes."""
        strategy = _build_strategy()
        state = strategy._init_pair_state("EURUSD")
        state.is_position_open = True

        persist_calls: list[int] = []
        original_persist = strategy._lifecycle._persist_daily_state

        def _track_persist(**kwargs: Any) -> None:
            persist_calls.append(1)
            original_persist(**kwargs)

        strategy._lifecycle._persist_daily_state = _track_persist

        strategy._lifecycle._on_trade_closed("EURUSD")
        await asyncio.sleep(0.1)

        assert state.is_position_open is False
        assert len(persist_calls) == 1

    @pytest.mark.asyncio()
    async def test_state_persisted_after_close(self) -> None:
        """State file is written when a position is closed by SL/TP."""
        strategy = _build_strategy()
        state = strategy._init_pair_state("EURUSD")
        state.starting_equity = 10_000.0
        state.trades_today = 1
        state.is_position_open = True

        strategy._lifecycle._on_trade_closed("EURUSD")
        await asyncio.sleep(0.1)

        assert state.is_position_open is False
        loaded = load_daily_state()
        assert loaded is not None
        assert loaded.trades_today == 1
        assert "EURUSD" not in loaded.open_pairs

    @pytest.mark.asyncio()
    async def test_open_pairs_reflects_remaining_positions(self) -> None:
        """After one pair closes, open_pairs still contains the other open pair."""
        strategy = _build_strategy(["EURUSD", "GBPUSD"])
        eur_state = strategy._init_pair_state("EURUSD")
        gbp_state = strategy._init_pair_state("GBPUSD")
        eur_state.starting_equity = 10_000.0
        gbp_state.starting_equity = 10_000.0
        eur_state.trades_today = 1
        gbp_state.trades_today = 1
        eur_state.is_position_open = True
        gbp_state.is_position_open = True

        # Capture actual open_pairs at persist time
        persisted_open_pairs: list[list[str]] = []
        original_persist = strategy._lifecycle._persist_daily_state

        def _capture_persist(**kwargs: Any) -> None:
            # Compute open_pairs the same way _persist_daily_state does
            open_p = [p for p, s in strategy._states.items() if s.is_position_open]
            persisted_open_pairs.append(open_p)
            original_persist(**kwargs)

        strategy._lifecycle._persist_daily_state = _capture_persist

        strategy._lifecycle._on_trade_closed("EURUSD")
        await asyncio.sleep(0.1)

        assert eur_state.is_position_open is False
        assert gbp_state.is_position_open is True
        # At the moment of persist, GBPUSD was still open
        assert len(persisted_open_pairs) == 1
        assert "GBPUSD" in persisted_open_pairs[0]
        assert "EURUSD" not in persisted_open_pairs[0]


# ==================================================================
# Tests — startup reconcile call in run_session
# ==================================================================
class TestStartupReconcile:
    """Verify run_session calls _reconcile_positions at startup."""

    @pytest.mark.asyncio()
    async def test_reconcile_called_at_startup(self) -> None:
        """_reconcile_positions is awaited once during run_session startup."""
        strategy = _build_strategy(["EURUSD"])

        strategy._broker.connect = AsyncMock(return_value=True)
        strategy._executor.get_account_equity = AsyncMock(return_value=10_000.0)
        strategy._hist_feed.fetch_m5_pre_session = AsyncMock(return_value=[])
        strategy._hist_feed.fetch_bars = AsyncMock(return_value=[])
        strategy._rt_feed.on_bar = MagicMock()
        strategy._rt_feed.subscribe = AsyncMock()
        strategy._rt_feed.unsubscribe_all = AsyncMock()
        strategy._broker.disconnect = AsyncMock()
        strategy._executor.get_open_positions = AsyncMock(return_value=[])
        strategy._modules.fcr_detector.detect_fcr.return_value = None

        reconcile_calls: list[int] = []

        async def _mock_reconcile() -> None:
            reconcile_calls.append(1)

        with (
            patch(
                "alphaedge.engine.session_lifecycle.load_daily_state", return_value=None
            ),
            patch(
                "alphaedge.engine.session_lifecycle.get_session_window_utc",
                return_value=(MagicMock(), MagicMock()),
            ),
            patch(
                "alphaedge.engine.session_lifecycle.is_session_active",
                return_value=False,
            ),
        ):
            strategy._lifecycle._reconcile_positions = _mock_reconcile
            await strategy.run_session()

        # _reconcile_positions must have been called exactly once
        assert len(reconcile_calls) == 1

    @pytest.mark.asyncio()
    async def test_reconcile_restores_open_pairs(self) -> None:
        """reconcile_positions sets is_position_open based on actual IB state."""
        strategy = _build_strategy(["EURUSD"])

        strategy._broker.connect = AsyncMock(return_value=True)
        strategy._executor.get_account_equity = AsyncMock(return_value=10_000.0)
        strategy._hist_feed.fetch_m5_pre_session = AsyncMock(return_value=[])
        strategy._hist_feed.fetch_bars = AsyncMock(return_value=[])
        strategy._rt_feed.on_bar = MagicMock()
        strategy._rt_feed.subscribe = AsyncMock()
        strategy._rt_feed.unsubscribe_all = AsyncMock()
        strategy._broker.disconnect = AsyncMock()
        strategy._modules.fcr_detector.detect_fcr.return_value = None

        # Simulate IB position open on EURUSD
        mock_pos = MagicMock()
        mock_pos.position = 1000
        mock_pos.contract.pair = "EURUSD"
        mock_pos.contract.symbol = "EURUSD"
        strategy._executor.get_open_positions = AsyncMock(return_value=[mock_pos])

        with (
            patch(
                "alphaedge.engine.session_lifecycle.load_daily_state", return_value=None
            ),
            patch(
                "alphaedge.engine.session_lifecycle.get_session_window_utc",
                return_value=(MagicMock(), MagicMock()),
            ),
            patch(
                "alphaedge.engine.session_lifecycle.is_session_active",
                return_value=False,
            ),
        ):
            await strategy.run_session()

        # After reconciliation, EURUSD's is_position_open should be True
        state = strategy._states.get("EURUSD")
        assert state is not None
        assert state.is_position_open is True
