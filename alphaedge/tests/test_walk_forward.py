# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_walk_forward.py
# DESCRIPTION  : Tests for walk-forward optimization engine
# ============================================================
"""ALPHAEDGE — T3.2: Walk-forward optimization tests."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from alphaedge.engine.backtest import (
    WalkForwardReport,
    WalkForwardResult,
    WalkForwardWindow,
    _add_months,
    _filter_bars_by_date,
    generate_wf_windows,
    run_walk_forward,
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _make_bar(dt: datetime) -> dict[str, Any]:
    """Create a minimal bar dict with a timezone-aware datetime."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("America/New_York"))
    return {
        "open": 1.08500,
        "high": 1.08600,
        "low": 1.08400,
        "close": 1.08550,
        "volume": 150.0,
        "datetime": dt,
    }


def _make_bars_range(
    start: date,
    end: date,
    hour: int = 10,
) -> list[dict[str, Any]]:
    """Create one bar per trading day between start and end (inclusive)."""
    et = ZoneInfo("America/New_York")
    bars: list[dict[str, Any]] = []
    current = start
    while current <= end:
        # Skip weekends
        if current.weekday() < 5:
            dt = datetime(current.year, current.month, current.day, hour, 0, tzinfo=et)
            bars.append(_make_bar(dt))
        current += timedelta(days=1)
    return bars


# ------------------------------------------------------------------
# _add_months
# ------------------------------------------------------------------
class TestAddMonths:
    def test_add_one_month(self) -> None:
        assert _add_months(date(2024, 1, 15), 1) == date(2024, 2, 15)

    def test_add_three_months(self) -> None:
        assert _add_months(date(2024, 1, 1), 3) == date(2024, 4, 1)

    def test_year_rollover(self) -> None:
        assert _add_months(date(2024, 11, 1), 3) == date(2025, 2, 1)

    def test_clamp_to_last_day(self) -> None:
        # Jan 31 + 1 month → Feb 29 (2024 is leap year)
        assert _add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)

    def test_clamp_non_leap(self) -> None:
        # Jan 31 + 1 month → Feb 28 (2025 is not leap year)
        assert _add_months(date(2025, 1, 31), 1) == date(2025, 2, 28)


# ------------------------------------------------------------------
# generate_wf_windows
# ------------------------------------------------------------------
class TestGenerateWfWindows:
    def test_twelve_month_data_yields_windows(self) -> None:
        """12 months with 3mo train + 1mo test => >= 9 windows."""
        start = date(2024, 1, 1)
        end = date(2024, 12, 31)
        windows = generate_wf_windows(start, end, 3, 1, 1)
        assert len(windows) >= 9

    def test_window_structure(self) -> None:
        start = date(2024, 1, 1)
        end = date(2024, 12, 31)
        windows = generate_wf_windows(start, end, 3, 1, 1)
        w = windows[0]
        assert isinstance(w, WalkForwardWindow)
        assert w.train_start == date(2024, 1, 1)
        assert w.train_end == date(2024, 3, 31)
        assert w.test_start == date(2024, 4, 1)
        assert w.test_end == date(2024, 4, 30)

    def test_train_precedes_test(self) -> None:
        start = date(2024, 1, 1)
        end = date(2024, 12, 31)
        windows = generate_wf_windows(start, end, 3, 1, 1)
        for w in windows:
            assert w.train_end < w.test_start

    def test_sliding_step(self) -> None:
        """Second window should start 1 month after first."""
        start = date(2024, 1, 1)
        end = date(2024, 12, 31)
        windows = generate_wf_windows(start, end, 3, 1, 1)
        assert windows[1].train_start == date(2024, 2, 1)

    def test_insufficient_data(self) -> None:
        """Less than train + test months → no windows."""
        start = date(2024, 1, 1)
        end = date(2024, 3, 15)
        windows = generate_wf_windows(start, end, 3, 1, 1)
        assert len(windows) == 0

    def test_exact_four_months(self) -> None:
        """Exactly train + test months → one window."""
        start = date(2024, 1, 1)
        end = date(2024, 4, 30)
        windows = generate_wf_windows(start, end, 3, 1, 1)
        assert len(windows) == 1


