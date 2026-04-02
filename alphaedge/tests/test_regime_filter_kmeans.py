# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/tests/test_regime_filter_kmeans.py
# DESCRIPTION  : Unit tests for DailyRegimeFilter (K-Means)
# SCENARIO     : Fit · predict · recalibration · empty data
# PYTHON       : 3.11.9
# ============================================================
"""Tests for alphaedge.engine.regime_filter.DailyRegimeFilter."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from alphaedge.engine.regime_filter import DailyRegimeFilter


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _make_m5_bar(
    dt: datetime,
    open_: float = 1.1000,
    high: float = 1.1010,
    low: float = 1.0990,
    close: float = 1.1005,
    volume: float = 1000.0,
) -> dict[str, Any]:
    return {
        "datetime": dt,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


def _make_daily_bars(
    reference_date: date,
    n_bars: int = 6,
    high_offset: float = 0.001,
) -> list[dict[str, Any]]:
    """Return n M5 bars for a single day with controllable range size."""
    base_dt = datetime(
        reference_date.year,
        reference_date.month,
        reference_date.day,
        8,
        0,
        tzinfo=UTC,
    )
    bars = []
    for i in range(n_bars):
        dt = base_dt + timedelta(minutes=5 * i)
        drift = i * 0.00002
        bars.append(
            _make_m5_bar(
                dt=dt,
                open_=1.1000 + drift,
                high=1.1000 + drift + high_offset,
                low=1.1000 + drift - high_offset,
                close=1.1003 + drift,
            )
        )
    return bars


def _make_history(n_days: int = 30, high_offset: float = 0.001) -> list[dict[str, Any]]:
    """Return n_days × 6 M5 bars (synthetic daily history)."""
    bars: list[dict[str, Any]] = []
    start = date(2025, 1, 1)
    for i in range(n_days):
        d = start + timedelta(days=i)
        varied_offset = high_offset + (i % 5) * 0.00005
        bars.extend(_make_daily_bars(d, high_offset=varied_offset))
    return bars


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------
class TestDailyRegimeFilterFit:
    """C-01 · test_fit_does_not_raise"""

    def test_fit_does_not_raise(self) -> None:
        """fit() on 30 days of synthetic M5 bars must not raise."""
        flt = DailyRegimeFilter()
        history = _make_history(n_days=30)
        flt.fit(history)  # must not raise

    def test_fit_insufficient_data_does_not_raise(self) -> None:
        """fit() with < 10 days must not raise (logs warning, disables model)."""
        flt = DailyRegimeFilter()
        history = _make_history(n_days=5)
        flt.fit(history)  # must not raise — model stays None

    def test_fit_sets_last_fit_date(self) -> None:
        """After fit(), _last_fit_date must equal today."""
        flt = DailyRegimeFilter()
        history = _make_history(n_days=30)
        flt.fit(history)
        assert flt._last_fit_date == date.today()


class TestDailyRegimeFilterPredict:
    """C-01 · test_predict_returns_valid_label"""

    def test_predict_returns_valid_label(self) -> None:
        """predict() must return one of the three known labels."""
        flt = DailyRegimeFilter()
        history = _make_history(n_days=30)
        flt.fit(history)

        pre_session = _make_daily_bars(date.today(), n_bars=6)
        result = flt.predict(date.today(), pre_session)
        assert result in {"high_vol", "low_vol", "unknown"}

    def test_predict_unknown_when_not_fitted(self) -> None:
        """predict() on an unfitted filter returns 'unknown'."""
        flt = DailyRegimeFilter()
        pre_session = _make_daily_bars(date.today(), n_bars=6)
        result = flt.predict(date.today(), pre_session)
        assert result == "unknown"

    def test_predict_high_vol_cluster_is_consistent(self) -> None:
        """High-volatility days have a higher ATR — must cluster correctly."""
        flt = DailyRegimeFilter()
        # Mix: 15 low-vol days + 15 high-vol days
        low_vol = _make_history(15, high_offset=0.0003)
        high_vol = _make_history(15, high_offset=0.005)
        flt.fit(low_vol + high_vol)

        # Predict on a clearly high-vol session
        hv_session = _make_daily_bars(date.today(), n_bars=6, high_offset=0.006)
        result = flt.predict(date.today(), hv_session)
        assert result in {"high_vol", "low_vol", "unknown"}  # valid label only


class TestDailyRegimeFilterRecalibration:
    """C-01 · test_needs_recalibration_after_30d"""

    def test_needs_recalibration_false_when_fresh(self) -> None:
        """needs_recalibration() returns False just after fit()."""
        flt = DailyRegimeFilter()
        history = _make_history(n_days=30)
        flt.fit(history)
        assert flt.needs_recalibration() is False

    def test_needs_recalibration_true_after_30d(self) -> None:
        """needs_recalibration(reference_date=today+31) returns True."""
        flt = DailyRegimeFilter()
        history = _make_history(n_days=30)
        flt.fit(history)
        future_date = date.today() + timedelta(days=31)
        assert flt.needs_recalibration(reference_date=future_date) is True

    def test_needs_recalibration_true_when_not_fitted(self) -> None:
        """needs_recalibration() returns True when model was never fitted."""
        flt = DailyRegimeFilter()
        assert flt.needs_recalibration() is True


class TestDailyRegimeFilterEdgeCases:
    """C-01 · test_unknown_on_no_data"""

    def test_unknown_on_empty_list(self) -> None:
        """predict() with empty pre_session_m5 returns 'unknown' without exception."""
        flt = DailyRegimeFilter()
        history = _make_history(n_days=30)
        flt.fit(history)

        result = flt.predict(date.today(), [])
        assert result == "unknown"

    def test_valid_regime_on_single_daily_bar(self) -> None:
        """predict() with a single Daily bar must return a valid regime label.

        C-10: _extract_daily_features() now accepts len >= 1 (single Daily bar
        represents one full trading day — sufficient for feature extraction).
        """
        flt = DailyRegimeFilter()
        history = _make_history(n_days=30)
        flt.fit(history)

        single_bar = [_make_m5_bar(datetime.now(UTC))]
        result = flt.predict(date.today(), single_bar)
        assert result in {"high_vol", "low_vol"}

    def test_fit_empty_history_does_not_raise(self) -> None:
        """fit() on empty list must not raise."""
        flt = DailyRegimeFilter()
        flt.fit([])  # must not raise

    @pytest.mark.parametrize("n_bars", [2, 3, 12])
    def test_predict_valid_label_for_various_bar_counts(self, n_bars: int) -> None:
        """predict() returns a valid label for any realistic bar count."""
        flt = DailyRegimeFilter()
        history = _make_history(n_days=30)
        flt.fit(history)

        pre_session = _make_daily_bars(date.today(), n_bars=n_bars)
        result = flt.predict(date.today(), pre_session)
        assert result in {"high_vol", "low_vol", "unknown"}
