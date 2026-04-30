# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/tests/test_session_heartbeat_lifecycle.py
# DESCRIPTION  : Non-regression: heartbeat activated/stopped in session lifecycle
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-04-13
# ============================================================
"""Non-regression tests for heartbeat lifecycle (m-02).

Verifies that:
  1. start_heartbeat() is called immediately after a successful broker.connect()
  2. stop_heartbeat() is awaited in the run_session() finally block
  3. start_heartbeat() is called after a successful _handle_reconnection()
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alphaedge.config.loader import AppConfig, IBConfig, TradingConfig
from alphaedge.engine.strategy import CoreModules, SwingStrategy


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _make_config() -> AppConfig:
    cfg = AppConfig()
    cfg.ib = IBConfig(is_paper=True)
    cfg.trading = TradingConfig()
    cfg.trading.pairs = ["EURUSD"]
    return cfg


def _build_strategy() -> SwingStrategy:
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
        mock_mods.return_value = CoreModules(
            momentum_detector=MagicMock(),
            order_manager=MagicMock(),
            risk_manager=MagicMock(),
        )
        return SwingStrategy(_make_config())


# ==================================================================
# Test 1 — start_heartbeat called after successful connect
# ==================================================================
class TestHeartbeatStartedAfterConnect:
    """start_heartbeat() must be called once after broker.connect() succeeds."""

    @pytest.mark.asyncio()
    async def test_start_heartbeat_called_after_connect(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        strategy = _build_strategy()

        start_hb = MagicMock()
        monkeypatch.setattr(strategy._broker, "connect", AsyncMock(return_value=True))
        monkeypatch.setattr(strategy._broker, "disconnect", AsyncMock())
        monkeypatch.setattr(strategy._broker, "stop_heartbeat", AsyncMock())
        monkeypatch.setattr(strategy._broker, "start_heartbeat", start_hb)
        monkeypatch.setattr(strategy._broker, "refresh_account_funds", AsyncMock())
        monkeypatch.setattr(
            strategy._executor, "get_account_equity", AsyncMock(return_value=10000.0)
        )
        monkeypatch.setattr(strategy._rt_feed, "on_bar", MagicMock())
        monkeypatch.setattr(strategy._rt_feed, "unsubscribe_all", AsyncMock())
        monkeypatch.setattr(
            strategy._lifecycle, "_init_session_pairs", AsyncMock(return_value=[])
        )
        monkeypatch.setattr(strategy._lifecycle, "_run_reconcile", AsyncMock())
        monkeypatch.setattr(strategy._lifecycle, "_handle_session_end", AsyncMock())
        monkeypatch.setattr(strategy._lifecycle, "_wait_for_session_open", AsyncMock())
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.ensure_gateway_ready",
            AsyncMock(return_value=True),
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.is_session_active",
            lambda: False,
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.load_daily_state",
            lambda: None,
        )
        strategy._shutdown_requested = False

        await strategy._lifecycle.run_session()

        start_hb.assert_called_once()


# ==================================================================
# Test 2 — stop_heartbeat awaited in finally
# ==================================================================
class TestHeartbeatStoppedInFinally:
    """stop_heartbeat() must be awaited before disconnect in run_session finally."""

    @pytest.mark.asyncio()
    async def test_stop_heartbeat_called_in_finally(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        strategy = _build_strategy()

        call_order: list[str] = []

        async def _stop_hb() -> None:
            call_order.append("stop_heartbeat")

        async def _disconnect() -> None:
            call_order.append("disconnect")

        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.ensure_gateway_ready",
            AsyncMock(return_value=True),
        )
        monkeypatch.setattr(strategy._broker, "connect", AsyncMock(return_value=True))
        monkeypatch.setattr(strategy._broker, "start_heartbeat", MagicMock())
        monkeypatch.setattr(strategy._broker, "stop_heartbeat", _stop_hb)
        monkeypatch.setattr(strategy._broker, "disconnect", _disconnect)
        monkeypatch.setattr(strategy._broker, "refresh_account_funds", AsyncMock())
        monkeypatch.setattr(
            strategy._executor, "get_account_equity", AsyncMock(return_value=10000.0)
        )
        monkeypatch.setattr(strategy._rt_feed, "on_bar", MagicMock())
        monkeypatch.setattr(strategy._rt_feed, "unsubscribe_all", AsyncMock())
        monkeypatch.setattr(
            strategy._lifecycle, "_init_session_pairs", AsyncMock(return_value=[])
        )
        monkeypatch.setattr(strategy._lifecycle, "_run_reconcile", AsyncMock())
        monkeypatch.setattr(strategy._lifecycle, "_handle_session_end", AsyncMock())
        monkeypatch.setattr(strategy._lifecycle, "_wait_for_session_open", AsyncMock())
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.is_session_active", lambda: False
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.load_daily_state", lambda: None
        )
        strategy._shutdown_requested = False

        await strategy._lifecycle.run_session()

        assert "stop_heartbeat" in call_order
        assert "disconnect" in call_order
        # stop_heartbeat must come BEFORE disconnect
        assert call_order.index("stop_heartbeat") < call_order.index("disconnect")


# ==================================================================
# Test 3 — start_heartbeat restarted after successful reconnect
# ==================================================================
class TestHeartbeatRestartedAfterReconnect:
    """start_heartbeat() must be called once after a successful _handle_reconnection."""

    @pytest.mark.asyncio()
    async def test_heartbeat_restarted_after_reconnect(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        strategy = _build_strategy()

        start_hb = MagicMock()
        monkeypatch.setattr(strategy._broker, "start_heartbeat", start_hb)
        monkeypatch.setattr(strategy._broker, "reconnect", AsyncMock(return_value=True))
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.ensure_gateway_ready",
            AsyncMock(return_value=True),
        )
        monkeypatch.setattr(strategy._rt_feed, "subscribe", AsyncMock())
        monkeypatch.setattr(strategy._lifecycle, "_run_reconcile", AsyncMock())
        monkeypatch.setattr(
            strategy._lifecycle._reconciler,
            "reconcile",
            AsyncMock(return_value=MagicMock(pairs_corrected=[], orphan_pairs=[])),
        )

        await strategy._lifecycle._handle_reconnection()

        start_hb.assert_called_once()
        assert strategy._reconnecting is False


class TestConfiguredStartingEquity:
    @pytest.mark.asyncio()
    async def test_run_session_uses_configured_virtual_capital(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        strategy = _build_strategy()
        strategy._config.trading.starting_equity = 1000.0

        captured_args: list[tuple[float, float, object, object]] = []

        async def _capture_init_pairs(
            self: object,
            starting_equity: float,
            current_equity: float,
            persisted: object,
            session_start: object,
        ) -> list[str]:
            captured_args.append(
                (starting_equity, current_equity, persisted, session_start)
            )
            return []

        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.ensure_gateway_ready",
            AsyncMock(return_value=True),
        )
        monkeypatch.setattr(strategy._broker, "connect", AsyncMock(return_value=True))
        monkeypatch.setattr(strategy._broker, "disconnect", AsyncMock())
        monkeypatch.setattr(strategy._broker, "stop_heartbeat", AsyncMock())
        monkeypatch.setattr(strategy._broker, "start_heartbeat", MagicMock())
        monkeypatch.setattr(strategy._broker, "refresh_account_funds", AsyncMock())
        monkeypatch.setattr(
            strategy._executor,
            "get_account_equity",
            AsyncMock(return_value=1_002_297.26),
        )
        monkeypatch.setattr(strategy._rt_feed, "on_bar", MagicMock())
        monkeypatch.setattr(strategy._rt_feed, "unsubscribe_all", AsyncMock())
        monkeypatch.setattr(
            strategy._lifecycle,
            "_init_session_pairs",
            _capture_init_pairs.__get__(strategy._lifecycle, type(strategy._lifecycle)),
        )
        monkeypatch.setattr(strategy._lifecycle, "_run_reconcile", AsyncMock())
        monkeypatch.setattr(strategy._lifecycle, "_handle_session_end", AsyncMock())
        monkeypatch.setattr(strategy._lifecycle, "_wait_for_session_open", AsyncMock())
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.is_session_active",
            lambda: False,
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.load_daily_state",
            lambda: None,
        )
        strategy._shutdown_requested = False

        await strategy._lifecycle.run_session()

        assert strategy._lifecycle._session_starting_equity == 1000.0
        assert captured_args == [(1000.0, 1000.0, None, captured_args[0][3])]
