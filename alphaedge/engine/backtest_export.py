# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/engine/backtest_export.py
# DESCRIPTION  : Backtest result export: CSV and equity curve chart
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — backtest export utilities: CSV and equity curve chart."""

from __future__ import annotations

import os
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from alphaedge.config.constants import PROJECT_TITLE
from alphaedge.engine.backtest_types import BacktestStats, TradeRecord
from alphaedge.utils.logger import get_logger

matplotlib.use("Agg")  # Non-interactive backend

logger = get_logger()


# ------------------------------------------------------------------
# Export trade records and stats to CSV
# ------------------------------------------------------------------
def export_results_csv(
    trades: list[TradeRecord],
    stats: BacktestStats,
    output_path: str = "reports/ALPHAEDGE_backtest_results.csv",
    eur_usd_rate: float = 1.08,
) -> None:
    """
    Export trade records and stats to CSV.

    Parameters
    ----------
    trades : list[TradeRecord]
        Completed trade records.
    stats : BacktestStats
        Aggregate statistics.
    output_path : str
        Output file path.
    """
    rows: list[dict[str, Any]] = []
    for t in trades:
        rows.append(
            {
                "pair": t.pair,
                "direction": "LONG" if t.direction == 1 else "SHORT",
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "stop_loss": t.stop_loss,
                "take_profit": t.take_profit,
                "pnl_pips": round(t.pnl_pips, 2),
                "pnl_usd": round(t.pnl_usd, 2),
                "pnl_eur": round(t.pnl_usd / eur_usd_rate, 2),
                "outcome": t.outcome,
                "entry_time": t.entry_time,
                "exit_time": t.exit_time,
                "sample_type": t.sample_type,
            }
        )

    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    df.to_csv(output_path, index=False)
    logger.info(f"ALPHAEDGE backtest results exported to {output_path}")


# ------------------------------------------------------------------
# Plot equity curve
# ------------------------------------------------------------------
def plot_equity_curve(
    trades: list[TradeRecord],
    output_path: str = "reports/ALPHAEDGE_equity_curve.png",
    starting_equity: float = 10000.0,
) -> None:
    """
    Generate and save the equity curve chart.

    Parameters
    ----------
    trades : list[TradeRecord]
        Completed trades in chronological order.
    output_path : str
        Path to save the PNG file.
    starting_equity : float
        Initial equity for the curve.
    """
    equity_values = [starting_equity]
    labels = ["Start"]

    for i, trade in enumerate(trades):
        equity_values.append(equity_values[-1] + trade.pnl_usd)
        labels.append(f"T{i + 1}")

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(range(len(equity_values)), equity_values, "b-", linewidth=1.5)
    ax.fill_between(
        range(len(equity_values)),
        starting_equity,
        np.array(equity_values),
        alpha=0.1,
    )
    ax.set_title(f"{PROJECT_TITLE} — Equity Curve")
    ax.set_xlabel("Trade #")
    ax.set_ylabel("Equity ($)")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    logger.info(f"ALPHAEDGE equity curve saved to {output_path}")
