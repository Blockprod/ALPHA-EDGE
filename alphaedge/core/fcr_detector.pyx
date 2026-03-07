# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/core/fcr_detector.pyx
# DESCRIPTION  : Cython FCR (Failed Candle Range) detection on M5
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True

"""ALPHAEDGE — FCR Forex Trading Bot: M5 Failed Candle Range detector."""


# ------------------------------------------------------------------
# Data structure for a single OHLC candle
# ------------------------------------------------------------------
cdef struct Candle:
    double open_price
    double high
    double low
    double close_price
    double tick_volume
    long timestamp  # UTC epoch seconds


# ------------------------------------------------------------------
# Data structure for FCR detection result
# ------------------------------------------------------------------
cdef struct FCRResult:
    bint detected          # 1 if FCR found, else 0
    double range_high      # M5 candle high
    double range_low       # M5 candle low
    double range_size      # high - low in price
    long candle_timestamp  # UTC epoch of the FCR candle


# ------------------------------------------------------------------
# Build a Candle struct from raw values
# ------------------------------------------------------------------
cdef Candle _build_candle(
    double open_price,
    double high,
    double low,
    double close_price,
    double tick_volume,
    long timestamp,
):
    """Create a Candle struct from individual OHLCV fields."""
    cdef Candle c
    c.open_price = open_price
    c.high = high
    c.low = low
    c.close_price = close_price
    c.tick_volume = tick_volume
    c.timestamp = timestamp
    return c


# ------------------------------------------------------------------
# Check if a candle qualifies as a valid FCR candle
# ------------------------------------------------------------------
cdef bint _is_valid_fcr_candle(Candle candle, double min_range_pips, double pip_size):
    """
    Validate that the candle has a meaningful range.

    A valid FCR candle must have a range >= min_range_pips.
    """
    # Calculate range in pips
    cdef double range_pips = (candle.high - candle.low) / pip_size
    return range_pips >= min_range_pips


# ------------------------------------------------------------------
# Compute the FCR range from a single M5 candle
# ------------------------------------------------------------------
cdef FCRResult _compute_fcr_range(Candle candle):
    """Extract high/low range boundaries from the FCR candle."""
    cdef FCRResult result
    result.detected = 1
    result.range_high = candle.high
    result.range_low = candle.low
    result.range_size = candle.high - candle.low
    result.candle_timestamp = candle.timestamp
    return result


# ------------------------------------------------------------------
# Public: detect FCR from a list of M5 candles before session open
# ------------------------------------------------------------------
def detect_fcr(
    list candles_data,
    double min_range_pips,
    double pip_size,
):
    """
    Detect the FCR (Failed Candle Range) from M5 candles before NYSE open.

    Parameters
    ----------
    candles_data : list[dict]
        List of M5 candle dicts with keys: open, high, low, close, volume, timestamp.
    min_range_pips : float
        Minimum range in pips for a valid FCR candle.
    pip_size : float
        Pip size for the pair (0.0001 for EUR/USD, 0.01 for JPY pairs).

    Returns
    -------
    dict | None
        FCR result dict with keys: detected, range_high, range_low,
        range_size, candle_timestamp. None if no valid FCR found.
    """
    if not candles_data:
        return None

    # Use the last M5 candle before session open as FCR candidate
    cdef dict last_candle_data = candles_data[len(candles_data) - 1]

    # Build the Candle struct from dict
    cdef Candle candle = _build_candle(
        open_price=last_candle_data["open"],
        high=last_candle_data["high"],
        low=last_candle_data["low"],
        close_price=last_candle_data["close"],
        tick_volume=last_candle_data.get("volume", 0.0),
        timestamp=last_candle_data["timestamp"],
    )

    # Validate minimum range
    if not _is_valid_fcr_candle(candle, min_range_pips, pip_size):
        return None

    # Compute and return FCR range
    cdef FCRResult result = _compute_fcr_range(candle)
    return _fcr_result_to_dict(result)


# ------------------------------------------------------------------
# Convert FCRResult struct to Python dict
# ------------------------------------------------------------------
cdef dict _fcr_result_to_dict(FCRResult result):
    """Serialize FCRResult struct into a Python dictionary."""
    return {
        "detected": bool(result.detected),
        "range_high": result.range_high,
        "range_low": result.range_low,
        "range_size": result.range_size,
        "candle_timestamp": result.candle_timestamp,
    }


# ------------------------------------------------------------------
# Public: detect FCR from multiple candidate candles (scan mode)
# ------------------------------------------------------------------
def detect_fcr_scan(
    list candles_data,
    double min_range_pips,
    double pip_size,
    int lookback,
):
    """
    Scan the last N M5 candles for the strongest FCR candidate.

    Parameters
    ----------
    candles_data : list[dict]
        Full list of M5 candle dicts.
    min_range_pips : float
        Minimum range in pips for a valid FCR candle.
    pip_size : float
        Pip size for the pair.
    lookback : int
        Number of recent candles to scan.

    Returns
    -------
    dict | None
        The FCR result with the largest range, or None.
    """
    if not candles_data:
        return None

    # Determine scan window
    cdef int start_idx = max(0, len(candles_data) - lookback)
    cdef list candidates = candles_data[start_idx:]

    return _find_best_fcr(candidates, min_range_pips, pip_size)


# ------------------------------------------------------------------
# Find the FCR candle with the largest range in a candidate list
# ------------------------------------------------------------------
cdef dict _find_best_fcr(
    list candidates,
    double min_range_pips,
    double pip_size,
):
    """Iterate candidates and return the one with the widest range."""
    cdef double best_range = 0.0
    cdef dict best_result = None
    cdef Candle candle
    cdef FCRResult result
    cdef dict candle_data

    for candle_data in candidates:
        candle = _build_candle(
            open_price=candle_data["open"],
            high=candle_data["high"],
            low=candle_data["low"],
            close_price=candle_data["close"],
            tick_volume=candle_data.get("volume", 0.0),
            timestamp=candle_data["timestamp"],
        )
        if not _is_valid_fcr_candle(candle, min_range_pips, pip_size):
            continue
        result = _compute_fcr_range(candle)
        if result.range_size > best_range:
            best_range = result.range_size
            best_result = _fcr_result_to_dict(result)

    return best_result