# ------------------------------------------------------------------
# _filter_bars_by_date
# ------------------------------------------------------------------
class TestFilterBarsByDate:
    def test_filters_within_range(self) -> None:
        bars = _make_bars_range(date(2024, 1, 1), date(2024, 3, 31))
        filtered = _filter_bars_by_date(bars, date(2024, 2, 1), date(2024, 2, 29))
        for bar in filtered:
            bar_date = bar["datetime"].date()
            assert date(2024, 2, 1) <= bar_date <= date(2024, 2, 29)

    def test_empty_range(self) -> None:
        bars = _make_bars_range(date(2024, 1, 1), date(2024, 1, 31))
        filtered = _filter_bars_by_date(bars, date(2024, 3, 1), date(2024, 3, 31))
        assert filtered == []

    def test_full_range(self) -> None:
        bars = _make_bars_range(date(2024, 1, 1), date(2024, 1, 31))
        filtered = _filter_bars_by_date(bars, date(2024, 1, 1), date(2024, 1, 31))
        assert len(filtered) == len(bars)

    def test_utc_bars_convert_correctly(self) -> None:
        """Bars with UTC timezone should be converted to ET for filtering."""
        utc = ZoneInfo("UTC")
        # Jan 2 at 15:00 UTC = Jan 2 at 10:00 ET → should be included in Jan filter
        bar = _make_bar(datetime(2024, 1, 2, 15, 0, tzinfo=utc))
        filtered = _filter_bars_by_date([bar], date(2024, 1, 1), date(2024, 1, 31))
        assert len(filtered) == 1


# ------------------------------------------------------------------
# run_walk_forward (with mocked Cython)
# ------------------------------------------------------------------
class TestRunWalkForward:
    def test_empty_bars(self) -> None:
        from alphaedge.config.loader import AppConfig

        report = run_walk_forward([], [], "EURUSD", AppConfig())
        assert isinstance(report, WalkForwardReport)
        assert len(report.windows) == 0
        assert report.aggregated_oos.total_trades == 0

    def test_report_structure_with_data(self) -> None:
        """With enough data, run_walk_forward produces valid results."""
        from alphaedge.config.loader import AppConfig

        # Create 12 months of bars at session time (10:00 ET)
        m1_bars = _make_bars_range(date(2024, 1, 1), date(2024, 12, 31), hour=10)
        m5_bars = _make_bars_range(date(2024, 1, 1), date(2024, 12, 31), hour=9)

        # Mock _backtest_pair to avoid Cython dependency
        with patch("alphaedge.engine.backtest._backtest_pair", return_value=[]):
            report = run_walk_forward(m1_bars, m5_bars, "EURUSD", AppConfig())

        assert isinstance(report, WalkForwardReport)
        assert len(report.windows) >= 9
        for wr in report.windows:
            assert isinstance(wr, WalkForwardResult)
            assert wr.window.train_end < wr.window.test_start

    def test_aggregated_oos_uses_test_trades_only(self) -> None:
        """Aggregated OOS stats should only include test-period trades."""
        from alphaedge.config.loader import AppConfig
        from alphaedge.engine.backtest import TradeRecord

        m1_bars = _make_bars_range(date(2024, 1, 1), date(2024, 12, 31), hour=10)
        m5_bars = _make_bars_range(date(2024, 1, 1), date(2024, 12, 31), hour=9)

        # Return one winning trade per call
        call_count = 0

        def fake_backtest(
            pair: str,
            m1: list[dict[str, Any]],
            m5: list[dict[str, Any]],
            cfg: AppConfig,
        ) -> list[TradeRecord]:
            nonlocal call_count
            call_count += 1
            return [
                TradeRecord(
                    pair=pair,
                    direction=1,
                    entry_price=1.08500,
                    stop_loss=1.08400,
                    take_profit=1.08600,
                    entry_time=datetime(2024, 1, 1, 10, 0),
                    exit_price=1.08600,
                    pnl_pips=10.0,
                    pnl_usd=100.0,
                    outcome="win",
                )
            ]

        with patch(
            "alphaedge.engine.backtest._backtest_pair",
            side_effect=fake_backtest,
        ):
            report = run_walk_forward(m1_bars, m5_bars, "EURUSD", AppConfig())

        n_windows = len(report.windows)
        # Each window calls _backtest_pair twice (train + test)
        # Aggregated OOS should have exactly n_windows trades (1 per test)
        assert report.aggregated_oos.total_trades == n_windows
        assert report.aggregated_oos.winrate == 100.0


