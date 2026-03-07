# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/utils/timezone.py
# DESCRIPTION  : DST-aware timezone conversion using zoneinfo
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: timezone utilities with auto DST."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from alphaedge.config.constants import (
    SESSION_END_HOUR,
    SESSION_END_MINUTE,
    SESSION_START_HOUR,
    SESSION_START_MINUTE,
    TZ_NEW_YORK,
    TZ_PARIS,
    TZ_UTC,
)


# ------------------------------------------------------------------
# Get ZoneInfo objects for supported timezones
# ------------------------------------------------------------------
def get_tz_utc() -> ZoneInfo:
    """Return the UTC ZoneInfo object."""
    return ZoneInfo(TZ_UTC)


def get_tz_ny() -> ZoneInfo:
    """Return the America/New_York ZoneInfo object."""
    return ZoneInfo(TZ_NEW_YORK)


def get_tz_paris() -> ZoneInfo:
    """Return the Europe/Paris ZoneInfo object."""
    return ZoneInfo(TZ_PARIS)


# ------------------------------------------------------------------
# Get current time in a given timezone
# ------------------------------------------------------------------
def now_utc() -> datetime:
    """Return the current UTC datetime (timezone-aware)."""
    return datetime.now(tz=get_tz_utc())


def now_paris() -> datetime:
    """Return the current Europe/Paris datetime (timezone-aware)."""
    return datetime.now(tz=get_tz_paris())


def now_ny() -> datetime:
    """Return the current America/New_York datetime (timezone-aware)."""
    return datetime.now(tz=get_tz_ny())


# ------------------------------------------------------------------
# Convert a UTC datetime to a target timezone
# ------------------------------------------------------------------
def utc_to_tz(dt_utc: datetime, tz_name: str) -> datetime:
    """
    Convert a UTC datetime to the specified timezone.

    Parameters
    ----------
    dt_utc : datetime
        A timezone-aware datetime in UTC.
    tz_name : str
        Target timezone name (e.g., 'Europe/Paris').

    Returns
    -------
    datetime
        The datetime converted to the target timezone.
    """
    target_tz = ZoneInfo(tz_name)
    return dt_utc.astimezone(target_tz)


# ------------------------------------------------------------------
# Convert any aware datetime to UTC
# ------------------------------------------------------------------
def to_utc(dt_aware: datetime) -> datetime:
    """
    Convert any timezone-aware datetime to UTC.

    Parameters
    ----------
    dt_aware : datetime
        A timezone-aware datetime in any timezone.

    Returns
    -------
    datetime
        The datetime in UTC.
    """
    return dt_aware.astimezone(get_tz_utc())


# ------------------------------------------------------------------
# Get today's NYSE session window in UTC
# ------------------------------------------------------------------
def get_session_window_utc(
    date: datetime | None = None,
) -> tuple[datetime, datetime]:
    """
    Compute today's NYSE session window (9:30-10:30 ET) in UTC.

    Handles DST automatically via zoneinfo.

    Parameters
    ----------
    date : datetime | None
        Reference date. Defaults to today.

    Returns
    -------
    tuple[datetime, datetime]
        (session_start_utc, session_end_utc) as aware datetimes.
    """
    ny_tz = get_tz_ny()

    # Determine the reference date
    if date is None:
        ref = datetime.now(tz=ny_tz)
    else:
        ref = date.astimezone(ny_tz)

    # Build session start/end in NY timezone
    session_start_ny = ref.replace(
        hour=SESSION_START_HOUR,
        minute=SESSION_START_MINUTE,
        second=0,
        microsecond=0,
    )
    session_end_ny = ref.replace(
        hour=SESSION_END_HOUR,
        minute=SESSION_END_MINUTE,
        second=0,
        microsecond=0,
    )

    # Convert to UTC
    return (to_utc(session_start_ny), to_utc(session_end_ny))


# ------------------------------------------------------------------
# Check if current time is within the session window
# ------------------------------------------------------------------
def is_session_active(dt_utc: datetime | None = None) -> bool:
    """
    Check if the given UTC time falls within the NYSE session window.

    Parameters
    ----------
    dt_utc : datetime | None
        UTC datetime to check. Defaults to now.

    Returns
    -------
    bool
        True if within the 9:30-10:30 ET window.
    """
    if dt_utc is None:
        dt_utc = now_utc()

    start, end = get_session_window_utc(dt_utc)
    return start <= dt_utc <= end


# ------------------------------------------------------------------
# Format a UTC datetime for dual-column log display
# ------------------------------------------------------------------
def format_dual_time(dt_utc: datetime) -> str:
    """
    Format a UTC datetime as 'UTC_time | Paris_time' for logging.

    Parameters
    ----------
    dt_utc : datetime
        Timezone-aware UTC datetime.

    Returns
    -------
    str
        Formatted string with both UTC and Paris times.
    """
    utc_str = dt_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
    paris_dt = utc_to_tz(dt_utc, TZ_PARIS)
    paris_str = paris_dt.strftime("%Y-%m-%d %H:%M:%S %Z")
    return f"{utc_str} | {paris_str}"


# ------------------------------------------------------------------
# Get pre-session time window for FCR detection
# ------------------------------------------------------------------
def get_pre_session_window_utc(
    minutes_before: int = 30,
    date: datetime | None = None,
) -> tuple[datetime, datetime]:
    """
    Get the time window before session open for M5 FCR detection.

    Parameters
    ----------
    minutes_before : int
        How many minutes before session start to begin scanning.
    date : datetime | None
        Reference date. Defaults to today.

    Returns
    -------
    tuple[datetime, datetime]
        (window_start_utc, session_start_utc).
    """
    session_start, _ = get_session_window_utc(date)
    window_start = session_start - timedelta(minutes=minutes_before)
    return (window_start, session_start)


if __name__ == "__main__":
    print("ALPHAEDGE — Timezone Utilities Test")
    print(f"  UTC now:   {now_utc()}")
    print(f"  Paris now: {now_paris()}")
    print(f"  NY now:    {now_ny()}")

    start, end = get_session_window_utc()
    print(f"  Session:   {start} → {end}")
    print(f"  Active:    {is_session_active()}")
    print(f"  Dual:      {format_dual_time(now_utc())}")
