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
)
from alphaedge.config.loader import AppConfig, SessionSpec, load_config
from alphaedge.engine.backtest_export import export_results_csv, plot_equity_curve
from alphaedge.engine.backtest_stats import (
    _apply_equity_sizing,
    _compute_max_drawdown,
    _compute_profit_factor,
    _compute_sharpe,
    _compute_winrate,
    _log_per_pair_report,
    _log_split_report,
    _log_stats_summary,
    compute_split_report,
    compute_stats,
    print_rich_summary,
    split_trades_is_oos,
)
from alphaedge.engine.backtest_types import BacktestReport, BacktestStats, TradeRecord
from alphaedge.engine.data_feed import BarDiskCache
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
    "_apply_equity_sizing",
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
    Walk forward through bars to find the trade exit (NumPy-vectorized).

    Replaces the bar-by-bar Python loop with NumPy boolean masks so that
    SL/TP detection runs at C speed rather than interpreter speed.

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
    future = bars[entry_bar_idx + 1 :]
    if not future:
        return _close_trade(trade, bars[-1]["close"], bars[-1], "timeout")

    n = len(future)
    highs = np.fromiter((b["high"] for b in future), dtype=np.float64, count=n)
    lows = np.fromiter((b["low"] for b in future), dtype=np.float64, count=n)

    if trade.direction == 1:  # Long
        sl_mask = lows <= trade.stop_loss
        tp_mask = highs >= trade.take_profit
    else:  # Short
        sl_mask = highs >= trade.stop_loss
        tp_mask = lows <= trade.take_profit

    sl_hits = np.nonzero(sl_mask)[0]
    tp_hits = np.nonzero(tp_mask)[0]

    first_sl = int(sl_hits[0]) if len(sl_hits) else n
    first_tp = int(tp_hits[0]) if len(tp_hits) else n

    if first_sl == n and first_tp == n:
        return _close_trade(trade, future[-1]["close"], future[-1], "timeout")
    if first_sl < first_tp:
        return _close_trade(trade, trade.stop_loss, future[first_sl], "loss")
    if first_tp < first_sl:
        return _close_trade(trade, trade.take_profit, future[first_tp], "win")
    # Both hit on the same bar — use bar direction to decide which was first
    bar = future[first_sl]
    if _sl_hit_first(trade, bar):
        return _close_trade(trade, trade.stop_loss, bar, "loss")
    return _close_trade(trade, trade.take_profit, bar, "win")


# ------------------------------------------------------------------
# Fast exit simulation using pre-built NumPy arrays (zero-copy)
# ------------------------------------------------------------------
def _simulate_trade_exit_fast(
    trade: TradeRecord,
    bars: list[dict[str, Any]],
    entry_bar_idx: int,
    all_highs: np.ndarray,
    all_lows: np.ndarray,
) -> TradeRecord:
    """
    Vectorized trade exit using pre-built bar arrays.

    The caller pre-builds ``all_highs`` / ``all_lows`` once from the
    same ``bars`` list, so NumPy slicing (O(1) view) replaces repeated
    per-trade dict key extraction (O(n) Python iteration).

    Parameters
    ----------
    trade : TradeRecord
        The trade to simulate.
    bars : list[dict]
        M1 bar data — used only to retrieve exit bar metadata.
    entry_bar_idx : int
        Index of the entry bar.
    all_highs : np.ndarray
        float64 array of bar highs aligned with ``bars``.
    all_lows : np.ndarray
        float64 array of bar lows aligned with ``bars``.

    Returns
    -------
    TradeRecord
        The trade with exit fields populated.
    """
    start = entry_bar_idx + 1
    if start >= len(bars):
        return _close_trade(trade, bars[-1]["close"], bars[-1], "timeout")

    highs = all_highs[start:]  # O(1) NumPy view — no copy
    lows = all_lows[start:]

    if trade.direction == 1:  # Long
        sl_mask = lows <= trade.stop_loss
        tp_mask = highs >= trade.take_profit
    else:  # Short
        sl_mask = highs >= trade.stop_loss
        tp_mask = lows <= trade.take_profit

    sl_hits = np.nonzero(sl_mask)[0]
    tp_hits = np.nonzero(tp_mask)[0]

    n = len(highs)
    first_sl = int(sl_hits[0]) if len(sl_hits) else n
    first_tp = int(tp_hits[0]) if len(tp_hits) else n

    if first_sl == n and first_tp == n:
        return _close_trade(trade, bars[-1]["close"], bars[-1], "timeout")
    if first_sl < first_tp:
        return _close_trade(trade, trade.stop_loss, bars[start + first_sl], "loss")
    if first_tp < first_sl:
        return _close_trade(trade, trade.take_profit, bars[start + first_tp], "win")
    # Both hit on the same bar
    bar = bars[start + first_sl]
    if _sl_hit_first(trade, bar):
        return _close_trade(trade, trade.stop_loss, bar, "loss")
    return _close_trade(trade, trade.take_profit, bar, "win")


