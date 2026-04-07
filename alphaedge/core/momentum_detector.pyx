# ============================================================
# PROJECT      : ALPHAEDGE
# FILE         : alphaedge/core/momentum_detector.pyx
# DESCRIPTION  : Cython momentum signal — EMA crossover + ADX gate
# STRATEGY     : Time Series Momentum (Moskowitz 2012) · Swing Daily/H4
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-25
# ============================================================
# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True

"""ALPHAEDGE — Momentum detector: EMA crossover + ADX strength gate."""

import math as _math

from libc.math cimport fabs


# ------------------------------------------------------------------
# Result container
# ------------------------------------------------------------------
cdef struct MomentumResult:
    bint detected          # 1 if signal passes ADX gate
    int direction          # 1 = LONG, -1 = SHORT
    double strength        # ADX normalised 0-1
    double ema_fast        # last EMA fast value
    double ema_slow        # last EMA slow value
    double adx             # raw ADX value
    long long timestamp    # timestamp of the last bar (unix ms)


# ------------------------------------------------------------------
# EMA computation (iterative, Cython cdef)
# ------------------------------------------------------------------
cdef double _ema(list bars, int period, str key):
    """Compute the final EMA value over *bars* for the given OHLC *key*."""
    cdef double k, ema_val, price
    cdef int i, n

    n = len(bars)
    if n < period:
        return 0.0

    k = 2.0 / (period + 1.0)

    # Seed with SMA of first *period* values
    ema_val = 0.0
    for i in range(period):
        ema_val += <double>bars[i][key]
    ema_val /= period

    for i in range(period, n):
        price = <double>bars[i][key]
        ema_val = price * k + ema_val * (1.0 - k)

    return ema_val


# ------------------------------------------------------------------
# True Range helper
# ------------------------------------------------------------------
cdef double _true_range(dict bar, dict prev_bar):
    """Compute True Range for a single bar."""
    cdef double high, low, prev_close, tr1, tr2, tr3

    high = <double>bar["high"]
    low = <double>bar["low"]
    prev_close = <double>prev_bar["close"]

    tr1 = high - low
    tr2 = fabs(high - prev_close)
    tr3 = fabs(low - prev_close)

    if tr2 > tr1:
        tr1 = tr2
    if tr3 > tr1:
        tr1 = tr3
    return tr1


