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
import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from alphaedge.config.constants import (
    BASE_SLIPPAGE_PIPS,
    BASE_SPREAD_BY_PAIR,
    BASE_SPREAD_PIPS,
    DEFAULT_ATR_PERIOD,
    DEFAULT_MIN_ATR_RATIO,
    DEFAULT_MIN_RANGE_PIPS,
    DEFAULT_MIN_VOLUME_RATIO,
    DEFAULT_VOLUME_PERIOD,
    NEWS_SLIPPAGE_MULTIPLIER,
    NEWS_SPREAD_PIPS,
    NYSE_OPEN_SLIPPAGE_MULTIPLIER,
    NYSE_OPEN_SPREAD_PIPS,
    NYSE_OPEN_WINDOW_MINUTES,
    PIP_SIZES,
    PROJECT_TITLE,
    SESSION_END_HOUR,
    SESSION_END_MINUTE,
    SESSION_START_HOUR,
    SESSION_START_MINUTE,
    TF_M5,
)
from alphaedge.config.loader import AppConfig, load_config
from alphaedge.engine.backtest_export import export_results_csv, plot_equity_curve
from alphaedge.engine.backtest_stats import (
    _compute_max_drawdown,
    _compute_profit_factor,
    _compute_sharpe,
    _compute_winrate,
    _log_split_report,
    _log_stats_summary,
    compute_split_report,
    compute_stats,
    split_trades_is_oos,
)
from alphaedge.engine.backtest_types import BacktestReport, BacktestStats, TradeRecord
from alphaedge.engine.walk_forward import (
    WalkForwardReport,
    WalkForwardResult,
    WalkForwardWindow,
    _add_months,
    _filter_bars_by_date,
    _log_walk_forward_report,
    generate_wf_windows,
    run_walk_forward,
)
from alphaedge.utils.logger import get_logger, setup_logging
from alphaedge.utils.news_filter import EconomicNewsFilter

logger = get_logger()

# Re-export all public symbols for backward compatibility so that existing
# test imports such as ``from alphaedge.engine.backtest import compute_stats``
# continue to work without modification.
__all__ = [
    # --- data types (backtest_types) ---
    "TradeRecord",
    "BacktestStats",
    "BacktestReport",
    # --- statistics (backtest_stats) ---
    "compute_stats",
    "_compute_winrate",
    "_compute_profit_factor",
    "_compute_max_drawdown",
    "_compute_sharpe",
    "split_trades_is_oos",
    "compute_split_report",
    "_log_stats_summary",
    "_log_split_report",
    # --- export (backtest_export) ---
    "export_results_csv",
    "plot_equity_curve",
    # --- walk-forward (walk_forward) ---
    "WalkForwardWindow",
    "WalkForwardResult",
    "WalkForwardReport",
    "_add_months",
    "_filter_bars_by_date",
    "generate_wf_windows",
    "run_walk_forward",
    "_log_walk_forward_report",
]


# ------------------------------------------------------------------
# Variable slippage model
# ------------------------------------------------------------------
def compute_variable_slippage(
    bar_time: datetime | None,
    is_news: bool = False,
    pair: str = "EURUSD",
) -> float:
    """
    Compute variable slippage + spread cost based on market conditions.

    Parameters
    ----------
    bar_time : datetime | None
        Bar timestamp (timezone-aware, ET preferred).
    is_news : bool
        Whether a high-impact news event is active.
    pair : str
        Currency pair (e.g., 'EURUSD') used to look up per-pair base spread.

    Returns
    -------
    float
        Total spread+slippage cost in pips.
    """
    slippage = BASE_SLIPPAGE_PIPS
    base_spread = BASE_SPREAD_BY_PAIR.get(pair, BASE_SPREAD_PIPS)
    spread = base_spread

    # News events take priority (highest cost)
    if is_news:
        slippage = BASE_SLIPPAGE_PIPS * NEWS_SLIPPAGE_MULTIPLIER
        spread = NEWS_SPREAD_PIPS
    elif bar_time is not None:
        # NYSE open window: first N minutes after 9:30 ET
        et_hour = bar_time.hour
        et_minute = bar_time.minute
        if (
            et_hour == SESSION_START_HOUR
            and SESSION_START_MINUTE
            <= et_minute
            < SESSION_START_MINUTE + NYSE_OPEN_WINDOW_MINUTES
        ):
            slippage = BASE_SLIPPAGE_PIPS * NYSE_OPEN_SLIPPAGE_MULTIPLIER
            spread = NYSE_OPEN_SPREAD_PIPS

    return slippage + spread


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
    # pip_value for micro lot (1 000 units); for JPY pairs this is in JPY
    # — acceptable approximation for offline backtest without live FX rates
    pip_value = 1000.0 * pip_size
    trade.pnl_usd = trade.pnl_pips * pip_value
    return trade


