# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_volatility_regime.py
# DESCRIPTION  : Tests for volatility regime filter
# ============================================================
"""ALPHAEDGE — T4.1: Volatility regime filter tests."""

from __future__ import annotations

from typing import Any

import pytest

from alphaedge.config.constants import (
    REGIME_ATR_HIGH_MULTIPLIER,
    REGIME_ATR_LOOKBACK_DAYS,
    REGIME_ATR_LOW_MULTIPLIER,
)
from alphaedge.utils.volatility_regime import (
    VolatilityRegimeResult,
    check_volatility_regime,
    compute_daily_atr,
    compute_rolling_atr,
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _make_daily_bars(n: int = 25, base_range: float = 0.0050) -> list[dict[str, Any]]:
    """Create n daily bars with a consistent range."""
    bars: list[dict[str, Any]] = []
    price = 1.08000
    for _ in range(n):
        bars.append(
            {
                "open": price,
                "high": price + base_range / 2,
                "low": price - base_range / 2,
                "close": price + 0.0001,
            }
        )
        price += 0.0001
    return bars


# ------------------------------------------------------------------
# compute_daily_atr
# ------------------------------------------------------------------
class TestComputeDailyAtr:
    def test_empty_returns_empty(self) -> None:
        assert compute_daily_atr([]) == []

    def test_single_bar(self) -> None:
        bars = [{"high": 1.0850, "low": 1.0800, "close": 1.0830}]
        trs = compute_daily_atr(bars)
        assert len(trs) == 1
        assert trs[0] == pytest.approx(0.0050)

    def test_true_range_uses_prev_close(self) -> None:
        """TR = max(H-L, |H-prevC|, |L-prevC|) when gap exists."""
        bars = [
            {"high": 1.0850, "low": 1.0800, "close": 1.0810},
            {"high": 1.0900, "low": 1.0860, "close": 1.0880},
        ]
        trs = compute_daily_atr(bars)
        assert len(trs) == 2
        # Bar 1: H-L=0.005, first bar
        assert trs[0] == pytest.approx(0.005)
        # Bar 2: H-L=0.004, |H-prevC|=|1.0900-1.0810|=0.009,
        #         |L-prevC|=|1.0860-1.0810|=0.005 → TR=0.009
        assert trs[1] == pytest.approx(0.009)

    def test_consistent_ranges(self) -> None:
        bars = _make_daily_bars(10, base_range=0.0050)
        trs = compute_daily_atr(bars)
        assert len(trs) == 10
        # First bar gets H-L = 0.005 exactly
        assert trs[0] == pytest.approx(0.0050)


# ------------------------------------------------------------------
# compute_rolling_atr
# ------------------------------------------------------------------
class TestComputeRollingAtr:
    def test_insufficient_data_returns_zero(self) -> None:
        bars = _make_daily_bars(10)
        assert compute_rolling_atr(bars, lookback=20) == 0.0

    def test_exact_lookback(self) -> None:
        bars = _make_daily_bars(20, base_range=0.0050)
        atr = compute_rolling_atr(bars, lookback=20)
        assert atr > 0.0

    def test_uses_last_n_bars(self) -> None:
        """Only last N bars count for the rolling mean."""
        small_bars = _make_daily_bars(10, base_range=0.002)
        big_bars = _make_daily_bars(20, base_range=0.010)
        combined = small_bars + big_bars
        atr = compute_rolling_atr(combined, lookback=20)
        # Should be dominated by the bigger ranges
        assert atr > 0.005

    def test_default_lookback_is_20(self) -> None:
        bars = _make_daily_bars(25, base_range=0.0050)
        atr_default = compute_rolling_atr(bars)
        atr_explicit = compute_rolling_atr(bars, lookback=REGIME_ATR_LOOKBACK_DAYS)
        assert atr_default == atr_explicit


# ------------------------------------------------------------------
# check_volatility_regime
# ------------------------------------------------------------------
class TestCheckVolatilityRegime:
    def test_normal_range_allowed(self) -> None:
        daily = _make_daily_bars(20, base_range=0.0050)
        current = {"high": 1.09000, "low": 1.08500}  # range = 0.005
        result = check_volatility_regime(daily, current)
        assert isinstance(result, VolatilityRegimeResult)
        assert result.allowed is True
        assert result.reason == "normal"

    def test_too_quiet_blocked(self) -> None:
        daily = _make_daily_bars(20, base_range=0.0100)
        # Range = 0.001 which is < 0.5 × 0.01 = 0.005
        current = {"high": 1.08050, "low": 1.07960}  # 0.0009
        result = check_volatility_regime(daily, current)
        assert result.allowed is False
        assert result.reason == "too_quiet"

    def test_too_volatile_blocked(self) -> None:
        daily = _make_daily_bars(20, base_range=0.0050)
        # Range = 0.020 which is > 2.0 × 0.005 = 0.010 (approx)
        current = {"high": 1.10000, "low": 1.08000}  # 0.02
        result = check_volatility_regime(daily, current)
        assert result.allowed is False
        assert result.reason == "too_volatile"

    def test_insufficient_data_allows_trading(self) -> None:
        daily = _make_daily_bars(5)  # < 20
        current = {"high": 1.09, "low": 1.08}
        result = check_volatility_regime(daily, current)
        assert result.allowed is True
        assert result.reason == "insufficient_data"

    def test_thresholds_computed(self) -> None:
        daily = _make_daily_bars(20, base_range=0.0050)
        current = {"high": 1.09000, "low": 1.08500}
        result = check_volatility_regime(daily, current)
        assert result.rolling_mean_atr > 0
        assert result.low_threshold == pytest.approx(
            result.rolling_mean_atr * REGIME_ATR_LOW_MULTIPLIER
        )
        assert result.high_threshold == pytest.approx(
            result.rolling_mean_atr * REGIME_ATR_HIGH_MULTIPLIER
        )

    def test_custom_multipliers(self) -> None:
        daily = _make_daily_bars(20, base_range=0.0050)
        current = {"high": 1.09000, "low": 1.08500}
        # Very tight filter: only accept exact match
        result = check_volatility_regime(daily, current, low_mult=0.99, high_mult=1.01)
        # Current range ~= rolling ATR so this might pass or fail
        # depending on exact numbers, but thresholds should be tighter
        assert result.high_threshold < result.rolling_mean_atr * 2.0

    def test_boundary_at_low_threshold(self) -> None:
        """ATR exactly at low threshold should be allowed (>=)."""
        daily = _make_daily_bars(20, base_range=0.0100)
        rolling = compute_rolling_atr(daily, 20)
        low_val = rolling * REGIME_ATR_LOW_MULTIPLIER
        current = {"high": 1.08000 + low_val, "low": 1.08000}
        result = check_volatility_regime(daily, current)
        assert result.allowed is True

    def test_boundary_at_high_threshold(self) -> None:
        """ATR exactly at high threshold should be allowed (<=)."""
        daily = _make_daily_bars(20, base_range=0.0050)
        rolling = compute_rolling_atr(daily, 20)
        high_val = rolling * REGIME_ATR_HIGH_MULTIPLIER
        current = {"high": 1.08000 + high_val, "low": 1.08000}
        result = check_volatility_regime(daily, current)
        assert result.allowed is True

    def test_result_carries_current_atr(self) -> None:
        daily = _make_daily_bars(20, base_range=0.0050)
        current = {"high": 1.09000, "low": 1.08200}
        result = check_volatility_regime(daily, current)
        assert result.current_atr == pytest.approx(0.008)
