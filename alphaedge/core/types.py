# ============================================================
# PROJECT      : ALPHAEDGE
# FILE         : alphaedge/core/types.py
# DESCRIPTION  : TypedDict definitions for Cython core return values.
#                Shared between .pyx stubs and engine consumers.
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-05-05
# ============================================================
"""ALPHAEDGE — Typed return contracts for core Cython modules."""

from __future__ import annotations

from typing import TypedDict


class MomentumSignal(TypedDict):
    """Return value of ``momentum_detector.detect_momentum()``."""

    detected: bool
    direction: int
    strength: float
    ema_fast: float
    ema_slow: float
    adx: float
    timestamp: int


class PositionSizeResult(TypedDict):
    """Return value of ``risk_manager.calculate_position_size()``."""

    lot_size: float
    risk_amount: float
    pip_value: float
    sl_pips: float
    is_valid: bool


class DailyLimitResult(TypedDict):
    """Return value of ``risk_manager.check_daily_limit()``."""

    daily_pnl: float
    daily_pnl_pct: float
    limit_breached: bool
    trades_today: int
    max_trades: int
    can_trade: bool


class _BracketOrderBase(TypedDict):
    """Required fields present in every ``create_bracket_order`` return value."""

    is_valid: bool
    rejection_reason: str | None


class BracketOrderResult(_BracketOrderBase, total=False):
    """Return value of ``order_manager.create_bracket_order()``.

    Fields from ``_BracketOrderBase`` (``is_valid``, ``rejection_reason``) are
    always present.  All other fields are present only when ``is_valid`` is
    ``True``, except ``rejection_value`` which is present only when
    ``is_valid`` is ``False``.
    """

    rejection_value: float
    direction: int
    entry_price: float
    stop_loss: float
    take_profit: float
    lot_size: float
    risk_pips: float
    reward_pips: float
    rr_ratio: float


class PairLimitResult(TypedDict):
    """Return value of ``risk_manager.check_pair_limit()``."""

    allowed: bool
    reason: str | None
    open_count: int
    max_allowed: int
    open_pairs: list[str]
