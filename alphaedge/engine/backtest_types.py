# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/engine/backtest_types.py
# DESCRIPTION  : Shared data types used by the backtest subsystem
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — backtest shared data types.

Includes: TradeRecord, BacktestStats, BacktestReport.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


# ------------------------------------------------------------------
# Backtest trade record
# ------------------------------------------------------------------
@dataclass
class TradeRecord:
    """Stores a single backtest trade result."""

    pair: str
    direction: int  # 1 = long, -1 = short
    entry_price: float
    stop_loss: float
    take_profit: float
    entry_time: datetime
    exit_price: float = 0.0
    exit_time: datetime | None = None
    pnl_pips: float = 0.0
    pnl_usd: float = 0.0
    outcome: str = ""  # 'win', 'loss', 'breakeven'
    spread_cost_pips: float = 0.0
    sl_pips: float = 0.0  # SL distance in pips (set at entry, used for equity sizing)
    sample_type: str = ""  # 'IS', 'OOS', or ''


# ------------------------------------------------------------------
# Backtest statistics
# ------------------------------------------------------------------
@dataclass
class BacktestStats:
    """Aggregate backtest performance statistics."""

    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    breakeven: int = 0
    winrate: float = 0.0
    profit_factor: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0  # signal quality: annualised Sharpe on raw pips
    sharpe_equity: float = 0.0  # real Sharpe: annualised Sharpe on equity % returns
    total_pnl_pips: float = 0.0
    total_pnl_usd: float = 0.0
    total_pnl_eur: float = 0.0
    avg_rr_achieved: float = 0.0
    avg_win_pips: float = 0.0
    avg_loss_pips: float = 0.0
    expectancy_pips: float = 0.0
    max_consec_wins: int = 0
    max_consec_losses: int = 0


# ------------------------------------------------------------------
# Combined IS/OOS report
# ------------------------------------------------------------------
@dataclass
class BacktestReport:
    """Combined IS/OOS backtest report."""

    in_sample: BacktestStats = field(default_factory=BacktestStats)
    out_of_sample: BacktestStats = field(default_factory=BacktestStats)
    degradation: dict[str, float] = field(default_factory=dict)
