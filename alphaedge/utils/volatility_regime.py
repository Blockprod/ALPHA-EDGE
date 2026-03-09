# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/utils/volatility_regime.py
# DESCRIPTION  : Session volatility regime filter (rolling ATR)
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-08
# ============================================================
"""ALPHAEDGE — T4.1: Volatility regime filter.

Computes a rolling 20-day ATR at session open (9:30 ET) and gates
trading to sessions where the current day's ATR falls within
0.5×–2.0× of the rolling mean.  Abnormally quiet or violent
sessions are skipped and logged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from alphaedge.config.constants import (
    REGIME_ATR_HIGH_MULTIPLIER,
    REGIME_ATR_LOOKBACK_DAYS,
    REGIME_ATR_LOW_MULTIPLIER,
)
from alphaedge.utils.logger import get_logger

logger = get_logger()


# ------------------------------------------------------------------
# Data structures
# ------------------------------------------------------------------
@dataclass
class VolatilityRegimeResult:
    """Result of a volatility regime check."""

    allowed: bool = True
    current_atr: float = 0.0
    rolling_mean_atr: float = 0.0
    low_threshold: float = 0.0
    high_threshold: float = 0.0
    reason: str = ""


# ------------------------------------------------------------------
# ATR computation
# ------------------------------------------------------------------
def compute_daily_atr(daily_bars: list[dict[str, Any]]) -> list[float]:
    """
    Compute True Range for each daily bar.

    Parameters
    ----------
    daily_bars : list[dict]
        Daily OHLC bars with 'high', 'low', and 'close' keys.

    Returns
    -------
    list[float]
        True Range value for each bar.
    """
    if not daily_bars:
        return []

    true_ranges: list[float] = []
    for i, bar in enumerate(daily_bars):
        high = bar["high"]
        low = bar["low"]
        if i == 0:
            tr = high - low
        else:
            prev_close = daily_bars[i - 1]["close"]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)

    return true_ranges


def compute_rolling_atr(
    daily_bars: list[dict[str, Any]],
    lookback: int = REGIME_ATR_LOOKBACK_DAYS,
) -> float:
    """
    Compute average of the last N days' True Ranges.

    Parameters
    ----------
    daily_bars : list[dict]
        Daily OHLC bars (chronological order).
    lookback : int
        Number of days for the rolling window.

    Returns
    -------
    float
        Rolling ATR (mean of last `lookback` True Ranges).
        Returns 0.0 if insufficient data.
    """
    true_ranges = compute_daily_atr(daily_bars)
    if len(true_ranges) < lookback:
        return 0.0

    window = true_ranges[-lookback:]
    return sum(window) / len(window)


# ------------------------------------------------------------------
# Regime filter
# ------------------------------------------------------------------
def check_volatility_regime(
    daily_bars: list[dict[str, Any]],
    current_day_bar: dict[str, Any],
    lookback: int = REGIME_ATR_LOOKBACK_DAYS,
    low_mult: float = REGIME_ATR_LOW_MULTIPLIER,
    high_mult: float = REGIME_ATR_HIGH_MULTIPLIER,
) -> VolatilityRegimeResult:
    """
    Check whether today's ATR is within the acceptable volatility range.

    Parameters
    ----------
    daily_bars : list[dict]
        Historical daily bars (must have at least `lookback` bars,
        NOT including the current day).
    current_day_bar : dict
        Today's bar with 'high', 'low' (at session open, partial or full).
    lookback : int
        Number of days for the rolling mean.
    low_mult : float
        Lower bound multiplier (default 0.5).
    high_mult : float
        Upper bound multiplier (default 2.0).

    Returns
    -------
    VolatilityRegimeResult
        Whether trading is allowed and the regime metrics.
    """
    rolling_atr = compute_rolling_atr(daily_bars, lookback)

    if rolling_atr <= 0.0:
        logger.warning(
            "ALPHAEDGE REGIME: Insufficient data for rolling ATR "
            f"(need {lookback} daily bars, have {len(daily_bars)})"
        )
        return VolatilityRegimeResult(
            allowed=True,
            reason="insufficient_data",
        )

    # Current day's range as ATR proxy
    current_atr = current_day_bar["high"] - current_day_bar["low"]
    low_threshold = rolling_atr * low_mult
    high_threshold = rolling_atr * high_mult

    result = VolatilityRegimeResult(
        current_atr=current_atr,
        rolling_mean_atr=rolling_atr,
        low_threshold=low_threshold,
        high_threshold=high_threshold,
    )

    if current_atr < low_threshold:
        result.allowed = False
        result.reason = "too_quiet"
        logger.warning(
            f"ALPHAEDGE REGIME: Session SKIPPED — too quiet. "
            f"ATR {current_atr:.5f} < {low_threshold:.5f} "
            f"({low_mult}× rolling mean {rolling_atr:.5f})"
        )
    elif current_atr > high_threshold:
        result.allowed = False
        result.reason = "too_volatile"
        logger.warning(
            f"ALPHAEDGE REGIME: Session SKIPPED — too volatile. "
            f"ATR {current_atr:.5f} > {high_threshold:.5f} "
            f"({high_mult}× rolling mean {rolling_atr:.5f})"
        )
    else:
        result.allowed = True
        result.reason = "normal"
        logger.info(
            f"ALPHAEDGE REGIME: Session ALLOWED — "
            f"ATR {current_atr:.5f} within "
            f"[{low_threshold:.5f}, {high_threshold:.5f}]"
        )

    return result