# ------------------------------------------------------------------
# Partial exit: 50% at 1R, 50% at 2R with SL moved to breakeven
# ------------------------------------------------------------------
def _simulate_partial_exit_fast(
    trade: TradeRecord,
    bars: list[dict[str, Any]],
    entry_bar_idx: int,
    all_highs: np.ndarray,
    all_lows: np.ndarray,
) -> TradeRecord:
    """
    Simulate partial exit: 50% closes at 1R, remaining 50% has SL moved
    to breakeven (entry price) and targets the full 2R TP.

    Outcomes:
    - SL hit before 1R  → full loss (unchanged from normal)
    - 1R hit, then BE   → blended = 0.5 × 1R pips  (locked profit)
    - 1R hit, then 2R   → blended = 0.5 × 1R + 0.5 × 2R = 1.5R pips
    - 1R + 2R same bar  → treated as 1.5R (blew through both levels)
    """
    pip_size = PIP_SIZES.get(trade.pair, 0.0001)
    sl_dist = abs(trade.entry_price - trade.stop_loss)
    sl_pips = sl_dist / pip_size

    partial_tp = (
        trade.entry_price + sl_dist
        if trade.direction == 1
        else trade.entry_price - sl_dist
    )

    start = entry_bar_idx + 1
    if start >= len(bars):
        return _close_trade(trade, bars[-1]["close"], bars[-1], "timeout")

    highs = all_highs[start:]
    lows = all_lows[start:]
    n = len(highs)

    if trade.direction == 1:
        sl_mask = lows <= trade.stop_loss
        tp1_mask = highs >= partial_tp
    else:
        sl_mask = highs >= trade.stop_loss
        tp1_mask = lows <= partial_tp

    sl_hits = np.nonzero(sl_mask)[0]
    tp1_hits = np.nonzero(tp1_mask)[0]
    first_sl = int(sl_hits[0]) if len(sl_hits) else n
    first_tp1 = int(tp1_hits[0]) if len(tp1_hits) else n

    # SL hits before 1R — full loss
    if first_sl < first_tp1:
        return _close_trade(trade, trade.stop_loss, bars[start + first_sl], "loss")
    # Same bar: SL and 1R both hit — check bar direction
    if first_sl == first_tp1 < n and _sl_hit_first(trade, bars[start + first_sl]):
        return _close_trade(trade, trade.stop_loss, bars[start + first_sl], "loss")
    # No 1R hit at all — timeout
    if first_tp1 == n:
        return _close_trade(trade, bars[-1]["close"], bars[-1], "timeout")

    # Check if 2R was hit on the same candle as 1R (blowthrough)
    if trade.direction == 1:
        tp2_same_bar = all_highs[start + first_tp1] >= trade.take_profit
    else:
        tp2_same_bar = all_lows[start + first_tp1] <= trade.take_profit

    if tp2_same_bar:
        blended = 0.5 * sl_pips + 0.5 * (2.0 * sl_pips) - trade.spread_cost_pips
        exit_bar = bars[start + first_tp1]
        trade.pnl_pips = blended
        trade.pnl_usd = blended * 1000.0 * pip_size
        trade.outcome = "win"
        trade.exit_price = trade.take_profit
        trade.exit_time = exit_bar.get("datetime")
        return trade

    # 1R hit. Phase 2: SL at BE, target 2R.
    search_start_abs = start + first_tp1 + 1
    if search_start_abs >= len(bars):
        blended = 0.5 * sl_pips - trade.spread_cost_pips
        trade.pnl_pips = blended
        trade.pnl_usd = blended * 1000.0 * pip_size
        trade.outcome = "win" if blended > 0 else "loss"
        trade.exit_price = partial_tp
        trade.exit_time = bars[start + first_tp1].get("datetime")
        return trade

    highs2 = all_highs[search_start_abs:]
    lows2 = all_lows[search_start_abs:]
    n2 = len(highs2)

    if trade.direction == 1:
        be_mask = lows2 <= trade.entry_price
        tp2_mask = highs2 >= trade.take_profit
    else:
        be_mask = highs2 >= trade.entry_price
        tp2_mask = lows2 <= trade.take_profit

    first_be = int(np.nonzero(be_mask)[0][0]) if be_mask.any() else n2
    first_tp2 = int(np.nonzero(tp2_mask)[0][0]) if tp2_mask.any() else n2

    if first_be <= first_tp2:
        # BE stop hit — second half closes at entry (0 pips)
        pnl_second = 0.0
        idx_abs = search_start_abs + first_be
        exit_bar = bars[idx_abs] if idx_abs < len(bars) else bars[-1]
    elif first_tp2 < n2:
        # 2R TP hit — second half wins
        pnl_second = 2.0 * sl_pips
        idx_abs = search_start_abs + first_tp2
        exit_bar = bars[idx_abs] if idx_abs < len(bars) else bars[-1]
    else:
        # Timeout — price stayed above BE, below 2R
        raw2 = (bars[-1]["close"] - trade.entry_price) * trade.direction
        pnl_second = max(raw2 / pip_size, 0.0)
        exit_bar = bars[-1]

    blended = 0.5 * sl_pips + 0.5 * pnl_second - trade.spread_cost_pips
    trade.pnl_pips = blended
    trade.pnl_usd = blended * 1000.0 * pip_size
    trade.outcome = "win" if blended > 0 else "loss"
    trade.exit_price = partial_tp
    trade.exit_time = exit_bar.get("datetime")
    return trade


