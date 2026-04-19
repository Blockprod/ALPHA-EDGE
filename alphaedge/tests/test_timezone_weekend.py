# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/tests/test_timezone_weekend.py
# DESCRIPTION  : Tests for weekend guard in timezone utils
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — Momentum+Carry Forex Trading Bot: timezone weekend guard tests."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from alphaedge.utils.timezone import is_session_active, is_weekend_paris


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


class TestIsWeekendParis:
    """Tests for is_weekend_paris() — Paris-time weekend detection.

    The critical edge cases are the UTC/Paris boundary crossings:
    - Friday night Paris: UTC is still Friday, Paris is already Saturday.
    - Sunday night Paris: UTC is still Sunday, Paris is already Monday.
    """

    # ------------------------------------------------------------------
    # Plain weekend days (no ambiguity)
    # ------------------------------------------------------------------
    def test_saturday_paris_returns_true(self) -> None:
        """Saturday afternoon in Paris → True."""
        # Saturday, January 25, 2025 at 14:00 UTC = 15:00 CET
        dt = datetime(2025, 1, 25, 14, 0, tzinfo=ZoneInfo("UTC"))
        assert is_weekend_paris(dt) is True

    def test_sunday_paris_returns_true(self) -> None:
        """Sunday afternoon in Paris → True."""
        # Sunday, January 26, 2025 at 14:00 UTC = 15:00 CET
        dt = datetime(2025, 1, 26, 14, 0, tzinfo=ZoneInfo("UTC"))
        assert is_weekend_paris(dt) is True

    def test_monday_paris_returns_false(self) -> None:
        """Monday in Paris → False."""
        # Monday, January 27, 2025 at 14:00 UTC = 15:00 CET
        dt = datetime(2025, 1, 27, 14, 0, tzinfo=ZoneInfo("UTC"))
        assert is_weekend_paris(dt) is False

    def test_friday_midday_paris_returns_false(self) -> None:
        """Friday midday in Paris → False."""
        # Friday, January 24, 2025 at 14:00 UTC = 15:00 CET
        dt = datetime(2025, 1, 24, 14, 0, tzinfo=ZoneInfo("UTC"))
        assert is_weekend_paris(dt) is False

    # ------------------------------------------------------------------
    # Edge case — CET (winter): Friday 23:30 UTC = Saturday 00:30 CET
    # UTC still says Friday (weekday 4), Paris says Saturday (weekday 5).
    # A UTC-based check would wrongly allow gateway launch.
    # ------------------------------------------------------------------
    def test_friday_night_utc_is_saturday_paris_cet(self) -> None:
        """Friday 23:30 UTC = Saturday 00:30 CET → must return True (Paris Saturday)."""
        dt = datetime(2025, 1, 24, 23, 30, tzinfo=ZoneInfo("UTC"))
        # UTC says Friday (weekday 4) but Paris CET says Saturday (weekday 5)
        assert dt.weekday() == 4, "pre-condition: UTC day is Friday"
        assert is_weekend_paris(dt) is True

    # ------------------------------------------------------------------
    # Edge case — CEST (summer): Friday 22:30 UTC = Saturday 00:30 CEST
    # ------------------------------------------------------------------
    def test_friday_night_utc_is_saturday_paris_cest(self) -> None:
        """Friday 22:30 UTC = Saturday 00:30 CEST → True (Paris Saturday)."""
        # Friday July 4, 2025 22:30 UTC = Saturday July 5 00:30 CEST
        dt = datetime(2025, 7, 4, 22, 30, tzinfo=ZoneInfo("UTC"))
        assert dt.weekday() == 4, "pre-condition: UTC day is Friday"
        assert is_weekend_paris(dt) is True

    # ------------------------------------------------------------------
    # Edge case — Sunday night Paris → Monday UTC not yet reached.
    # Sunday 22:30 Paris CET = 21:30 UTC → still Sunday in both zones.
    # The gateway MUST remain blocked.
    # ------------------------------------------------------------------
    def test_sunday_night_paris_still_sunday(self) -> None:
        """Sunday 22:30 Paris CET = 21:30 UTC → still weekend, must return True."""
        # Sunday, January 26, 2025 21:30 UTC = 22:30 CET
        dt = datetime(2025, 1, 26, 21, 30, tzinfo=ZoneInfo("UTC"))
        assert is_weekend_paris(dt) is True

    # ------------------------------------------------------------------
    # Confirm: once Paris crosses into Monday, returns False
    # (even though UTC may still be Sunday for up to 2 hours in CEST).
    # Paris is UTC+1/+2 so Paris Monday always starts BEFORE UTC Monday.
    # ------------------------------------------------------------------
    def test_sunday_utc_already_monday_paris_is_impossible(self) -> None:
        """Paris is ahead of UTC — Sunday UTC cannot be Monday Paris.

        Paris is UTC+1 (CET) or UTC+2 (CEST), so Monday 00:00 Paris
        equals Sunday 23:00 or 22:00 UTC.  Verify that at 23:30 UTC Sunday
        (= Monday 00:30 Paris CET) is_weekend_paris correctly returns False.
        """
        # Sunday January 26 23:30 UTC = Monday January 27 00:30 CET
        dt = datetime(2025, 1, 26, 23, 30, tzinfo=ZoneInfo("UTC"))
        assert dt.weekday() == 6, "pre-condition: UTC day is Sunday"
        assert is_weekend_paris(dt) is False
