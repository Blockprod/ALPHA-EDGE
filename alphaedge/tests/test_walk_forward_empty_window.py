# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/tests/test_walk_forward_empty_window.py
# DESCRIPTION  : S-05 — walk-forward edge case: N<5 bars returns empty report
# ============================================================
"""ALPHAEDGE — S-05: Verify walk-forward handles too-few bars without crash."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from alphaedge.config.loader import AppConfig
from alphaedge.engine.walk_forward import WalkForwardReport, run_walk_forward


def _make_bar(dt: datetime, close: float = 1.085) -> dict[str, Any]:
    return {
        "datetime": dt,
        "open": close,
        "high": close + 0.001,
        "low": close - 0.001,
        "close": close,
        "volume": 100,
    }


def _make_bars(n: int) -> list[dict[str, Any]]:
    """Generate n daily bars starting from 2024-01-02 at 10:00 ET."""
    base = datetime(2024, 1, 2, 10, 0, tzinfo=ZoneInfo("America/New_York"))
    return [_make_bar(base + timedelta(days=i)) for i in range(n)]


class TestWalkForwardEmptyWindow:
    """S-05 — walk-forward must not crash when data is too short."""

    def test_empty_bars_returns_empty_report(self) -> None:
        """Zero bars: run_walk_forward returns an empty WalkForwardReport."""
        report = run_walk_forward([], "EURUSD", AppConfig())
        assert isinstance(report, WalkForwardReport)
        assert report.windows == []
        assert report.aggregated_oos.total_trades == 0

    def test_single_bar_returns_empty_report(self) -> None:
        """Single bar: too short for any window, returns empty report."""
        report = run_walk_forward(_make_bars(1), "EURUSD", AppConfig())
        assert isinstance(report, WalkForwardReport)
        assert report.windows == []

    def test_four_bars_returns_empty_report(self) -> None:
        """Four bars: still too short for 3-month train + 1-month test."""
        report = run_walk_forward(_make_bars(4), "EURUSD", AppConfig())
        assert isinstance(report, WalkForwardReport)
        assert report.windows == []

    def test_insufficient_data_no_crash(self) -> None:
        """run_walk_forward never raises even with extremely short data."""
        for n in range(6):
            report = run_walk_forward(_make_bars(n), "EURUSD", AppConfig())
            assert isinstance(report, WalkForwardReport)
            assert report.windows == []

    def test_data_range_returns_valid_report_structure(self) -> None:
        """Even with no windows, the report has valid default aggregated stats."""
        report = run_walk_forward(_make_bars(2), "EURUSD", AppConfig())
        assert report.aggregated_oos.total_trades == 0
        assert report.aggregated_oos.winrate == 0.0
        assert report.aggregated_oos_optimized.total_trades == 0
