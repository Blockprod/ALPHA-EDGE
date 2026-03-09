"""ALPHAEDGE — Pure-Python stub for gap_detector (Cython fallback)."""

from __future__ import annotations

from typing import Any


def detect_gap(
    pre_session_m1: list[dict[str, Any]],
    session_m1: list[dict[str, Any]],
    pre_close: float,
    session_open: float,
    atr_period: int,
    min_atr_ratio: float,
) -> dict[str, Any]:
    """Detect NYSE-open volatility expansion as Forex gap equivalent."""
    baseline = _compute_atr(pre_session_m1, atr_period)
    current = _compute_atr(session_m1, atr_period)

    ratio = 0.0
    if baseline > 0.0:
        ratio = current / baseline

    gap_size = abs(session_open - pre_close)

    if session_open > pre_close:
        direction = 1
    elif session_open < pre_close:
        direction = -1
    else:
        direction = 0

    if ratio >= min_atr_ratio:
        if pre_close > session_open:
            gap_high, gap_low = pre_close, session_open
        else:
            gap_high, gap_low = session_open, pre_close
        return {
            "detected": True,
            "gap_high": gap_high,
            "gap_low": gap_low,
            "gap_size": gap_size,
            "atr_ratio": ratio,
            "direction": direction,
        }

    return {
        "detected": False,
        "gap_high": 0.0,
        "gap_low": 0.0,
        "gap_size": 0.0,
        "atr_ratio": ratio,
        "direction": direction,
    }


def is_in_gap_zone(
    price: float,
    gap_high: float,
    gap_low: float,
    tolerance_pips: float,
    pip_size: float,
) -> bool:
    """Check if a price is inside or near the gap zone."""
    tolerance = tolerance_pips * pip_size
    extended_high = gap_high + tolerance
    extended_low = gap_low - tolerance
    return extended_low <= price <= extended_high


def _compute_atr(candles: list[dict[str, Any]], period: int) -> float:
    """Calculate simple ATR from candle high-low ranges."""
    if not candles or period <= 0:
        return 0.0
    count = min(period, len(candles))
    total: float = sum(
        float(candles[-(i + 1)]["high"]) - float(candles[-(i + 1)]["low"])
        for i in range(count)
    )
    return total / count