# ------------------------------------------------------------------
# Group bars into per-day trading sessions
# ------------------------------------------------------------------
def _group_bars_by_session(
    m1_bars: list[dict[str, Any]],
    m5_bars: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Group M1 and M5 bars into per-day trading sessions.

    Returns a list of session dicts, each containing:
    - 'date': the ET trading date
    - 'm5_pre': M5 bars from before session start (last 6)
    - 'm1_indices': indices into m1_bars for session-window bars
    """
    et_tz = ZoneInfo("America/New_York")

    m5_by_date: dict[date, list[dict[str, Any]]] = defaultdict(list)
    for bar in m5_bars:
        dt_val = bar["datetime"]
        if dt_val.tzinfo is None:
            dt_val = dt_val.replace(tzinfo=ZoneInfo("UTC"))
        et_dt = dt_val.astimezone(et_tz)
        m5_by_date[et_dt.date()].append(bar)

    session_indices: dict[date, list[int]] = defaultdict(list)
    for idx, bar in enumerate(m1_bars):
        dt_val = bar["datetime"]
        if dt_val.tzinfo is None:
            dt_val = dt_val.replace(tzinfo=ZoneInfo("UTC"))
        et_dt = dt_val.astimezone(et_tz)
        sess_start = et_dt.replace(
            hour=SESSION_START_HOUR,
            minute=SESSION_START_MINUTE,
            second=0,
            microsecond=0,
        )
        sess_end = et_dt.replace(
            hour=SESSION_END_HOUR,
            minute=SESSION_END_MINUTE,
            second=0,
            microsecond=0,
        )
        if sess_start <= et_dt <= sess_end:
            session_indices[et_dt.date()].append(idx)

    result: list[dict[str, Any]] = []
    for day in sorted(session_indices.keys()):
        day_m5 = m5_by_date.get(day, [])
        sess_start_dt = datetime(
            day.year,
            day.month,
            day.day,
            SESSION_START_HOUR,
            SESSION_START_MINUTE,
            tzinfo=et_tz,
        )
        pre_m5 = [b for b in day_m5 if b["datetime"].astimezone(et_tz) < sess_start_dt][
            -6:
        ]

        result.append(
            {
                "date": day,
                "m5_pre": pre_m5,
                "m1_indices": session_indices[day],
            }
        )

    return result


# ------------------------------------------------------------------
# Main backtest runner
# ------------------------------------------------------------------
async def _fetch_pair_trades(
    hist_feed: Any,
    pair: str,
    config: AppConfig,
    start_dt: datetime,
    end_dt: datetime,
) -> list[TradeRecord]:
    """Fetch historical M1 and M5 bars for a pair and run backtest."""
    logger.info(f"ALPHAEDGE backtesting: {pair} ({start_dt.date()} → {end_dt.date()})")
    m1_bars = await hist_feed.fetch_bars_chunked(
        pair=pair,
        timeframe="1 min",
        start_dt=start_dt,
        end_dt=end_dt,
    )
    m5_bars = await hist_feed.fetch_bars_chunked(
        pair=pair,
        timeframe=TF_M5,
        start_dt=start_dt,
        end_dt=end_dt,
    )
    if not m1_bars:
        return []
    return _backtest_pair(pair, m1_bars, m5_bars, config)


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

    end_dt = datetime.now(tz=ZoneInfo("UTC"))
    start_dt = end_dt - timedelta(days=365 * config.trading.backtest_years)
    logger.info(
        f"ALPHAEDGE: Backtest range {start_dt.date()} → {end_dt.date()} "
        f"({config.trading.backtest_years} years, {len(config.trading.pairs)} pairs)"
    )

    for pair in config.trading.pairs:
        trades = await _fetch_pair_trades(hist_feed, pair, config, start_dt, end_dt)
        all_trades.extend(trades)

    await broker.disconnect()

    eur_usd_rate = config.trading.eur_usd_rate

    # Overall stats
    stats = compute_stats(all_trades, eur_usd_rate)
    export_results_csv(all_trades, stats, eur_usd_rate=eur_usd_rate)
    plot_equity_curve(all_trades)
    _log_stats_summary(stats, eur_usd_rate)
    _validate_with_vectorbt(all_trades, manual_sharpe=stats.sharpe_ratio)

    # IS/OOS split report
    if all_trades:
        report = compute_split_report(all_trades, eur_usd_rate=eur_usd_rate)
        _log_split_report(report, eur_usd_rate)

    return stats


# ------------------------------------------------------------------
# Backtest a single pair
# ------------------------------------------------------------------
def _detect_signal_at_bar(
    session_m1: list[dict[str, Any]],
    local_index: int,
    pip_size: float,
    config: AppConfig,
    eng_mod: Any,
    fcr_result: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Detect engulfing signal at a session bar using pre-calculated FCR.

    FCR and gap are computed once per session (no look-ahead bias).
    Only engulfing detection runs per-bar.
    """
    m1_recent = session_m1[max(0, local_index - 3) : local_index + 1]

    result: dict[str, Any] | None = eng_mod.detect_engulfing(
        candles_data=m1_recent,
        fcr_high=fcr_result["range_high"],
        fcr_low=fcr_result["range_low"],
        rr_ratio=config.trading.rr_ratio,
        pip_size=pip_size,
        volume_period=DEFAULT_VOLUME_PERIOD,
        min_volume_ratio=DEFAULT_MIN_VOLUME_RATIO,
        min_body_ratio=config.trading.min_body_ratio,
        max_wick_ratio=config.trading.max_wick_ratio,
    )
    if result and result.get("detected"):
        return result
    return None


def _build_trade_record(
    pair: str,
    signal: dict[str, Any],
    bars: list[dict[str, Any]],
    bar_index: int,
) -> TradeRecord:
    """Create a TradeRecord from a detected signal and simulate exit."""
    bar_time = bars[bar_index].get("datetime")
    spread_cost = compute_variable_slippage(bar_time, pair=pair)
    trade = TradeRecord(
        pair=pair,
        direction=signal["signal"],
        entry_price=signal["entry_price"],
        stop_loss=signal["stop_loss"],
        take_profit=signal["take_profit"],
        entry_time=bar_time if bar_time is not None else datetime.now(),
        spread_cost_pips=spread_cost,
    )
    return _simulate_trade_exit(trade, bars, bar_index)


def _backtest_pair(
    pair: str,
    m1_bars: list[dict[str, Any]],
    m5_bars: list[dict[str, Any]],
    config: AppConfig,
    news_filter: EconomicNewsFilter | None = None,
) -> list[TradeRecord]:
    """
    Run the strategy logic on historical bars for one pair.

    Mirrors the live flow: FCR once per session from pre-session M5,
    gap/ATR once from first M1 bars, then engulfing on remaining M1.
    """
    trades: list[TradeRecord] = []
    pip_size = PIP_SIZES.get(pair, 0.0001)

    try:
        from alphaedge.core import (
            engulfing_detector,
            fcr_detector,
            gap_detector,
        )
    except ImportError:
        logger.warning(f"ALPHAEDGE: Cython not compiled — skipping backtest for {pair}")
        return trades

    sessions = _group_bars_by_session(m1_bars, m5_bars)

    for session in sessions:
        m5_pre = session["m5_pre"]
        m1_idx = session["m1_indices"]

        if len(m5_pre) < 2 or len(m1_idx) < 4:
            continue

        # Step 1: FCR detection on pre-session M5 bars (once per session)
        fcr_result = fcr_detector.detect_fcr(
            candles_data=m5_pre,
            min_range_pips=DEFAULT_MIN_RANGE_PIPS,
            pip_size=pip_size,
        )
        if not fcr_result:
            continue

        # Step 2: Gap/ATR detection on first 3 session M1 bars (once)
        first_3_m1 = [m1_bars[i] for i in m1_idx[:3]]
        pre_close = m5_pre[-1]["close"]
        session_open = m1_bars[m1_idx[0]]["open"]
        gap_result = gap_detector.detect_gap(
            pre_session_m1=m5_pre,
            session_m1=first_3_m1,
            pre_close=pre_close,
            session_open=session_open,
            atr_period=DEFAULT_ATR_PERIOD,
            min_atr_ratio=DEFAULT_MIN_ATR_RATIO,
        )
        if not gap_result or not gap_result.get("detected"):
            continue

        # Step 3: Engulfing detection on remaining session M1 bars
        session_m1 = [m1_bars[i] for i in m1_idx]
        for local_i in range(3, len(session_m1)):
            # Skip signal if we're in a news blackout window
            if news_filter is not None:
                bar_dt = session_m1[local_i].get("datetime")
                if bar_dt is not None and news_filter.is_news_blackout(bar_dt, pair):
                    continue
            signal = _detect_signal_at_bar(
                session_m1,
                local_i,
                pip_size,
                config,
                engulfing_detector,
                fcr_result,
            )
            if not signal:
                continue
            global_idx = m1_idx[local_i]
            trades.append(_build_trade_record(pair, signal, m1_bars, global_idx))

    return trades


# ------------------------------------------------------------------
# Validate results with vectorbt
# ------------------------------------------------------------------
def _validate_with_vectorbt(
    trades: list[TradeRecord],
    manual_sharpe: float = 0.0,
    starting_equity: float = 10000.0,
) -> None:
    """
    Cross-validate backtest Sharpe using vectorbt with percentage returns.

    Parameters
    ----------
    trades : list[TradeRecord]
        Completed trades.
    manual_sharpe : float
        The Sharpe ratio computed by ``_compute_sharpe`` for comparison.
    starting_equity : float
        Initial equity for computing percentage returns.
    """
    if not trades:
        return

    # Build percentage returns from running equity
    equity = starting_equity
    pct_returns: list[float] = []
    for t in trades:
        if equity > 0:
            pct_returns.append(t.pnl_usd / equity)
        else:
            pct_returns.append(0.0)
        equity += t.pnl_usd

    return_series = pd.Series(pct_returns)
    vbt_accessor = getattr(return_series, "vbt")  # vectorbt accessor
    vbt_sharpe: float = vbt_accessor.returns.sharpe_ratio()

    logger.info(
        f"ALPHAEDGE vectorbt validation — "
        f"Sharpe (vbt): {vbt_sharpe:.2f}, "
        f"Sharpe (manual): {manual_sharpe:.2f}, "
        f"Total PnL: {sum(t.pnl_pips for t in trades):.1f} pips"
    )

    # Compare: warn if divergence > 5%
    if manual_sharpe != 0.0:
        divergence = abs(vbt_sharpe - manual_sharpe) / abs(manual_sharpe) * 100.0
        if divergence > 5.0:
            logger.warning(
                f"ALPHAEDGE: Sharpe divergence {divergence:.1f}% "
                f"(vbt={vbt_sharpe:.2f} vs manual={manual_sharpe:.2f})"
            )


# ------------------------------------------------------------------
# Random baseline benchmark
# ------------------------------------------------------------------
@dataclass
class RandomBaselineReport:
    """Results of random baseline comparison."""

    n_simulations: int = 0
    strategy_pf: float = 0.0
    baseline_pf_mean: float = 0.0
    baseline_pf_95th: float = 0.0
    p_value: float = 1.0
    baseline_pfs: list[float] = field(default_factory=list)


def _generate_random_trades(
    m1_bars: list[dict[str, Any]],
    pair: str,
    n_trades: int,
    rr_ratio: float = 3.0,
    sl_pips: float = 10.0,
    rng: random.Random | None = None,
) -> list[TradeRecord]:
    """
    Generate random entry trades on real M1 bars.

    Parameters
    ----------
    m1_bars : list[dict]
        Real M1 bar data.
    pair : str
        Currency pair.
    n_trades : int
        Number of random trades to generate.
    rr_ratio : float
        Risk-reward ratio for TP distance.
    sl_pips : float
        Stop-loss distance in pips.
    rng : random.Random | None
        Random number generator (for reproducibility).

    Returns
    -------
    list[TradeRecord]
        Simulated random trades.
    """
    if rng is None:
        rng = random.Random()

    if len(m1_bars) < 20:
        return []

    pip_size = PIP_SIZES.get(pair, 0.0001)
    sl_price_dist = sl_pips * pip_size
    tp_price_dist = sl_price_dist * rr_ratio
    trades: list[TradeRecord] = []

    # Avoid entries near the end of data (need room for exit)
    max_entry_idx = len(m1_bars) - 10

    for _ in range(n_trades):
        bar_idx = rng.randint(5, max_entry_idx)
        direction = rng.choice([1, -1])
        entry_price = m1_bars[bar_idx]["close"]

        if direction == 1:  # Long
            stop_loss = entry_price - sl_price_dist
            take_profit = entry_price + tp_price_dist
        else:  # Short
            stop_loss = entry_price + sl_price_dist
            take_profit = entry_price - tp_price_dist

        bar_time = m1_bars[bar_idx].get("datetime")
        spread_cost = compute_variable_slippage(bar_time)
        trade = TradeRecord(
            pair=pair,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            entry_time=bar_time if bar_time is not None else datetime.now(),
            spread_cost_pips=spread_cost,
        )
        trade = _simulate_trade_exit(trade, m1_bars, bar_idx)
        trades.append(trade)

    return trades


def run_random_baseline(
    m1_bars: list[dict[str, Any]],
    pair: str,
    strategy_trades: list[TradeRecord],
    n_simulations: int = 1000,
    rr_ratio: float = 3.0,
    sl_pips: float = 10.0,
    seed: int | None = None,
) -> RandomBaselineReport:
    """
    Compare strategy against random entry baseline.

    Parameters
    ----------
    m1_bars : list[dict]
        Real M1 bar data.
    pair : str
        Currency pair.
    strategy_trades : list[TradeRecord]
        Actual strategy trades for comparison.
    n_simulations : int
        Number of random simulations (default 1000).
    rr_ratio : float
        Risk-reward ratio for random entries.
    sl_pips : float
        Stop-loss distance in pips for random entries.
    seed : int | None
        Random seed for reproducibility.

    Returns
    -------
    RandomBaselineReport
        Comparison report with p-value.
    """
    strategy_stats = compute_stats(strategy_trades)
    n_trades = max(len(strategy_trades), 10)

    rng = random.Random(seed)
    baseline_pfs: list[float] = []

    for _ in range(n_simulations):
        rand_trades = _generate_random_trades(
            m1_bars, pair, n_trades, rr_ratio, sl_pips, rng
        )
        rand_stats = compute_stats(rand_trades)
        baseline_pfs.append(rand_stats.profit_factor)

    if not baseline_pfs:
        return RandomBaselineReport()

    baseline_pfs_sorted = sorted(baseline_pfs)
    baseline_mean = float(np.mean(baseline_pfs))
    idx_95 = int(len(baseline_pfs_sorted) * 0.95)
    baseline_95th = baseline_pfs_sorted[min(idx_95, len(baseline_pfs_sorted) - 1)]

    # p-value: proportion of random runs with PF >= strategy PF
    beats = sum(1 for pf in baseline_pfs if pf >= strategy_stats.profit_factor)
    p_value = beats / len(baseline_pfs)

    report = RandomBaselineReport(
        n_simulations=n_simulations,
        strategy_pf=strategy_stats.profit_factor,
        baseline_pf_mean=baseline_mean,
        baseline_pf_95th=baseline_95th,
        p_value=p_value,
        baseline_pfs=baseline_pfs,
    )

    _log_random_baseline_report(report)
    return report


def _log_random_baseline_report(report: RandomBaselineReport) -> None:
    """Log random baseline comparison results."""
    logger.info("=" * 50)
    logger.info(f"{PROJECT_TITLE} — RANDOM BASELINE BENCHMARK")
    logger.info(f"  Simulations:       {report.n_simulations}")
    logger.info(f"  Strategy PF:       {report.strategy_pf:.2f}")
    logger.info(f"  Baseline mean PF:  {report.baseline_pf_mean:.2f}")
    logger.info(f"  Baseline 95th PF:  {report.baseline_pf_95th:.2f}")
    logger.info(f"  p-value:           {report.p_value:.4f}")
    logger.info("=" * 50)

    if report.p_value < 0.05:
        logger.info(
            "ALPHAEDGE: Strategy SIGNIFICANTLY better than random "
            f"(p={report.p_value:.4f} < 0.05)"
        )
    else:
        logger.warning(
            f"ALPHAEDGE: Strategy NOT significant vs random (p={report.p_value:.4f})"
        )

    if report.strategy_pf > report.baseline_pf_95th:
        logger.info(
            f"ALPHAEDGE: Strategy PF ({report.strategy_pf:.2f}) > "
            f"baseline 95th percentile ({report.baseline_pf_95th:.2f})"
        )
    else:
        logger.warning(
            f"ALPHAEDGE: Strategy PF ({report.strategy_pf:.2f}) <= "
            f"baseline 95th percentile ({report.baseline_pf_95th:.2f})"
        )


if __name__ == "__main__":
    setup_logging()
    try:
        config = load_config()
    except FileNotFoundError:
        logger.warning("ALPHAEDGE: config.yaml not found — using defaults")
        config = AppConfig()

    asyncio.run(run_backtest(config))
