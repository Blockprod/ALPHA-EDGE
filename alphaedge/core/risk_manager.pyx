# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/core/risk_manager.pyx
# DESCRIPTION  : Cython risk management — position sizing and limits
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True

"""ALPHAEDGE — FCR Forex Trading Bot: risk management and position sizing."""

from libc.math cimport fabs, floor


# ------------------------------------------------------------------
# Data structure for position sizing result
# ------------------------------------------------------------------
cdef struct PositionSize:
    double lot_size         # computed lot size
    double risk_amount      # dollar risk per trade
    double pip_value        # value per pip in account currency
    double sl_pips          # stop loss distance in pips
    bint is_valid           # 1 if sizing passes all checks


# ------------------------------------------------------------------
# Data structure for daily risk status
# ------------------------------------------------------------------
cdef struct DailyRiskStatus:
    double daily_pnl        # accumulated P&L today
    double daily_pnl_pct    # P&L as % of starting equity
    bint limit_breached     # 1 if daily loss limit hit
    int trades_today        # number of trades executed today


# ------------------------------------------------------------------
# Compute pip value for a currency pair
# ------------------------------------------------------------------
cdef double _compute_pip_value(
    str pair,
    double pip_size,
    str lot_type,
    double exchange_rate=0.0,
):
    """
    Calculate the pip value in USD for standard/mini/micro lots.

    For pairs where USD is quote (EUR/USD, GBP/USD): pip value is fixed.
    For JPY pairs (USD/JPY): divide by exchange rate to convert.
    """
    cdef double lot_units
    if lot_type == "standard":
        lot_units = 100000.0
    elif lot_type == "mini":
        lot_units = 10000.0
    elif lot_type == "micro":
        lot_units = 1000.0
    else:
        lot_units = 100000.0

    cdef double raw_pip_value = lot_units * pip_size

    # For non-USD-quoted pairs convert via exchange rate
    if exchange_rate > 0.0 and pip_size >= 0.001:
        return raw_pip_value / exchange_rate
    return raw_pip_value


# ------------------------------------------------------------------
# Compute lot size from risk parameters
# ------------------------------------------------------------------
cdef PositionSize _compute_position_size(
    double account_equity,
    double risk_pct,
    double sl_pips,
    double pip_value_per_lot,
    double min_lots,
    double max_lots,
):
    """
    Calculate position size based on account % risk.

    lot_size = risk_amount / (sl_pips * pip_value_per_lot)
    """
    cdef PositionSize result

    # Dollar amount at risk
    result.risk_amount = account_equity * (risk_pct / 100.0)
    result.sl_pips = sl_pips
    result.pip_value = pip_value_per_lot

    # Avoid division by zero
    if sl_pips <= 0.0 or pip_value_per_lot <= 0.0:
        result.lot_size = 0.0
        result.is_valid = 0
        return result

    # Raw lot size
    cdef double raw_lots = result.risk_amount / (sl_pips * pip_value_per_lot)

    # Round down to 2 decimal places (micro-lot precision)
    result.lot_size = floor(raw_lots * 100.0) / 100.0

    # Validate bounds
    result.is_valid = _validate_lot_bounds(
        result.lot_size, min_lots, max_lots,
    )

    return result


# ------------------------------------------------------------------
# Validate lot size is within acceptable range
# ------------------------------------------------------------------
cdef bint _validate_lot_bounds(
    double lot_size,
    double min_lots,
    double max_lots,
):
    """Ensure lot size falls within min/max boundaries."""
    return min_lots <= lot_size <= max_lots


# ------------------------------------------------------------------
# Public: calculate position size
# ------------------------------------------------------------------
def calculate_position_size(
    double account_equity,
    double risk_pct,
    double sl_pips,
    str pair,
    double pip_size,
    str lot_type,
    double min_lots,
    double max_lots,
    double exchange_rate=0.0,
):
    """
    Calculate optimal position size based on risk parameters.

    Parameters
    ----------
    account_equity : float
        Current account equity in USD.
    risk_pct : float
        Risk percentage per trade (e.g., 1.0 for 1%).
    sl_pips : float
        Stop loss distance in pips.
    pair : str
        Currency pair (e.g., 'EURUSD').
    pip_size : float
        Pip size (0.0001 or 0.01 for JPY).
    lot_type : str
        'standard', 'mini', or 'micro'.
    min_lots : float
        Minimum lot size allowed.
    max_lots : float
        Maximum lot size allowed.
    exchange_rate : float
        Live exchange rate for non-USD-quoted pairs (0.0 to skip).

    Returns
    -------
    dict
        Position sizing result with lot_size, risk_amount, pip_value.
    """
    # Compute pip value per single lot
    cdef double pip_val = _compute_pip_value(
        pair, pip_size, lot_type, exchange_rate,
    )

    # Compute position size
    cdef PositionSize result = _compute_position_size(
        account_equity, risk_pct, sl_pips, pip_val, min_lots, max_lots,
    )

    return _position_to_dict(result)


