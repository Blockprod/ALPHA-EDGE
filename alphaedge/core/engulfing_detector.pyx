# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/core/engulfing_detector.pyx
# DESCRIPTION  : Cython M1 engulfing pattern detector with volume
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True

"""ALPHAEDGE — FCR Forex Trading Bot: M1 engulfing candle pattern detector."""

from libc.math cimport fabs


# ------------------------------------------------------------------
# Data structure for engulfing detection result
# ------------------------------------------------------------------
cdef struct EngulfingResult:
    bint detected            # 1 if engulfing found
    int signal               # 1 = bullish, -1 = bearish, 0 = none
    double entry_price       # close of engulfing candle
    double stop_loss         # beyond engulfing wick
    double take_profit       # at target RR
    double risk_pips         # SL distance in pips
    double reward_pips       # TP distance in pips


# ------------------------------------------------------------------
# Check if candle is bearish
# ------------------------------------------------------------------
cdef bint _is_bearish(dict candle):
    """Return True if the candle closed below its open."""
    return candle["close"] < candle["open"]


# ------------------------------------------------------------------
# Check if candle is bullish
# ------------------------------------------------------------------
cdef bint _is_bullish(dict candle):
    """Return True if the candle closed above its open."""
    return candle["close"] > candle["open"]


# ------------------------------------------------------------------
# Check bearish engulfing: current candle engulfs previous candle
# ------------------------------------------------------------------
cdef bint _is_bearish_engulfing(dict prev_candle, dict curr_candle):
    """
    Validate a bearish engulfing pattern.

    Current candle must: open above prev close, close below prev open.
    """
    cdef bint prev_bullish = _is_bullish(prev_candle)
    cdef bint curr_bearish = _is_bearish(curr_candle)

    if not (prev_bullish and curr_bearish):
        return 0

    # Current body engulfs previous body
    cdef bint engulfs_open = curr_candle["open"] >= prev_candle["close"]
    cdef bint engulfs_close = curr_candle["close"] <= prev_candle["open"]
    return engulfs_open and engulfs_close


# ------------------------------------------------------------------
# Check bullish engulfing: current candle engulfs previous candle
# ------------------------------------------------------------------
cdef bint _is_bullish_engulfing(dict prev_candle, dict curr_candle):
    """
    Validate a bullish engulfing pattern.

    Current candle must: open below prev close, close above prev open.
    """
    cdef bint prev_bearish = _is_bearish(prev_candle)
    cdef bint curr_bullish = _is_bullish(curr_candle)

    if not (prev_bearish and curr_bullish):
        return 0

    # Current body engulfs previous body
    cdef bint engulfs_open = curr_candle["open"] <= prev_candle["close"]
    cdef bint engulfs_close = curr_candle["close"] >= prev_candle["open"]
    return engulfs_open and engulfs_close


# ------------------------------------------------------------------
# Validate tick-count volume confirmation
# ------------------------------------------------------------------
cdef bint _has_volume_confirmation(
    dict curr_candle,
    double avg_volume,
    double min_volume_ratio,
):
    """
    Confirm the engulfing candle has above-average tick volume.

    Tick count is used as volume proxy for Forex.
    """
    cdef double curr_vol = curr_candle.get("volume", 0.0)
    if avg_volume <= 0.0:
        return 1  # No baseline — skip volume filter
    return curr_vol >= (avg_volume * min_volume_ratio)


# ------------------------------------------------------------------
# Compute average tick volume from recent candles
# ------------------------------------------------------------------
cdef double _compute_avg_volume(list candles, int period):
    """Calculate the mean tick volume over the last N candles."""
    if not candles or period <= 0:
        return 0.0

    cdef int count = min(period, len(candles))
    cdef double total = 0.0
    cdef int i
    cdef int n_vol = len(candles)

    for i in range(count):
        total += candles[n_vol - 1 - i].get("volume", 0.0)

    return total / <double>count


# ------------------------------------------------------------------
# Compute stop loss for bearish engulfing
# ------------------------------------------------------------------
cdef double _bearish_stop_loss(dict candle):
    """SL above the high wick of the bearish engulfing candle."""
    return candle["high"]


# ------------------------------------------------------------------
# Compute stop loss for bullish engulfing
# ------------------------------------------------------------------
cdef double _bullish_stop_loss(dict candle):
    """SL below the low wick of the bullish engulfing candle."""
    return candle["low"]


