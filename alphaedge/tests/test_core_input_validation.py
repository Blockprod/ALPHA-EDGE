# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/tests/test_core_input_validation.py
# DESCRIPTION  : P3-04 — robustness: None/NaN/inf/negative inputs
#                must not crash core functions (anti-segfault)
# PYTHON       : 3.11.9
# ============================================================
"""P3-04: Core input validation — malformed inputs return safe results.

Tests run against the Python stubs (ALPHAEDGE_CORE_BACKEND=stubs).
The same guards are mirrored in the .pyx Cython files.
"""

from __future__ import annotations

from typing import Any

from alphaedge.core import momentum_detector, order_manager, risk_manager
from alphaedge.core.types import BracketOrderResult, PositionSizeResult

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_valid_bars(n: int = 30) -> list[dict[str, Any]]:
    """Build a minimal list of valid OHLC bars."""
    price = 1.1000
    bars = []
    for i in range(n):
        bars.append(
            {
                "open": price,
                "high": price + 0.001,
                "low": price - 0.001,
                "close": price + 0.0005,
                "timestamp": i * 86400000,
            }
        )
        price += 0.0001
    return bars


def _call_size(
    account_equity: float = 10000.0,
    sl_pips: float = 20.0,
    pip_size: float = 0.0001,
) -> PositionSizeResult:
    return risk_manager.calculate_position_size(
        account_equity=account_equity,
        risk_pct=1.0,
        sl_pips=sl_pips,
        pair="EURUSD",
        pip_size=pip_size,
        lot_type="micro",
        min_lots=0.01,
        max_lots=10.0,
    )


def _call_bracket(
    pip_size: float = 0.0001,
    spread_pips: float = 0.5,
) -> BracketOrderResult:
    return order_manager.create_bracket_order(
        direction=1,
        entry_price=1.1000,
        stop_loss=1.0980,
        take_profit=1.1040,
        lot_size=0.1,
        pip_size=pip_size,
        spread_pips=spread_pips,
        max_spread_pips=2.0,
        min_rr=1.5,
        min_lots=0.01,
        max_lots=10.0,
        adjust_for_spread=False,
    )


# ------------------------------------------------------------------
# detect_momentum — malformed bars
# ------------------------------------------------------------------


class TestDetectMomentumInvalidBars:
    def test_close_none_returns_none(self) -> None:
        """A bar with close=None must not crash — returns None."""
        bars = _make_valid_bars(30)
        bars[-1]["close"] = None
        result = momentum_detector.detect_momentum(
            bars=bars,
            fast_period=12,
            slow_period=26,
            adx_period=14,
            adx_threshold=25.0,
        )
        assert result is None

    def test_close_nan_returns_none(self) -> None:
        """A bar with close=NaN must not crash — returns None."""
        bars = _make_valid_bars(30)
        bars[-1]["close"] = float("nan")
        result = momentum_detector.detect_momentum(
            bars=bars,
            fast_period=12,
            slow_period=26,
            adx_period=14,
            adx_threshold=25.0,
        )
        assert result is None

    def test_close_inf_returns_none(self) -> None:
        """A bar with close=inf must not crash — returns None."""
        bars = _make_valid_bars(30)
        bars[5]["close"] = float("inf")
        result = momentum_detector.detect_momentum(
            bars=bars,
            fast_period=12,
            slow_period=26,
            adx_period=14,
            adx_threshold=25.0,
        )
        assert result is None

    def test_close_negative_returns_none(self) -> None:
        """A bar with close=-1.0 (IB sentinel) must not crash — returns None."""
        bars = _make_valid_bars(30)
        bars[10]["close"] = -1.0
        result = momentum_detector.detect_momentum(
            bars=bars,
            fast_period=12,
            slow_period=26,
            adx_period=14,
            adx_threshold=25.0,
        )
        assert result is None

    def test_close_zero_returns_none(self) -> None:
        """A bar with close=0.0 must not crash — returns None."""
        bars = _make_valid_bars(30)
        bars[0]["close"] = 0.0
        result = momentum_detector.detect_momentum(
            bars=bars,
            fast_period=12,
            slow_period=26,
            adx_period=14,
            adx_threshold=25.0,
        )
        assert result is None

    def test_close_string_nan_returns_none(self) -> None:
        """A bar with close='NaN' (string from bad CSV) must not crash."""
        bars = _make_valid_bars(30)
        bars[2]["close"] = "NaN"
        result = momentum_detector.detect_momentum(
            bars=bars,
            fast_period=12,
            slow_period=26,
            adx_period=14,
            adx_threshold=25.0,
        )
        assert result is None

    def test_bar_missing_ohlc_key_returns_none(self) -> None:
        """A bar missing the 'high' key entirely must return None."""
        bars = _make_valid_bars(30)
        del bars[1]["high"]
        result = momentum_detector.detect_momentum(
            bars=bars,
            fast_period=12,
            slow_period=26,
            adx_period=14,
            adx_threshold=25.0,
        )
        assert result is None


