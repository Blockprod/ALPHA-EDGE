"""ALPHAEDGE — Pure-Python stub for order_manager (Cython fallback)."""

from __future__ import annotations

from typing import Any


def create_bracket_order(
    direction: int,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    lot_size: float,
    pip_size: float,
    spread_pips: float,
    max_spread_pips: float,
    min_rr: float,
    min_lots: float,
    max_lots: float,
    adjust_for_spread: bool,
) -> dict[str, Any]:
    """Create and validate a bracket order for IB submission."""
    if spread_pips > max_spread_pips:
        return {
            "is_valid": False,
            "rejection_reason": "spread_too_wide",
            "rejection_value": spread_pips,
        }

    adj_sl = stop_loss
    if adjust_for_spread:
        buffer = spread_pips * pip_size
        adj_sl = (stop_loss - buffer) if direction == 1 else (stop_loss + buffer)

    risk_pips = abs(entry_price - adj_sl) / pip_size
    reward_pips = abs(entry_price - take_profit) / pip_size
    rr_ratio = (reward_pips / risk_pips) if risk_pips > 0 else 0.0

    # Validate SL/TP placement
    if direction == 1:
        if not adj_sl < entry_price < take_profit:
            return {
                "is_valid": False,
                "rejection_reason": "invalid_sl_tp_placement",
                "rejection_value": 0.0,
            }
    elif direction == -1:
        if not take_profit < entry_price < adj_sl:
            return {
                "is_valid": False,
                "rejection_reason": "invalid_sl_tp_placement",
                "rejection_value": 0.0,
            }
    else:
        return {
            "is_valid": False,
            "rejection_reason": "invalid_sl_tp_placement",
            "rejection_value": 0.0,
        }

    if rr_ratio < min_rr:
        return {
            "is_valid": False,
            "rejection_reason": "rr_below_minimum",
            "rejection_value": rr_ratio,
        }

    if not min_lots <= lot_size <= max_lots:
        return {
            "is_valid": False,
            "rejection_reason": "invalid_lot_size",
            "rejection_value": lot_size,
        }

    return {
        "is_valid": True,
        "direction": direction,
        "entry_price": entry_price,
        "stop_loss": adj_sl,
        "take_profit": take_profit,
        "lot_size": lot_size,
        "risk_pips": risk_pips,
        "reward_pips": reward_pips,
        "rr_ratio": rr_ratio,
        "rejection_reason": None,
    }


def lots_to_units(lot_size: float, lot_type: str) -> int:
    """Convert lot size to IB Forex order units."""
    multipliers = {"standard": 100000.0, "mini": 10000.0, "micro": 1000.0}
    multiplier = multipliers.get(lot_type, 100000.0)
    return int(lot_size * multiplier)
