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
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np

from alphaedge.config.constants import (
    DEFAULT_ATR_PERIOD,
    DEFAULT_MIN_ATR_RATIO,
    DEFAULT_MIN_RANGE_PIPS,
    DEFAULT_MIN_VOLUME_RATIO,
    DEFAULT_VOLUME_PERIOD,
    MIN_LOTS,
    PIP_SIZES,
    PROJECT_TITLE,
)
from alphaedge.config.loader import AppConfig, SessionSpec, load_config
from alphaedge.engine.backtest_export import export_results_csv, plot_equity_curve
from alphaedge.engine.backtest_filters import (  # noqa: F401
    _apply_global_session_limit,
    _apply_usd_correlation_filter,
    _group_bars_by_session,
)
from alphaedge.engine.backtest_simulation import (
    _simulate_partial_exit_fast,
    _simulate_trade_exit,
    _simulate_trade_exit_fast,
    _simulate_trailing_partial_exit_fast,
    compute_variable_slippage,
)
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
    # --- simulation (backtest_simulation) ---
    "compute_variable_slippage",
]


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
        min_atr_ratio=config.trading.min_atr_ratio_by_pair.get(
            pair, config.trading.min_atr_ratio
        ),
        min_range_pips=pair_min_range,
        min_volume_ratio=pair_min_volume,
        session_spec=config.trading.pair_sessions.get(pair),
    )


async def run_backtest(config: AppConfig) -> BacktestStats:
    """Run the strategy backtest using IB historical data.

    Pairs are fetched sequentially on a single IB connection — required
    because ib_insync is not thread-safe and cannot share an event loop
    across threads.  The token-bucket throttler ensures we stay within
    IB's historical data pacing limit.
    """
    logger.info(f"{PROJECT_TITLE} — Backtest starting")

    # Lazy imports: avoids circular dependency (backtest → broker → backtest)
    # and allows importing this module without IB Gateway present (offline tests).
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
        config.trading.max_lot_size,  # _max_lot_size: kept for call-site compatibility
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
    spread_cost_pips: float | None = None,
    _all_highs: np.ndarray | None = None,
    _all_lows: np.ndarray | None = None,
    partial_exit: bool = False,
    trailing_partial_exit: bool = False,
) -> TradeRecord:
    """Create a TradeRecord from a detected signal and simulate exit."""
    bar_time = bars[bar_index].get("datetime")
    spread_cost = (
        spread_cost_pips
        if spread_cost_pips is not None
        else compute_variable_slippage(bar_time, pair=pair)
    )
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


def _validate_backtest_signal(
    pair: str,
    signal: dict[str, Any],
    config: AppConfig,
    pip_size: float,
    spread_pips: float,
    risk_mod: Any,
    order_mod: Any,
) -> dict[str, Any] | None:
    """Apply live-like sizing and bracket validation before simulating a trade."""
    pos_result: dict[str, Any] = risk_mod.calculate_position_size(
        account_equity=config.trading.starting_equity,
        risk_pct=config.trading.risk_pct,
        sl_pips=signal["risk_pips"],
        pair=pair,
        pip_size=pip_size,
        lot_type=config.trading.lot_type,
        min_lots=MIN_LOTS,
        max_lots=config.trading.max_lot_size,
        exchange_rate=0.0,
    )
    if not pos_result.get("is_valid", False):
        return None

    bracket: dict[str, Any] = order_mod.create_bracket_order(
        direction=signal["signal"],
        entry_price=signal["entry_price"],
        stop_loss=signal["stop_loss"],
        take_profit=signal["take_profit"],
        lot_size=pos_result["lot_size"],
        pip_size=pip_size,
        spread_pips=spread_pips,
        max_spread_pips=config.trading.max_spread_pips,
        min_rr=config.trading.rr_ratio * 0.9,
        min_lots=MIN_LOTS,
        max_lots=config.trading.max_lot_size,
        adjust_for_spread=True,
    )
    if not bracket.get("is_valid", False):
        return None

    return {
        "signal": {
            **signal,
            "stop_loss": bracket["stop_loss"],
            "take_profit": bracket["take_profit"],
            "risk_pips": bracket["risk_pips"],
            "reward_pips": bracket["reward_pips"],
        },
        "spread_pips": spread_pips,
        "lot_size": pos_result["lot_size"],
    }


