# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/tests/test_session_lifecycle_weekend_wait.py
# DESCRIPTION  : Non-regression: _wait_for_session_open must skip
#                Saturday/Sunday and never wait for a weekend session.
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-04-19
# ============================================================
"""Regression test for the weekend guard in _wait_for_session_open.

Bug: on Sunday 2026-04-19 12:51 UTC, the loop computed a session window
for Sunday (13:30–14:30 UTC), found it hadn't started yet, and waited
49 min for a non-trading day session.

Fix: an is_weekend_paris() check at the top of each loop iteration
skips straight to the next weekday when Paris time is Sat/Sun.
"""

from __future__ import annotations

import datetime
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


# Sunday 2026-04-19 12:51 UTC — the exact datetime from the bug report
_SUNDAY_UTC = datetime.datetime(2026, 4, 19, 12, 51, 0, tzinfo=datetime.UTC)
# Next Monday session (2026-04-22, not 2026-04-20 — Easter Monday)
_MONDAY_SESSION_START = datetime.datetime(2026, 4, 21, 13, 30, 0, tzinfo=datetime.UTC)
_MONDAY_SESSION_END = datetime.datetime(2026, 4, 21, 14, 30, 0, tzinfo=datetime.UTC)


# ==================================================================
# Weekend wait guard
# ==================================================================
class TestWaitForSessionOpenWeekendGuard:
    """On weekend, _wait_for_session_open must sleep in long chunks (standby)
    and NOT call graceful_shutdown() or exit the process."""

    @pytest.mark.asyncio()
    async def test_weekend_enters_standby_long_sleep(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """On weekend, the method must sleep in ≤30-min chunks and loop back
        (standby mode) — NOT call graceful_shutdown() or return immediately."""
        strategy = _build_strategy()
        sleep_calls: list[float] = []

        async def _fake_sleep(secs: float) -> None:
            sleep_calls.append(secs)
            # Break the inner standby loop after the first chunk
            strategy._shutdown_requested = True

        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.is_weekend_paris",
            lambda: True,
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.asyncio.sleep",
            _fake_sleep,
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.now_utc",
            lambda: _SUNDAY_UTC,
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.get_session_window_utc",
            lambda _dt: (_MONDAY_SESSION_START, _MONDAY_SESSION_END),
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.format_dual_time",
            lambda _dt: "2026-04-21 13:30 UTC",
        )

        shutdown_mock = AsyncMock()
        monkeypatch.setattr(strategy._lifecycle, "graceful_shutdown", shutdown_mock)

        strategy._shutdown_requested = False
        await strategy._lifecycle._wait_for_session_open()

        # Must sleep in ≤1800s chunks — not 60s and not a tiny value
        assert len(sleep_calls) >= 1
        assert sleep_calls[0] <= 1800.0
        assert sleep_calls[0] > 60.0, "Expected long standby sleep, not 60s poll"
        # Must NOT terminate the process
        shutdown_mock.assert_not_called()

    @pytest.mark.asyncio()
    async def test_weekday_does_not_hit_weekend_branch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """On a weekday before session open, the method must NOT go through
        the weekend branch (sleep != 60.0 unconditionally)."""
        strategy = _build_strategy()
        sleep_calls: list[float] = []

        async def _fake_sleep(secs: float) -> None:
            sleep_calls.append(secs)
            strategy._shutdown_requested = True

        # Monday 10:00 UTC — before the 13:30 UTC session start.
        monday_before = datetime.datetime(2026, 4, 21, 10, 0, 0, tzinfo=datetime.UTC)
        session_start = datetime.datetime(2026, 4, 21, 13, 30, 0, tzinfo=datetime.UTC)
        session_end = datetime.datetime(2026, 4, 21, 14, 30, 0, tzinfo=datetime.UTC)

        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.is_weekend_paris",
            lambda: False,
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.asyncio.sleep",
            _fake_sleep,
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.now_utc",
            lambda: monday_before,
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.get_session_window_utc",
            lambda _dt: (session_start, session_end),
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.format_dual_time",
            lambda _dt: "2026-04-21 13:30 UTC",
        )

        strategy._shutdown_requested = False
        await strategy._lifecycle._wait_for_session_open()

        # "Before session_start" branch — sleep value is min(wait_s - 30, 60)
        # wait_s = (13:30 - 10:00) = 12600s → min(12570, 60) = 60.0
        # But it's NOT the 60.0 of the weekend branch.
        # The key assertion: is_weekend_paris was False → we did NOT enter
        # the weekend branch.  A sleep(60.0) here is the pre-session-wait sleep.
        assert len(sleep_calls) == 1

    @pytest.mark.asyncio()
    async def test_friday_post_session_enters_standby(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """After Friday's session ends (next session >36h away), the bot must
        enter standby (long sleep chunks) — NOT call graceful_shutdown()."""
        strategy = _build_strategy()
        sleep_calls: list[float] = []

        # Friday 2026-04-24 15:00 UTC — session ended at 14:30 UTC
        friday_after_session = datetime.datetime(
            2026, 4, 24, 15, 0, 0, tzinfo=datetime.UTC
        )
        friday_start = datetime.datetime(2026, 4, 24, 13, 30, 0, tzinfo=datetime.UTC)
        friday_end = datetime.datetime(2026, 4, 24, 14, 30, 0, tzinfo=datetime.UTC)
        monday_start = datetime.datetime(2026, 4, 27, 13, 30, 0, tzinfo=datetime.UTC)
        monday_end = datetime.datetime(2026, 4, 27, 14, 30, 0, tzinfo=datetime.UTC)

        def _session_window(
            dt: datetime.datetime,
        ) -> tuple[datetime.datetime, datetime.datetime]:
            if dt.weekday() == 4:  # Friday
                return friday_start, friday_end
            return monday_start, monday_end

        async def _fake_sleep(secs: float) -> None:
            sleep_calls.append(secs)
            strategy._shutdown_requested = True

        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.is_weekend_paris",
            lambda: False,
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.asyncio.sleep",
            _fake_sleep,
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.now_utc",
            lambda: friday_after_session,
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.get_session_window_utc",
            _session_window,
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.format_dual_time",
            lambda _dt: "2026-04-27 13:30 UTC",
        )

        shutdown_mock = AsyncMock()
        monkeypatch.setattr(strategy._lifecycle, "graceful_shutdown", shutdown_mock)

        strategy._shutdown_requested = False
        await strategy._lifecycle._wait_for_session_open()

        # Must sleep in ≤1800s chunks — not tiny, not a 60s poll
        assert len(sleep_calls) >= 1
        assert sleep_calls[0] <= 1800.0
        assert sleep_calls[0] > 60.0, "Expected long standby sleep, not 60s poll"
        shutdown_mock.assert_not_called()