# ------------------------------------------------------------------
# Trailing partial exit: 50% at 1R, trailing stop (1×SL behind peak)
# ------------------------------------------------------------------
def _simulate_trailing_partial_exit_fast(
    trade: TradeRecord,
    bars: list[dict[str, Any]],
    entry_bar_idx: int,
    all_highs: np.ndarray,
    all_lows: np.ndarray,
) -> TradeRecord:
    """
    Partial exit: 50% closes at 1R, remaining 50% held with a trailing
    stop that stays 1×SL-distance behind the running price peak.

    After 1R hit:
    - Trailing stop initialises at entry (BE)
    - Advances pip-for-pip as price extends in trade direction
    - Remaining 50% exits when trailing stop is touched, or at timeout
    """
    pip_size = PIP_SIZES.get(trade.pair, 0.0001)
    sl_dist = abs(trade.entry_price - trade.stop_loss)
    sl_pips = sl_dist / pip_size

    partial_tp = (
        trade.entry_price + sl_dist
        if trade.direction == 1
        else trade.entry_price - sl_dist
    )

    start = entry_bar_idx + 1
    if start >= len(bars):
        return _close_trade(trade, bars[-1]["close"], bars[-1], "timeout")

    highs = all_highs[start:]
    lows = all_lows[start:]
    n = len(highs)

    if trade.direction == 1:
        sl_mask = lows <= trade.stop_loss
        tp1_mask = highs >= partial_tp
    else:
        sl_mask = highs >= trade.stop_loss
        tp1_mask = lows <= partial_tp

    sl_hits = np.nonzero(sl_mask)[0]
    tp1_hits = np.nonzero(tp1_mask)[0]
    first_sl = int(sl_hits[0]) if len(sl_hits) else n
    first_tp1 = int(tp1_hits[0]) if len(tp1_hits) else n

    # Full loss before 1R
    if first_sl < first_tp1:
        return _close_trade(trade, trade.stop_loss, bars[start + first_sl], "loss")
    if first_sl == first_tp1 < n and _sl_hit_first(trade, bars[start + first_sl]):
        return _close_trade(trade, trade.stop_loss, bars[start + first_sl], "loss")
    # No 1R hit — timeout
    if first_tp1 == n:
        return _close_trade(trade, bars[-1]["close"], bars[-1], "timeout")

    # Phase 2: trailing stop on remaining 50%
    # Peak starts at the high/low of the 1R-hit bar; trailing stop = BE
    tp1_bar_abs = start + first_tp1
    if trade.direction == 1:
        trailing_peak = float(all_highs[tp1_bar_abs])
    else:
        trailing_peak = float(all_lows[tp1_bar_abs])
    trailing_stop = (
        trailing_peak - sl_dist if trade.direction == 1 else trailing_peak + sl_dist
    )

    pnl_second = 0.0
    exit_bar = bars[tp1_bar_abs]

    for i in range(tp1_bar_abs + 1, len(bars)):
        h = float(all_highs[i])
        lv = float(all_lows[i])
        bar = bars[i]

        if trade.direction == 1:
            if h > trailing_peak:
                trailing_peak = h
                trailing_stop = trailing_peak - sl_dist
            if lv <= trailing_stop:
                pnl_second = (trailing_stop - trade.entry_price) / pip_size
                exit_bar = bar
                break
        else:
            if lv < trailing_peak:
                trailing_peak = lv
                trailing_stop = trailing_peak + sl_dist
            if h >= trailing_stop:
                pnl_second = (trade.entry_price - trailing_stop) / pip_size
                exit_bar = bar
                break
    else:
        last_close = bars[-1]["close"]
        if trade.direction == 1:
            pnl_second = max((last_close - trade.entry_price) / pip_size, 0.0)
        else:
            pnl_second = max((trade.entry_price - last_close) / pip_size, 0.0)
        exit_bar = bars[-1]

    blended = 0.5 * sl_pips + 0.5 * pnl_second - trade.spread_cost_pips
    trade.pnl_pips = blended
    trade.pnl_usd = blended * 1000.0 * pip_size
    trade.outcome = "win" if blended > 0 else "loss"
    trade.exit_price = partial_tp
    trade.exit_time = exit_bar.get("datetime")
    return trade


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
    session_spec: SessionSpec | None = None,
) -> list[dict[str, Any]]:
    """
    Group M1 and M5 bars into per-day trading sessions.

    Returns a list of session dicts, each containing:
    - 'date': the trading date (in the session timezone)
    - 'm5_pre': M5 bars from before session start (last 6)
    - 'm1_pre': M1 bars from before session start (last 30, for ATR baseline)
    - 'm1_indices': indices into m1_bars for session-window bars

    Parameters
    ----------
    session_spec : SessionSpec | None
        Per-pair session window. Falls back to NYSE 9:30-10:30 ET when None.
    """
    if session_spec is None:
        sess_tz_name = "America/New_York"
        sess_start_h = SESSION_START_HOUR
        sess_start_m = SESSION_START_MINUTE
        sess_end_h = SESSION_END_HOUR
        sess_end_m = SESSION_END_MINUTE
    else:
        sess_tz_name = session_spec.tz_name
        sess_start_h = session_spec.start_hour
        sess_start_m = session_spec.start_minute
        sess_end_h = session_spec.end_hour
        sess_end_m = session_spec.end_minute

    sess_tz = ZoneInfo(sess_tz_name)

    m5_by_date: dict[date, list[dict[str, Any]]] = defaultdict(list)
    for bar in m5_bars:
        dt_val = bar["datetime"]
        if dt_val.tzinfo is None:
            dt_val = dt_val.replace(tzinfo=ZoneInfo("UTC"))
        local_dt = dt_val.astimezone(sess_tz)
        m5_by_date[local_dt.date()].append(bar)

    # Collect pre-session and in-session M1 bars by date
    m1_pre_by_date: dict[date, list[int]] = defaultdict(list)
    session_indices: dict[date, list[int]] = defaultdict(list)
    for idx, bar in enumerate(m1_bars):
        dt_val = bar["datetime"]
        if dt_val.tzinfo is None:
            dt_val = dt_val.replace(tzinfo=ZoneInfo("UTC"))
        local_dt = dt_val.astimezone(sess_tz)
        sess_start = local_dt.replace(
            hour=sess_start_h,
            minute=sess_start_m,
            second=0,
            microsecond=0,
        )
        sess_end = local_dt.replace(
            hour=sess_end_h,
            minute=sess_end_m,
            second=0,
            microsecond=0,
        )
        if sess_start <= local_dt <= sess_end:
            session_indices[local_dt.date()].append(idx)
        elif local_dt < sess_start:
            m1_pre_by_date[local_dt.date()].append(idx)

    result: list[dict[str, Any]] = []
    for day in sorted(session_indices.keys()):
        day_m5 = m5_by_date.get(day, [])
        sess_start_dt = datetime(
            day.year,
            day.month,
            day.day,
            sess_start_h,
            sess_start_m,
            tzinfo=sess_tz,
        )
        pre_m5 = [
            b for b in day_m5 if b["datetime"].astimezone(sess_tz) < sess_start_dt
        ][-6:]
        # Last 30 pre-session M1 bars — used as ATR baseline for gap detection
        pre_m1_indices = m1_pre_by_date.get(day, [])[-30:]
        pre_m1 = [m1_bars[i] for i in pre_m1_indices]

        result.append(
            {
                "date": day,
                "m5_pre": pre_m5,
                "m1_pre": pre_m1,
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
    cache: Any = None,
) -> list[TradeRecord]:
    """Fetch historical bars for a pair and run backtest.

    Requests are strictly sequential (entry TF first, then FCR TF) — IB's historical
    data pacing rejects concurrent requests with error 162 regardless of
    semaphore depth.  The rolling cache makes subsequent runs near-instant.
    """
    # Resolve alias: e.g. EURUSD_LC → EURUSD for IB data fetch (reuses cached bars)
    data_pair = config.trading.pair_aliases.get(pair, pair)
    entry_tf = config.trading.entry_timeframe
    fcr_tf = config.trading.fcr_timeframe
    logger.info(f"ALPHAEDGE backtesting: {pair} ({start_dt.date()} → {end_dt.date()})")
    entry_bars = await hist_feed.fetch_bars_chunked(
        pair=data_pair,
        timeframe=entry_tf,
        start_dt=start_dt,
        end_dt=end_dt,
        cache=cache,
    )
    fcr_bars = await hist_feed.fetch_bars_chunked(
        pair=data_pair,
        timeframe=fcr_tf,
        start_dt=start_dt,
        end_dt=end_dt,
        cache=cache,
    )
    if not entry_bars:
        return []
    # Per-pair parameter overrides (fall back to global config values)
    pair_min_range = config.trading.min_range_pips_by_pair.get(
        pair, config.trading.min_range_pips
    )
    pair_min_volume = config.trading.min_volume_ratio_by_pair.get(
        pair, DEFAULT_MIN_VOLUME_RATIO
    )
    return _backtest_pair(
        pair,
        entry_bars,
        fcr_bars,
        config,
        min_atr_ratio=config.trading.min_atr_ratio,
        min_range_pips=pair_min_range,
        min_volume_ratio=pair_min_volume,
        session_spec=config.trading.pair_sessions.get(pair),
    )


def _apply_usd_correlation_filter(
    trades: list[TradeRecord],
) -> list[TradeRecord]:
    """Block trades that amplify USD directional exposure within the same session.

    USD direction encoding:
    - EURUSD (USD is quote): long trade → USD short (-1), short trade → USD long (+1)
    - USDJPY (USD is base): long trade → USD long (+1), short trade → USD short (-1)

    If two trades in the same session have the same net USD direction, the
    second (later entry) is dropped.  Opposite-direction trades (hedge) are
    both kept.
    """
    _usd_base_pairs = {"USDJPY", "USDCHF", "USDCAD", "USDMXN"}

    def _usd_dir(t: TradeRecord) -> int:
        if t.pair in _usd_base_pairs:
            return t.direction  # long USDJPY = USD long
        return -t.direction  # long EURUSD = USD short

    et_tz = ZoneInfo("America/New_York")
    sessions: defaultdict[date, list[TradeRecord]] = defaultdict(list)
    for t in trades:
        dt = t.entry_time
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        sessions[dt.astimezone(et_tz).date()].append(t)

    filtered: list[TradeRecord] = []
    blocked = 0
    for day in sorted(sessions):
        net_usd = 0
        for t in sorted(sessions[day], key=lambda x: x.entry_time):
            d = _usd_dir(t)
            if net_usd != 0 and d == net_usd:
                blocked += 1
                continue
            net_usd += d
            filtered.append(t)

    if blocked > 0:
        logger.info(
            f"ALPHAEDGE: USD correlation filter blocked {blocked} trade(s) "
            f"(same-direction USD amplification)"
        )
    return filtered


def _apply_global_session_limit(
    trades: list[TradeRecord],
    max_trades_per_session: int,
    pair_priority: list[str] | None = None,
) -> list[TradeRecord]:
    """Enforce global max trades per session across all pairs.

    Groups trades by NYSE session date and keeps only the first
    *max_trades_per_session* trades per session, ordered by:
    1. Pair priority rank (index in *pair_priority*, lower = higher priority)
    2. Entry time within the session (earlier = higher priority)

    This ensures that higher-priority pairs (e.g. EURUSD) always get their
    slot before lower-priority pairs on the same day, instead of losing out
    due to a later entry time.
    """
    if max_trades_per_session <= 0:
        return trades
    et_tz = ZoneInfo("America/New_York")
    priority_map: dict[str, int] = (
        {pair: idx for idx, pair in enumerate(pair_priority)} if pair_priority else {}
    )
    n_pairs = len(priority_map) if priority_map else 0

    def _sort_key(t: TradeRecord) -> tuple[int, datetime]:
        rank = priority_map.get(t.pair, n_pairs)  # unknown pairs go last
        return (rank, t.entry_time)

    # Group by session date
    sessions: defaultdict[date, list[TradeRecord]] = defaultdict(list)
    for trade in trades:
        dt = trade.entry_time
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        session_date = dt.astimezone(et_tz).date()
        sessions[session_date].append(trade)

    filtered: list[TradeRecord] = []
    for day in sorted(sessions):
        day_trades = sorted(sessions[day], key=_sort_key)
        filtered.extend(day_trades[:max_trades_per_session])

    dropped = len(trades) - len(filtered)
    if dropped > 0:
        logger.info(
            f"ALPHAEDGE: Global session limit ({max_trades_per_session}/session) "
            f"dropped {dropped} trade(s) across all pairs"
        )
    return filtered


async def run_backtest(config: AppConfig) -> BacktestStats:
    """Run the strategy backtest using IB historical data.

    Pairs are fetched sequentially on a single IB connection — required
    because ib_insync is not thread-safe and cannot share an event loop
    across threads.  The token-bucket throttler ensures we stay within
    IB's historical data pacing limit.
    """
    logger.info(f"{PROJECT_TITLE} — Backtest starting")

    from alphaedge.engine.broker import BrokerConnection
    from alphaedge.engine.data_feed import HistoricalDataFeed

    broker = BrokerConnection(config.ib)
    if not await broker.connect():
        logger.error("ALPHAEDGE: Cannot backtest — IB Gateway unavailable")
        return BacktestStats()

    hist_feed = HistoricalDataFeed(broker)
    cache = BarDiskCache()
    all_trades: list[TradeRecord] = []

    end_dt = datetime.now(tz=ZoneInfo("UTC"))
    start_dt = end_dt - timedelta(days=365 * config.trading.backtest_years)
    pairs = config.trading.pairs
    logger.info(
        f"ALPHAEDGE: Backtest range {start_dt.date()} → {end_dt.date()} "
        f"({config.trading.backtest_years} years, {len(pairs)} pairs)"
    )

    for idx, pair in enumerate(pairs, 1):
        logger.info(f"ALPHAEDGE [{idx}/{len(pairs)}] Starting {pair}...")
        try:
            trades = await _fetch_pair_trades(
                hist_feed, pair, config, start_dt, end_dt, cache
            )
            all_trades.extend(trades)
            logger.info(
                f"ALPHAEDGE [{idx}/{len(pairs)}] {pair} done "
                f"\u2014 {len(trades)} trades"
            )
        except Exception:
            logger.exception(
                f"ALPHAEDGE [{idx}/{len(pairs)}] {pair} SKIPPED — fetch failed"
            )

    await broker.disconnect()

    eur_usd_rate = config.trading.eur_usd_rate
    starting_equity = config.trading.starting_equity

    # USD correlation filter: drop trades that double USD directional exposure
    if config.trading.usd_correlation_filter:
        all_trades = _apply_usd_correlation_filter(all_trades)

    # Enforce global max trades per session across all pairs (priority-ordered)
    all_trades = _apply_global_session_limit(
        all_trades,
        config.trading.max_trades_per_session,
        pair_priority=config.trading.pairs,
    )

    # Apply compound fixed-fraction equity sizing before stats
    _apply_equity_sizing(
        all_trades,
        starting_equity,
        config.trading.risk_pct,
        max_lot_size=config.trading.max_lot_size,
    )

    # Overall stats
    stats = compute_stats(all_trades, eur_usd_rate, starting_equity)
    export_results_csv(all_trades, stats, eur_usd_rate=eur_usd_rate)
    plot_equity_curve(all_trades, starting_equity=starting_equity)
    _log_stats_summary(stats, eur_usd_rate, starting_equity)
    _log_per_pair_report(all_trades, eur_usd_rate)
    _validate_with_vectorbt(
        all_trades, manual_sharpe=stats.sharpe_equity, starting_equity=starting_equity
    )

    # IS/OOS split report
    if all_trades:
        report = compute_split_report(
            all_trades, eur_usd_rate=eur_usd_rate, starting_equity=starting_equity
        )
        _log_split_report(report, eur_usd_rate)

    # Rich table — printed last so it's the final thing visible in the terminal
    print_rich_summary(all_trades, stats, starting_equity, eur_usd_rate)

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
    min_volume_ratio: float = DEFAULT_MIN_VOLUME_RATIO,
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
        min_volume_ratio=min_volume_ratio,
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
    _all_highs: np.ndarray | None = None,
    _all_lows: np.ndarray | None = None,
    partial_exit: bool = False,
    trailing_partial_exit: bool = False,
) -> TradeRecord:
    """Create a TradeRecord from a detected signal and simulate exit."""
    bar_time = bars[bar_index].get("datetime")
    spread_cost = compute_variable_slippage(bar_time, pair=pair)
    pip_size = PIP_SIZES.get(pair, 0.0001)
    sl_pips = abs(signal["entry_price"] - signal["stop_loss"]) / pip_size
    trade = TradeRecord(
        pair=pair,
        direction=signal["signal"],
        entry_price=signal["entry_price"],
        stop_loss=signal["stop_loss"],
        take_profit=signal["take_profit"],
        entry_time=bar_time if bar_time is not None else datetime.now(),
        spread_cost_pips=spread_cost,
        sl_pips=sl_pips,
    )
    if _all_highs is not None and _all_lows is not None:
        if trailing_partial_exit:
            return _simulate_trailing_partial_exit_fast(
                trade, bars, bar_index, _all_highs, _all_lows
            )
        if partial_exit:
            return _simulate_partial_exit_fast(
                trade, bars, bar_index, _all_highs, _all_lows
            )
        return _simulate_trade_exit_fast(trade, bars, bar_index, _all_highs, _all_lows)
    return _simulate_trade_exit(trade, bars, bar_index)