# ------------------------------------------------------------------
# Serialize PositionSize to Python dict
# ------------------------------------------------------------------
cdef dict _position_to_dict(PositionSize result):
    """Convert PositionSize struct into a Python dictionary."""
    return {
        "lot_size": result.lot_size,
        "risk_amount": result.risk_amount,
        "pip_value": result.pip_value,
        "sl_pips": result.sl_pips,
        "is_valid": bool(result.is_valid),
    }


# ------------------------------------------------------------------
# Public: check daily loss limit
# ------------------------------------------------------------------
def check_daily_limit(
    double starting_equity,
    double current_equity,
    double max_daily_loss_pct,
    int trades_today,
    int max_trades,
):
    """
    Check if the daily loss limit or trade count is breached.

    Parameters
    ----------
    starting_equity : float
        Account equity at start of day.
    current_equity : float
        Current account equity.
    max_daily_loss_pct : float
        Maximum daily loss as percentage (e.g., 3.0 for -3%).
    trades_today : int
        Number of trades executed today.
    max_trades : int
        Maximum trades allowed per session.

    Returns
    -------
    dict
        Daily risk status with limit_breached flag.
    """
    cdef DailyRiskStatus status = _compute_daily_status(
        starting_equity, current_equity, max_daily_loss_pct, trades_today,
    )

    # Also check trade count limit
    if trades_today >= max_trades:
        status.limit_breached = 1

    return _daily_status_to_dict(status, max_trades)


# ------------------------------------------------------------------
# Compute daily P&L status
# ------------------------------------------------------------------
cdef DailyRiskStatus _compute_daily_status(
    double starting_equity,
    double current_equity,
    double max_daily_loss_pct,
    int trades_today,
):
    """Calculate daily P&L and check against the loss limit."""
    cdef DailyRiskStatus status
    status.daily_pnl = current_equity - starting_equity
    status.trades_today = trades_today

    # Compute P&L percentage
    if starting_equity > 0:
        status.daily_pnl_pct = (status.daily_pnl / starting_equity) * 100.0
    else:
        status.daily_pnl_pct = 0.0

    # Check if loss limit is breached (negative threshold)
    status.limit_breached = status.daily_pnl_pct <= -max_daily_loss_pct
    return status


# ------------------------------------------------------------------
# Serialize DailyRiskStatus to Python dict
# ------------------------------------------------------------------
cdef dict _daily_status_to_dict(DailyRiskStatus status, int max_trades):
    """Convert DailyRiskStatus struct into a Python dictionary."""
    return {
        "daily_pnl": status.daily_pnl,
        "daily_pnl_pct": status.daily_pnl_pct,
        "limit_breached": bool(status.limit_breached),
        "trades_today": status.trades_today,
        "max_trades": max_trades,
        "can_trade": not status.limit_breached,
    }


# ------------------------------------------------------------------
# Public: enforce per-pair risk cap (max 1 pair open at a time)
# ------------------------------------------------------------------
def check_pair_limit(
    str pair,
    list open_pairs,
    int max_open_pairs=1,
):
    """
    Enforce per-pair risk cap: max 1 pair open at a time.

    Parameters
    ----------
    pair : str
        Pair requesting a new position.
    open_pairs : list[str]
        List of pairs currently holding open positions.
    max_open_pairs : int
        Maximum number of concurrent open pairs (default 1).

    Returns
    -------
    dict
        Result with 'allowed' flag and 'reason' if blocked.
    """
    cdef int count = len(open_pairs)

    if count >= max_open_pairs:
        return {
            "allowed": False,
            "reason": "max_pairs_reached",
            "open_count": count,
            "max_allowed": max_open_pairs,
            "open_pairs": open_pairs,
        }

    return {
        "allowed": True,
        "reason": None,
        "open_count": count,
        "max_allowed": max_open_pairs,
        "open_pairs": open_pairs,
    }


# ------------------------------------------------------------------
# Public: add slippage buffer to stop loss
# ------------------------------------------------------------------
def apply_slippage_buffer(
    double stop_loss,
    int direction,
    double slippage_pips,
    double pip_size,
):
    """
    Widen stop loss by slippage buffer.

    Parameters
    ----------
    stop_loss : float
        Original stop loss price.
    direction : int
        1 for BUY (SL below), -1 for SELL (SL above).
    slippage_pips : float
        Buffer in pips to add.
    pip_size : float
        Pip size for the pair.

    Returns
    -------
    float
        Adjusted stop loss price.
    """
    cdef double buffer = slippage_pips * pip_size
    if direction == 1:
        return stop_loss - buffer
    return stop_loss + buffer
