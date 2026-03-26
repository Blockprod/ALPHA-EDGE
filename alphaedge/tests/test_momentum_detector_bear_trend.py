# ============================================================
# PROJECT      : ALPHAEDGE
# FILE         : alphaedge/tests/test_momentum_detector_bear_trend.py
# DESCRIPTION  : Happy-path: clear bearish trend → direction == -1, ADX >= 25
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-25
# ============================================================
"""ALPHAEDGE — Momentum detector: bear-trend detection."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("ALPHAEDGE_CORE_BACKEND", "stubs")

from alphaedge.core._stubs.momentum_detector import detect_momentum  # noqa: E402


def _make_bear_bars(n: int = 35) -> list[dict]:
    """Return *n* Daily bars with monotonically decreasing OHLC (clear downtrend)."""
    bars = []
    base = 1.13500
    for i in range(n):
        close = base - i * 0.00100
        bars.append(
            {
                "open": close + 0.00040,
                "high": close + 0.00050,
                "low": close - 0.00050,
                "close": close,
                "timestamp": 1_700_000_000_000 + i * 86_400_000,
            }
        )
    return bars


def test_bear_trend_detected() -> None:
    bars = _make_bear_bars(35)
    result = detect_momentum(
        bars=bars,
        fast_period=12,
        slow_period=26,
        adx_period=14,
        adx_threshold=25.0,
    )
    assert result is not None, "Expected a momentum signal on a clear bear trend"
    assert result["detected"] is True
    assert result["direction"] == -1, (
        f"Expected direction=-1, got {result['direction']}"
    )
    assert result["adx"] >= 25.0, f"Expected ADX >= 25, got {result['adx']}"
    assert 0.0 < result["strength"] <= 1.0
    assert result["ema_fast"] < result["ema_slow"]
    assert result["timestamp"] > 0


@pytest.mark.parametrize("n", [35, 50, 80])
def test_bear_trend_various_lengths(n: int) -> None:
    bars = _make_bear_bars(n)
    result = detect_momentum(
        bars=bars,
        fast_period=12,
        slow_period=26,
        adx_period=14,
        adx_threshold=25.0,
    )
    assert result is not None
    assert result["direction"] == -1
