# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_variable_slippage.py
# DESCRIPTION  : Tests for variable slippage model
# ============================================================
"""ALPHAEDGE — T3.7: Variable slippage model tests."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from alphaedge.config.constants import (
    BASE_SLIPPAGE_PIPS,
    BASE_SPREAD_BY_PAIR,
    BASE_SPREAD_PIPS,
    NEWS_SLIPPAGE_MULTIPLIER,
    NEWS_SPREAD_PIPS,
    NYSE_OPEN_SLIPPAGE_MULTIPLIER,
    NYSE_OPEN_SPREAD_PIPS,
)
from alphaedge.engine.backtest import compute_variable_slippage

ET = ZoneInfo("America/New_York")


# ------------------------------------------------------------------
# compute_variable_slippage
# ------------------------------------------------------------------
class TestComputeVariableSlippage:
    def test_normal_conditions(self) -> None:
        """Outside NYSE open window → base slippage + base spread."""
        bar_time = datetime(2024, 1, 2, 10, 15, tzinfo=ET)  # 10:15 ET
        cost = compute_variable_slippage(bar_time)
        assert cost == pytest.approx(BASE_SLIPPAGE_PIPS + BASE_SPREAD_PIPS)

    def test_nyse_open_window(self) -> None:
        """9:30 ET → elevated slippage and spread."""
        bar_time = datetime(2024, 1, 2, 9, 30, tzinfo=ET)
        cost = compute_variable_slippage(bar_time)
        expected = (
            BASE_SLIPPAGE_PIPS * NYSE_OPEN_SLIPPAGE_MULTIPLIER + NYSE_OPEN_SPREAD_PIPS
        )
        assert cost == pytest.approx(expected)

    def test_nyse_open_minute_31(self) -> None:
        """9:31 ET → still in NYSE open window (first 5 min)."""
        bar_time = datetime(2024, 1, 2, 9, 31, tzinfo=ET)
        cost = compute_variable_slippage(bar_time)
        expected = (
            BASE_SLIPPAGE_PIPS * NYSE_OPEN_SLIPPAGE_MULTIPLIER + NYSE_OPEN_SPREAD_PIPS
        )
        assert cost == pytest.approx(expected)

    def test_nyse_open_minute_34(self) -> None:
        """9:34 ET → still in NYSE open window (last minute)."""
        bar_time = datetime(2024, 1, 2, 9, 34, tzinfo=ET)
        cost = compute_variable_slippage(bar_time)
        expected = (
            BASE_SLIPPAGE_PIPS * NYSE_OPEN_SLIPPAGE_MULTIPLIER + NYSE_OPEN_SPREAD_PIPS
        )
        assert cost == pytest.approx(expected)

    def test_after_nyse_open_window(self) -> None:
        """9:35 ET → back to normal conditions."""
        bar_time = datetime(2024, 1, 2, 9, 35, tzinfo=ET)
        cost = compute_variable_slippage(bar_time)
        assert cost == pytest.approx(BASE_SLIPPAGE_PIPS + BASE_SPREAD_PIPS)

    def test_news_event_highest_cost(self) -> None:
        """News event → highest slippage and spread."""
        bar_time = datetime(2024, 1, 2, 9, 30, tzinfo=ET)
        cost = compute_variable_slippage(bar_time, is_news=True)
        expected = BASE_SLIPPAGE_PIPS * NEWS_SLIPPAGE_MULTIPLIER + NEWS_SPREAD_PIPS
        assert cost == pytest.approx(expected)

    def test_news_overrides_nyse_open(self) -> None:
        """News during NYSE open → news cost takes priority."""
        bar_time = datetime(2024, 1, 2, 9, 30, tzinfo=ET)
        cost_news = compute_variable_slippage(bar_time, is_news=True)
        cost_nyse = compute_variable_slippage(bar_time, is_news=False)
        assert cost_news > cost_nyse

    def test_none_bar_time(self) -> None:
        """None bar_time → base slippage + base spread."""
        cost = compute_variable_slippage(None)
        assert cost == pytest.approx(BASE_SLIPPAGE_PIPS + BASE_SPREAD_PIPS)

    def test_variable_higher_than_fixed(self) -> None:
        """NYSE open slippage should exceed the old fixed 0.8 total."""
        bar_time = datetime(2024, 1, 2, 9, 30, tzinfo=ET)
        cost = compute_variable_slippage(bar_time)
        old_fixed = 0.5 + 0.3  # DEFAULT_SLIPPAGE_PIPS + DEFAULT_MARKET_SLIPPAGE_PIPS
        assert cost > old_fixed

    def test_news_slippage_value(self) -> None:
        """Verify news slippage is 1.5 pips per spec."""
        bar_time = datetime(2024, 1, 2, 10, 0, tzinfo=ET)
        cost = compute_variable_slippage(bar_time, is_news=True)
        news_slippage = BASE_SLIPPAGE_PIPS * NEWS_SLIPPAGE_MULTIPLIER
        assert news_slippage == pytest.approx(1.5)
        assert cost == pytest.approx(news_slippage + NEWS_SPREAD_PIPS)

    def test_different_hours_normal(self) -> None:
        """Various non-NYSE-open hours → all return base cost."""
        base_cost = BASE_SLIPPAGE_PIPS + BASE_SPREAD_PIPS
        for hour in [8, 10, 11, 14, 16]:
            bar_time = datetime(2024, 1, 2, hour, 0, tzinfo=ET)
            assert compute_variable_slippage(bar_time) == pytest.approx(base_cost)


class TestPerPairSpread:
    """Verify per-pair base spreads are used in normal conditions."""

    def test_gbpjpy_higher_spread_than_eurusd(self) -> None:
        """GBP/JPY spread (3.0) should exceed EUR/USD (0.8)."""
        bar_time = datetime(2024, 1, 2, 10, 0, tzinfo=ET)
        cost_eurusd = compute_variable_slippage(bar_time, pair="EURUSD")
        cost_gbpjpy = compute_variable_slippage(bar_time, pair="GBPJPY")
        assert cost_gbpjpy > cost_eurusd

    def test_eurusd_normal_spread(self) -> None:
        """EUR/USD should use its 0.8 pip spread."""
        bar_time = datetime(2024, 1, 2, 10, 0, tzinfo=ET)
        cost = compute_variable_slippage(bar_time, pair="EURUSD")
        expected = BASE_SLIPPAGE_PIPS + BASE_SPREAD_BY_PAIR["EURUSD"]
        assert cost == pytest.approx(expected)

    def test_gbpjpy_normal_spread(self) -> None:
        """GBP/JPY should use its 3.0 pip spread."""
        bar_time = datetime(2024, 1, 2, 10, 0, tzinfo=ET)
        cost = compute_variable_slippage(bar_time, pair="GBPJPY")
        expected = BASE_SLIPPAGE_PIPS + BASE_SPREAD_BY_PAIR["GBPJPY"]
        assert cost == pytest.approx(expected)

    def test_unknown_pair_falls_back_to_base(self) -> None:
        """Unknown pair falls back to BASE_SPREAD_PIPS."""
        bar_time = datetime(2024, 1, 2, 10, 0, tzinfo=ET)
        cost = compute_variable_slippage(bar_time, pair="XYZABC")
        expected = BASE_SLIPPAGE_PIPS + BASE_SPREAD_PIPS
        assert cost == pytest.approx(expected)

    def test_news_overrides_per_pair_spread(self) -> None:
        """News events override per-pair spread with NEWS_SPREAD_PIPS."""
        bar_time = datetime(2024, 1, 2, 10, 0, tzinfo=ET)
        cost = compute_variable_slippage(bar_time, is_news=True, pair="GBPJPY")
        expected = BASE_SLIPPAGE_PIPS * NEWS_SLIPPAGE_MULTIPLIER + NEWS_SPREAD_PIPS
        assert cost == pytest.approx(expected)

    def test_all_defined_pairs_have_spread(self) -> None:
        """Every pair in BASE_SPREAD_BY_PAIR has a positive spread."""
        for pair, spread in BASE_SPREAD_BY_PAIR.items():
            assert spread > 0.0, f"{pair} has non-positive spread {spread}"