# ------------------------------------------------------------------
# Compute take profit from entry, SL, and RR ratio
# ------------------------------------------------------------------
cdef double _compute_take_profit(
    double entry,
    double stop_loss,
    double rr_ratio,
    int signal,
):
    """
    Calculate TP at the given risk/reward ratio.

    signal = -1 (short): TP below entry
    signal = +1 (long):  TP above entry
    """
    cdef double risk = fabs(entry - stop_loss)
    if signal == -1:
        return entry - (risk * rr_ratio)
    return entry + (risk * rr_ratio)


# ------------------------------------------------------------------
# Build the EngulfingResult struct
# ------------------------------------------------------------------
cdef EngulfingResult _build_result(
    int signal,
    double entry,
    double stop_loss,
    double rr_ratio,
    double pip_size,
):
    """Assemble the full engulfing result with SL/TP/risk metrics."""
    cdef EngulfingResult result
    result.detected = 1
    result.signal = signal
    result.entry_price = entry
    result.stop_loss = stop_loss

    result.take_profit = _compute_take_profit(
        entry, stop_loss, rr_ratio, signal,
    )
    result.risk_pips = fabs(entry - stop_loss) / pip_size
    result.reward_pips = fabs(entry - result.take_profit) / pip_size
    return result


# ------------------------------------------------------------------
# Public: detect engulfing pattern on M1 candles
# ------------------------------------------------------------------
def detect_engulfing(
    list candles_data,
    double fcr_high,
    double fcr_low,
    double rr_ratio,
    double pip_size,
    int volume_period,
    double min_volume_ratio,
):
    """
    Detect bearish or bullish engulfing pattern on M1 candles.

    Parameters
    ----------
    candles_data : list[dict]
        M1 candle dicts with keys: open, high, low, close, volume.
    fcr_high : float
        Upper boundary of the FCR range.
    fcr_low : float
        Lower boundary of the FCR range.
    rr_ratio : float
        Risk/reward ratio for TP calculation (e.g., 3.0).
    pip_size : float
        Pip size for the pair.
    volume_period : int
        Lookback period for average volume calculation.
    min_volume_ratio : float
        Minimum ratio of current volume to average for confirmation.

    Returns
    -------
    dict | None
        Engulfing result dict or None if no valid pattern found.
    """
    if len(candles_data) < 2:
        return None

    # Get the last two candles
    cdef int n = len(candles_data)
    cdef dict prev_candle = candles_data[n - 2]
    cdef dict curr_candle = candles_data[n - 1]

    # Compute average volume for confirmation
    cdef double avg_vol = _compute_avg_volume(
        candles_data[:n - 1], volume_period,
    )

    # Check volume confirmation
    if not _has_volume_confirmation(curr_candle, avg_vol, min_volume_ratio):
        return None

    return _evaluate_engulfing(
        prev_candle, curr_candle, fcr_high, fcr_low,
        rr_ratio, pip_size,
    )


# ------------------------------------------------------------------
# Evaluate bearish and bullish engulfing conditions
# ------------------------------------------------------------------
cdef dict _evaluate_engulfing(
    dict prev_candle,
    dict curr_candle,
    double fcr_high,
    double fcr_low,
    double rr_ratio,
    double pip_size,
):
    """Test for bearish then bullish engulfing against FCR levels."""
    cdef EngulfingResult result

    # --- Bearish engulfing: close below FCR low ---
    if _is_bearish_engulfing(prev_candle, curr_candle):
        if curr_candle["close"] <= fcr_low:
            result = _build_result(
                signal=-1,
                entry=curr_candle["close"],
                stop_loss=_bearish_stop_loss(curr_candle),
                rr_ratio=rr_ratio,
                pip_size=pip_size,
            )
            return _engulfing_to_dict(result)

    # --- Bullish engulfing: close above FCR high ---
    if _is_bullish_engulfing(prev_candle, curr_candle):
        if curr_candle["close"] >= fcr_high:
            result = _build_result(
                signal=1,
                entry=curr_candle["close"],
                stop_loss=_bullish_stop_loss(curr_candle),
                rr_ratio=rr_ratio,
                pip_size=pip_size,
            )
            return _engulfing_to_dict(result)

    return None


# ------------------------------------------------------------------
# Serialize EngulfingResult to Python dict
# ------------------------------------------------------------------
cdef dict _engulfing_to_dict(EngulfingResult result):
    """Convert EngulfingResult struct into a Python dictionary."""
    return {
        "detected": bool(result.detected),
        "signal": result.signal,
        "entry_price": result.entry_price,
        "stop_loss": result.stop_loss,
        "take_profit": result.take_profit,
        "risk_pips": result.risk_pips,
        "reward_pips": result.reward_pips,
    }
