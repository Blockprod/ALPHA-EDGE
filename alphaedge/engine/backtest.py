# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/engine/backtest.py
# DESCRIPTION  : Backtesting engine with vectorbt and IB data
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: historical backtesting engine."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from alphaedge.config.constants import (
    DEFAULT_MIN_RANGE_PIPS,
    DEFAULT_MIN_VOLUME_RATIO,
    DEFAULT_SLIPPAGE_PIPS,
    DEFAULT_VOLUME_PERIOD,
    PIP_SIZES,
    PROJECT_TITLE,
)
from alphaedge.config.loader import AppConfig, load_config
from alphaedge.utils.logger import get_logger, setup_logging

matplotlib.use("Agg")  # Non-interactive backend

logger = get_logger()


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


# ------------------------------------------------------------------
# Backtest statistics
# ------------------------------------------------------------------
@dataclass
class BacktestStats:
    """Aggregate backtest performance statistics."""

    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    winrate: float = 0.0
    profit_factor: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    total_pnl_pips: float = 0.0
    total_pnl_usd: float = 0.0
    avg_rr_achieved: float = 0.0


# ------------------------------------------------------------------
# Simulate a single trade to its exit
# ------------------------------------------------------------------
def _simulate_trade_exit(
    trade: TradeRecord,
    bars: list[dict[str, Any]],
    entry_bar_idx: int,
) -> TradeRecord:
    """
    Walk forward through bars to find the trade exit.

    Parameters
    ----------
    trade : TradeRecord
        The trade to simulate.
    bars : list[dict]
        M1 bar data.
    entry_bar_idx : int
        Index of the entry bar.

    Returns
    -------
    TradeRecord
        The trade with exit fields populated.
    """
    for i in range(entry_bar_idx + 1, len(bars)):
        bar = bars[i]
        hit_sl, hit_tp = _check_sl_tp_hit(trade, bar)

        if hit_sl and hit_tp:
            # Both hit — use bar direction to decide which was hit first
            if _sl_hit_first(trade, bar):
                return _close_trade(trade, trade.stop_loss, bar, "loss")
            return _close_trade(trade, trade.take_profit, bar, "win")
        if hit_sl:
            return _close_trade(trade, trade.stop_loss, bar, "loss")
        if hit_tp:
            return _close_trade(trade, trade.take_profit, bar, "win")

    # No exit triggered — close at last bar
    return _close_trade(trade, bars[-1]["close"], bars[-1], "timeout")


# ------------------------------------------------------------------
# Check if SL or TP was hit on a bar
# ------------------------------------------------------------------
def _check_sl_tp_hit(
    trade: TradeRecord,
    bar: dict[str, Any],
) -> tuple[bool, bool]:
    """
    Check whether the bar's high/low hit SL or TP.

    Returns
    -------
    tuple[bool, bool]
        (sl_hit, tp_hit).
    """
    if trade.direction == 1:  # Long
        sl_hit = bar["low"] <= trade.stop_loss
        tp_hit = bar["high"] >= trade.take_profit
    else:  # Short
        sl_hit = bar["high"] >= trade.stop_loss
        tp_hit = bar["low"] <= trade.take_profit

    return sl_hit, tp_hit


# ------------------------------------------------------------------
# Determine SL/TP priority when both hit on same bar
# ------------------------------------------------------------------
def _sl_hit_first(
    trade: TradeRecord,
    bar: dict[str, Any],
) -> bool:
    """
    Use bar direction to estimate which level was hit first.

    If the bar moves against the trade direction first (bearish bar for
    a long, bullish bar for a short), assume SL was hit first.
    """
    bar_is_bearish: bool = bar["close"] < bar["open"]
    if trade.direction == 1:  # Long
        return bar_is_bearish  # bearish bar → low hit first → SL
    return not bar_is_bearish  # bullish bar → high hit first → SL


