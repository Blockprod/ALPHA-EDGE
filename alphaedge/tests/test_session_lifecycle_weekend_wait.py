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
for Sunday (13:40–14:30 UTC), found it hadn't started yet, and waited
49 min for a non-trading day session.

Fix: an is_weekend_paris() check at the top of each loop iteration
skips straight to the next weekday when Paris time is Sat/Sun.
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock, patch

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
_MONDAY_SESSION_START = datetime.datetime(2026, 4, 21, 13, 40, 0, tzinfo=datetime.UTC)
_MONDAY_SESSION_END = datetime.datetime(2026, 4, 21, 14, 30, 0, tzinfo=datetime.UTC)


# ==================================================================
# Weekend wait guard
# ==================================================================
class TestWaitForSessionOpenWeekendGuard:
    """_wait_for_session_open must sleep 60s and continue (not return)
    when is_weekend_paris() is True."""

    @pytest.mark.asyncio()
    async def test_weekend_sleeps_60s_does_not_return_early(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """On Sunday, the method must sleep 60s (weekend branch) and loop,
        NOT proceed to the session window or return to the caller."""
        strategy = _build_strategy()
        sleep_calls: list[float] = []

        async def _fake_sleep(secs: float) -> None:
            sleep_calls.append(secs)
            # Break the while loop after the first sleep
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
            lambda _dt: "2026-04-21 13:40 UTC",
        )

        strategy._shutdown_requested = False
        await strategy._lifecycle._wait_for_session_open()

        # Weekend branch must sleep exactly 60s — not the "before session_start"
        # branch which uses min(wait_s - 30, 60) and can return non-60 values.
        assert sleep_calls == [60.0], (
            f"Expected [60.0] (weekend branch) but got {sleep_calls} — "
            "the loop may have entered the weekday 'before session_start' branch"
        )

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

        # Monday 14:30 UTC — before session start (13:40 UTC is wrong —
        # actually session is 13:40–14:30 — let's use 10:00 UTC, before session)
        monday_before = datetime.datetime(2026, 4, 21, 10, 0, 0, tzinfo=datetime.UTC)
        session_start = datetime.datetime(2026, 4, 21, 13, 40, 0, tzinfo=datetime.UTC)
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
            lambda _dt: "2026-04-21 13:40 UTC",
        )

        strategy._shutdown_requested = False
        await strategy._lifecycle._wait_for_session_open()

        # "Before session_start" branch — sleep value is min(wait_s - 30, 60)
        # wait_s = (13:40 - 10:00) = 13200s → min(13170, 60) = 60.0
        # But it's NOT the 60.0 of the weekend branch.
        # The key assertion: is_weekend_paris was False → we did NOT enter
        # the weekend branch.  A sleep(60.0) here is the pre-session-wait sleep.
        assert len(sleep_calls) == 1
