# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/core/order_manager.pyx
# DESCRIPTION  : Cython order management — entry, SL, TP brackets
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True

"""ALPHAEDGE — FCR Forex Trading Bot: bracket order builder and validator."""

from libc.math cimport fabs


# ------------------------------------------------------------------
# Data structure for a bracket order
# ------------------------------------------------------------------
cdef struct BracketOrder:
    int direction          # 1 = BUY, -1 = SELL
    double entry_price     # target entry price
    double stop_loss       # stop loss price
    double take_profit     # take profit price
    double lot_size        # position size in lots
    double risk_pips       # risk distance in pips
    double reward_pips     # reward distance in pips
    double rr_ratio        # reward / risk ratio
    bint is_valid          # 1 if order passes all checks


# ------------------------------------------------------------------
# Build a bracket order from signal parameters
# ------------------------------------------------------------------
cdef BracketOrder _build_bracket(
    int direction,
    double entry_price,
    double stop_loss,
    double take_profit,
    double lot_size,
    double pip_size,
):
    """Assemble a BracketOrder struct with computed metrics."""
    cdef BracketOrder order
    order.direction = direction
    order.entry_price = entry_price
    order.stop_loss = stop_loss
    order.take_profit = take_profit
    order.lot_size = lot_size

    # Compute risk/reward in pips
    order.risk_pips = fabs(entry_price - stop_loss) / pip_size
    order.reward_pips = fabs(entry_price - take_profit) / pip_size

    # Compute actual RR ratio
    if order.risk_pips > 0:
        order.rr_ratio = order.reward_pips / order.risk_pips
    else:
        order.rr_ratio = 0.0

    order.is_valid = 1
    return order


# ------------------------------------------------------------------
# Validate SL/TP placement relative to entry and direction
# ------------------------------------------------------------------
cdef bint _validate_sl_tp_placement(BracketOrder order):
    """
    Ensure SL and TP are on the correct sides of entry.

    For BUY:  SL < entry < TP
    For SELL: TP < entry < SL
    """
    if order.direction == 1:  # BUY
        return order.stop_loss < order.entry_price < order.take_profit
    elif order.direction == -1:  # SELL
        return order.take_profit < order.entry_price < order.stop_loss
    return 0


# ------------------------------------------------------------------
# Validate minimum risk/reward ratio
# ------------------------------------------------------------------
cdef bint _validate_min_rr(BracketOrder order, double min_rr):
    """Ensure the order meets the minimum RR requirement."""
    return order.rr_ratio >= min_rr


# ------------------------------------------------------------------
# Validate lot size within acceptable bounds
# ------------------------------------------------------------------
cdef bint _validate_lot_size(
    double lot_size,
    double min_lots,
    double max_lots,
):
    """Ensure lot size is within broker-acceptable range."""
    return min_lots <= lot_size <= max_lots


# ------------------------------------------------------------------
# Validate spread is within acceptable range
# ------------------------------------------------------------------
cdef bint _validate_spread(
    double spread_pips,
    double max_spread_pips,
):
    """Skip trade if current spread exceeds maximum threshold."""
    return spread_pips <= max_spread_pips


# ------------------------------------------------------------------
# Adjust SL for spread buffer
# ------------------------------------------------------------------
cdef double _adjust_sl_for_spread(
    double stop_loss,
    int direction,
    double spread_pips,
    double pip_size,
):
    """
    Add spread buffer to stop loss.

    BUY:  widen SL downward
    SELL: widen SL upward
    """
    cdef double buffer = spread_pips * pip_size
    if direction == 1:  # BUY — SL is below
        return stop_loss - buffer
    # SELL — SL is above
    return stop_loss + buffer


# ------------------------------------------------------------------
# Public: create a validated bracket order
# ------------------------------------------------------------------
def create_bracket_order(
    int direction,
    double entry_price,
    double stop_loss,
    double take_profit,
    double lot_size,
    double pip_size,
    double spread_pips,
    double max_spread_pips,
    double min_rr,
    double min_lots,
    double max_lots,
    bint adjust_for_spread,
):
    """
    Create and validate a bracket order for IB submission.

    Args: direction (1=BUY/-1=SELL), entry/SL/TP prices, lot_size,
          pip_size, spread_pips, max_spread_pips, min_rr, lot bounds,
          adjust_for_spread flag.
    Returns: dict with is_valid, order fields, rejection_reason.
    """
    # Check spread first — cheapest filter
    if not _validate_spread(spread_pips, max_spread_pips):
        return _rejection("spread_too_wide", spread_pips)

    # Adjust SL for spread if enabled
    cdef double adj_sl = stop_loss
    if adjust_for_spread:
        adj_sl = _adjust_sl_for_spread(
            stop_loss, direction, spread_pips, pip_size,
        )

    # Build the order
    cdef BracketOrder order = _build_bracket(
        direction, entry_price, adj_sl, take_profit, lot_size, pip_size,
    )

    # Run validation checks
    return _run_validations(
        order, min_rr, min_lots, max_lots, pip_size,
    )


# ------------------------------------------------------------------
# Run all validation checks and return result dict
# ------------------------------------------------------------------
cdef dict _run_validations(
    BracketOrder order,
    double min_rr,
    double min_lots,
    double max_lots,
    double pip_size,
):
    """Execute all order validations and return dict."""
    if not _validate_sl_tp_placement(order):
        return _rejection("invalid_sl_tp_placement", 0.0)

    if not _validate_min_rr(order, min_rr):
        return _rejection("rr_below_minimum", order.rr_ratio)

    if not _validate_lot_size(order.lot_size, min_lots, max_lots):
        return _rejection("invalid_lot_size", order.lot_size)

    return _bracket_to_dict(order)


# ------------------------------------------------------------------
# Build a rejection response
# ------------------------------------------------------------------
cdef dict _rejection(str reason, double value):
    """Return a standardized rejection dict."""
    return {
        "is_valid": False,
        "rejection_reason": reason,
        "rejection_value": value,
    }


# ------------------------------------------------------------------
# Serialize BracketOrder to Python dict
# ------------------------------------------------------------------
cdef dict _bracket_to_dict(BracketOrder order):
    """Convert BracketOrder struct into a Python dictionary."""
    return {
        "is_valid": bool(order.is_valid),
        "direction": order.direction,
        "entry_price": order.entry_price,
        "stop_loss": order.stop_loss,
        "take_profit": order.take_profit,
        "lot_size": order.lot_size,
        "risk_pips": order.risk_pips,
        "reward_pips": order.reward_pips,
        "rr_ratio": order.rr_ratio,
        "rejection_reason": None,
    }


# ------------------------------------------------------------------
# Public: compute IB order quantities from lot size
# ------------------------------------------------------------------
def lots_to_units(double lot_size, str lot_type):
    """
    Convert lot size to IB Forex order units.

    Parameters
    ----------
    lot_size : float
        Number of lots.
    lot_type : str
        One of: 'standard' (100k), 'mini' (10k), 'micro' (1k).

    Returns
    -------
    int
        Number of currency units for IB order.
    """
    cdef double multiplier
    if lot_type == "standard":
        multiplier = 100000.0
    elif lot_type == "mini":
        multiplier = 10000.0
    elif lot_type == "micro":
        multiplier = 1000.0
    else:
        multiplier = 100000.0  # Default to standard

    return int(lot_size * multiplier)
