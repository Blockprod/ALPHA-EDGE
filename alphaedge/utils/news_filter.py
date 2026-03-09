# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/utils/news_filter.py
# DESCRIPTION  : Economic news blackout filter
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-08
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: economic news blackout filter.

Loads an economic calendar CSV and blocks trading signals during
high-impact news windows to avoid volatile whipsaw moves.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from alphaedge.config.constants import (
    DEFAULT_BLACKOUT_MINUTES,
    DEFAULT_IMPACT_LEVELS,
)
from alphaedge.utils.logger import get_logger

logger = get_logger()


# ------------------------------------------------------------------
# Data types
# ------------------------------------------------------------------
@dataclass
class NewsEvent:
    """A single economic calendar event."""

    event_time: datetime
    currency: str
    impact: str
    title: str = ""


@dataclass
class NewsFilterConfig:
    """Configuration for the news filter."""

    enabled: bool = True
    blackout_minutes: int = DEFAULT_BLACKOUT_MINUTES
    impact_levels: list[str] = field(
        default_factory=lambda: list(DEFAULT_IMPACT_LEVELS)
    )
    calendar_path: str = "data/economic_calendar.csv"


# ------------------------------------------------------------------
# CSV calendar loader
# ------------------------------------------------------------------
def _load_calendar(path: Path) -> list[NewsEvent]:
    """
    Load economic calendar events from a CSV file.

    Expected CSV columns: datetime, currency, impact, title
    datetime format: ISO 8601 (e.g., 2026-03-06T13:30:00+00:00)

    Parameters
    ----------
    path : Path
        Path to the CSV file.

    Returns
    -------
    list[NewsEvent]
        Parsed calendar events.
    """
    events: list[NewsEvent] = []
    if not path.exists():
        logger.warning(f"ALPHAEDGE NEWS: Calendar file not found: {path}")
        return events

    with open(path, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            try:
                event_time = datetime.fromisoformat(row["datetime"])
                events.append(
                    NewsEvent(
                        event_time=event_time,
                        currency=row["currency"].upper().strip(),
                        impact=row["impact"].lower().strip(),
                        title=row.get("title", "").strip(),
                    )
                )
            except (KeyError, ValueError) as exc:
                logger.debug(f"ALPHAEDGE NEWS: Skipping invalid row: {exc}")
    logger.info(f"ALPHAEDGE NEWS: Loaded {len(events)} events from {path}")
    return events


# ------------------------------------------------------------------
# Core filter
# ------------------------------------------------------------------
class EconomicNewsFilter:
    """
    Blocks trading signals during high-impact economic news windows.

    Usage::

        nf = EconomicNewsFilter(config)
        if nf.is_news_blackout(now_utc, "EURUSD"):
            # skip signal
    """

    def __init__(self, config: NewsFilterConfig) -> None:
        """Initialize the filter with configuration."""
        self._config = config
        self._events: list[NewsEvent] = []
        if config.enabled:
            self._events = _load_calendar(Path(config.calendar_path))

    @property
    def event_count(self) -> int:
        """Return total loaded events."""
        return len(self._events)

    def _pair_currencies(self, pair: str) -> tuple[str, str]:
        """Extract base and quote currencies from a pair string."""
        return pair[:3].upper(), pair[3:6].upper()

    def is_news_blackout(self, dt: datetime, pair: str) -> bool:
        """
        Check if a datetime falls within a news blackout window.

        Parameters
        ----------
        dt : datetime
            Current UTC datetime (timezone-aware).
        pair : str
            Currency pair (e.g., 'EURUSD').

        Returns
        -------
        bool
            True if trading should be blocked.
        """
        if not self._config.enabled:
            return False

        base, quote = self._pair_currencies(pair)
        half_window = timedelta(minutes=self._config.blackout_minutes)
        impact_set = {lvl.lower() for lvl in self._config.impact_levels}

        for event in self._events:
            if event.impact not in impact_set:
                continue
            if event.currency not in (base, quote):
                continue
            window_start = event.event_time - half_window
            window_end = event.event_time + half_window
            if window_start <= dt <= window_end:
                logger.warning(
                    f"ALPHAEDGE NEWS BLACKOUT: {pair} blocked — "
                    f"{event.title or event.currency} "
                    f"({event.impact}) at {event.event_time.isoformat()}"
                )
                return True

        return False


# ------------------------------------------------------------------
# Factory helper
# ------------------------------------------------------------------
def build_news_filter(raw_config: dict[str, Any]) -> EconomicNewsFilter:
    """
    Build an EconomicNewsFilter from a raw YAML config dict.

    Parameters
    ----------
    raw_config : dict
        The 'news_filter' section from config.yaml.

    Returns
    -------
    EconomicNewsFilter
        Configured filter instance.
    """
    nf_section: dict[str, Any] = raw_config.get("news_filter", {})
    config = NewsFilterConfig(
        enabled=bool(nf_section.get("enabled", True)),
        blackout_minutes=int(
            nf_section.get("blackout_minutes", DEFAULT_BLACKOUT_MINUTES)
        ),
        impact_levels=nf_section.get("impact_levels", list(DEFAULT_IMPACT_LEVELS)),
        calendar_path=str(
            nf_section.get("calendar_path", "data/economic_calendar.csv")
        ),
    )
    return EconomicNewsFilter(config)