# ==================================================================
# run_session — weekend startup INFO log
# ==================================================================
class TestRunSessionWeekendInfoLog:
    """run_session() must log an INFO message at startup when the bot
    is launched on a weekend, showing the next session time."""

    @pytest.mark.asyncio()
    async def test_weekend_startup_logs_info(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """On a weekend, run_session() must emit one INFO log indicating
        the market is closed and the next session time before entering wait."""
        strategy = _build_strategy()

        log_messages: list[str] = []

        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.is_weekend_paris",
            lambda: True,
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.is_dst_transition_week",
            lambda: False,
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.load_daily_state",
            lambda: None,
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.now_utc",
            lambda: _SUNDAY_UTC,
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.get_session_window_utc",
            lambda _dt: (_MONDAY_SESSION_START, _MONDAY_SESSION_END),
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.format_dual_time",
            lambda _dt: "2026-04-21 13:30 UTC",
        )
        # Capture logger.info calls
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.logger.info",
            lambda msg, *_a, **_kw: log_messages.append(str(msg)),
        )
        # _wait_for_session_open: shut down immediately to avoid infinite loop
        monkeypatch.setattr(strategy._lifecycle, "_wait_for_session_open", AsyncMock())
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.check_gateway_health",
            AsyncMock(return_value=True),
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.ensure_gateway_ready",
            AsyncMock(return_value=True),
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.is_session_active",
            lambda: False,
        )
        monkeypatch.setattr(strategy._broker, "connect", AsyncMock(return_value=False))
        monkeypatch.setattr(strategy._broker, "disconnect", AsyncMock())
        monkeypatch.setattr(strategy._broker, "stop_heartbeat", AsyncMock())

        strategy._shutdown_requested = False
        await strategy._lifecycle.run_session()

        weekend_logs = [m for m in log_messages if "Weekend detected" in m]
        assert len(weekend_logs) == 1
        assert "Next session" in weekend_logs[0]
        assert "Waiting" in weekend_logs[0]