# ------------------------------------------------------------------
# Close a trade with exit details
# ------------------------------------------------------------------
def _close_trade(
    trade: TradeRecord,
    exit_price: float,
    bar: dict[str, Any],
    outcome: str,
) -> TradeRecord:
    """
    Populate exit fields on a trade record.

    Parameters
    ----------
    trade : TradeRecord
        The open trade.
    exit_price : float
        Price at which the trade exited.
    bar : dict
        The bar at exit.
    outcome : str
        'win', 'loss', or 'timeout'.

    Returns
    -------
    TradeRecord
        Updated trade record.
    """
    pip_size = PIP_SIZES.get(trade.pair, 0.0001)
    trade.exit_price = exit_price
    trade.exit_time = bar.get("datetime")
    trade.outcome = outcome

    # P&L in pips (accounting for spread cost)
    raw_pnl = (exit_price - trade.entry_price) * trade.direction
    trade.pnl_pips = (raw_pnl / pip_size) - trade.spread_cost_pips
    trade.pnl_usd = trade.pnl_pips * 10.0  # Approximate for micro lot
    return trade


# ------------------------------------------------------------------
# Compute aggregate statistics from trade list
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
# Winrate calculation
# ------------------------------------------------------------------
def _compute_winrate(wins: int, total: int) -> float:
    """Calculate win rate as percentage."""
    if total == 0:
        return 0.0
    return (wins / total) * 100.0


# ------------------------------------------------------------------
# Profit factor calculation
# ------------------------------------------------------------------
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


# ------------------------------------------------------------------
# Maximum drawdown calculation
# ------------------------------------------------------------------
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
        if equity > peak:
            peak = equity
        drawdown = ((peak - equity) / peak) * 100.0
        if drawdown > max_dd:
            max_dd = drawdown

    return max_dd


# ------------------------------------------------------------------
# Sharpe ratio calculation
# ------------------------------------------------------------------
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
# Export backtest results to CSV
# ------------------------------------------------------------------
def export_results_csv(
    trades: list[TradeRecord],
    stats: BacktestStats,
    output_path: str = "ALPHAEDGE_backtest_results.csv",
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
                "outcome": t.outcome,
                "entry_time": t.entry_time,
                "exit_time": t.exit_time,
            }
        )

    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    logger.info(f"ALPHAEDGE backtest results exported to {output_path}")


# ------------------------------------------------------------------
# Plot equity curve
# ------------------------------------------------------------------
def plot_equity_curve(
    trades: list[TradeRecord],
    output_path: str = "ALPHAEDGE_equity_curve.png",
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
        equity_values,
        alpha=0.1,
    )
    ax.set_title(f"{PROJECT_TITLE} — Equity Curve")
    ax.set_xlabel("Trade #")
    ax.set_ylabel("Equity ($)")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    logger.info(f"ALPHAEDGE equity curve saved to {output_path}")


# ------------------------------------------------------------------
# Main backtest runner
# ------------------------------------------------------------------
async def _fetch_pair_trades(
    hist_feed: Any,
    pair: str,
    config: AppConfig,
) -> list[TradeRecord]:
    """Fetch historical bars for a pair and run backtest logic."""
    logger.info(f"ALPHAEDGE backtesting: {pair}")
    bars = await hist_feed.fetch_bars(
        pair=pair,
        timeframe="1 min",
        duration="30 D",
    )
    if not bars:
        return []
    return _backtest_pair(pair, bars, config)


async def run_backtest(config: AppConfig) -> BacktestStats:
    """Run the strategy backtest using IB historical data."""
    logger.info(f"{PROJECT_TITLE} — Backtest starting")

    from alphaedge.engine.broker import BrokerConnection
    from alphaedge.engine.data_feed import HistoricalDataFeed

    broker = BrokerConnection(config.ib)
    if not await broker.connect():
        logger.error("ALPHAEDGE: Cannot backtest — IB Gateway unavailable")
        return BacktestStats()

    hist_feed = HistoricalDataFeed(broker)
    all_trades: list[TradeRecord] = []

    for pair in config.trading.pairs:
        trades = await _fetch_pair_trades(hist_feed, pair, config)
        all_trades.extend(trades)

    await broker.disconnect()

    stats = compute_stats(all_trades)
    export_results_csv(all_trades, stats)
    plot_equity_curve(all_trades)
    _log_stats_summary(stats)
    _validate_with_vectorbt(all_trades)
    return stats


