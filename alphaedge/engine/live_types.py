# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/engine/live_types.py
# DESCRIPTION  : Live trade record type — journal de trading live
# AUTHOR       : ALPHAEDGE Dev Team
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-24
# ============================================================
"""ALPHAEDGE — Live trade data type for session journal."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class LiveTradeRecord:
    """Stores a single live trade — populated at fill then updated at close."""

    pair: str
    direction: int  # 1 = long, -1 = short
    entry_price: float  # prix demandé (bracket["entry_price"])
    fill_price: float  # prix réel IB (trade.orderStatus.avgFillPrice)
    stop_loss: float
    take_profit: float
    lot_size: float
    sl_pips: float  # distance SL en pips (signal["risk_pips"])
    spread_pips: float  # spread capturé à l'entrée
    exchange_rate: float  # taux pour conversion PnL (1.0 si USD-quoted)
    entry_time: datetime  # now_utc() au moment du fill
    exit_price: float = 0.0
    exit_time: datetime | None = None
    pnl_pips: float = 0.0
    pnl_usd: float = 0.0
    outcome: str = ""  # 'win' | 'loss' | 'breakeven' | 'unknown'
    slippage_pips: float = 0.0  # abs(fill_price - entry_price) / pip_size
    exit_reason: str = ""  # 'sl_hit' | 'tp_hit' | 'session_end' | 'unknown'
    adx_at_entry: float = 0.0  # ADX value at signal detection time
    strength_at_entry: float = 0.0  # momentum strength score at entry
    duration_s: float = 0.0  # trade duration in seconds (exit_time - entry_time)
    pnl_eur: float = 0.0  # pnl_usd converted to EUR for accounting
    fill_status: str = "unknown"  # "full" | "partial" | "rejected"
