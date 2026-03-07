# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_timezone_weekend.py
# DESCRIPTION  : Tests for weekend guard in timezone utils
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: timezone weekend guard tests."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from alphaedge.utils.timezone import is_session_active


class TestTimezoneWeekend:
    """Tests for weekend guard in is_session_active."""

    def test_saturday_returns_false(self) -> None:
        """is_session_active should return False on Saturday."""
        # Saturday, January 18, 2025 at 14:45 UTC (inside session time)
        dt_sat = datetime(2025, 1, 18, 14, 45, tzinfo=ZoneInfo("UTC"))
        assert is_session_active(dt_sat) is False

    def test_sunday_returns_false(self) -> None:
        """is_session_active should return False on Sunday."""
        # Sunday, January 19, 2025 at 14:45 UTC (inside session time)
        dt_sun = datetime(2025, 1, 19, 14, 45, tzinfo=ZoneInfo("UTC"))
        assert is_session_active(dt_sun) is False

    def test_friday_returns_true(self) -> None:
        """is_session_active should return True on Friday during session."""
        # Friday, January 17, 2025 at 14:45 UTC (EST: 9:45 AM — in session)
        dt_fri = datetime(2025, 1, 17, 14, 45, tzinfo=ZoneInfo("UTC"))
        assert is_session_active(dt_fri) is True

    def test_monday_returns_true(self) -> None:
        """is_session_active should return True on Monday during session."""
        # Monday, January 20, 2025 at 14:45 UTC (EST: 9:45 AM — in session)
        dt_mon = datetime(2025, 1, 20, 14, 45, tzinfo=ZoneInfo("UTC"))
        assert is_session_active(dt_mon) is True

    def test_weekday_outside_session_returns_false(self) -> None:
        """is_session_active should return False outside session window."""
        # Wednesday, January 15, 2025 at 20:00 UTC (EST: 3:00 PM)
        dt_outside = datetime(2025, 1, 15, 20, 0, tzinfo=ZoneInfo("UTC"))
        assert is_session_active(dt_outside) is False
