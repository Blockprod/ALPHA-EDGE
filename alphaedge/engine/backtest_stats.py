# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/engine/backtest_stats.py
# DESCRIPTION  : Aggregate statistics computation for backtests
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — backtest statistics: compute_stats, split IS/OOS, degrade report."""

from __future__ import annotations

import numpy as np

from alphaedge.config.constants import PROJECT_TITLE
from alphaedge.engine.backtest_types import BacktestReport, BacktestStats, TradeRecord
from alphaedge.utils.logger import get_logger

logger = get_logger()


# ------------------------------------------------------------------
# Aggregate statistics
# ------------------------------------------------------------------
def compute_stats(trades: list[TradeRecord]) -> BacktestStats:
    """
    Calculate aggregate backtest statistics.

    Parameters
    ----------
    trades : list[TradeRecord]
        Completed trade records.

    Returns
    -------
    BacktestStats
        Aggregate performance metrics.
    """
    stats = BacktestStats()
    stats.total_trades = len(trades)

    if not trades:
        return stats

    wins = [t for t in trades if t.pnl_pips > 0]
    losses = [t for t in trades if t.pnl_pips <= 0]
    stats.wins = len(wins)
    stats.losses = len(losses)

    stats.winrate = _compute_winrate(stats.wins, stats.total_trades)
    stats.profit_factor = _compute_profit_factor(wins, losses)
    stats.total_pnl_pips = sum(t.pnl_pips for t in trades)
    stats.total_pnl_usd = sum(t.pnl_usd for t in trades)
    stats.max_drawdown_pct = _compute_max_drawdown(trades)
    stats.sharpe_ratio = _compute_sharpe(trades)

    return stats


# ------------------------------------------------------------------
# Component helpers
# ------------------------------------------------------------------
def _compute_winrate(wins: int, total: int) -> float:
    """Calculate win rate as percentage."""
    if total == 0:
        return 0.0
    return (wins / total) * 100.0


def _compute_profit_factor(
    wins: list[TradeRecord],
    losses: list[TradeRecord],
) -> float:
    """Calculate profit factor (gross profit / gross loss)."""
    gross_profit = sum(t.pnl_pips for t in wins)
    gross_loss = abs(sum(t.pnl_pips for t in losses))

    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def _compute_max_drawdown(trades: list[TradeRecord]) -> float:
    """
    Calculate maximum drawdown percentage from equity curve.

    Parameters
    ----------
    trades : list[TradeRecord]
        Completed trades in chronological order.

    Returns
    -------
    float
        Max drawdown as a percentage.
    """
    if not trades:
        return 0.0

    equity = 10000.0  # Hypothetical starting equity
    peak = equity
    max_dd = 0.0

    for trade in trades:
        equity += trade.pnl_usd
        peak = max(peak, equity)
        drawdown = ((peak - equity) / peak) * 100.0
        max_dd = max(max_dd, drawdown)

    return max_dd


def _compute_sharpe(
    trades: list[TradeRecord],
    risk_free_rate: float = 0.0,
) -> float:
    """
    Calculate annualized Sharpe ratio from trade P&L.

    Parameters
    ----------
    trades : list[TradeRecord]
        Completed trades.
    risk_free_rate : float
        Annual risk-free rate.

    Returns
    -------
    float
        Annualized Sharpe ratio.
    """
    if len(trades) < 2:
        return 0.0

    returns = [t.pnl_pips for t in trades]
    avg_return = np.mean(returns)
    std_return = np.std(returns, ddof=1)

    if std_return == 0:
        return 0.0

    # Annualize assuming ~252 trading days
    sharpe = (avg_return - risk_free_rate) / std_return
    return float(sharpe * np.sqrt(252))


# ------------------------------------------------------------------
# In-Sample / Out-of-Sample split
# ------------------------------------------------------------------
def split_trades_is_oos(
    trades: list[TradeRecord],
    is_ratio: float = 0.7,
) -> tuple[list[TradeRecord], list[TradeRecord]]:
    """
    Split trades chronologically into In-Sample and Out-of-Sample.

    Parameters
    ----------
    trades : list[TradeRecord]
        All trades sorted by entry_time.
    is_ratio : float
        Fraction of trades for the in-sample set (default 0.7).

    Returns
    -------
    tuple[list[TradeRecord], list[TradeRecord]]
        (in_sample_trades, out_of_sample_trades) with sample_type tagged.
    """
    sorted_trades = sorted(trades, key=lambda t: t.entry_time)
    split_idx = int(len(sorted_trades) * is_ratio)

    is_trades = sorted_trades[:split_idx]
    oos_trades = sorted_trades[split_idx:]

    for t in is_trades:
        t.sample_type = "IS"
    for t in oos_trades:
        t.sample_type = "OOS"

    return is_trades, oos_trades


def compute_split_report(
    trades: list[TradeRecord],
    is_ratio: float = 0.7,
) -> BacktestReport:
    """
    Compute IS/OOS statistics and degradation metrics.

    Parameters
    ----------
    trades : list[TradeRecord]
        All backtest trades.
    is_ratio : float
        Fraction for in-sample (default 0.7).

    Returns
    -------
    BacktestReport
        Report with IS stats, OOS stats, and degradation percentages.
    """
    is_trades, oos_trades = split_trades_is_oos(trades, is_ratio)
    is_stats = compute_stats(is_trades)
    oos_stats = compute_stats(oos_trades)

    degradation: dict[str, float] = {}
    for metric in ("winrate", "profit_factor", "sharpe_ratio"):
        is_val = getattr(is_stats, metric)
        oos_val = getattr(oos_stats, metric)
        if is_val != 0.0 and is_val != float("inf"):
            degradation[metric] = ((is_val - oos_val) / abs(is_val)) * 100.0
        else:
            degradation[metric] = 0.0

    return BacktestReport(
        in_sample=is_stats,
        out_of_sample=oos_stats,
        degradation=degradation,
    )


# ------------------------------------------------------------------
# Logging helpers
# ------------------------------------------------------------------
def _log_stats_summary(stats: BacktestStats) -> None:
    """Print a summary of backtest statistics to the log."""
    logger.info("=" * 50)
    logger.info(f"{PROJECT_TITLE} — BACKTEST RESULTS")
    logger.info(f"  Total trades:   {stats.total_trades}")
    logger.info(f"  Wins:           {stats.wins}")
    logger.info(f"  Losses:         {stats.losses}")
    logger.info(f"  Win rate:       {stats.winrate:.1f}%")
    logger.info(f"  Profit factor:  {stats.profit_factor:.2f}")
    logger.info(f"  Max drawdown:   {stats.max_drawdown_pct:.2f}%")
    logger.info(f"  Sharpe ratio:   {stats.sharpe_ratio:.2f}")
    logger.info(f"  Total P&L:      {stats.total_pnl_pips:.1f} pips")
    logger.info("=" * 50)


def _log_split_report(report: BacktestReport) -> None:
    """Log IS/OOS comparison and degradation metrics."""
    logger.info("=" * 50)
    logger.info(f"{PROJECT_TITLE} — IN-SAMPLE / OUT-OF-SAMPLE REPORT")
    logger.info("-" * 50)

    is_s = report.in_sample
    oos_s = report.out_of_sample

    logger.info(f"  {'Metric':<18} {'IS':>10} {'OOS':>10} {'Degrad%':>10}")
    logger.info(f"  {'-' * 48}")
    logger.info(
        f"  {'Trades':<18} {is_s.total_trades:>10} {oos_s.total_trades:>10} {'':>10}"
    )
    logger.info(
        f"  {'Win rate':<18} {is_s.winrate:>9.1f}% {oos_s.winrate:>9.1f}% "
        f"{report.degradation.get('winrate', 0.0):>9.1f}%"
    )
    logger.info(
        f"  {'Profit factor':<18} {is_s.profit_factor:>10.2f} "
        f"{oos_s.profit_factor:>10.2f} "
        f"{report.degradation.get('profit_factor', 0.0):>9.1f}%"
    )
    logger.info(
        f"  {'Max drawdown':<18} {is_s.max_drawdown_pct:>9.2f}% "
        f"{oos_s.max_drawdown_pct:>9.2f}%"
    )
    logger.info(
        f"  {'Sharpe ratio':<18} {is_s.sharpe_ratio:>10.2f} "
        f"{oos_s.sharpe_ratio:>10.2f} "
        f"{report.degradation.get('sharpe_ratio', 0.0):>9.1f}%"
    )
    logger.info(
        f"  {'Total P&L':<18} {is_s.total_pnl_pips:>9.1f}p "
        f"{oos_s.total_pnl_pips:>9.1f}p"
    )
    logger.info("=" * 50)

    # Warn if OOS degrades > 30% on any key metric
    for metric, pct in report.degradation.items():
        if pct > 30.0:
            logger.warning(
                f"ALPHAEDGE: OOS {metric} degraded {pct:.1f}% vs IS (threshold: 30%)"
            )
