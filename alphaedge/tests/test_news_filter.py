# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_news_filter.py
# DESCRIPTION  : Tests for economic news blackout filter (T2.2)
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-08
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: news filter tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from alphaedge.utils.news_filter import (
    EconomicNewsFilter,
    NewsEvent,
    NewsFilterConfig,
)


def _utc(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    """Build a timezone-aware UTC datetime."""
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


# ------------------------------------------------------------------
# NFP-style blackout test
# ------------------------------------------------------------------
class TestNFPBlackout:
    """NFP on first Friday of month at 13:30 UTC (8:30 ET)."""

    def test_nfp_blackout_blocks_signal(self) -> None:
        """Signal during NFP ±15min window is blocked."""
        nfp_time = _utc(2026, 3, 6, 13, 30)  # Friday 8:30 ET
        config = NewsFilterConfig(enabled=True, blackout_minutes=15)
        nf = EconomicNewsFilter(config)
        nf._events = [
            NewsEvent(
                event_time=nfp_time,
                currency="USD",
                impact="high",
                title="Non-Farm Payrolls",
            ),
        ]

        # 13:20 UTC = 5 min before NFP - 15 = inside window
        assert nf.is_news_blackout(_utc(2026, 3, 6, 13, 20), "EURUSD") is True

    def test_nfp_blackout_before_window(self) -> None:
        """Signal well before NFP window passes through."""
        nfp_time = _utc(2026, 3, 6, 13, 30)
        config = NewsFilterConfig(enabled=True, blackout_minutes=15)
        nf = EconomicNewsFilter(config)
        nf._events = [
            NewsEvent(
                event_time=nfp_time,
                currency="USD",
                impact="high",
                title="Non-Farm Payrolls",
            ),
        ]

        # 13:00 UTC = 30 min before → outside 15-min window
        assert nf.is_news_blackout(_utc(2026, 3, 6, 13, 0), "EURUSD") is False

    def test_nfp_does_not_block_unrelated_pair(self) -> None:
        """USD news does not block EURGBP."""
        nfp_time = _utc(2026, 3, 6, 13, 30)
        config = NewsFilterConfig(enabled=True, blackout_minutes=15)
        nf = EconomicNewsFilter(config)
        nf._events = [
            NewsEvent(
                event_time=nfp_time,
                currency="USD",
                impact="high",
                title="Non-Farm Payrolls",
            ),
        ]

        assert nf.is_news_blackout(_utc(2026, 3, 6, 13, 25), "EURGBP") is False


# ------------------------------------------------------------------
# Disabled filter test
# ------------------------------------------------------------------
class TestNewsFilterDisabled:
    """When filter is disabled, nothing is blocked."""

    def test_disabled_allows_all(self) -> None:
        """Disabled filter never blocks."""
        nfp_time = _utc(2026, 3, 6, 13, 30)
        config = NewsFilterConfig(enabled=False, blackout_minutes=15)
        nf = EconomicNewsFilter(config)
        nf._events = [
            NewsEvent(
                event_time=nfp_time,
                currency="USD",
                impact="high",
                title="Non-Farm Payrolls",
            ),
        ]

        # Right at event time, but filter disabled
        assert nf.is_news_blackout(nfp_time, "EURUSD") is False


# ------------------------------------------------------------------
# No events → no blocking
# ------------------------------------------------------------------
class TestNewsFilterNoEvents:
    """Empty calendar never blocks."""

    def test_no_events_allows_all(self) -> None:
        """No events means no blackout."""
        config = NewsFilterConfig(enabled=True, blackout_minutes=15)
        nf = EconomicNewsFilter(config)
        nf._events = []

        assert nf.is_news_blackout(_utc(2026, 3, 6, 14, 0), "EURUSD") is False


# ------------------------------------------------------------------
# Impact level filtering
# ------------------------------------------------------------------
class TestImpactLevelFilter:
    """Only configured impact levels trigger blackout."""

    def test_medium_impact_ignored_when_only_high(self) -> None:
        """Medium-impact event is ignored when filter is set to 'high' only."""
        event_time = _utc(2026, 3, 6, 14, 0)
        config = NewsFilterConfig(
            enabled=True,
            blackout_minutes=15,
            impact_levels=["high"],
        )
        nf = EconomicNewsFilter(config)
        nf._events = [
            NewsEvent(
                event_time=event_time,
                currency="EUR",
                impact="medium",
                title="EU Consumer Confidence",
            ),
        ]

        assert nf.is_news_blackout(event_time, "EURUSD") is False

    def test_high_impact_blocked(self) -> None:
        """High-impact event triggers blackout."""
        event_time = _utc(2026, 3, 6, 14, 0)
        config = NewsFilterConfig(
            enabled=True,
            blackout_minutes=15,
            impact_levels=["high"],
        )
        nf = EconomicNewsFilter(config)
        nf._events = [
            NewsEvent(
                event_time=event_time,
                currency="EUR",
                impact="high",
                title="ECB Rate Decision",
            ),
        ]

        assert nf.is_news_blackout(event_time, "EURUSD") is True


# ------------------------------------------------------------------
# Window boundary precision
# ------------------------------------------------------------------
class TestBlackoutWindow:
    """Edge cases at the exact window boundaries."""

    def test_exactly_at_window_start(self) -> None:
        """Exactly at window_start (event - blackout_minutes) is blocked."""
        event_time = _utc(2026, 3, 6, 14, 0)
        config = NewsFilterConfig(enabled=True, blackout_minutes=15)
        nf = EconomicNewsFilter(config)
        nf._events = [
            NewsEvent(event_time=event_time, currency="USD", impact="high"),
        ]

        window_start = event_time - timedelta(minutes=15)
        assert nf.is_news_blackout(window_start, "USDJPY") is True

    def test_one_second_before_window_passes(self) -> None:
        """One second before window_start is not blocked."""
        event_time = _utc(2026, 3, 6, 14, 0)
        config = NewsFilterConfig(enabled=True, blackout_minutes=15)
        nf = EconomicNewsFilter(config)
        nf._events = [
            NewsEvent(event_time=event_time, currency="USD", impact="high"),
        ]

        just_before = event_time - timedelta(minutes=15, seconds=1)
        assert nf.is_news_blackout(just_before, "USDJPY") is False
