"""ALPHAEDGE — Pure-Python stub for risk_manager (Cython fallback)."""

from __future__ import annotations

import math
from typing import Any


def calculate_position_size(
    account_equity: float,
    risk_pct: float,
    sl_pips: float,
    pair: str,
    pip_size: float,
    lot_type: str,
    min_lots: float,
    max_lots: float,
    exchange_rate: float = 0.0,
) -> dict[str, Any]:
    """Calculate optimal position size based on risk parameters."""
    pip_val = _compute_pip_value(pair, pip_size, lot_type, exchange_rate)

    risk_amount = account_equity * (risk_pct / 100.0)

    if sl_pips <= 0.0 or pip_val <= 0.0:
        return {
            "lot_size": 0.0,
            "risk_amount": risk_amount,
            "pip_value": pip_val,
            "sl_pips": sl_pips,
            "is_valid": False,
        }

    raw_lots = risk_amount / (sl_pips * pip_val)
    lot_size = math.floor(raw_lots * 100.0) / 100.0
    is_valid = min_lots <= lot_size <= max_lots

    return {
        "lot_size": lot_size,
        "risk_amount": risk_amount,
        "pip_value": pip_val,
        "sl_pips": sl_pips,
        "is_valid": is_valid,
    }


def check_daily_limit(
    starting_equity: float,
    current_equity: float,
    max_daily_loss_pct: float,
    trades_today: int,
    max_trades: int,
) -> dict[str, Any]:
    """Check if the daily loss limit or trade count is breached."""
    daily_pnl = current_equity - starting_equity
    daily_pnl_pct = (
        (daily_pnl / starting_equity * 100.0) if starting_equity > 0 else 0.0
    )
    limit_breached = daily_pnl_pct <= -max_daily_loss_pct

    if trades_today >= max_trades:
        limit_breached = True

    return {
        "daily_pnl": daily_pnl,
        "daily_pnl_pct": daily_pnl_pct,
        "limit_breached": limit_breached,
        "trades_today": trades_today,
        "max_trades": max_trades,
        "can_trade": not limit_breached,
    }


def check_pair_limit(
    pair: str,
    open_pairs: list[str],
    max_open_pairs: int = 1,
) -> dict[str, Any]:
    """Enforce per-pair risk cap: max N pairs open at a time."""
    count = len(open_pairs)
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


def apply_slippage_buffer(
    stop_loss: float,
    direction: int,
    slippage_pips: float,
    pip_size: float,
) -> float:
    """Widen stop loss by slippage buffer."""
    buffer = slippage_pips * pip_size
    if direction == 1:
        return stop_loss - buffer
    return stop_loss + buffer


def _compute_pip_value(
    pair: str, pip_size: float, lot_type: str, exchange_rate: float
) -> float:
    """Calculate pip value in USD for the given lot type."""
    lot_units = {"standard": 100000.0, "mini": 10000.0, "micro": 1000.0}
    units = lot_units.get(lot_type, 100000.0)
    raw = units * pip_size
    if exchange_rate > 0.0 and pip_size >= 0.001:
        return raw / exchange_rate
    return raw