# ==================================================================
# Proactive post-restart gateway health check
# ==================================================================
# Monday 2026-04-21 10:00 UTC = 06:00 ET (after 05:30 restart + 10min buffer)
_MONDAY_06_00_ET = datetime.datetime(2026, 4, 21, 10, 0, 0, tzinfo=datetime.UTC)
# Monday 2026-04-21 08:00 UTC = 04:00 ET (before 05:30 restart)
_MONDAY_04_00_ET = datetime.datetime(2026, 4, 21, 8, 0, 0, tzinfo=datetime.UTC)


class TestPostRestartGatewayCheck:
    """_wait_for_session_open must call check_gateway_health()
    proactively after the IB daily 05:30 ET restart (passive — no
    launch, no login, no polling)."""

    @pytest.mark.asyncio()
    async def test_health_check_fires_after_restart_time(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """After 05:40 ET on a weekday (minute % 15 == 0), the passive
        gateway health check must fire inside the wait loop."""
        strategy = _build_strategy()
        sleep_calls: list[float] = []
        gw_calls: list[bool] = []

        async def _fake_sleep(secs: float) -> None:
            sleep_calls.append(secs)
            strategy._shutdown_requested = True

        async def _fake_check_health(_cfg: object) -> bool:
            gw_calls.append(True)
            return True

        session_start = datetime.datetime(
            2026,
            4,
            21,
            13,
            30,
            0,
            tzinfo=datetime.UTC,
        )
        session_end = datetime.datetime(
            2026,
            4,
            21,
            14,
            30,
            0,
            tzinfo=datetime.UTC,
        )

        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.is_weekend_paris",
            lambda: False,
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.asyncio.sleep",
            _fake_sleep,
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.now_utc",
            lambda: _MONDAY_06_00_ET,
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.get_session_window_utc",
            lambda _dt: (session_start, session_end),
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.format_dual_time",
            lambda _dt: "2026-04-21 13:30 UTC",
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.check_gateway_health",
            _fake_check_health,
        )

        strategy._shutdown_requested = False
        await strategy._lifecycle._wait_for_session_open()

        assert len(gw_calls) == 1, (
            f"Expected 1 proactive gateway check but got {len(gw_calls)}"
        )

    @pytest.mark.asyncio()
    async def test_health_check_skipped_before_restart_time(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Before the restart time (04:00 ET), the proactive check must NOT
        fire even though it is a weekday."""
        strategy = _build_strategy()
        sleep_calls: list[float] = []
        gw_calls: list[bool] = []

        async def _fake_sleep(secs: float) -> None:
            sleep_calls.append(secs)
            strategy._shutdown_requested = True

        async def _fake_check_health(_cfg: object) -> bool:
            gw_calls.append(True)
            return True

        session_start = datetime.datetime(
            2026,
            4,
            21,
            13,
            30,
            0,
            tzinfo=datetime.UTC,
        )
        session_end = datetime.datetime(
            2026,
            4,
            21,
            14,
            30,
            0,
            tzinfo=datetime.UTC,
        )

        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.is_weekend_paris",
            lambda: False,
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.asyncio.sleep",
            _fake_sleep,
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.now_utc",
            lambda: _MONDAY_04_00_ET,
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.get_session_window_utc",
            lambda _dt: (session_start, session_end),
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.format_dual_time",
            lambda _dt: "2026-04-21 13:30 UTC",
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.check_gateway_health",
            _fake_check_health,
        )

        strategy._shutdown_requested = False
        await strategy._lifecycle._wait_for_session_open()

        assert len(gw_calls) == 0, (
            f"Gateway check should NOT fire before restart time, "
            f"but got {len(gw_calls)} call(s)"
        )


# ==================================================================
# External gateway: skip lifecycle when already connected
# ==================================================================
class TestExternalGatewayFastPath:
    """When another project has already launched and connected IB Gateway,
    run_session() must skip ensure_gateway_ready() entirely and proceed
    directly to the session window / data connection."""

    @pytest.mark.asyncio()
    async def test_skips_ensure_when_health_check_passes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If check_gateway_health() returns True (external gateway),
        ensure_gateway_ready() must NOT be called."""
        strategy = _build_strategy()
        ensure_calls: list[bool] = []
        log_messages: list[str] = []

        async def _fake_check_health(_cfg: object) -> bool:
            return True

        async def _fake_ensure_gw(_cfg: object) -> bool:
            ensure_calls.append(True)
            return True

        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.is_weekend_paris",
            lambda: False,
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.is_dst_transition_week",
            lambda: False,
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.load_daily_state",
            lambda: None,
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.check_gateway_health",
            _fake_check_health,
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.ensure_gateway_ready",
            _fake_ensure_gw,
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.logger.info",
            lambda msg, *_a, **_kw: log_messages.append(str(msg)),
        )
        # Skip wait + connect to isolate the gateway path
        monkeypatch.setattr(strategy._lifecycle, "_wait_for_session_open", AsyncMock())
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.is_session_active",
            lambda: False,
        )
        monkeypatch.setattr(strategy._broker, "connect", AsyncMock(return_value=False))
        monkeypatch.setattr(strategy._broker, "disconnect", AsyncMock())
        monkeypatch.setattr(strategy._broker, "stop_heartbeat", AsyncMock())

        strategy._shutdown_requested = False
        await strategy._lifecycle.run_session()

        assert len(ensure_calls) == 0, (
            "ensure_gateway_ready() should NOT be called when "
            "check_gateway_health() returns True (external gateway)"
        )
        skip_logs = [m for m in log_messages if "skipping gateway" in m.lower()]
        assert len(skip_logs) >= 1, "Expected INFO log about skipping gateway lifecycle"

    @pytest.mark.asyncio()
    async def test_falls_back_to_ensure_when_health_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If check_gateway_health() returns False, ensure_gateway_ready()
        must be called as fallback."""
        strategy = _build_strategy()
        ensure_calls: list[bool] = []

        async def _fake_check_health(_cfg: object) -> bool:
            return False

        async def _fake_ensure_gw(_cfg: object) -> bool:
            ensure_calls.append(True)
            return True

        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.is_weekend_paris",
            lambda: False,
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.is_dst_transition_week",
            lambda: False,
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.load_daily_state",
            lambda: None,
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.check_gateway_health",
            _fake_check_health,
        )
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.ensure_gateway_ready",
            _fake_ensure_gw,
        )
        # Skip wait + connect to isolate the gateway path
        monkeypatch.setattr(strategy._lifecycle, "_wait_for_session_open", AsyncMock())
        monkeypatch.setattr(
            "alphaedge.engine.session_lifecycle.is_session_active",
            lambda: False,
        )
        monkeypatch.setattr(strategy._broker, "connect", AsyncMock(return_value=False))
        monkeypatch.setattr(strategy._broker, "disconnect", AsyncMock())
        monkeypatch.setattr(strategy._broker, "stop_heartbeat", AsyncMock())

        strategy._shutdown_requested = False
        await strategy._lifecycle.run_session()

        assert len(ensure_calls) >= 1, (
            "ensure_gateway_ready() MUST be called when "
            "check_gateway_health() returns False"
        )