# ------------------------------------------------------------------
# _validate_bar utility
# ------------------------------------------------------------------


class TestValidateBar:
    def test_valid_bar_returns_true(self) -> None:
        from alphaedge.core._stubs.momentum_detector import _validate_bar

        assert _validate_bar({"open": 1.1, "high": 1.11, "low": 1.09, "close": 1.105})

    def test_none_close_returns_false(self) -> None:
        from alphaedge.core._stubs.momentum_detector import _validate_bar

        assert not _validate_bar(
            {"open": 1.1, "high": 1.11, "low": 1.09, "close": None}
        )

    def test_nan_high_returns_false(self) -> None:
        from alphaedge.core._stubs.momentum_detector import _validate_bar

        assert not _validate_bar(
            {"open": 1.1, "high": float("nan"), "low": 1.09, "close": 1.105}
        )

    def test_negative_low_returns_false(self) -> None:
        from alphaedge.core._stubs.momentum_detector import _validate_bar

        assert not _validate_bar(
            {"open": 1.1, "high": 1.11, "low": -0.01, "close": 1.105}
        )


# ------------------------------------------------------------------
# calculate_position_size — malformed numeric inputs
# ------------------------------------------------------------------


class TestCalculatePositionSizeInvalidInputs:
    def test_sl_pips_negative_is_invalid(self) -> None:
        result = _call_size(sl_pips=-5.0)
        assert result["is_valid"] is False

    def test_sl_pips_zero_is_invalid(self) -> None:
        result = _call_size(sl_pips=0.0)
        assert result["is_valid"] is False

    def test_pip_size_zero_is_invalid(self) -> None:
        result = _call_size(pip_size=0.0)
        assert result["is_valid"] is False

    def test_account_equity_nan_is_invalid(self) -> None:
        result = _call_size(account_equity=float("nan"))
        assert result["is_valid"] is False

    def test_sl_pips_nan_is_invalid(self) -> None:
        result = _call_size(sl_pips=float("nan"))
        assert result["is_valid"] is False

    def test_pip_size_inf_is_invalid(self) -> None:
        result = _call_size(pip_size=float("inf"))
        assert result["is_valid"] is False


# ------------------------------------------------------------------
# create_bracket_order — malformed numeric inputs
# ------------------------------------------------------------------


class TestCreateBracketOrderInvalidInputs:
    def test_pip_size_zero_is_invalid(self) -> None:
        result = _call_bracket(pip_size=0.0)
        assert result["is_valid"] is False
        assert result["rejection_reason"] == "invalid_pip_size"

    def test_pip_size_negative_is_invalid(self) -> None:
        result = _call_bracket(pip_size=-0.0001)
        assert result["is_valid"] is False
        assert result["rejection_reason"] == "invalid_pip_size"

    def test_spread_too_wide_is_invalid(self) -> None:
        result = _call_bracket(spread_pips=5.0)
        assert result["is_valid"] is False
        assert result["rejection_reason"] == "spread_too_wide"
