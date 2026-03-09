# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/utils/session_manager.py
# DESCRIPTION  : Multi-session window manager (NYSE + London)
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-08
# ============================================================
"""ALPHAEDGE — T4.2: Multi-session window manager.

Provides a configurable session window abstraction that supports
both the primary NYSE Open session (9:30–10:30 ET) and an optional
London Open session (8:00–9:00 UTC).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from alphaedge.config.constants import (
    LONDON_END_HOUR,
    LONDON_END_MINUTE,
    LONDON_START_HOUR,
    LONDON_START_MINUTE,
    LONDON_TZ,
    SESSION_END_HOUR,
    SESSION_END_MINUTE,
    SESSION_START_HOUR,
    SESSION_START_MINUTE,
    TZ_NEW_YORK,
)
from alphaedge.utils.logger import get_logger

logger = get_logger()


# ------------------------------------------------------------------
# Data structures
# ------------------------------------------------------------------
@dataclass(frozen=True)
class SessionWindow:
    """A named trading session with start/end times and timezone."""

    name: str
    start_hour: int
    start_minute: int
    end_hour: int
    end_minute: int
    tz_name: str
    enabled: bool = True

    def contains(self, dt: datetime) -> bool:
        """
        Check if a datetime falls within this session window.

        Parameters
        ----------
        dt : datetime
            Timezone-aware datetime.

        Returns
        -------
        bool
            True if dt is within [start, end] in the session's timezone.
        """
        if not self.enabled:
            return False

        tz = ZoneInfo(self.tz_name)
        local = dt.astimezone(tz)

        # Weekend check (Forex closed)
        if local.weekday() >= 5:
            return False

        start_minutes = self.start_hour * 60 + self.start_minute
        end_minutes = self.end_hour * 60 + self.end_minute
        current_minutes = local.hour * 60 + local.minute

        return start_minutes <= current_minutes <= end_minutes

    def get_window_utc(self, ref: datetime) -> tuple[datetime, datetime]:
        """
        Get session start/end as UTC datetimes for a given reference date.

        Parameters
        ----------
        ref : datetime
            Reference datetime (timezone-aware).

        Returns
        -------
        tuple[datetime, datetime]
            (start_utc, end_utc).
        """
        tz = ZoneInfo(self.tz_name)
        local = ref.astimezone(tz)
        utc = ZoneInfo("UTC")

        start = local.replace(
            hour=self.start_hour,
            minute=self.start_minute,
            second=0,
            microsecond=0,
        )
        end = local.replace(
            hour=self.end_hour,
            minute=self.end_minute,
            second=0,
            microsecond=0,
        )
        return (start.astimezone(utc), end.astimezone(utc))


# ------------------------------------------------------------------
# Pre-built session definitions
# ------------------------------------------------------------------
NYSE_SESSION = SessionWindow(
    name="NYSE Open",
    start_hour=SESSION_START_HOUR,
    start_minute=SESSION_START_MINUTE,
    end_hour=SESSION_END_HOUR,
    end_minute=SESSION_END_MINUTE,
    tz_name=TZ_NEW_YORK,
    enabled=True,
)

LONDON_SESSION = SessionWindow(
    name="London Open",
    start_hour=LONDON_START_HOUR,
    start_minute=LONDON_START_MINUTE,
    end_hour=LONDON_END_HOUR,
    end_minute=LONDON_END_MINUTE,
    tz_name=LONDON_TZ,
    enabled=False,  # Disabled by default — enable after OOS validation
)


# ------------------------------------------------------------------
# Session manager
# ------------------------------------------------------------------
def get_active_sessions(
    dt: datetime,
    sessions: list[SessionWindow] | None = None,
) -> list[SessionWindow]:
    """
    Return all sessions that are active at the given time.

    Parameters
    ----------
    dt : datetime
        Timezone-aware datetime to check.
    sessions : list[SessionWindow] | None
        Sessions to check. Defaults to [NYSE_SESSION, LONDON_SESSION].

    Returns
    -------
    list[SessionWindow]
        List of active sessions (may be empty).
    """
    if sessions is None:
        sessions = [NYSE_SESSION, LONDON_SESSION]

    return [s for s in sessions if s.contains(dt)]


def is_any_session_active(
    dt: datetime,
    sessions: list[SessionWindow] | None = None,
) -> bool:
    """
    Check if any configured session is active at the given time.

    Parameters
    ----------
    dt : datetime
        Timezone-aware datetime to check.
    sessions : list[SessionWindow] | None
        Sessions to check.

    Returns
    -------
    bool
        True if at least one session window is active.
    """
    return len(get_active_sessions(dt, sessions)) > 0


def build_sessions_from_config(
    nyse_enabled: bool = True,
    london_enabled: bool = False,
) -> list[SessionWindow]:
    """
    Build session list from configuration flags.

    Parameters
    ----------
    nyse_enabled : bool
        Whether NYSE Open session is active.
    london_enabled : bool
        Whether London Open session is active.

    Returns
    -------
    list[SessionWindow]
        Configured session windows.
    """
    sessions: list[SessionWindow] = []

    if nyse_enabled:
        sessions.append(NYSE_SESSION)
        logger.info(
            f"ALPHAEDGE SESSION: {NYSE_SESSION.name} enabled "
            f"({NYSE_SESSION.start_hour:02d}:{NYSE_SESSION.start_minute:02d}"
            f"–{NYSE_SESSION.end_hour:02d}:{NYSE_SESSION.end_minute:02d} "
            f"{NYSE_SESSION.tz_name})"
        )

    if london_enabled:
        london_on = SessionWindow(
            name=LONDON_SESSION.name,
            start_hour=LONDON_SESSION.start_hour,
            start_minute=LONDON_SESSION.start_minute,
            end_hour=LONDON_SESSION.end_hour,
            end_minute=LONDON_SESSION.end_minute,
            tz_name=LONDON_SESSION.tz_name,
            enabled=True,
        )
        sessions.append(london_on)
        logger.info(
            f"ALPHAEDGE SESSION: {london_on.name} enabled "
            f"({london_on.start_hour:02d}:{london_on.start_minute:02d}"
            f"–{london_on.end_hour:02d}:{london_on.end_minute:02d} "
            f"{london_on.tz_name})"
        )

    return sessions
