# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
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
import tempfile
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from alphaedge.config.constants import PROJECT_TITLE
from alphaedge.engine.backtest_types import BacktestStats, RejectionLog, TradeRecord
from alphaedge.utils.logger import get_logger

matplotlib.use("Agg")  # Non-interactive backend

logger = get_logger()


def _records_to_dataframe(records: Any) -> pd.DataFrame:
    """Normalize records into a DataFrame for export helpers."""
    if isinstance(records, pd.DataFrame):
        return records.copy()
    if isinstance(records, list):
        if not records:
            return pd.DataFrame()
        if isinstance(records[0], dict):
            return pd.DataFrame(records)
        normalized = []
        for item in records:
            normalized.append(
                {
                    key: getattr(item, key)
                    for key in dir(item)
                    if not key.startswith("_") and not callable(getattr(item, key))
                }
            )
        return pd.DataFrame(normalized)
    return pd.DataFrame()


def cost_divergence_within_tolerance(
    comparison_df: pd.DataFrame,
    tolerance_pct: float = 15.0,
) -> bool:
    """Return True if all measurable divergences are within tolerance."""
    if comparison_df.empty or "diff_pct" not in comparison_df.columns:
        return True
    valid = comparison_df["diff_pct"].dropna().abs()
    if valid.empty:
        return True
    return bool((valid <= tolerance_pct).all())


def _column_or_default(df: pd.DataFrame, column: str, default: float) -> pd.Series:
    """Return a DataFrame column or a default-valued Series with matching index."""
    if column in df.columns:
        return pd.to_numeric(df[column], errors="coerce").fillna(default)
    return pd.Series(default, index=df.index, dtype="float64")


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
                "sl_pips": round(t.sl_pips, 2),
                "spread_cost_pips": round(t.spread_cost_pips, 2),
            }
        )

    df = pd.DataFrame(rows)
    dest = output_path
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=os.path.dirname(dest) or ".",
        suffix=".tmp",
        prefix="backtest_export_",
    )
    try:
        with os.fdopen(tmp_fd, "w", newline="", encoding="utf-8") as fh:
            df.to_csv(fh, index=False)
        os.replace(tmp_path, dest)
    except OSError:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
    logger.info(
        f"ALPHAEDGE backtest results exported to {output_path} "
        f"({stats.total_trades} trades \u00b7 ${stats.total_pnl_usd:+,.2f} P&L)"
    )


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


# ------------------------------------------------------------------
# Export rejection logs to CSV
# ------------------------------------------------------------------
def export_rejection_logs(
    rejection_logs: list[RejectionLog],
    output_path: str = "reports/ALPHAEDGE_rejection_logs.csv",
) -> None:
    """
    Export per-trade signal rejection logs to CSV.

    Useful for diagnosing filter cascade effects and signal silence periods.

    Parameters
    ----------
    rejection_logs : list[RejectionLog]
        Rejection log entries from backtest.
    output_path : str
        Path to save the CSV file.
    """
    if not rejection_logs:
        logger.warning("ALPHAEDGE: No rejection logs to export")
        return

    records = []
    for log in rejection_logs:
        records.append(
            {
                "date": log.date.isoformat(),
                "pair": log.pair,
                "direction": "LONG"
                if log.direction == 1
                else "SHORT"
                if log.direction == -1
                else "NONE",
                "rejection_reason": log.rejection_reason,
                "rejection_value": round(log.rejection_value, 4),
                "primary_filter": log.primary_filter,
                "signal_strength_adx": round(log.signal_strength, 2),
                "alternative_carries": "|".join(log.alternative_carries) or "",
            }
        )

    df = pd.DataFrame(records)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    df.to_csv(output_path, index=False)
    logger.info(
        f"ALPHAEDGE: {len(rejection_logs)} rejection logs exported to {output_path}"
    )