def _backtest_pair(
    pair: str,
    m1_bars: list[dict[str, Any]],
    m5_bars: list[dict[str, Any]],
    config: AppConfig,
    news_filter: EconomicNewsFilter | None = None,
    *,
    min_atr_ratio: float = DEFAULT_MIN_ATR_RATIO,
    min_range_pips: float = DEFAULT_MIN_RANGE_PIPS,
    min_volume_ratio: float = DEFAULT_MIN_VOLUME_RATIO,
    min_sl_pips: float = 0.0,
    session_spec: SessionSpec | None = None,
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

    sessions = _group_bars_by_session(m1_bars, m5_bars, session_spec=session_spec)

    # Pre-build bar arrays once — amortises per-trade dict extraction across all trades
    _m1_highs = np.array([b["high"] for b in m1_bars], dtype=np.float64)
    _m1_lows = np.array([b["low"] for b in m1_bars], dtype=np.float64)

    excluded_days = set(config.trading.excluded_days)
    for session in sessions:
        if excluded_days and session["date"].weekday() in excluded_days:
            continue
        m5_pre = session["m5_pre"]
        m1_pre = session["m1_pre"]
        m1_idx = session["m1_indices"]

        if len(m5_pre) < 2 or len(m1_idx) < 4:
            continue

        # Step 1: FCR detection on pre-session M5 bars (once per session)
        # Optional CV quality filter: skip noisy/irregular ranges
        cv_max = config.trading.fcr_range_cv_max
        if cv_max > 0.0 and len(m5_pre) >= 2:
            bar_ranges = [
                b["high"] - b["low"] for b in m5_pre if b["high"] - b["low"] > 0
            ]
            if bar_ranges:
                mu = sum(bar_ranges) / len(bar_ranges)
                if mu > 0:
                    sigma = (
                        sum((r - mu) ** 2 for r in bar_ranges) / len(bar_ranges)
                    ) ** 0.5
                    cv = sigma / mu
                    if cv > cv_max:
                        continue

        fcr_result = fcr_detector.detect_fcr(
            candles_data=m5_pre,
            min_range_pips=min_range_pips,
            pip_size=pip_size,
        )
        if not fcr_result:
            continue

        # Step 2: Gap/ATR detection on first 3 session M1 bars (once)
        # Baseline uses pre-session M1 bars (same timeframe scale)
        first_3_m1 = [m1_bars[i] for i in m1_idx[:3]]
        pre_close = m5_pre[-1]["close"]
        session_open = m1_bars[m1_idx[0]]["open"]
        gap_result = gap_detector.detect_gap(
            pre_session_m1=m1_pre,
            session_m1=first_3_m1,
            pre_close=pre_close,
            session_open=session_open,
            atr_period=DEFAULT_ATR_PERIOD,
            min_atr_ratio=min_atr_ratio,
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
                min_volume_ratio=min_volume_ratio,
            )
            if not signal:
                continue
            # Reject signals where SL is too small — spread becomes too large
            # a fraction of 1R, destroying the edge in USD terms
            if min_sl_pips > 0.0 and (
                abs(signal["entry_price"] - signal["stop_loss"]) / pip_size
                < min_sl_pips
            ):
                continue
            global_idx = m1_idx[local_i]
            trades.append(
                _build_trade_record(
                    pair,
                    signal,
                    m1_bars,
                    global_idx,
                    _m1_highs,
                    _m1_lows,
                    partial_exit=config.trading.partial_exit,
                    trailing_partial_exit=config.trading.trailing_partial_exit,
                )
            )

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

    arr = np.array(pct_returns)
    std = float(arr.std(ddof=1))
    vbt_sharpe: float = float(arr.mean() / std * np.sqrt(252)) if std > 0.0 else 0.0

    logger.info(
        f"ALPHAEDGE cross-validation — "
        f"Sharpe (numpy annualised): {vbt_sharpe:.2f}, "
        f"Sharpe (manual): {manual_sharpe:.2f}, "
        f"Total PnL: {sum(t.pnl_pips for t in trades):.1f} pips"
    )

    # Compare: warn if divergence > 5%
    if manual_sharpe != 0.0:
        divergence = abs(vbt_sharpe - manual_sharpe) / abs(manual_sharpe) * 100.0
        if divergence > 5.0:
            logger.warning(
                f"ALPHAEDGE: Sharpe divergence {divergence:.1f}% "
                f"(numpy={vbt_sharpe:.2f} vs manual={manual_sharpe:.2f})"
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

    # Pre-build bar arrays once for vectorized exit simulation
    _all_highs = np.array([b["high"] for b in m1_bars], dtype=np.float64)
    _all_lows = np.array([b["low"] for b in m1_bars], dtype=np.float64)

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
        trade = _simulate_trade_exit_fast(
            trade, m1_bars, bar_idx, _all_highs, _all_lows
        )
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