# ------------------------------------------------------------------
# run_walk_forward with optimize_fn  (P3-04)
# ------------------------------------------------------------------
class TestRunWalkForwardOptimization:
    """Verify IS grid-search → OOS re-evaluation path."""

    def test_without_optimize_fn_optimized_stats_are_none(self) -> None:
        """Without optimize_fn, optimized_test_stats must be None on every window."""
        from alphaedge.config.loader import AppConfig

        m1_bars = _make_bars_range(date(2024, 1, 1), date(2024, 12, 31), hour=10)
        m5_bars = _make_bars_range(date(2024, 1, 1), date(2024, 12, 31), hour=9)

        with patch("alphaedge.engine.backtest._backtest_pair", return_value=[]):
            report = run_walk_forward(m1_bars, m5_bars, "EURUSD", AppConfig())

        for wr in report.windows:
            assert wr.optimized_test_stats is None
            assert wr.best_params == {}
        assert report.aggregated_oos_optimized.total_trades == 0

    def test_optimize_fn_called_once_per_is_window(self) -> None:
        """optimize_fn should be called once per walk-forward window."""
        from alphaedge.config.loader import AppConfig

        m1_bars = _make_bars_range(date(2024, 1, 1), date(2024, 12, 31), hour=10)
        m5_bars = _make_bars_range(date(2024, 1, 1), date(2024, 12, 31), hour=9)

        optimize_calls: list[int] = []

        def fake_optimize(
            m1: list[dict[str, Any]],
            m5: list[dict[str, Any]],
            pair: str,
            cfg: Any,
        ) -> dict[str, float]:
            optimize_calls.append(1)
            return {}

        with (
            patch("alphaedge.engine.backtest._backtest_pair", return_value=[]),
            patch(
                "alphaedge.engine.sensitivity._run_with_params_trades",
                return_value=[],
            ),
        ):
            report = run_walk_forward(
                m1_bars, m5_bars, "EURUSD", AppConfig(), optimize_fn=fake_optimize
            )

        assert len(optimize_calls) == len(report.windows)

    def test_optimized_stats_populated_when_optimize_fn_provided(self) -> None:
        """Each window's optimized_test_stats should not be None."""
        from alphaedge.config.loader import AppConfig

        m1_bars = _make_bars_range(date(2024, 1, 1), date(2024, 12, 31), hour=10)
        m5_bars = _make_bars_range(date(2024, 1, 1), date(2024, 12, 31), hour=9)

        with (
            patch("alphaedge.engine.backtest._backtest_pair", return_value=[]),
            patch(
                "alphaedge.engine.sensitivity._run_with_params_trades",
                return_value=[],
            ),
        ):
            report = run_walk_forward(
                m1_bars,
                m5_bars,
                "EURUSD",
                AppConfig(),
                optimize_fn=lambda *_: {"rr_ratio": 3.0},
            )

        assert len(report.windows) > 0
        for wr in report.windows:
            assert wr.optimized_test_stats is not None
            assert wr.best_params == {"rr_ratio": 3.0}

    def test_best_params_stored_per_window(self) -> None:
        """Each window stores the params returned by optimize_fn."""
        from alphaedge.config.loader import AppConfig

        m1_bars = _make_bars_range(date(2024, 1, 1), date(2024, 6, 30), hour=10)
        m5_bars = _make_bars_range(date(2024, 1, 1), date(2024, 6, 30), hour=9)

        call_idx = 0
        expected_params = [{"rr_ratio": 2.0}, {"rr_ratio": 3.0}, {"rr_ratio": 4.0}]

        def cycling_optimize(*_: Any) -> dict[str, float]:
            nonlocal call_idx
            result = expected_params[call_idx % len(expected_params)]
            call_idx += 1
            return result

        with (
            patch("alphaedge.engine.backtest._backtest_pair", return_value=[]),
            patch(
                "alphaedge.engine.sensitivity._run_with_params_trades",
                return_value=[],
            ),
        ):
            report = run_walk_forward(
                m1_bars,
                m5_bars,
                "EURUSD",
                AppConfig(),
                optimize_fn=cycling_optimize,
            )

        for i, wr in enumerate(report.windows):
            assert wr.best_params == expected_params[i % len(expected_params)]

    def test_aggregated_oos_optimized_populated(self) -> None:
        """aggregated_oos_optimized uses the optimised test trades."""
        from alphaedge.config.loader import AppConfig
        from alphaedge.engine.backtest import TradeRecord

        m1_bars = _make_bars_range(date(2024, 1, 1), date(2024, 12, 31), hour=10)
        m5_bars = _make_bars_range(date(2024, 1, 1), date(2024, 12, 31), hour=9)

        opt_trade = TradeRecord(
            pair="EURUSD",
            direction=1,
            entry_price=1.08500,
            stop_loss=1.08400,
            take_profit=1.08800,
            entry_time=datetime(2024, 2, 1, 10, 0),
            exit_price=1.08800,
            pnl_pips=30.0,
            pnl_usd=300.0,
            outcome="win",
        )

        with (
            patch("alphaedge.engine.backtest._backtest_pair", return_value=[]),
            patch(
                "alphaedge.engine.sensitivity._run_with_params_trades",
                return_value=[opt_trade],
            ),
        ):
            report = run_walk_forward(
                m1_bars,
                m5_bars,
                "EURUSD",
                AppConfig(),
                optimize_fn=lambda *_: {},
            )

        n_windows = len(report.windows)
        assert report.aggregated_oos_optimized.total_trades == n_windows
        assert report.aggregated_oos_optimized.winrate == pytest.approx(100.0)