def export_cost_comparison(
    backtest_trades: Any,
    live_trades: Any,
    output_path: str = "reports/ALPHAEDGE_cost_comparison.csv",
) -> pd.DataFrame:
    """
    Export backtest vs live transaction cost comparison to CSV.

    Matching strategy: sort by entry_time and match by (pair, direction, ordinal).
    """
    output_columns = [
        "pair",
        "direction",
        "entry_time",
        "backtest_slippage_cost",
        "live_slippage_cost",
        "diff_pips",
        "diff_pct",
        "backtest_spread_cost_pips",
        "backtest_slippage_cost_pips",
        "live_spread_cost_pips",
        "live_slippage_cost_pips",
    ]

    bt_df = _records_to_dataframe(backtest_trades)
    lv_df = _records_to_dataframe(live_trades)

    if bt_df.empty or lv_df.empty:
        logger.warning("ALPHAEDGE: Cost comparison skipped (empty backtest/live set)")
        out = pd.DataFrame(columns=output_columns)
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        out.to_csv(output_path, index=False)
        return out

    if "pair" not in bt_df.columns or "direction" not in bt_df.columns:
        logger.warning("ALPHAEDGE: Backtest trades missing pair/direction columns")
        out = pd.DataFrame(columns=output_columns)
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        out.to_csv(output_path, index=False)
        return out
    if "pair" not in lv_df.columns or "direction" not in lv_df.columns:
        logger.warning("ALPHAEDGE: Live trades missing pair/direction columns")
        out = pd.DataFrame(columns=output_columns)
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        out.to_csv(output_path, index=False)
        return out

    bt_df = bt_df.copy()
    lv_df = lv_df.copy()

    if "entry_time" in bt_df.columns:
        bt_df["entry_time"] = pd.to_datetime(bt_df["entry_time"], errors="coerce")
    else:
        bt_df["entry_time"] = pd.NaT
    if "entry_time" in lv_df.columns:
        lv_df["entry_time"] = pd.to_datetime(lv_df["entry_time"], errors="coerce")
    else:
        lv_df["entry_time"] = pd.NaT

    bt_df["direction"] = bt_df["direction"].astype(str).str.upper()
    lv_df["direction"] = lv_df["direction"].astype(str).str.upper()

    bt_df["backtest_spread_cost_pips"] = _column_or_default(
        bt_df, "spread_cost_pips", 0.0
    )
    bt_df["backtest_slippage_cost_pips"] = _column_or_default(
        bt_df, "slippage_pips", 0.0
    )
    bt_df["backtest_total_cost_pips"] = (
        bt_df["backtest_spread_cost_pips"] + bt_df["backtest_slippage_cost_pips"]
    )

    lv_df["live_spread_cost_pips"] = _column_or_default(lv_df, "spread_pips", 0.0)
    lv_df["live_slippage_cost_pips"] = _column_or_default(lv_df, "slippage_pips", 0.0)
    lv_df["live_total_cost_pips"] = (
        lv_df["live_spread_cost_pips"] + lv_df["live_slippage_cost_pips"]
    )

    bt_df = bt_df.sort_values(["pair", "direction", "entry_time"]).reset_index(
        drop=True
    )
    lv_df = lv_df.sort_values(["pair", "direction", "entry_time"]).reset_index(
        drop=True
    )

    bt_df["ordinal"] = bt_df.groupby(["pair", "direction"]).cumcount()
    lv_df["ordinal"] = lv_df.groupby(["pair", "direction"]).cumcount()

    merged = bt_df.merge(
        lv_df,
        on=["pair", "direction", "ordinal"],
        how="inner",
        suffixes=("_bt", "_lv"),
    )

    if merged.empty:
        logger.warning("ALPHAEDGE: Cost comparison produced no matched trades")
        out = pd.DataFrame(columns=output_columns)
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        out.to_csv(output_path, index=False)
        return out

    merged["backtest_slippage_cost"] = merged["backtest_total_cost_pips"]
    merged["live_slippage_cost"] = merged["live_total_cost_pips"]
    merged["diff_pips"] = (
        merged["live_slippage_cost"] - merged["backtest_slippage_cost"]
    )
    merged["diff_pct"] = np.where(
        merged["backtest_slippage_cost"].abs() > 0.0,
        merged["diff_pips"] / merged["backtest_slippage_cost"] * 100.0,
        np.nan,
    )

    out = (
        merged[
            [
                "pair",
                "direction",
                "entry_time_bt",
                "backtest_slippage_cost",
                "live_slippage_cost",
                "diff_pips",
                "diff_pct",
                "backtest_spread_cost_pips",
                "backtest_slippage_cost_pips",
                "live_spread_cost_pips",
                "live_slippage_cost_pips",
            ]
        ]
        .rename(columns={"entry_time_bt": "entry_time"})
        .reindex(columns=output_columns)
    )

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    out.to_csv(output_path, index=False)
    logger.info(
        "ALPHAEDGE: Cost comparison exported to {} (matched_trades={})",
        output_path,
        len(out),
    )
    return out