# ------------------------------------------------------------------
# Backtest a single pair
# ------------------------------------------------------------------
def _detect_signal_at_bar(
    bars: list[dict[str, Any]],
    index: int,
    pip_size: float,
    config: AppConfig,
    fcr_mod: Any,
    eng_mod: Any,
) -> dict[str, Any] | None:
    """
    Detect FCR + engulfing signal at a single bar index.

    Returns signal dict if detected, None otherwise.
    """
    m5_equivalent = bars[max(0, index - 10) : index - 2]
    m1_recent = bars[max(0, index - 3) : index + 1]

    # FCR detection on M5-equivalent bars
    fcr = fcr_mod.detect_fcr(
        candles_data=m5_equivalent,
        min_range_pips=DEFAULT_MIN_RANGE_PIPS,
        pip_size=pip_size,
    )
    if not fcr:
        return None

    # Engulfing detection on M1 bars
    signal = eng_mod.detect_engulfing(
        candles_data=m1_recent,
        fcr_high=fcr["range_high"],
        fcr_low=fcr["range_low"],
        rr_ratio=config.trading.rr_ratio,
        pip_size=pip_size,
        volume_period=DEFAULT_VOLUME_PERIOD,
        min_volume_ratio=DEFAULT_MIN_VOLUME_RATIO,
    )
    if signal and signal.get("detected"):
        return signal  # type: ignore[no-any-return]
    return None


def _build_trade_record(
    pair: str,
    signal: dict[str, Any],
    bars: list[dict[str, Any]],
    bar_index: int,
) -> TradeRecord:
    """Create a TradeRecord from a detected signal and simulate exit."""
    trade = TradeRecord(
        pair=pair,
        direction=signal["signal"],
        entry_price=signal["entry_price"],
        stop_loss=signal["stop_loss"],
        take_profit=signal["take_profit"],
        entry_time=bars[bar_index].get("datetime", datetime.now()),
        spread_cost_pips=DEFAULT_SLIPPAGE_PIPS,
    )
    return _simulate_trade_exit(trade, bars, bar_index)


def _backtest_pair(
    pair: str,
    bars: list[dict[str, Any]],
    config: AppConfig,
) -> list[TradeRecord]:
    """Run the strategy logic on historical bars for one pair."""
    trades: list[TradeRecord] = []
    pip_size = PIP_SIZES.get(pair, 0.0001)

    try:
        from alphaedge.core import (  # type: ignore[attr-defined]
            engulfing_detector,
            fcr_detector,
        )
    except ImportError:
        logger.warning(
            f"ALPHAEDGE: Cython not compiled — " f"skipping backtest for {pair}"
        )
        return trades

    window_size = 60
    for i in range(window_size, len(bars)):
        signal = _detect_signal_at_bar(
            bars,
            i,
            pip_size,
            config,
            fcr_detector,
            engulfing_detector,
        )
        if not signal:
            continue
        trades.append(_build_trade_record(pair, signal, bars, i))

    return trades


# ------------------------------------------------------------------
# Validate results with vectorbt
# ------------------------------------------------------------------
def _validate_with_vectorbt(trades: list[TradeRecord]) -> None:
    """Cross-validate backtest PnL using vectorbt Portfolio."""
    if not trades:
        return

    pnl_series = pd.Series([t.pnl_pips for t in trades])

    vbt_sharpe = pnl_series.vbt.returns.sharpe_ratio()  # type: ignore[attr-defined]
    logger.info(
        f"ALPHAEDGE vectorbt validation — "
        f"Sharpe: {vbt_sharpe:.2f}, "
        f"Total PnL: {pnl_series.sum():.1f} pips"
    )


# ------------------------------------------------------------------
# Log statistics summary
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


if __name__ == "__main__":
    setup_logging()
    try:
        config = load_config()
    except FileNotFoundError:
        logger.warning("ALPHAEDGE: config.yaml not found — using defaults")
        config = AppConfig()

    asyncio.run(run_backtest(config))
