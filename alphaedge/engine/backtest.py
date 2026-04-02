# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/engine/backtest.py
# DESCRIPTION  : Backtesting engine with vectorbt and IB data
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — Momentum+Carry Forex Trading Bot: historical backtesting engine."""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np

from alphaedge.config.constants import (
    DEFAULT_ADX_THRESHOLD,
    DEFAULT_PIP_SIZE,
    DEFAULT_RR_RATIO,
    MIN_LOTS,
    PIP_SIZES,
    PROJECT_TITLE,
    REFERENCE_FX_RATE,
)
from alphaedge.config.loader import AppConfig, load_config
from alphaedge.engine.backtest_export import export_results_csv, plot_equity_curve
from alphaedge.engine.backtest_filters import (
    _apply_global_session_limit,
    _apply_usd_correlation_filter,
)
from alphaedge.engine.backtest_simulation import (
    _simulate_partial_exit_fast,
    _simulate_trade_exit,
    _simulate_trade_exit_fast,
    _simulate_trailing_partial_exit_fast,
    compute_overnight_carry,
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
    # --- constants re-exported for sensitivity analysis ---
    "DEFAULT_ADX_THRESHOLD",
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
    "compute_overnight_carry",
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
    news_filter: EconomicNewsFilter | None = None,
) -> list[TradeRecord]:
    """Fetch historical Daily bars for a pair and run the Momentum+Carry backtest.

    A single sequential fetch is used — IB pacing rejects concurrent requests.
    The rolling cache makes subsequent runs near-instant.
    """
    # Resolve alias: e.g. EURUSD_LC → EURUSD for IB data fetch
    data_pair = config.trading.pair_aliases.get(pair, pair)
    signal_tf = config.trading.signal_timeframe  # "1 day"
    logger.info(f"ALPHAEDGE backtesting: {pair} ({start_dt.date()} → {end_dt.date()})")
    daily_bars = await hist_feed.fetch_bars_chunked(
        pair=data_pair,
        timeframe=signal_tf,
        start_dt=start_dt,
        end_dt=end_dt,
        cache=cache,
    )
    if not daily_bars:
        return []

    # Walk-forward validation (optional, post main backtest)
    if config.trading.walk_forward_enabled:
        wf_report = run_walk_forward(
            daily_bars,
            pair,
            config,
            train_months=config.trading.walk_forward_train_months,
            test_months=config.trading.walk_forward_test_months,
            step_months=config.trading.walk_forward_step_months,
        )
        _log_walk_forward_report(wf_report)

    return _backtest_pair(
        pair,
        daily_bars,
        config,
        news_filter=news_filter,
    )[0]


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

    # C-03: Instantiate news filter from config if enabled
    news_filter: EconomicNewsFilter | None = None
    if config.news_filter_raw.get("enabled", False):
        from alphaedge.utils.news_filter import EconomicNewsFilter as _EcNF
        from alphaedge.utils.news_filter import NewsFilterConfig

        nf_cfg = NewsFilterConfig(
            enabled=True,
            blackout_minutes=int(config.news_filter_raw.get("blackout_minutes", 15)),
            impact_levels=list(config.news_filter_raw.get("impact_levels", ["high"])),
            calendar_path=str(
                config.news_filter_raw.get(
                    "calendar_path", "data/economic_calendar.csv"
                )
            ),
        )
        news_filter = _EcNF(nf_cfg)
        logger.info(
            f"ALPHAEDGE: News filter active — {news_filter.event_count} events loaded"
        )

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
                hist_feed, pair, config, start_dt, end_dt, cache, news_filter
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

    # USD correlation filter: drop trades that double USD directional exposure.
    # NOTE: This backtest algorithm uses USD directional exposure (long vs short USD)
    # which differs from the live algorithm in session_lifecycle.py that uses a
    # pairwise correlation matrix. Align both algorithms before enabling
    # multi-pair trading. See audit_pipeline_alphaedge.md — P-05.
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
        risk_pct_by_pair=config.trading.risk_pct_by_pair or None,
        atr_ref_pips_by_pair=config.trading.atr_ref_pips_by_pair or None,
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

    # C-06: Warn if consecutive losses exceed circuit breaker threshold
    if all_trades:
        max_consec = config.trading.max_consecutive_losses
        consec = 0
        peak_consec = 0
        for t in all_trades:
            if t.pnl_pips < 0:
                consec += 1
                peak_consec = max(peak_consec, consec)
            else:
                consec = 0
        if peak_consec >= max_consec:
            logger.warning(
                f"ALPHAEDGE RISK: {peak_consec} consecutive losses detected — "
                f"circuit breaker threshold is {max_consec}. "
                "Review strategy before live deployment."
            )

    return stats


# ------------------------------------------------------------------
# Backtest a single pair
# ------------------------------------------------------------------
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
    carry_rates: dict[str, float] | None = None,
    session_end_action: str = "hold",
) -> TradeRecord:
    """Create a TradeRecord from a detected signal and simulate exit."""
    bar_time = bars[bar_index].get("datetime")
    spread_cost = (
        spread_cost_pips
        if spread_cost_pips is not None
        else compute_variable_slippage(bar_time, pair=pair)
    )
    pip_size = PIP_SIZES.get(pair, DEFAULT_PIP_SIZE)
    sl_pips = abs(signal["entry_price"] - signal["stop_loss"]) / pip_size
    trade = TradeRecord(
        pair=pair,
        direction=signal["direction"],
        entry_price=signal["entry_price"],
        stop_loss=signal["stop_loss"],
        take_profit=signal["take_profit"],
        entry_time=bar_time if bar_time is not None else datetime.now(),
        spread_cost_pips=spread_cost,
        sl_pips=sl_pips,
    )
    max_lookahead: int | None = 1 if session_end_action == "close" else None
    if _all_highs is not None and _all_lows is not None:
        if trailing_partial_exit:
            return _simulate_trailing_partial_exit_fast(
                trade, bars, bar_index, _all_highs, _all_lows
            )
        if partial_exit:
            return _simulate_partial_exit_fast(
                trade, bars, bar_index, _all_highs, _all_lows
            )
        return _simulate_trade_exit_fast(
            trade, bars, bar_index, _all_highs, _all_lows, carry_rates, max_lookahead
        )
    return _simulate_trade_exit(trade, bars, bar_index, carry_rates, max_lookahead)


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
    # C-02: use REFERENCE_FX_RATE instead of 0.0 so USDJPY pip_value is correct.
    # This is a gate-only check — P&L is always overridden by _apply_equity_sizing.
    # C-03: starting_equity is fixed (not the running equity). Diverges from live
    # (position_manager uses current_equity). Dormant: equity never falls below
    # starting_equity in observed runs. Full fix deferred — requires equity tracker
    # threaded through _collect_daily_trades.
    pos_result: dict[str, Any] = risk_mod.calculate_position_size(
        account_equity=config.trading.starting_equity,
        risk_pct=config.trading.risk_pct,
        sl_pips=signal["risk_pips"],
        pair=pair,
        pip_size=pip_size,
        lot_type=config.trading.lot_type,
        min_lots=MIN_LOTS,
        max_lots=config.trading.max_lot_size,
        exchange_rate=REFERENCE_FX_RATE.get(pair, 1.0),
    )
    if not pos_result.get("is_valid", False):
        return None

    bracket: dict[str, Any] = order_mod.create_bracket_order(
        direction=signal["direction"],
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

    # C-04: lot_size is returned for API consistency but is not stored in TradeRecord
    # and is not used in _simulate_trade_exit (which uses 1 micro lot implicitly).
    # P&L is driven entirely by _apply_equity_sizing. If a USD P&L variant or
    # ATR-scaling (Piste 3.3) is implemented, store lot_size in TradeRecord then.
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


def _compute_regime_label(
    daily_bars: list[dict[str, Any]],
    bar_index: int,
    pip_size: float,
    period: int = 20,
) -> str:
    """Classify bar_index as 'high_vol' or 'low_vol' vs rolling True-Range median.

    Returns 'unknown' when fewer than period//2 bars are available.
    A session is labelled 'low_vol' when its TR is below 80% of the prior-N
    bar median — indicating a ranging/choppy market where EMA signals are noisy.
    """
    if bar_index < 2:
        return "unknown"
    start = max(1, bar_index - period)
    trs: list[float] = []
    for i in range(start, bar_index + 1):
        high = float(daily_bars[i]["high"])
        low = float(daily_bars[i]["low"])
        prev_close = float(daily_bars[i - 1]["close"])
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr / pip_size)
    if len(trs) < max(2, period // 2):
        return "unknown"
    current_tr = trs[-1]
    median_tr = float(np.median(trs[:-1]))
    if median_tr <= 0:
        return "unknown"
    return "low_vol" if current_tr < 0.80 * median_tr else "high_vol"


def _extract_signal_features(
    signal: dict[str, Any],
    bar_dt: Any,
    all_atrs: np.ndarray,
    bar_index: int,
    carry_rates: dict[str, float] | None,
    pair: str,
) -> list[float]:
    """Extract ML feature vector from a momentum signal (no lookahead)."""
    adx = float(signal.get("adx", 0.0))
    ema_fast = float(signal.get("ema_fast", 0.0))
    ema_slow = float(signal.get("ema_slow", 1.0))
    ema_delta_pct = (ema_fast - ema_slow) / ema_slow if ema_slow != 0.0 else 0.0
    carry_diff = 0.0
    if carry_rates and len(pair) >= 6:
        carry_diff = abs(
            carry_rates.get(pair[:3], 0.0) - carry_rates.get(pair[3:6], 0.0)
        )
    atr_now = float(all_atrs[bar_index]) if bar_index < len(all_atrs) else 0.0
    atr_slice = all_atrs[max(0, bar_index - 20) : bar_index]
    atr_avg = float(np.mean(atr_slice)) if len(atr_slice) > 0 else 0.0
    atr_ratio = atr_now / atr_avg if atr_avg > 0.0 else 1.0
    dow = bar_dt.weekday() if bar_dt is not None and hasattr(bar_dt, "weekday") else 0
    return [adx, ema_delta_pct, carry_diff, atr_ratio, float(dow)]


def _compute_atr_pips(
    daily_bars: list[dict[str, Any]],
    bar_index: int,
    pip_size: float,
    period: int = 14,
) -> float:
    """Compute ATR(period) in pips using bars ending at bar_index - 1.

    Uses True Range = max(H-L, |H-prev_C|, |L-prev_C|), plain SMA.
    Returns 0.0 when insufficient bars are available.
    """
    start = max(1, bar_index - period)
    trs: list[float] = []
    for i in range(start, bar_index):
        high = float(daily_bars[i]["high"])
        low = float(daily_bars[i]["low"])
        prev_close = float(daily_bars[i - 1]["close"])
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
    if not trs or pip_size <= 0:
        return 0.0
    return float(np.mean(trs)) / pip_size


def _collect_daily_trades(
    pair: str,
    daily_bars: list[dict[str, Any]],
    bar_index: int,
    signal: dict[str, Any],
    pip_size: float,
    config: AppConfig,
    risk_manager: Any,
    order_manager: Any,
    _all_highs: np.ndarray,
    _all_lows: np.ndarray,
    *,
    news_filter: EconomicNewsFilter | None,
    min_sl_pips: float = 0.0,
    carry_rates: dict[str, float] | None = None,
    session_end_action: str = "hold",
) -> list[TradeRecord]:
    """Build validated trade records for one daily momentum signal."""
    trades: list[TradeRecord] = []
    bar = daily_bars[bar_index]
    bar_dt = bar.get("datetime")

    if news_filter is not None and bar_dt is not None:
        if news_filter.is_news_blackout(bar_dt, pair):
            return trades

    # Direction filter
    direction_filter = config.trading.direction_filter
    if direction_filter != "ALL":
        dir_val = signal.get("direction", 0)
        if direction_filter == "LONG" and dir_val != 1:
            return trades
        if direction_filter == "SHORT" and dir_val != -1:
            return trades

    # Build a synthetic entry from the daily signal
    direction: int = int(signal["direction"])
    entry_price: float = float(bar["close"])

    # SL distance: ATR-adaptive (institutional standard) or fixed fallback.
    # ATR-based: SL = sl_atr_multiplier × ATR(14) pips. On EURUSD daily ATR ≈ 80 pips,
    # the fixed 16-pip SL (rr_ratio × min_range_pips) is hit by noise ~65% of sessions.
    atr_mult = config.trading.sl_atr_multiplier
    if atr_mult > 0:
        atr_pips = _compute_atr_pips(daily_bars, bar_index, pip_size)
        pip_dist_sl = (
            max(config.trading.min_range_pips, atr_pips * atr_mult)
            if atr_pips > 0
            else config.trading.rr_ratio * config.trading.min_range_pips
        )
    else:
        pip_dist_sl = config.trading.rr_ratio * config.trading.min_range_pips

    if min_sl_pips > 0.0 and pip_dist_sl < min_sl_pips:
        return trades
    if direction == 1:
        stop_loss = entry_price - pip_dist_sl * pip_size
        take_profit = entry_price + pip_dist_sl * config.trading.rr_ratio * pip_size
    else:
        stop_loss = entry_price + pip_dist_sl * pip_size
        take_profit = entry_price - pip_dist_sl * config.trading.rr_ratio * pip_size

    trade_signal: dict[str, Any] = {
        "direction": direction,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "risk_pips": pip_dist_sl,
    }

    spread_pips = compute_variable_slippage(bar_dt, pair=pair)
    validated = _validate_backtest_signal(
        pair, trade_signal, config, pip_size, spread_pips, risk_manager, order_manager
    )
    if validated is None:
        return trades

    trades.append(
        _build_trade_record(
            pair,
            validated["signal"],
            daily_bars,
            bar_index,
            spread_cost_pips=validated["spread_pips"],
            _all_highs=_all_highs,
            _all_lows=_all_lows,
            partial_exit=config.trading.partial_exit,
            trailing_partial_exit=config.trading.trailing_partial_exit,
            carry_rates=carry_rates,
            session_end_action=session_end_action,
        )
    )
    return trades


def _backtest_pair(
    pair: str,
    daily_bars: list[dict[str, Any]],
    config: AppConfig,
    news_filter: EconomicNewsFilter | None = None,
    *,
    min_sl_pips: float = 0.0,
) -> tuple[list[TradeRecord], dict[str, int]]:
    """
    Run the Momentum+Carry strategy on historical Daily bars for one pair.

    Mirrors the live flow: momentum detection on the rolling lookback window,
    carry filter, then bracket order sizing.  One trade per Daily bar maximum.
    """
    trades: list[TradeRecord] = []
    pip_size = PIP_SIZES.get(pair, DEFAULT_PIP_SIZE)

    try:
        from alphaedge.core import momentum_detector, order_manager, risk_manager
    except ImportError:
        logger.warning(f"ALPHAEDGE: Cython not compiled — skipping backtest for {pair}")
        return trades, {}

    from alphaedge.engine.carry_signal import get_carry_bias

    lookback = config.trading.momentum_lookback_days
    fast = config.trading.momentum_fast_period
    slow = config.trading.momentum_slow_period
    adx_p = config.trading.momentum_adx_period
    adx_t = config.trading.momentum_adx_threshold
    carry_enabled = config.trading.carry_enabled
    carry_rates = config.trading.carry_rates

    # Pre-build bar arrays once
    _all_highs = np.array([b["high"] for b in daily_bars], dtype=np.float64)
    _all_lows = np.array([b["low"] for b in daily_bars], dtype=np.float64)
    _all_atrs = np.array(
        [_compute_atr_pips(daily_bars, i, pip_size) for i in range(len(daily_bars))],
        dtype=np.float64,
    )

    excluded_days = set(config.trading.excluded_days)
    max_trades_per_day = config.trading.max_trades_per_day
    max_daily_loss_pct = config.trading.max_daily_loss_pct
    starting_equity = config.trading.starting_equity
    _adx_rejections: int = 0
    _carry_rejections: int = 0
    _regime_rejections: int = 0
    _day_limit_rejections: int = 0
    _daily_loss_rejections: int = 0
    _ml_rejections: int = 0
    _bars_processed: int = 0
    _trades_by_day: dict[str, int] = {}
    _daily_pnl_usd: dict[str, float] = {}  # daily loss circuit breaker

    # ML filter: walk-forward logistic regression (trained on past realized trades)
    _ml_filter: MLSignalFilter | None = None
    _ml_features_buf: list[list[float]] = []
    _ml_labels_buf: list[int] = []
    _ml_min_samples: int = config.trading.ml_filter_min_samples
    if config.trading.ml_filter_enabled:
        from alphaedge.engine._experimental.ml_filter import MLSignalFilter

        _ml_filter = MLSignalFilter()

    for bar_index in range(lookback, len(daily_bars)):
        bar = daily_bars[bar_index]
        bar_dt = bar.get("datetime")

        if excluded_days and bar_dt is not None:
            if hasattr(bar_dt, "weekday") and bar_dt.weekday() in excluded_days:
                continue

        _bars_processed += 1
        window = daily_bars[bar_index - lookback : bar_index + 1]
        signal = momentum_detector.detect_momentum(
            bars=window,
            fast_period=fast,
            slow_period=slow,
            adx_period=adx_p,
            adx_threshold=adx_t,
        )
        if signal is None or not signal.get("detected"):
            _adx_rejections += 1
            continue

        # Carry filter (optional)
        if carry_enabled and carry_rates:
            carry = get_carry_bias(pair=pair, rates=carry_rates)
            if carry.is_valid and carry.direction != "NEUTRAL":
                mom_dir: int = int(signal.get("direction", 0))
                if (mom_dir == 1 and carry.direction == "SHORT") or (
                    mom_dir == -1 and carry.direction == "LONG"
                ):
                    _carry_rejections += 1
                    continue

        # Regime gate: block ranging/choppy sessions (low_vol) for momentum signals
        if config.regime_gate_enabled:
            regime = _compute_regime_label(daily_bars, bar_index, pip_size)
            if regime == config.regime_block_on:
                _regime_rejections += 1
                continue

        # ML filter gate — trained incrementally on past trades (no lookahead)
        _ml_feats: list[float] | None = None
        if _ml_filter is not None:
            _ml_feats = _extract_signal_features(
                signal, bar_dt, _all_atrs, bar_index, carry_rates, pair
            )
            if _ml_filter.is_trained:
                _ml_pred = _ml_filter.predict(_ml_feats)
                if not _ml_pred.passed:
                    _ml_rejections += 1
                    continue

        bar_trades = _collect_daily_trades(
            pair,
            daily_bars,
            bar_index,
            signal,
            pip_size,
            config,
            risk_manager,
            order_manager,
            _all_highs,
            _all_lows,
            news_filter=news_filter,
            min_sl_pips=min_sl_pips,
            carry_rates=carry_rates,
            session_end_action=config.trading.session_end_action,
        )
        if bar_trades:
            day_key = (
                bar_dt.strftime("%Y-%m-%d")
                if bar_dt is not None and hasattr(bar_dt, "strftime")
                else str(bar_index)
            )
            # Daily loss circuit breaker — mirrors live check_daily_limit()
            daily_loss = _daily_pnl_usd.get(day_key, 0.0)
            max_loss_usd = starting_equity * max_daily_loss_pct / 100.0
            if daily_loss <= -max_loss_usd:
                _daily_loss_rejections += len(bar_trades)
                continue

            _trades_by_day[day_key] = _trades_by_day.get(day_key, 0) + len(bar_trades)
            if _trades_by_day[day_key] - len(bar_trades) >= max_trades_per_day:
                _day_limit_rejections += len(bar_trades)
                continue

            # Accumulate daily P&L for circuit breaker tracking
            for t in bar_trades:
                _daily_pnl_usd[day_key] = _daily_pnl_usd.get(day_key, 0.0) + t.pnl_usd
        # Store ATR at entry for each trade (used by ATR-scaling in sizing)
        atr_at_bar = float(_all_atrs[bar_index])
        for t in bar_trades:
            t.atr_pips = atr_at_bar
        trades.extend(bar_trades)
        # Feed realized outcomes back into ML training buffer (no lookahead)
        if _ml_filter is not None and _ml_feats is not None and bar_trades:
            for t in bar_trades:
                _ml_features_buf.append(_ml_feats)
                _ml_labels_buf.append(1 if t.outcome == "win" else 0)
            if len(_ml_labels_buf) >= _ml_min_samples:
                _ml_filter.train(_ml_features_buf, _ml_labels_buf)

    logger.info(
        "ALPHAEDGE BACKTEST: {} \u2014 {} bars, {} signals "
        "(ADX={}, carry={}, regime={}, day-limit={}, daily-loss={}, ml={}, trades={})",
        pair,
        _bars_processed,
        _bars_processed - _adx_rejections,
        _adx_rejections,
        _carry_rejections,
        _regime_rejections,
        _day_limit_rejections,
        _daily_loss_rejections,
        _ml_rejections,
        len(trades),
    )
    rejection_counts = {
        "adx_gate": _adx_rejections,
        "carry_conflict": _carry_rejections,
        "regime_gate": _regime_rejections,
        "day_limit": _day_limit_rejections,
        "daily_loss_breaker": _daily_loss_rejections,
        "ml_filter": _ml_rejections,
    }
    return trades, rejection_counts


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
    rr_ratio: float = DEFAULT_RR_RATIO,
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

    pip_size = PIP_SIZES.get(pair, DEFAULT_PIP_SIZE)
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
    rr_ratio: float = DEFAULT_RR_RATIO,
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
