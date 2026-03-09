"""ALPHAEDGE — Pure-Python stub for fcr_detector (Cython fallback)."""

from __future__ import annotations

from typing import Any


def detect_fcr(
    candles_data: list[dict[str, Any]],
    min_range_pips: float,
    pip_size: float,
) -> dict[str, Any] | None:
    """Detect FCR from the last M5 candle before session open."""
    if not candles_data:
        return None

    last = candles_data[-1]
    range_pips = (last["high"] - last["low"]) / pip_size
    if range_pips < min_range_pips:
        return None

    return {
        "detected": True,
        "range_high": last["high"],
        "range_low": last["low"],
        "range_size": last["high"] - last["low"],
        "candle_timestamp": last["timestamp"],
    }


def detect_fcr_scan(
    candles_data: list[dict[str, Any]],
    min_range_pips: float,
    pip_size: float,
    lookback: int,
) -> dict[str, Any] | None:
    """Scan last N M5 candles for the strongest FCR candidate."""
    if not candles_data:
        return None

    start_idx = max(0, len(candles_data) - lookback)
    candidates = candles_data[start_idx:]

    best_range = 0.0
    best_result: dict[str, Any] | None = None

    for candle in candidates:
        range_pips = (candle["high"] - candle["low"]) / pip_size
        if range_pips < min_range_pips:
            continue
        range_size = candle["high"] - candle["low"]
        if range_size > best_range:
            best_range = range_size
            best_result = {
                "detected": True,
                "range_high": candle["high"],
                "range_low": candle["low"],
                "range_size": range_size,
                "candle_timestamp": candle["timestamp"],
            }

    return best_result
