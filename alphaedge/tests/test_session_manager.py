# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_session_manager.py
# DESCRIPTION  : Tests for multi-session window manager
# ============================================================
"""ALPHAEDGE — T4.2: Multi-session manager tests."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from alphaedge.utils.session_manager import (
    LONDON_SESSION,
    NYSE_SESSION,
    SessionWindow,
    build_sessions_from_config,
    get_active_sessions,
    is_any_session_active,
)

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


# ------------------------------------------------------------------
# SessionWindow.contains
# ------------------------------------------------------------------
class TestSessionWindowContains:
    def test_nyse_within_window(self) -> None:
        dt = datetime(2024, 1, 2, 10, 0, tzinfo=ET)  # Tuesday 10:00 ET
        assert NYSE_SESSION.contains(dt) is True

    def test_nyse_at_start(self) -> None:
        dt = datetime(2024, 1, 2, 9, 30, tzinfo=ET)
        assert NYSE_SESSION.contains(dt) is True

    def test_nyse_at_end(self) -> None:
        dt = datetime(2024, 1, 2, 10, 30, tzinfo=ET)
        assert NYSE_SESSION.contains(dt) is True

    def test_nyse_before_window(self) -> None:
        dt = datetime(2024, 1, 2, 9, 29, tzinfo=ET)
        assert NYSE_SESSION.contains(dt) is False

    def test_nyse_after_window(self) -> None:
        dt = datetime(2024, 1, 2, 10, 31, tzinfo=ET)
        assert NYSE_SESSION.contains(dt) is False

    def test_nyse_weekend_rejected(self) -> None:
        dt = datetime(2024, 1, 6, 10, 0, tzinfo=ET)  # Saturday
        assert NYSE_SESSION.contains(dt) is False

    def test_london_within_window(self) -> None:
        london_on = SessionWindow(
            name="London Open",
            start_hour=8,
            start_minute=0,
            end_hour=9,
            end_minute=0,
            tz_name="UTC",
            enabled=True,
        )
        dt = datetime(2024, 1, 2, 8, 30, tzinfo=UTC)
        assert london_on.contains(dt) is True

    def test_london_outside_window(self) -> None:
        london_on = SessionWindow(
            name="London Open",
            start_hour=8,
            start_minute=0,
            end_hour=9,
            end_minute=0,
            tz_name="UTC",
            enabled=True,
        )
        dt = datetime(2024, 1, 2, 9, 1, tzinfo=UTC)
        assert london_on.contains(dt) is False

    def test_disabled_session_never_active(self) -> None:
        disabled = SessionWindow(
            name="Test",
            start_hour=0,
            start_minute=0,
            end_hour=23,
            end_minute=59,
            tz_name="UTC",
            enabled=False,
        )
        dt = datetime(2024, 1, 2, 12, 0, tzinfo=UTC)
        assert disabled.contains(dt) is False

    def test_london_default_disabled(self) -> None:
        """LONDON_SESSION is disabled by default."""
        dt = datetime(2024, 1, 2, 8, 30, tzinfo=UTC)
        assert LONDON_SESSION.enabled is False
        assert LONDON_SESSION.contains(dt) is False


# ------------------------------------------------------------------
# SessionWindow.get_window_utc
# ------------------------------------------------------------------
class TestSessionWindowGetWindowUtc:
    def test_nyse_returns_utc_pair(self) -> None:
        ref = datetime(2024, 1, 2, 12, 0, tzinfo=UTC)
        start, end = NYSE_SESSION.get_window_utc(ref)
        assert start.tzinfo is not None
        assert end.tzinfo is not None
        assert start < end

    def test_london_utc_no_offset(self) -> None:
        london_on = SessionWindow(
            name="London Open",
            start_hour=8,
            start_minute=0,
            end_hour=9,
            end_minute=0,
            tz_name="UTC",
            enabled=True,
        )
        ref = datetime(2024, 1, 2, 12, 0, tzinfo=UTC)
        start, end = london_on.get_window_utc(ref)
        assert start.hour == 8
        assert end.hour == 9


# ------------------------------------------------------------------
# get_active_sessions / is_any_session_active
# ------------------------------------------------------------------
class TestGetActiveSessions:
    def test_nyse_active_during_nyse_hours(self) -> None:
        dt = datetime(2024, 1, 2, 10, 0, tzinfo=ET)
        sessions = [NYSE_SESSION]
        active = get_active_sessions(dt, sessions)
        assert len(active) == 1
        assert active[0].name == "NYSE Open"

    def test_no_sessions_active_at_midnight(self) -> None:
        dt = datetime(2024, 1, 2, 3, 0, tzinfo=UTC)
        sessions = [NYSE_SESSION, LONDON_SESSION]
        active = get_active_sessions(dt, sessions)
        assert len(active) == 0

    def test_both_sessions_checked(self) -> None:
        london_on = SessionWindow(
            name="London Open",
            start_hour=8,
            start_minute=0,
            end_hour=9,
            end_minute=0,
            tz_name="UTC",
            enabled=True,
        )
        dt = datetime(2024, 1, 2, 8, 30, tzinfo=UTC)
        sessions = [NYSE_SESSION, london_on]
        active = get_active_sessions(dt, sessions)
        names = [s.name for s in active]
        assert "London Open" in names

    def test_is_any_session_active_true(self) -> None:
        dt = datetime(2024, 1, 2, 10, 0, tzinfo=ET)
        assert is_any_session_active(dt, [NYSE_SESSION]) is True

    def test_is_any_session_active_false(self) -> None:
        dt = datetime(2024, 1, 2, 3, 0, tzinfo=UTC)
        assert is_any_session_active(dt, [NYSE_SESSION]) is False


# ------------------------------------------------------------------
# build_sessions_from_config
# ------------------------------------------------------------------
class TestBuildSessionsFromConfig:
    def test_default_nyse_only(self) -> None:
        sessions = build_sessions_from_config()
        assert len(sessions) == 1
        assert sessions[0].name == "NYSE Open"

    def test_both_enabled(self) -> None:
        sessions = build_sessions_from_config(nyse_enabled=True, london_enabled=True)
        assert len(sessions) == 2
        names = {s.name for s in sessions}
        assert "NYSE Open" in names
        assert "London Open" in names

    def test_london_only(self) -> None:
        sessions = build_sessions_from_config(nyse_enabled=False, london_enabled=True)
        assert len(sessions) == 1
        assert sessions[0].name == "London Open"
        assert sessions[0].enabled is True

    def test_none_enabled(self) -> None:
        sessions = build_sessions_from_config(nyse_enabled=False, london_enabled=False)
        assert len(sessions) == 0

    def test_london_built_as_enabled(self) -> None:
        """London session from build_sessions should be enabled=True."""
        sessions = build_sessions_from_config(london_enabled=True)
        london = [s for s in sessions if s.name == "London Open"]
        assert len(london) == 1
        assert london[0].enabled is True
        dt = datetime(2024, 1, 2, 8, 30, tzinfo=UTC)
        assert london[0].contains(dt) is True
