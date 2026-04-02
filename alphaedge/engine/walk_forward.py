# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/engine/walk_forward.py
# DESCRIPTION  : Walk-forward optimization framework
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-09
# ============================================================
"""Walk-forward optimization framework for ALPHAEDGE backtesting."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from alphaedge.config.constants import PROJECT_TITLE
from alphaedge.config.loader import AppConfig
from alphaedge.engine.backtest_stats import compute_stats
from alphaedge.engine.backtest_types import BacktestStats, TradeRecord
from alphaedge.utils.logger import get_logger

logger = get_logger()


# ------------------------------------------------------------------
# Walk-Forward Optimization data types
# ------------------------------------------------------------------
@dataclass
class WalkForwardWindow:
    """A single walk-forward train/test window."""

    train_start: date
    train_end: date
    test_start: date
    test_end: date


@dataclass
class WalkForwardResult:
    """Results for one walk-forward iteration."""

    window: WalkForwardWindow
    train_stats: BacktestStats
    test_stats: BacktestStats
    # Set when run_walk_forward is called with an optimize_fn
    optimized_test_stats: BacktestStats | None = None
    best_params: dict[str, float] = field(default_factory=dict)


@dataclass
class WalkForwardReport:
    """Aggregated walk-forward optimization report."""

    windows: list[WalkForwardResult] = field(default_factory=list)
    aggregated_oos: BacktestStats = field(default_factory=BacktestStats)
    # Populated only when optimize_fn is provided
    aggregated_oos_optimized: BacktestStats = field(default_factory=BacktestStats)


def _add_months(d: date, months: int) -> date:
    """Add months to a date, clamping to last day of month."""
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    import calendar

    max_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, max_day))


def generate_wf_windows(
    start_date: date,
    end_date: date,
    train_months: int = 3,
    test_months: int = 1,
    step_months: int = 1,
) -> list[WalkForwardWindow]:
    """
    Generate rolling walk-forward windows.

    Parameters
    ----------
    start_date : date
        First date of available data.
    end_date : date
        Last date of available data.
    train_months : int
        Length of training window in months.
    test_months : int
        Length of test window in months.
    step_months : int
        Slide step in months.

    Returns
    -------
    list[WalkForwardWindow]
        List of non-overlapping test windows.
    """
    windows: list[WalkForwardWindow] = []
    cursor = start_date

    while True:
        train_start = cursor
        train_end = _add_months(cursor, train_months) - timedelta(days=1)
        test_start = _add_months(cursor, train_months)
        test_end = _add_months(test_start, test_months) - timedelta(days=1)

        if test_end > end_date:
            break

        windows.append(
            WalkForwardWindow(
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
            )
        )
        cursor = _add_months(cursor, step_months)

    return windows


def _filter_bars_by_date(
    bars: list[dict[str, Any]],
    start_date: date,
    end_date: date,
) -> list[dict[str, Any]]:
    """Filter bars to those whose datetime falls within [start_date, end_date]."""
    et_tz = ZoneInfo("America/New_York")
    filtered: list[dict[str, Any]] = []
    for bar in bars:
        dt_val = bar["datetime"]
        if dt_val.tzinfo is None:
            dt_val = dt_val.replace(tzinfo=ZoneInfo("UTC"))
        bar_date = dt_val.astimezone(et_tz).date()
        if start_date <= bar_date <= end_date:
            filtered.append(bar)
    return filtered


def _extract_data_range(bars: list[dict[str, Any]]) -> tuple[date, date] | None:
    """Return the first and last dates represented by the bar data."""
    et_tz = ZoneInfo("America/New_York")
    all_dates: list[date] = []
    for bar in bars:
        dt_val = bar["datetime"]
        if dt_val.tzinfo is None:
            dt_val = dt_val.replace(tzinfo=ZoneInfo("UTC"))
        all_dates.append(dt_val.astimezone(et_tz).date())

    if not all_dates:
        return None

    return min(all_dates), max(all_dates)


def _run_window_backtests(
    wf_win: WalkForwardWindow,
    daily_bars: list[dict[str, Any]],
    pair: str,
    config: AppConfig,
) -> tuple[list[TradeRecord], list[TradeRecord]]:
    """Run baseline IS/OOS backtests for one walk-forward window.

    The OOS run uses the full [train_start, test_end] bar window so that the
    EMA / ADX indicators have their full lookback warmup before the OOS period
    starts.  Only trades whose entry falls inside [test_start, test_end] (in
    ET timezone) are counted as OOS results.
    """
    from alphaedge.engine.backtest import _backtest_pair  # noqa: PLC0415

    et_tz = ZoneInfo("America/New_York")

    # IS run — train-only bars (IS stats, no future leakage)
    train_bars = _filter_bars_by_date(daily_bars, wf_win.train_start, wf_win.train_end)
    train_trades = _backtest_pair(pair, train_bars, config)[0]

    # OOS run — combined [train_start, test_end] for EMA warmup; keep only
    # trades that entered on or after test_start (ET date).
    combined_bars = _filter_bars_by_date(
        daily_bars, wf_win.train_start, wf_win.test_end
    )
    combined_trades = _backtest_pair(pair, combined_bars, config)[0]

    def _et_entry_date(t: TradeRecord) -> date:
        dt = t.entry_time
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        return dt.astimezone(et_tz).date()

    test_trades = [t for t in combined_trades if _et_entry_date(t) >= wf_win.test_start]
    return train_trades, test_trades


def _run_optimized_oos_fold(
    wf_win: WalkForwardWindow,
    daily_bars: list[dict[str, Any]],
    pair: str,
    config: AppConfig,
    optimize_fn: Any | None,
) -> tuple[BacktestStats | None, dict[str, float], list[TradeRecord]]:
    """Run optional IS optimisation and return OOS optimised trades."""
    if optimize_fn is None:
        return None, {}, []

    from alphaedge.engine.sensitivity import _run_with_params_trades  # noqa: PLC0415

    train_bars = _filter_bars_by_date(daily_bars, wf_win.train_start, wf_win.train_end)
    test_bars = _filter_bars_by_date(daily_bars, wf_win.test_start, wf_win.test_end)

    best_params = optimize_fn(train_bars, pair, config)
    opt_trades = _run_with_params_trades(test_bars, pair, config, best_params)
    for trade in opt_trades:
        trade.sample_type = "OOS_OPT"
    return compute_stats(opt_trades), best_params, opt_trades


def run_walk_forward(  # pylint: disable=too-many-locals
    daily_bars: list[dict[str, Any]],
    pair: str,
    config: AppConfig,
    train_months: int = 3,
    test_months: int = 1,
    step_months: int = 1,
    optimize_fn: Any | None = None,
) -> WalkForwardReport:
    """
    Run walk-forward optimization on pre-fetched Daily bars.

    For each window:
    - Train: backtest on the training period (parameters from config)
    - Test: backtest on the test period with same parameters
    - If ``optimize_fn`` is provided, also grid-search the IS period and
      apply the best params to the OOS period for comparison

    Parameters
    ----------
    daily_bars : list[dict]
        All Daily bars for the pair.
    pair : str
        Currency pair name.
    config : AppConfig
        Strategy configuration.
    train_months : int
        Training window in months.
    test_months : int
        Test window in months.
    step_months : int
        Slide step in months.
    optimize_fn : callable | None
        Optional ``(daily_bars, pair, config) -> dict[str, float]``
        that returns parameter overrides found from IS grid-search.
        When provided, each window's OOS fold is also run with those params
        and the results are stored in ``WalkForwardResult.optimized_test_stats``.

    Returns
    -------
    WalkForwardReport
        Report with per-window results and aggregated OOS stats.
        ``aggregated_oos_optimized`` is populated only when ``optimize_fn``
        is not None.
    """
    data_range = _extract_data_range(daily_bars)
    if data_range is None:
        return WalkForwardReport()

    data_start, data_end = data_range

    windows = generate_wf_windows(
        data_start, data_end, train_months, test_months, step_months
    )

    if not windows:
        logger.warning(
            "ALPHAEDGE walk-forward: %s — no windows generated "
            "(data range %s → %s too short for train=%d + test=%d months). "
            "Need N >= 100 trades before activating walk-forward.",
            pair,
            data_start,
            data_end,
            train_months,
            test_months,
        )
        return WalkForwardReport()

    report = WalkForwardReport()
    all_test_trades: list[TradeRecord] = []
    all_optimized_test_trades: list[TradeRecord] = []

    for wf_win in windows:
        train_trades, test_trades = _run_window_backtests(
            wf_win,
            daily_bars,
            pair,
            config,
        )

        train_stats = compute_stats(train_trades)
        test_stats = compute_stats(test_trades)

        # Tag test trades as OOS (flat-param baseline)
        for t in test_trades:
            t.sample_type = "OOS"

        all_test_trades.extend(test_trades)

        optimized_test_stats, best_params, opt_trades = _run_optimized_oos_fold(
            wf_win,
            daily_bars,
            pair,
            config,
            optimize_fn,
        )
        all_optimized_test_trades.extend(opt_trades)

        report.windows.append(
            WalkForwardResult(
                window=wf_win,
                train_stats=train_stats,
                test_stats=test_stats,
                optimized_test_stats=optimized_test_stats,
                best_params=best_params,
            )
        )

    report.aggregated_oos = compute_stats(all_test_trades)
    if optimize_fn is not None:
        report.aggregated_oos_optimized = compute_stats(all_optimized_test_trades)
    return report


def _log_walk_forward_report(report: WalkForwardReport) -> None:
    """Log walk-forward optimization results."""
    logger.info("=" * 60)
    logger.info(f"{PROJECT_TITLE} — WALK-FORWARD REPORT")
    logger.info("-" * 60)
    logger.info(
        f"  {'Window':<8} {'Train':>12} {'Test':>12} "
        f"{'Trn PF':>8} {'Tst PF':>8} {'Tst WR':>8}"
        + (
            " {'Opt PF':>8} {'Opt WR':>8}"
            if any(wr.optimized_test_stats for wr in report.windows)
            else ""
        )
    )
    logger.info(f"  {'-' * 56}")

    has_opt = any(wr.optimized_test_stats is not None for wr in report.windows)
    for i, wr in enumerate(report.windows, 1):
        w = wr.window
        line = (
            f"  {i:<8} "
            f"{w.train_start.isoformat()[:7]:>12} "
            f"{w.test_start.isoformat()[:7]:>12} "
            f"{wr.train_stats.profit_factor:>8.2f} "
            f"{wr.test_stats.profit_factor:>8.2f} "
            f"{wr.test_stats.winrate:>7.1f}%"
        )
        if has_opt and wr.optimized_test_stats is not None:
            line += (
                f" {wr.optimized_test_stats.profit_factor:>8.2f}"
                f" {wr.optimized_test_stats.winrate:>7.1f}%"
            )
        logger.info(line)

    logger.info("-" * 60)
    agg = report.aggregated_oos
    logger.info(f"  Aggregated OOS — {agg.total_trades} trades")
    logger.info(f"  Profit factor:  {agg.profit_factor:.2f}")
    logger.info(f"  Sharpe ratio:   {agg.sharpe_ratio:.2f}")
    logger.info(f"  Win rate:       {agg.winrate:.1f}%")
    logger.info(f"  Total P&L:      {agg.total_pnl_pips:.1f} pips")

    if has_opt:
        opt = report.aggregated_oos_optimized
        logger.info("-" * 60)
        logger.info(f"  Optimised OOS  — {opt.total_trades} trades")
        logger.info(f"  Profit factor:  {opt.profit_factor:.2f}")
        logger.info(f"  Sharpe ratio:   {opt.sharpe_ratio:.2f}")
        logger.info(f"  Win rate:       {opt.winrate:.1f}%")
        logger.info(f"  Total P&L:      {opt.total_pnl_pips:.1f} pips")
        if agg.profit_factor > 0:
            pf_change = (
                (opt.profit_factor - agg.profit_factor) / agg.profit_factor * 100.0
            )
            sign = "+" if pf_change >= 0 else ""
            logger.info(f"  IS optimisation vs flat: PF {sign}{pf_change:.1f}%")

    logger.info("=" * 60)

    # Warn if thresholds not met
    if agg.profit_factor < 1.0:
        logger.warning(
            f"ALPHAEDGE: WF aggregated OOS profit factor {agg.profit_factor:.2f} < 1.0"
        )
    if agg.sharpe_ratio < 0.5:
        logger.warning(
            f"ALPHAEDGE: WF aggregated OOS Sharpe {agg.sharpe_ratio:.2f} < 0.5"
        )
