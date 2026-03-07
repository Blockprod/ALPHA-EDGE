# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/core/gap_detector.pyx
# DESCRIPTION  : Cython gap / volatility-expansion detection at NYSE open
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True

"""ALPHAEDGE — FCR Forex Trading Bot: NYSE-open gap / ATR-spike detector."""

from libc.math cimport fabs


# ------------------------------------------------------------------
# Data structure for gap detection result
# ------------------------------------------------------------------
cdef struct GapResult:
    bint detected         # 1 if gap / volatility spike found
    double gap_high       # upper boundary of gap zone
    double gap_low        # lower boundary of gap zone
    double gap_size       # absolute gap size in price
    double atr_ratio      # current ATR / baseline ATR
    int direction         # 1 = bullish gap, -1 = bearish gap, 0 = none


# ------------------------------------------------------------------
# Compute ATR over a list of M1 candle ranges
# ------------------------------------------------------------------
cdef double _compute_atr(list candles_data, int period):
    """
    Calculate simple Average True Range from M1 candle data.

    Uses high-low range as true range proxy (Forex is continuous).
    """
    if not candles_data or period <= 0:
        return 0.0

    cdef int count = min(period, len(candles_data))
    cdef double total = 0.0
    cdef dict c
    cdef int i
    cdef int n_atr = len(candles_data)

    for i in range(count):
        c = candles_data[n_atr - 1 - i]
        total += c["high"] - c["low"]

    return total / <double>count


# ------------------------------------------------------------------
# Compute baseline ATR from pre-session M1 candles
# ------------------------------------------------------------------
cdef double _compute_baseline_atr(list pre_session_candles, int period):
    """Get the ATR of M1 candles before NYSE open as a baseline."""
    return _compute_atr(pre_session_candles, period)


# ------------------------------------------------------------------
# Compute current ATR from early-session M1 candles
# ------------------------------------------------------------------
cdef double _compute_current_atr(list session_candles, int period):
    """Get the ATR of the first M1 candles at NYSE open."""
    return _compute_atr(session_candles, period)


# ------------------------------------------------------------------
# Determine gap direction from price movement
# ------------------------------------------------------------------
cdef int _determine_direction(double pre_close, double session_open):
    """Return 1 for bullish, -1 for bearish, 0 for flat."""
    cdef double diff = session_open - pre_close
    if diff > 0:
        return 1
    elif diff < 0:
        return -1
    return 0


# ------------------------------------------------------------------
# Build gap zone boundaries
# ------------------------------------------------------------------
cdef GapResult _build_gap_result(
    double pre_close,
    double session_open,
    double atr_ratio,
    double min_atr_ratio,
):
    """
    Construct GapResult based on price gap and ATR spike.

    For Forex, the 'gap' is a liquidity surge / volatility expansion.
    """
    cdef GapResult result
    cdef double gap_size = fabs(session_open - pre_close)

    result.atr_ratio = atr_ratio
    result.direction = _determine_direction(pre_close, session_open)

    # Gap detected if ATR ratio exceeds threshold
    if atr_ratio >= min_atr_ratio:
        result.detected = 1
        result.gap_size = gap_size
        _set_gap_boundaries(&result, pre_close, session_open)
    else:
        result.detected = 0
        result.gap_high = 0.0
        result.gap_low = 0.0
        result.gap_size = 0.0

    return result


# ------------------------------------------------------------------
# Set high/low boundaries of the gap zone
# ------------------------------------------------------------------
cdef void _set_gap_boundaries(
    GapResult* result,
    double pre_close,
    double session_open,
):
    """Assign gap_high and gap_low based on direction."""
    if pre_close > session_open:
        result.gap_high = pre_close
        result.gap_low = session_open
    else:
        result.gap_high = session_open
        result.gap_low = pre_close


# ------------------------------------------------------------------
# Public: detect gap / volatility expansion at NYSE open
# ------------------------------------------------------------------
def detect_gap(
    list pre_session_m1,
    list session_m1,
    double pre_close,
    double session_open,
    int atr_period,
    double min_atr_ratio,
):
    """
    Detect NYSE-open volatility expansion as Forex gap equivalent.

    Parameters
    ----------
    pre_session_m1 : list[dict]
        M1 candles before NYSE open (for baseline ATR).
    session_m1 : list[dict]
        First M1 candles at NYSE open (for current ATR).
    pre_close : float
        Last M5 close price before session.
    session_open : float
        First M1 open price at session start.
    atr_period : int
        Number of candles for ATR calculation.
    min_atr_ratio : float
        Minimum ATR ratio (current/baseline) to trigger gap detection.

    Returns
    -------
    dict
        Gap result with keys: detected, gap_high, gap_low, gap_size,
        atr_ratio, direction.
    """
    # Compute baseline and current ATR
    cdef double baseline = _compute_baseline_atr(pre_session_m1, atr_period)
    cdef double current = _compute_current_atr(session_m1, atr_period)

    # Avoid division by zero — if baseline is zero, no spike detectable
    cdef double ratio = 0.0
    if baseline > 0.0:
        ratio = current / baseline

    # Build and return result
    cdef GapResult result = _build_gap_result(
        pre_close, session_open, ratio, min_atr_ratio,
    )
    return _gap_result_to_dict(result)


# ------------------------------------------------------------------
# Serialize GapResult to Python dict
# ------------------------------------------------------------------
cdef dict _gap_result_to_dict(GapResult result):
    """Convert GapResult struct into a Python dictionary."""
    return {
        "detected": bool(result.detected),
        "gap_high": result.gap_high,
        "gap_low": result.gap_low,
        "gap_size": result.gap_size,
        "atr_ratio": result.atr_ratio,
        "direction": result.direction,
    }


# ------------------------------------------------------------------
# Public: check if price is within the gap zone
# ------------------------------------------------------------------
def is_in_gap_zone(
    double price,
    double gap_high,
    double gap_low,
    double tolerance_pips,
    double pip_size,
):
    """
    Check if a price is inside or near the gap zone.

    Parameters
    ----------
    price : float
        Current price to check.
    gap_high : float
        Upper boundary of the gap zone.
    gap_low : float
        Lower boundary of the gap zone.
    tolerance_pips : float
        Buffer zone in pips around the gap boundaries.
    pip_size : float
        Pip size for the pair.

    Returns
    -------
    bool
        True if price is within the extended gap zone.
    """
    cdef double tolerance = tolerance_pips * pip_size
    cdef double extended_high = gap_high + tolerance
    cdef double extended_low = gap_low - tolerance
    return extended_low <= price <= extended_high
