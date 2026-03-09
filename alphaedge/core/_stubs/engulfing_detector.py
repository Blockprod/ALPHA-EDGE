"""ALPHAEDGE — Pure-Python stub for engulfing_detector (Cython fallback)."""

from __future__ import annotations

from typing import Any


def detect_engulfing(
    candles_data: list[dict[str, Any]],
    fcr_high: float,
    fcr_low: float,
    rr_ratio: float,
    pip_size: float,
    volume_period: int,
    min_volume_ratio: float,
    min_body_ratio: float = 0.3,
    max_wick_ratio: float = 2.0,
) -> dict[str, Any] | None:
    """Detect bearish or bullish engulfing pattern on M1 candles."""
    if len(candles_data) < 2:
        return None

    n = len(candles_data)
    prev = candles_data[n - 2]
    curr = candles_data[n - 1]

    # Volume confirmation
    avg_vol = _compute_avg_volume(candles_data[: n - 1], volume_period)
    if not _has_volume_confirmation(curr, avg_vol, min_volume_ratio):
        return None

    fcr_range = abs(fcr_high - fcr_low)

    # Bearish engulfing
    if _is_bullish(prev) and _is_bearish(curr):
        if curr["open"] >= prev["close"] and curr["close"] <= prev["open"]:
            if curr["close"] <= fcr_low:
                if not _passes_quality(curr, fcr_range, min_body_ratio, max_wick_ratio):
                    return None
                return _build_result(
                    -1, curr["close"], curr["high"], rr_ratio, pip_size
                )

    # Bullish engulfing
    if _is_bearish(prev) and _is_bullish(curr):
        if curr["open"] <= prev["close"] and curr["close"] >= prev["open"]:
            if curr["close"] >= fcr_high:
                if not _passes_quality(curr, fcr_range, min_body_ratio, max_wick_ratio):
                    return None
                return _build_result(1, curr["close"], curr["low"], rr_ratio, pip_size)

    return None


def _is_bearish(candle: dict[str, Any]) -> bool:
    return bool(candle["close"] < candle["open"])


def _is_bullish(candle: dict[str, Any]) -> bool:
    return bool(candle["close"] > candle["open"])


def _has_volume_confirmation(
    curr: dict[str, Any], avg_vol: float, ratio: float
) -> bool:
    vol: float = curr.get("volume", 0.0)
    if avg_vol <= 0.0:
        return True
    return vol >= avg_vol * ratio


def _compute_avg_volume(candles: list[dict[str, Any]], period: int) -> float:
    if not candles or period <= 0:
        return 0.0
    count = min(period, len(candles))
    total: float = sum(
        float(candles[-(i + 1)].get("volume", 0.0)) for i in range(count)
    )
    return total / count


def _passes_quality(
    curr: dict[str, Any], fcr_range: float, min_body_ratio: float, max_wick_ratio: float
) -> bool:
    body = abs(curr["close"] - curr["open"])
    if body < fcr_range * min_body_ratio:
        return False
    upper_wick = curr["high"] - max(curr["open"], curr["close"])
    lower_wick = min(curr["open"], curr["close"]) - curr["low"]
    if (upper_wick + lower_wick) > max_wick_ratio * body:
        return False
    return True


def _build_result(
    signal: int, entry: float, stop_loss: float, rr_ratio: float, pip_size: float
) -> dict[str, Any]:
    risk = abs(entry - stop_loss)
    if signal == -1:
        take_profit = entry - risk * rr_ratio
    else:
        take_profit = entry + risk * rr_ratio
    return {
        "detected": True,
        "signal": signal,
        "entry_price": entry,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "risk_pips": risk / pip_size,
        "reward_pips": abs(entry - take_profit) / pip_size,
    }
