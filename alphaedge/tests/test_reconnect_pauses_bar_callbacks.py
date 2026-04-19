# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/tests/test_reconnect_pauses_bar_callbacks.py
# DESCRIPTION  : B-01-B regression — _on_new_m1_bar is silently dropped
#                while _reconnecting=True (avoids partially-reinitialised state)
# PYTHON       : 3.11.9
# ============================================================
"""ALPHAEDGE — Verify bar callbacks are paused during IB reconnection."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from alphaedge.config.loader import AppConfig, IBConfig, TradingConfig
from alphaedge.core.types import MomentumSignal
from alphaedge.engine.strategy import CoreModules, SwingStrategy


# ------------------------------------------------------------------
# Helpers  (reuse minimal factory pattern from test_race_condition_*)
# ------------------------------------------------------------------
def _make_config() -> AppConfig:
    cfg = AppConfig()
    cfg.ib = IBConfig(is_paper=True)
    cfg.trading = TradingConfig()
    cfg.trading.pairs = ["EURUSD"]
    cfg.trading.max_trades_per_session = 5
    return cfg


def _build_strategy() -> SwingStrategy:
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

        risk_mock = MagicMock()
        risk_mock.check_pair_limit.return_value = {"allowed": True}

        mock_modules.return_value = CoreModules(
            momentum_detector=MagicMock(),
            order_manager=MagicMock(),
            risk_manager=risk_mock,
        )
        strategy = SwingStrategy(_make_config())
    return strategy


def _live_candle() -> dict[str, Any]:
    return {
        "datetime": datetime.now(tz=UTC),
        "open": 1.25,
        "high": 1.251,
        "low": 1.249,
        "close": 1.250,
        "volume": 100,
    }


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------
class TestReconnectingFlagPausesBarCallbacks:
    """_on_new_m1_bar must be a no-op while _reconnecting is True."""

    def test_bar_dropped_when_reconnecting(self) -> None:
        """Bar arriving during reconnect does NOT schedule an execution task."""
        strategy = _build_strategy()
        state = strategy._init_pair_state("EURUSD")
        # Mark a momentum signal so the bar would normally reach execution
        state.signal_result = MomentumSignal(
            detected=True,
            direction=1,
            adx=30.0,
            strength=0.7,
            ema_fast=1.249,
            ema_slow=1.248,
            timestamp=0,
        )

        # Inject a spy on _atomic_check_and_execute to confirm it is never called
        spy = AsyncMock(return_value=False)
        strategy._lifecycle._atomic_check_and_execute = spy

        # Simulate reconnection in progress
        strategy._reconnecting = True

        strategy._lifecycle._on_new_m1_bar("EURUSD", _live_candle())

        # asyncio.ensure_future was never called for execution
        spy.assert_not_called()

    def test_bar_processed_when_not_reconnecting(self) -> None:
        """Normal bar (no reconnect) reaches the signal-check path."""
        strategy = _build_strategy()
        state = strategy._init_pair_state("EURUSD")
        state.signal_result = MomentumSignal(
            detected=True,
            direction=1,
            adx=30.0,
            strength=0.7,
            ema_fast=1.249,
            ema_slow=1.248,
            timestamp=0,
        )

        spy = AsyncMock(return_value=True)
        strategy._lifecycle._atomic_check_and_execute = spy

        strategy._reconnecting = False

        # Patch asyncio.ensure_future so the task is not actually scheduled
        # (avoids requiring a running event loop in this sync test)
        scheduled: list[Any] = []

        def _capture_future(coro: Any) -> MagicMock:
            scheduled.append(coro)
            mock_task = MagicMock()
            mock_task.add_done_callback = MagicMock()
            return mock_task

        with patch(
            "alphaedge.engine.session_lifecycle.asyncio.ensure_future",
            side_effect=_capture_future,
        ):
            strategy._lifecycle._on_new_m1_bar("EURUSD", _live_candle())

        # At least one future was scheduled (the execution task)
        assert len(scheduled) >= 1

    async def test_reconnecting_flag_cleared_after_reconnect(self) -> None:
        """After _handle_reconnection completes, _reconnecting is reset to False.

        Uses the 'gateway unreachable' early-return path to keep the mock surface
        minimal.  The finally-block must fire regardless of the exit path.
        """
        strategy = _build_strategy()
        strategy._reconnecting = True

        async def _fake_gw_unreachable(_cfg: Any) -> bool:  # noqa: ARG001
            return False

        with patch(
            "alphaedge.engine.session_lifecycle.ensure_gateway_ready",
            new=_fake_gw_unreachable,
        ):
            await strategy._lifecycle._handle_reconnection()

        assert strategy._reconnecting is False


class TestPersistStateSync:
    """_record_fill calls _persist_daily_state synchronously (B-01-C)."""

    def test_persist_called_synchronously_in_record_fill(self) -> None:
        """_persist_daily_state is invoked once, directly (not via to_thread)."""
        strategy = _build_strategy()
        state = strategy._init_pair_state("EURUSD")
        state.starting_equity = 10_000.0
        state.current_equity = 10_000.0

        persist_calls: list[int] = []

        def _mock_persist(**_kwargs: object) -> None:
            persist_calls.append(1)

        strategy._lifecycle._persist_daily_state = _mock_persist

        # Minimal mock objects for _record_fill
        mock_order_status = MagicMock()
        mock_order_status.avgFillPrice = 1.2501
        mock_parent_trade = MagicMock()
        mock_parent_trade.orderStatus = mock_order_status

        trades_placed = [mock_parent_trade]  # No child orders — simplest path

        bracket: dict[str, Any] = {
            "direction": 1,
            "entry_price": 1.2500,
            "stop_loss": 1.2450,
            "take_profit": 1.2600,
            "lot_size": 0.01,
            "units": 1000,
        }
        signal: dict[str, Any] = {
            "risk_pips": 50.0,
            "adx": 28.0,
            "strength": 0.7,
        }

        strategy._lifecycle._record_fill(
            state,
            trades_placed,
            bracket,
            signal,
            spread_pips=0.8,
            pip_size=0.0001,
            exchange_rate=0.0,
            fill_status="full",
        )

        # Must have been called exactly once, synchronously
        assert persist_calls == [1], (
            f"Expected 1 synchronous persist call, got {persist_calls}"
        )
