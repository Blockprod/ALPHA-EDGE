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
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from alphaedge.config.constants import PROJECT_TITLE
from alphaedge.engine.backtest_types import BacktestReport, BacktestStats, TradeRecord
from alphaedge.utils.logger import get_logger

logger = get_logger()
_console = Console(highlight=False)


# ------------------------------------------------------------------
# Aggregate statistics
# ------------------------------------------------------------------
def compute_stats(
    trades: list[TradeRecord],
    eur_usd_rate: float = 1.08,
    starting_equity: float = 10000.0,
) -> BacktestStats:
    """
    Calculate aggregate backtest statistics.

    Parameters
    ----------
    trades : list[TradeRecord]
        Completed trade records.
    eur_usd_rate : float
        EUR/USD conversion rate for EUR P&L display.

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
    losses = [t for t in trades if t.pnl_pips < 0]
    breakevens = [t for t in trades if t.pnl_pips == 0]
    stats.wins = len(wins)
    stats.losses = len(losses)
    stats.breakeven = len(breakevens)

    stats.winrate = _compute_winrate(stats.wins, stats.total_trades)
    stats.profit_factor = _compute_profit_factor(wins, losses)
    stats.total_pnl_pips = sum(t.pnl_pips for t in trades)
    stats.total_pnl_usd = sum(t.pnl_usd for t in trades)
    stats.total_pnl_eur = stats.total_pnl_usd / eur_usd_rate
    stats.max_drawdown_pct = _compute_max_drawdown(trades, starting_equity)
    stats.sharpe_ratio = _compute_sharpe(trades)
    stats.sharpe_equity = _compute_equity_sharpe(trades, starting_equity)

    stats.avg_win_pips = float(np.mean([t.pnl_pips for t in wins])) if wins else 0.0
    stats.avg_loss_pips = (
        float(np.mean([t.pnl_pips for t in losses])) if losses else 0.0
    )
    stats.expectancy_pips = _compute_expectancy(
        stats.winrate, stats.avg_win_pips, stats.avg_loss_pips
    )
    stats.max_consec_wins, stats.max_consec_losses = _compute_consec_wins_losses(trades)

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


def _compute_expectancy(
    winrate_pct: float,
    avg_win_pips: float,
    avg_loss_pips: float,
) -> float:
    """Calculate expectancy in pips per trade (E = WR*avgW + (1-WR)*avgL)."""
    wr = winrate_pct / 100.0
    return wr * avg_win_pips + (1.0 - wr) * avg_loss_pips


def _compute_consec_wins_losses(
    trades: list[TradeRecord],
) -> tuple[int, int]:
    """
    Calculate maximum consecutive wins and losses.

    Returns
    -------
    tuple[int, int]
        (max_consec_wins, max_consec_losses).
    """
    max_wins = max_losses = cur_wins = cur_losses = 0
    for t in trades:
        if t.pnl_pips > 0:
            cur_wins += 1
            cur_losses = 0
        else:
            cur_losses += 1
            cur_wins = 0
        max_wins = max(max_wins, cur_wins)
        max_losses = max(max_losses, cur_losses)
    return max_wins, max_losses


def _compute_max_drawdown(
    trades: list[TradeRecord], starting_equity: float = 10000.0
) -> float:
    """
    Calculate maximum drawdown percentage from equity curve.

    Parameters
    ----------
    trades : list[TradeRecord]
        Completed trades in chronological order.
    starting_equity : float
        Initial equity for drawdown calculation.

    Returns
    -------
    float
        Max drawdown as a percentage.
    """
    if not trades:
        return 0.0

    equity = starting_equity
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


def _compute_equity_sharpe(
    trades: list[TradeRecord],
    starting_equity: float = 10000.0,
) -> float:
    """
    Annualised Sharpe ratio computed from equity percentage returns.

    Uses ``pnl_usd / running_equity`` per trade (requires
    ``_apply_equity_sizing`` to have been called beforehand for accurate
    dollar values).  This is the Sharpe that corresponds to the % return
    shown in the P&L section.
    """
    if len(trades) < 2 or starting_equity <= 0:
        return 0.0
    equity = starting_equity
    pct_returns: list[float] = []
    for t in trades:
        if equity > 0:
            pct_returns.append(t.pnl_usd / equity)
        else:
            pct_returns.append(0.0)
        equity += t.pnl_usd
    arr = np.array(pct_returns)
    std = float(arr.std(ddof=1))
    if std == 0:
        return 0.0
    return float(arr.mean() / std * np.sqrt(252))


# ------------------------------------------------------------------
# Compound fixed-fraction equity sizing
# ------------------------------------------------------------------
def _apply_equity_sizing(
    trades: list[TradeRecord],
    starting_equity: float,
    risk_pct: float,
    max_lot_size: float = 10.0,  # unused — kept for call-site compatibility
) -> None:
    """
    Recompute pnl_usd using compound fixed-fraction position sizing.

    Formula (scale-invariant — no FX conversion required)::

        risk_usd = running_equity × risk_pct / 100
        pnl_usd  = risk_usd × pnl_pips / sl_pips

    This is equivalent to always allocating exactly the lot size needed to
    risk ``risk_pct`` percent of equity, regardless of the pair's pip value
    or FX rate.  A win at R=2.0 yields +2×risk_pct% of equity; a stop-out
    yields −risk_pct%.  Equity compounds trade by trade.

    Trades are mutated in-place and sorted by entry_time.  Requires
    ``TradeRecord.sl_pips`` to be set (filled by ``_build_trade_record``).
    """
    if not trades or risk_pct <= 0:
        return
    trades.sort(key=lambda t: t.entry_time)
    equity = starting_equity
    for t in trades:
        if t.sl_pips > 0:
            risk_usd = equity * risk_pct / 100.0
            t.pnl_usd = risk_usd * (t.pnl_pips / t.sl_pips)
        else:
            t.pnl_usd = 0.0
        equity += t.pnl_usd


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
    eur_usd_rate: float = 1.08,
    starting_equity: float = 10000.0,
) -> BacktestReport:
    """
    Compute IS/OOS statistics and degradation metrics.

    Parameters
    ----------
    trades : list[TradeRecord]
        All backtest trades.
    is_ratio : float
        Fraction for in-sample (default 0.7).
    eur_usd_rate : float
        EUR/USD rate for EUR P&L conversion.

    Returns
    -------
    BacktestReport
        Report with IS stats, OOS stats, and degradation percentages.
    """
    is_trades, oos_trades = split_trades_is_oos(trades, is_ratio)
    is_stats = compute_stats(is_trades, eur_usd_rate, starting_equity)
    oos_stats = compute_stats(oos_trades, eur_usd_rate, starting_equity)

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
def _log_stats_summary(
    stats: BacktestStats,
    eur_usd_rate: float = 1.08,
    starting_equity: float = 10000.0,
) -> None:
    """Print a full summary of backtest statistics to the log."""
    sep = "=" * 58
    logger.info(sep)
    logger.info(f"{PROJECT_TITLE} — BACKTEST RESULTS")
    logger.info(sep)
    logger.info(f"  {'CAPITAL'}")
    eq_eur = starting_equity / eur_usd_rate
    logger.info(f"    Starting equity:      ${starting_equity:,.2f}  (€{eq_eur:,.2f})")
    logger.info(f"  {'TRADES':}")
    logger.info(f"    Total trades:         {stats.total_trades}")
    logger.info(f"    Wins:                 {stats.wins}")
    logger.info(f"    Losses:               {stats.losses}")
    logger.info(f"    Breakeven:            {stats.breakeven}")
    logger.info(f"    Win rate:             {stats.winrate:.1f}%")
    logger.info(f"    Max consec. wins:     {stats.max_consec_wins}")
    logger.info(f"    Max consec. losses:   {stats.max_consec_losses}")
    logger.info(f"  {'PERFORMANCE':}")
    logger.info(f"    Profit factor:        {stats.profit_factor:.2f}")
    logger.info(f"    Sharpe (pips):        {stats.sharpe_ratio:.2f}  [signal quality]")
    logger.info(
        f"    Sharpe (equity %):    {stats.sharpe_equity:.2f}"
        f"  [real risk-adjusted return]"
    )
    logger.info(f"    Max drawdown:         {stats.max_drawdown_pct:.2f}%")
    total_return_pct = (
        stats.total_pnl_usd / starting_equity * 100.0 if starting_equity > 0 else 0.0
    )
    final_equity = starting_equity + stats.total_pnl_usd
    logger.info(f"  {'P&L':}")
    logger.info(f"    Total P&L (pips):     {stats.total_pnl_pips:+.1f} pips")
    logger.info(f"    Total return:         {total_return_pct:+.2f}%")
    logger.info(f"    Total P&L (USD):      ${stats.total_pnl_usd:+.2f}")
    logger.info(f"    Final equity (USD):   ${final_equity:,.2f}")
    logger.info(
        f"    Total P&L (EUR):      €{stats.total_pnl_eur:+.2f}  [@ {eur_usd_rate:.4f}]"
    )
    logger.info(f"  {'PER TRADE':}")
    logger.info(f"    Avg win:              {stats.avg_win_pips:+.1f} pips")
    logger.info(f"    Avg loss:             {stats.avg_loss_pips:+.1f} pips")
    logger.info(f"    Expectancy:           {stats.expectancy_pips:+.2f} pips/trade")
    logger.info(sep)


def _log_per_pair_report(trades: list[TradeRecord], eur_usd_rate: float = 1.08) -> None:
    """Log per-pair performance breakdown: trades, WR, PF, expectancy, P&L."""
    from collections import defaultdict

    by_pair: dict[str, list[TradeRecord]] = defaultdict(list)
    for t in trades:
        by_pair[t.pair].append(t)

    if not by_pair:
        return

    sep = "=" * 58
    logger.info(sep)
    logger.info(f"{PROJECT_TITLE} — PER-PAIR BREAKDOWN")
    logger.info("-" * 58)
    logger.info(
        f"  {'Pair':<8} {'N':>4} {'W':>4} {'WR%':>6} {'PF':>5} "
        f"{'Expect':>8} {'P&L pip':>9} {'P&L USD':>10}"
    )
    logger.info(f"  {'-' * 54}")
    for pair in sorted(by_pair):
        pts = by_pair[pair]
        wins = [t for t in pts if t.pnl_pips > 0]
        losses = [t for t in pts if t.pnl_pips < 0]
        wr = (len(wins) / len(pts) * 100.0) if pts else 0.0
        pf = _compute_profit_factor(wins, losses)
        pnl_pips = sum(t.pnl_pips for t in pts)
        pnl_usd = sum(t.pnl_usd for t in pts)
        avg_w = float(np.mean([t.pnl_pips for t in wins])) if wins else 0.0
        avg_l = float(np.mean([t.pnl_pips for t in losses])) if losses else 0.0
        expect = wr / 100.0 * avg_w + (1.0 - wr / 100.0) * avg_l
        pf_str = f"{pf:.2f}" if pf != float("inf") else "  inf"
        logger.info(
            f"  {pair:<8} {len(pts):>4} {len(wins):>4} {wr:>5.1f}% {pf_str:>5} "
            f"{expect:>+7.2f}p {pnl_pips:>+8.1f}p ${pnl_usd:>+9.2f}"
        )
    logger.info(sep)


# ------------------------------------------------------------------
# Rich console summary
# ------------------------------------------------------------------
def print_rich_summary(
    trades: list[TradeRecord],
    stats: BacktestStats,
    starting_equity: float = 10000.0,
    eur_usd_rate: float = 1.08,
) -> None:
    """Print a Rich-formatted summary table to the console."""
    from collections import defaultdict

    final_equity = starting_equity + stats.total_pnl_usd
    total_return_pct = (
        stats.total_pnl_usd / starting_equity * 100.0 if starting_equity else 0.0
    )
    pnl_color = "green" if stats.total_pnl_usd >= 0 else "red"
    sharpe_color = (
        "green"
        if stats.sharpe_equity >= 1.0
        else ("yellow" if stats.sharpe_equity >= 0 else "red")
    )
    dd_color = (
        "green"
        if stats.max_drawdown_pct < 10
        else ("yellow" if stats.max_drawdown_pct < 20 else "red")
    )
    wr_color = (
        "green"
        if stats.winrate >= 40
        else ("yellow" if stats.winrate >= 28.6 else "red")
    )

    # ── Main metrics table ────────────────────────────────────────
    tbl = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="bright_black",
        expand=True,
        pad_edge=True,
    )
    tbl.add_column("Metric", style="bold white", no_wrap=True)
    tbl.add_column("Value", justify="right")

    tbl.add_section()
    tbl.add_row("[bold]CAPITAL[/bold]", "")
    tbl.add_row("  Starting equity", f"[white]${starting_equity:,.2f}[/white]")
    tbl.add_row("  Final equity", f"[{pnl_color}]${final_equity:,.2f}[/{pnl_color}]")
    tbl.add_row(
        "  Total P&L (USD)", f"[{pnl_color}]${stats.total_pnl_usd:+,.2f}[/{pnl_color}]"
    )
    tbl.add_row(
        "  Total P&L (EUR)", f"[{pnl_color}]€{stats.total_pnl_eur:+,.2f}[/{pnl_color}]"
    )
    tbl.add_row(
        "  Total return", f"[{pnl_color}]{total_return_pct:+.2f}%[/{pnl_color}]"
    )

    tbl.add_section()
    tbl.add_row("[bold]TRADES[/bold]", "")
    tbl.add_row("  Total", str(stats.total_trades))
    tbl.add_row(
        "  Wins / Losses", f"[green]{stats.wins}[/green] / [red]{stats.losses}[/red]"
    )
    tbl.add_row("  Win rate", f"[{wr_color}]{stats.winrate:.1f}%[/{wr_color}]")
    tbl.add_row("  Avg win", f"[green]{stats.avg_win_pips:+.1f} pips[/green]")
    tbl.add_row("  Avg loss", f"[red]{stats.avg_loss_pips:+.1f} pips[/red]")
    tbl.add_row(
        "  Expectancy",
        f"[{pnl_color}]{stats.expectancy_pips:+.2f} pips/trade[/{pnl_color}]",
    )
    tbl.add_row("  Max consec. wins", str(stats.max_consec_wins))
    tbl.add_row("  Max consec. losses", str(stats.max_consec_losses))

    tbl.add_section()
    tbl.add_row("[bold]PERFORMANCE[/bold]", "")
    tbl.add_row("  Profit factor", f"{stats.profit_factor:.2f}")
    tbl.add_row("  Sharpe (pips)", f"{stats.sharpe_ratio:.2f}")
    tbl.add_row(
        "  Sharpe (equity %)",
        f"[{sharpe_color}]{stats.sharpe_equity:.2f}[/{sharpe_color}]",
    )
    tbl.add_row(
        "  Max drawdown", f"[{dd_color}]{stats.max_drawdown_pct:.2f}%[/{dd_color}]"
    )
    tbl.add_row(
        "  Total P&L (pips)",
        f"[{pnl_color}]{stats.total_pnl_pips:+.1f} pips[/{pnl_color}]",
    )

    # ── Per-pair table ────────────────────────────────────────────
    by_pair: dict[str, list[TradeRecord]] = defaultdict(list)
    for t in trades:
        by_pair[t.pair].append(t)

    pair_tbl = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="bright_black",
        expand=True,
        pad_edge=True,
    )
    pair_tbl.add_column("Pair", style="bold white", no_wrap=True)
    pair_tbl.add_column("N", justify="right")
    pair_tbl.add_column("W", justify="right")
    pair_tbl.add_column("WR%", justify="right")
    pair_tbl.add_column("PF", justify="right")
    pair_tbl.add_column("Expect", justify="right")
    pair_tbl.add_column("P&L pips", justify="right")
    pair_tbl.add_column("P&L USD", justify="right")

    for pair in sorted(by_pair):
        pts = by_pair[pair]
        pw = [t for t in pts if t.pnl_pips > 0]
        pl = [t for t in pts if t.pnl_pips < 0]
        wr = len(pw) / len(pts) * 100.0 if pts else 0.0
        pf = _compute_profit_factor(pw, pl)
        pnl_pips = sum(t.pnl_pips for t in pts)
        pnl_usd = sum(t.pnl_usd for t in pts)
        avg_w = float(np.mean([t.pnl_pips for t in pw])) if pw else 0.0
        avg_l = float(np.mean([t.pnl_pips for t in pl])) if pl else 0.0
        exp = wr / 100.0 * avg_w + (1.0 - wr / 100.0) * avg_l
        pf_str = "∞" if pf == float("inf") else f"{pf:.2f}"
        c = "green" if pnl_usd >= 0 else "red"
        wr_c = "green" if wr >= 40 else ("yellow" if wr >= 28.6 else "red")
        pair_tbl.add_row(
            pair,
            str(len(pts)),
            f"[green]{len(pw)}[/green]",
            f"[{wr_c}]{wr:.1f}%[/{wr_c}]",
            pf_str,
            f"[{c}]{exp:+.2f}p[/{c}]",
            f"[{c}]{pnl_pips:+.1f}p[/{c}]",
            f"[{c}]${pnl_usd:+,.2f}[/{c}]",
        )

    title = Text(f"⚡ {PROJECT_TITLE} — BACKTEST RESULTS", style="bold yellow")
    _console.print()
    _console.print(Panel(title, border_style="yellow", expand=False))
    _console.print(Columns([tbl, pair_tbl], equal=True, expand=True))
    _console.print()


def _log_split_report(report: BacktestReport, eur_usd_rate: float = 1.08) -> None:
    """Log IS/OOS comparison and degradation metrics."""
    sep = "=" * 58
    logger.info(sep)
    logger.info(f"{PROJECT_TITLE} — IN-SAMPLE / OUT-OF-SAMPLE REPORT")
    logger.info("-" * 58)

    is_s = report.in_sample
    oos_s = report.out_of_sample

    logger.info(f"  {'Metric':<22} {'IS':>10} {'OOS':>10} {'Degrad%':>10}")
    logger.info(f"  {'-' * 52}")
    logger.info(
        f"  {'Trades':<22} {is_s.total_trades:>10} {oos_s.total_trades:>10} {'':>10}"
    )
    logger.info(
        f"  {'Win rate':<22} {is_s.winrate:>9.1f}% {oos_s.winrate:>9.1f}% "
        f"{report.degradation.get('winrate', 0.0):>9.1f}%"
    )
    logger.info(
        f"  {'Profit factor':<22} {is_s.profit_factor:>10.2f} "
        f"{oos_s.profit_factor:>10.2f} "
        f"{report.degradation.get('profit_factor', 0.0):>9.1f}%"
    )
    logger.info(
        f"  {'Max drawdown':<22} {is_s.max_drawdown_pct:>9.2f}% "
        f"{oos_s.max_drawdown_pct:>9.2f}%"
    )
    logger.info(
        f"  {'Sharpe ratio':<22} {is_s.sharpe_ratio:>10.2f} "
        f"{oos_s.sharpe_ratio:>10.2f} "
        f"{report.degradation.get('sharpe_ratio', 0.0):>9.1f}%"
    )
    logger.info(
        f"  {'Expectancy (pips)':<22} {is_s.expectancy_pips:>+9.2f}p "
        f"{oos_s.expectancy_pips:>+9.2f}p"
    )
    logger.info(
        f"  {'P&L (pips)':<22} {is_s.total_pnl_pips:>+9.1f}p "
        f"{oos_s.total_pnl_pips:>+9.1f}p"
    )
    logger.info(
        f"  {'P&L (USD)':<22} ${is_s.total_pnl_usd:>+9.2f} "
        f"${oos_s.total_pnl_usd:>+9.2f}"
    )
    logger.info(
        f"  {'P&L (EUR)':<22} €{is_s.total_pnl_eur:>+9.2f} "
        f"€{oos_s.total_pnl_eur:>+9.2f}  [@ {eur_usd_rate:.4f}]"
    )
    logger.info(sep)

    # Warn if OOS degrades > 30% on any key metric
    # Skip degradation warnings when OOS sample is too small
    # to be statistically reliable
    _min_oos_trades = 15
    if report.out_of_sample.total_trades < _min_oos_trades:
        logger.warning(
            f"ALPHAEDGE: OOS sample too small "
            f"({report.out_of_sample.total_trades} trades)"
            f" — degradation metrics are unreliable (need ≥{_min_oos_trades})"
        )
    else:
        for metric, pct in report.degradation.items():
            if pct > 30.0:
                logger.warning(
                    f"ALPHAEDGE: OOS {metric} degraded {pct:.1f}%"
                    f" vs IS (threshold: 30%)"
                )
