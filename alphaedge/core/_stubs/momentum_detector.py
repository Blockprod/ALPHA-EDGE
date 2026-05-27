# ============================================================
# PROJECT      : ALPHAEDGE
# FILE         : alphaedge/core/_stubs/momentum_detector.py
# DESCRIPTION  : Pure-Python stub — mirrors momentum_detector.pyx interface
#                Used by Pyright, tests, and fallback when Cython unavailable.
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-25
# ============================================================
"""ALPHAEDGE — Momentum detector stub (EMA crossover + ADX gate)."""

from __future__ import annotations

import math
from typing import Any

from alphaedge.core.types import MomentumSignal


def _validate_bar(bar: dict[str, Any]) -> bool:
    """Return True iff bar has finite, positive OHLC values."""
    for key in ("open", "high", "low", "close"):
        v = bar.get(key)
        if v is None:
            return False
        try:
            fv = float(v)
        except (TypeError, ValueError):
            return False
        if not math.isfinite(fv) or fv <= 0.0:
            return False
    return True


def _validate_bars(bars: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return bars with invalid OHLC entries removed."""
    return [b for b in bars if _validate_bar(b)]


def _ema(bars: list[dict[str, Any]], period: int, key: str = "close") -> float:
    """Compute the final EMA value over *bars* for the given OHLC *key*."""
    if len(bars) < period:
        return 0.0
    k = 2.0 / (period + 1.0)
    ema_val = sum(float(b[key]) for b in bars[:period]) / period
    for b in bars[period:]:
        ema_val = float(b[key]) * k + ema_val * (1.0 - k)
    return ema_val


def _true_range(bar: dict[str, Any], prev_bar: dict[str, Any]) -> float:
    """Compute True Range for a single bar."""
    high = float(bar["high"])
    low = float(bar["low"])
    prev_close = float(prev_bar["close"])
    return max(high - low, abs(high - prev_close), abs(low - prev_close))


def _dm_pair(bar: dict[str, Any], prev: dict[str, Any]) -> tuple[float, float]:
    """Return (+DM, -DM) for a single bar transition."""
    p = float(bar["high"]) - float(prev["high"])
    m = float(prev["low"]) - float(bar["low"])
    plus_dm = p if (p > m and p > 0.0) else 0.0
    minus_dm = m if (m > p and m > 0.0) else 0.0
    return plus_dm, minus_dm


def _adx(bars: list[dict[str, Any]], period: int) -> float:
    """Compute Average Directional Index (ADX). Returns 0.0 if insufficient data.

    IMPLEMENTATION NOTE — EMA smoothing, NOT Wilder's:
    This implementation uses the standard EMA factor k = 2/(period+1) ~0.133
    instead of Welles Wilder's original k = 1/period ~0.071 (for period=14).
    Result: ADX responds ~2x faster than standard Wilder ADX.
    The threshold adx_threshold=32 is calibrated on this non-standard
    implementation. Do NOT compare raw ADX values with external charts
    (TradingView, IB Charts) which use Wilder smoothing.
    """
    n = len(bars)
    if n < 2 * period + 1:
        return 0.0
    k = 2.0 / (period + 1.0)  # EMA factor (non-Wilder; threshold=32 calibrated on this)
    atr_ema = 0.0
    plus_di_ema = 0.0
    minus_di_ema = 0.0
    for i in range(1, period + 1):
        tr = _true_range(bars[i], bars[i - 1])
        plus_dm, minus_dm = _dm_pair(bars[i], bars[i - 1])
        atr_ema += tr
        plus_di_ema += plus_dm
        minus_di_ema += minus_dm
    atr_ema /= period
    plus_di_ema /= period
    minus_di_ema /= period
    adx_seed = 0.0
    for i in range(period + 1, 2 * period + 1):
        tr = _true_range(bars[i], bars[i - 1])
        plus_dm, minus_dm = _dm_pair(bars[i], bars[i - 1])
        atr_ema = tr * k + atr_ema * (1.0 - k)
        plus_di_ema = plus_dm * k + plus_di_ema * (1.0 - k)
        minus_di_ema = minus_dm * k + minus_di_ema * (1.0 - k)
        if atr_ema > 0.0:
            plus_di = (plus_di_ema / atr_ema) * 100.0
            minus_di = (minus_di_ema / atr_ema) * 100.0
            di_sum = plus_di + minus_di
            dx = abs(plus_di - minus_di) / di_sum * 100.0 if di_sum > 0.0 else 0.0
        else:
            dx = 0.0
        adx_seed += dx
    adx_val = adx_seed / period
    for i in range(2 * period + 1, n):
        tr = _true_range(bars[i], bars[i - 1])
        plus_dm, minus_dm = _dm_pair(bars[i], bars[i - 1])
        atr_ema = tr * k + atr_ema * (1.0 - k)
        plus_di_ema = plus_dm * k + plus_di_ema * (1.0 - k)
        minus_di_ema = minus_dm * k + minus_di_ema * (1.0 - k)
        if atr_ema > 0.0:
            plus_di = (plus_di_ema / atr_ema) * 100.0
            minus_di = (minus_di_ema / atr_ema) * 100.0
            di_sum = plus_di + minus_di
            dx = abs(plus_di - minus_di) / di_sum * 100.0 if di_sum > 0.0 else 0.0
        else:
            dx = 0.0
        adx_val = dx * k + adx_val * (1.0 - k)
    return adx_val


def detect_momentum(
    bars: list[dict[str, Any]],
    fast_period: int,
    slow_period: int,
    adx_period: int,
    adx_threshold: float,
) -> MomentumSignal | None:
    """
    Detect a momentum signal on *bars* (Daily or H4, chronological order).

    Returns ``None`` when bars are insufficient or ADX < ``adx_threshold``.

    Parameters
    ----------
    bars:
        List of OHLC dicts with keys ``open``, ``high``, ``low``,
        ``close``, ``timestamp`` (unix ms int).
    fast_period:
        EMA fast period (e.g. 12).
    slow_period:
        EMA slow period (e.g. 26).
    adx_period:
        ADX smoothing period (e.g. 14).
    adx_threshold:
        Minimum ADX value to confirm a trend (e.g. 25.0).
    """
    min_bars = max(2 * adx_period + 1, slow_period)
    if len(bars) < min_bars:
        return None
    # Validate bars before Cython-style casts — abort on any invalid bar
    for _bar in bars:
        if not _validate_bar(_bar):
            return None
    ema_f = _ema(bars, fast_period)
    ema_s = _ema(bars, slow_period)
    adx_val = _adx(bars, adx_period)
    if adx_val < adx_threshold:
        return None
    direction = 1 if ema_f >= ema_s else -1
    strength = min(adx_val / 100.0, 1.0)
    last = bars[-1]
    return {
        "detected": True,
        "direction": direction,
        "strength": strength,
        "ema_fast": ema_f,
        "ema_slow": ema_s,
        "adx": adx_val,
        "timestamp": int(last.get("timestamp", 0)),
    }