def _session_passes_fcr_quality_gate(
    m5_pre: list[dict[str, Any]],
    cv_max: float,
) -> bool:
    """Return True when pre-session M5 bars pass the optional CV filter."""
    if cv_max <= 0.0 or len(m5_pre) < 2:
        return True

    bar_ranges = [b["high"] - b["low"] for b in m5_pre if b["high"] - b["low"] > 0]
    if not bar_ranges:
        return True

    mu = sum(bar_ranges) / len(bar_ranges)
    if mu <= 0.0:
        return True

    sigma = (sum((r - mu) ** 2 for r in bar_ranges) / len(bar_ranges)) ** 0.5
    return sigma / mu <= cv_max


def _detect_session_gap(
    session: dict[str, Any],
    m1_bars: list[dict[str, Any]],
    m5_pre: list[dict[str, Any]],
    gap_detector: Any,
    min_atr_ratio: float,
) -> dict[str, Any] | None:
    """Run once-per-session gap detection using the first three M1 bars."""
    first_3_m1 = [m1_bars[i] for i in session["m1_indices"][:3]]
    pre_close = m5_pre[-1]["close"]
    session_open = m1_bars[session["m1_indices"][0]]["open"]
    return gap_detector.detect_gap(
        pre_session_m1=session["m1_pre"],
        session_m1=first_3_m1,
        pre_close=pre_close,
        session_open=session_open,
        atr_period=DEFAULT_ATR_PERIOD,
        min_atr_ratio=min_atr_ratio,
    )


def _collect_session_trades(
    pair: str,
    session_m1: list[dict[str, Any]],
    m1_bars: list[dict[str, Any]],
    m1_idx: list[int],
    pip_size: float,
    config: AppConfig,
    engulfing_detector: Any,
    fcr_result: dict[str, Any],
    risk_manager: Any,
    order_manager: Any,
    _m1_highs: np.ndarray,
    _m1_lows: np.ndarray,
    *,
    min_volume_ratio: float,
    min_sl_pips: float,
    news_filter: EconomicNewsFilter | None,
) -> list[TradeRecord]:
    """Build all validated trade records for one historical session."""
    trades: list[TradeRecord] = []
    for local_i in range(3, len(session_m1)):
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

        if min_sl_pips > 0.0 and (
            abs(signal["entry_price"] - signal["stop_loss"]) / pip_size < min_sl_pips
        ):
            continue

        bar_time = session_m1[local_i].get("datetime")
        spread_pips = compute_variable_slippage(bar_time, pair=pair)
        validated = _validate_backtest_signal(
            pair,
            signal,
            config,
            pip_size,
            spread_pips,
            risk_manager,
            order_manager,
        )
        if validated is None:
            continue

        global_idx = m1_idx[local_i]
        trades.append(
            _build_trade_record(
                pair,
                validated["signal"],
                m1_bars,
                global_idx,
                spread_cost_pips=validated["spread_pips"],
                _all_highs=_m1_highs,
                _all_lows=_m1_lows,
                partial_exit=config.trading.partial_exit,
                trailing_partial_exit=config.trading.trailing_partial_exit,
            )
        )

    return trades


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
            order_manager,
            risk_manager,
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
        m1_idx = session["m1_indices"]

        if len(m5_pre) < 2 or len(m1_idx) < 4:
            continue

        if not _session_passes_fcr_quality_gate(
            m5_pre, config.trading.fcr_range_cv_max
        ):
            continue

        fcr_result = fcr_detector.detect_fcr(
            candles_data=m5_pre,
            min_range_pips=min_range_pips,
            pip_size=pip_size,
        )
        if not fcr_result:
            continue

        gap_result = _detect_session_gap(
            session,
            m1_bars,
            m5_pre,
            gap_detector,
            min_atr_ratio,
        )
        if not gap_result or not gap_result.get("detected"):
            continue

        session_m1 = [m1_bars[i] for i in m1_idx]
        trades.extend(
            _collect_session_trades(
                pair,
                session_m1,
                m1_bars,
                m1_idx,
                pip_size,
                config,
                engulfing_detector,
                fcr_result,
                risk_manager,
                order_manager,
                _m1_highs,
                _m1_lows,
                min_volume_ratio=min_volume_ratio,
                min_sl_pips=min_sl_pips,
                news_filter=news_filter,
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
