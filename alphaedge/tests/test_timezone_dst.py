# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_timezone_dst.py
# DESCRIPTION  : Tests for DST transition handling in timezone utils
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: timezone DST transition tests."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from alphaedge.utils.timezone import (
    get_session_window_utc,
    is_dst_transition_week,
    is_session_active,
)


class TestTimezoneDST:
    """Tests for correct DST handling in session window calculations."""

    def test_session_window_est_winter(self) -> None:
        """Session 9:30-10:30 ET in EST (UTC-5) should be 14:30-15:30 UTC."""
        # January 15, 2025 — EST (no DST)
        ref = datetime(2025, 1, 15, 10, 0, tzinfo=ZoneInfo("America/New_York"))
        start, end = get_session_window_utc(ref)

        assert start.hour == 14
        assert start.minute == 30
        assert end.hour == 15
        assert end.minute == 30

    def test_session_window_edt_summer(self) -> None:
        """Session 9:30-10:30 ET in EDT (UTC-4) should be 13:30-14:30 UTC."""
        # July 15, 2025 — EDT (DST active)
        ref = datetime(2025, 7, 15, 10, 0, tzinfo=ZoneInfo("America/New_York"))
        start, end = get_session_window_utc(ref)

        assert start.hour == 13
        assert start.minute == 30
        assert end.hour == 14
        assert end.minute == 30

    def test_session_active_dst_spring_forward(self) -> None:
        """Session should be active at correct UTC time after spring-forward."""
        # March 10, 2025 — DST starts (clocks spring forward)
        # 9:45 ET = 13:45 UTC (EDT, UTC-4)
        dt_utc = datetime(2025, 3, 10, 13, 45, tzinfo=ZoneInfo("UTC"))
        assert is_session_active(dt_utc) is True

        # 14:00 ET = 18:00 UTC — well outside session
        dt_utc_outside = datetime(2025, 3, 10, 18, 0, tzinfo=ZoneInfo("UTC"))
        assert is_session_active(dt_utc_outside) is False

    def test_session_active_dst_fall_back(self) -> None:
        """Session should be active at correct UTC time after fall-back."""
        # November 3, 2025 — DST ends (clocks fall back)
        # 9:45 ET = 14:45 UTC (EST, UTC-5)
        dt_utc = datetime(2025, 11, 3, 14, 45, tzinfo=ZoneInfo("UTC"))
        assert is_session_active(dt_utc) is True

        # 13:45 UTC = 8:45 ET — before session
        dt_utc_before = datetime(2025, 11, 3, 13, 45, tzinfo=ZoneInfo("UTC"))
        assert is_session_active(dt_utc_before) is False

    def test_session_window_utc_offset_changes(self) -> None:
        """UTC offsets should differ between EST and EDT dates."""
        est_ref = datetime(2025, 1, 15, 10, 0, tzinfo=ZoneInfo("America/New_York"))
        edt_ref = datetime(2025, 7, 15, 10, 0, tzinfo=ZoneInfo("America/New_York"))

        est_start, _ = get_session_window_utc(est_ref)
        edt_start, _ = get_session_window_utc(edt_ref)

        # EST start is 14:30 UTC, EDT start is 13:30 UTC — 1 hour difference
        assert est_start.hour - edt_start.hour == 1


class TestDSTTransitionWeek:
    """Tests for is_dst_transition_week() spring EU/US divergence detection."""

    def test_inside_transition_2025(self) -> None:
        """March 15, 2025 is between US (Mar 9) and EU (Mar 30) spring-forward."""
        dt = datetime(2025, 3, 15, 12, 0, tzinfo=ZoneInfo("UTC"))
        assert is_dst_transition_week(dt) is True

    def test_before_us_transition_2025(self) -> None:
        """March 8, 2025 is before US spring-forward (Mar 9) — not in window."""
        dt = datetime(2025, 3, 8, 12, 0, tzinfo=ZoneInfo("UTC"))
        assert is_dst_transition_week(dt) is False

    def test_us_transition_day_inclusive_2025(self) -> None:
        """March 9, 2025 is the US spring-forward day — included (inclusive start)."""
        dt = datetime(2025, 3, 9, 12, 0, tzinfo=ZoneInfo("UTC"))
        assert is_dst_transition_week(dt) is True

    def test_eu_transition_day_exclusive_2025(self) -> None:
        """March 30, 2025 is the EU spring-forward day — excluded (exclusive end)."""
        dt = datetime(2025, 3, 30, 12, 0, tzinfo=ZoneInfo("UTC"))
        assert is_dst_transition_week(dt) is False

    def test_after_eu_transition_2025(self) -> None:
        """April 1, 2025 is well after EU spring-forward — not in window."""
        dt = datetime(2025, 4, 1, 12, 0, tzinfo=ZoneInfo("UTC"))
        assert is_dst_transition_week(dt) is False

    def test_winter_date_not_in_window(self) -> None:
        """January 15, 2025 is outside any DST transition window."""
        dt = datetime(2025, 1, 15, 12, 0, tzinfo=ZoneInfo("UTC"))
        assert is_dst_transition_week(dt) is False

    def test_inside_transition_2024(self) -> None:
        """March 15, 2024 is between US (Mar 10) and EU (Mar 31) spring-forward."""
        dt = datetime(2024, 3, 15, 12, 0, tzinfo=ZoneInfo("UTC"))
        assert is_dst_transition_week(dt) is True

    def test_eu_transition_day_exclusive_2024(self) -> None:
        """March 31, 2024 is the EU spring-forward day — excluded."""
        dt = datetime(2024, 3, 31, 12, 0, tzinfo=ZoneInfo("UTC"))
        assert is_dst_transition_week(dt) is False