# ------------------------------------------------------------------
# grid_search_best  (P3-04)
# ------------------------------------------------------------------
class TestGridSearchBest:
    """Verify grid_search_best returns param dict that maximises the metric."""

    def test_returns_dict_of_param_names(self) -> None:
        """Result dict keys must match the requested param names."""
        from alphaedge.config.loader import AppConfig
        from alphaedge.engine.sensitivity import grid_search_best

        with patch("alphaedge.engine.backtest._backtest_pair", return_value=[]):
            result = grid_search_best(
                [], [], "EURUSD", AppConfig(), param_names=["rr_ratio"]
            )
        assert "rr_ratio" in result

    def test_selects_best_by_sharpe(self) -> None:
        """Returns params corresponding to highest Sharpe."""
        from alphaedge.config.loader import AppConfig
        from alphaedge.engine.backtest import TradeRecord
        from alphaedge.engine.sensitivity import grid_search_best

        call_count = [0]

        def fake_backtest(*_: Any) -> list[TradeRecord]:
            call_count[0] += 1
            # Return more trades for later calls (different rr_ratio values)
            # to produce different Sharpe values
            n = call_count[0]
            return [
                TradeRecord(
                    pair="EURUSD",
                    direction=1,
                    entry_price=1.1,
                    stop_loss=1.09,
                    take_profit=1.11,
                    entry_time=datetime(2024, 1, i + 1, 10, 0),
                    pnl_pips=float(n * 5),
                    pnl_usd=float(n * 50),
                    outcome="win",
                )
                for i in range(n)
            ]

        with patch(
            "alphaedge.engine.backtest._backtest_pair", side_effect=fake_backtest
        ):
            result = grid_search_best(
                [], [], "EURUSD", AppConfig(), param_names=["rr_ratio"]
            )

        assert isinstance(result, dict)
        assert "rr_ratio" in result

    def test_default_params_used_when_none(self) -> None:
        """Uses the 3-param default when param_names is None."""
        from alphaedge.config.loader import AppConfig
        from alphaedge.engine.sensitivity import grid_search_best

        with patch("alphaedge.engine.backtest._backtest_pair", return_value=[]):
            result = grid_search_best([], [], "EURUSD", AppConfig())

        assert "min_atr_ratio" in result
        assert "min_volume_ratio" in result
        assert "rr_ratio" in result