# ------------------------------------------------------------------
# ADX computation
# ------------------------------------------------------------------
cdef double _adx(list bars, int period):
    """
    Compute the Average Directional Index (ADX) over *bars*.

    Returns 0.0 if bars are insufficient.
    """
    cdef int n, i
    cdef double tr, plus_dm, minus_dm
    cdef double high, low, prev_high, prev_low, prev_close
    cdef double atr_ema, plus_di_ema, minus_di_ema
    cdef double plus_dm_raw, minus_dm_raw
    cdef double k, dx, adx_val
    cdef double plus_di, minus_di, di_sum

    n = len(bars)
    min_bars = 2 * period + 1
    if n < min_bars:
        return 0.0

    k = 2.0 / (period + 1.0)

    # Seed smoothers using first *period* bars after bar[0]
    atr_ema = 0.0
    plus_di_ema = 0.0
    minus_di_ema = 0.0

    for i in range(1, period + 1):
        high = <double>bars[i]["high"]
        low = <double>bars[i]["low"]
        prev_high = <double>bars[i - 1]["high"]
        prev_low = <double>bars[i - 1]["low"]
        prev_close = <double>bars[i - 1]["close"]

        tr = _true_range(bars[i], bars[i - 1])
        plus_dm_raw = high - prev_high
        minus_dm_raw = prev_low - low

        plus_dm = plus_dm_raw if (plus_dm_raw > minus_dm_raw and plus_dm_raw > 0.0) else 0.0
        minus_dm = minus_dm_raw if (minus_dm_raw > plus_dm_raw and minus_dm_raw > 0.0) else 0.0

        atr_ema += tr
        plus_di_ema += plus_dm
        minus_di_ema += minus_dm

    atr_ema /= period
    plus_di_ema /= period
    minus_di_ema /= period

    # Compute DX series and seed ADX EMA
    adx_val = 0.0
    cdef double adx_seed = 0.0
    cdef int adx_count = 0

    # First ADX window: bars period+1 .. 2*period
    for i in range(period + 1, 2 * period + 1):
        high = <double>bars[i]["high"]
        low = <double>bars[i]["low"]
        prev_close = <double>bars[i - 1]["close"]

        tr = _true_range(bars[i], bars[i - 1])
        plus_dm_raw = high - <double>bars[i - 1]["high"]
        minus_dm_raw = <double>bars[i - 1]["low"] - low

        plus_dm = plus_dm_raw if (plus_dm_raw > minus_dm_raw and plus_dm_raw > 0.0) else 0.0
        minus_dm = minus_dm_raw if (minus_dm_raw > plus_dm_raw and minus_dm_raw > 0.0) else 0.0

        atr_ema = tr * k + atr_ema * (1.0 - k)
        plus_di_ema = plus_dm * k + plus_di_ema * (1.0 - k)
        minus_di_ema = minus_dm * k + minus_di_ema * (1.0 - k)

        if atr_ema > 0.0:
            plus_di = (plus_di_ema / atr_ema) * 100.0
            minus_di = (minus_di_ema / atr_ema) * 100.0
            di_sum = plus_di + minus_di
            dx = (fabs(plus_di - minus_di) / di_sum) * 100.0 if di_sum > 0.0 else 0.0
        else:
            dx = 0.0

        adx_seed += dx
        adx_count += 1

    adx_val = adx_seed / adx_count if adx_count > 0 else 0.0

    # Smooth ADX over remaining bars
    for i in range(2 * period + 1, n):
        high = <double>bars[i]["high"]
        low = <double>bars[i]["low"]

        tr = _true_range(bars[i], bars[i - 1])
        plus_dm_raw = high - <double>bars[i - 1]["high"]
        minus_dm_raw = <double>bars[i - 1]["low"] - low

        plus_dm = plus_dm_raw if (plus_dm_raw > minus_dm_raw and plus_dm_raw > 0.0) else 0.0
        minus_dm = minus_dm_raw if (minus_dm_raw > plus_dm_raw and minus_dm_raw > 0.0) else 0.0

        atr_ema = tr * k + atr_ema * (1.0 - k)
        plus_di_ema = plus_dm * k + plus_di_ema * (1.0 - k)
        minus_di_ema = minus_dm * k + minus_di_ema * (1.0 - k)

        if atr_ema > 0.0:
            plus_di = (plus_di_ema / atr_ema) * 100.0
            minus_di = (minus_di_ema / atr_ema) * 100.0
            di_sum = plus_di + minus_di
            dx = (fabs(plus_di - minus_di) / di_sum) * 100.0 if di_sum > 0.0 else 0.0
        else:
            dx = 0.0

        adx_val = dx * k + adx_val * (1.0 - k)

    return adx_val


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------
def detect_momentum(
    bars: list,
    fast_period: int,
    slow_period: int,
    adx_period: int,
    adx_threshold: float,
) -> dict | None:
    """
    Detect a momentum signal on *bars* (Daily or H4, chronological order).

    Returns ``None`` when:
    - ``len(bars) < slow_period`` (insufficient history)
    - computed ADX < ``adx_threshold`` (no trend — pipeline STOP)

    Returns a result dict when a valid trend is detected:
    ``{"detected": True, "direction": 1|-1, "strength": float,
       "ema_fast": float, "ema_slow": float, "adx": float,
       "timestamp": int}``

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
    cdef MomentumResult result
    cdef int direction
    cdef double ema_f, ema_s, adx_val, strength

    min_bars = 2 * adx_period + 1
    if slow_period > min_bars:
        min_bars = slow_period

    if len(bars) < min_bars:
        return None

    # Validate bars before Cython casts — prevents crash on None/NaN/negative IB data
    for _bar in bars:
        if _bar is None:
            return None
        for _key in ("open", "high", "low", "close"):
            _v = _bar.get(_key)
            if _v is None:
                return None
            try:
                _fv = float(_v)
            except (TypeError, ValueError):
                return None
            if not _math.isfinite(_fv) or _fv <= 0.0:
                return None

    ema_f = _ema(bars, fast_period, "close")
    ema_s = _ema(bars, slow_period, "close")
    adx_val = _adx(bars, adx_period)

    if adx_val < adx_threshold:
        return None

    direction = 1 if ema_f >= ema_s else -1
    strength = adx_val / 100.0 if adx_val <= 100.0 else 1.0

    last = bars[len(bars) - 1]
    result.detected = 1
    result.direction = direction
    result.strength = strength
    result.ema_fast = ema_f
    result.ema_slow = ema_s
    result.adx = adx_val
    result.timestamp = <long long>last.get("timestamp", 0)

    return {
        "detected": True,
        "direction": result.direction,
        "strength": result.strength,
        "ema_fast": result.ema_fast,
        "ema_slow": result.ema_slow,
        "adx": result.adx,
        "timestamp": result.timestamp,
    }
