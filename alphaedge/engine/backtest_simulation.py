# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/engine/backtest_simulation.py
# DESCRIPTION  : Trade simulation functions (slippage, SL/TP exit models)
# PYTHON       : 3.11.9
# ============================================================
"""ALPHAEDGE — Backtest trade simulation: variable slippage and exit models.

Contains the low-level computation functions for simulating single-trade
outcomes against M1 bar data.  Extracted from backtest.py to keep module
size manageable.  All public symbols are re-exported via backtest.py for
backward compatibility.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np

from alphaedge.config.constants import (
    BASE_SLIPPAGE_PIPS,
    BASE_SPREAD_BY_PAIR,
    BASE_SPREAD_PIPS,
    NEWS_SLIPPAGE_MULTIPLIER,
    NEWS_SPREAD_PIPS,
    NYSE_OPEN_SLIPPAGE_MULTIPLIER,
    NYSE_OPEN_SPREAD_PIPS,
    NYSE_OPEN_WINDOW_MINUTES,
    PIP_SIZES,
    SESSION_START_HOUR,
    SESSION_START_MINUTE,
)
from alphaedge.engine.backtest_types import TradeRecord

# ------------------------------------------------------------------
# Pair → (base currency, quote currency) mapping
# Used by compute_overnight_carry to look up rate differentials.
# ------------------------------------------------------------------
_PAIR_CURRENCIES: dict[str, tuple[str, str]] = {
    "EURUSD": ("EUR", "USD"),
    "GBPUSD": ("GBP", "USD"),
    "USDJPY": ("USD", "JPY"),
    "USDCHF": ("USD", "CHF"),
    "USDCAD": ("USD", "CAD"),
    "AUDUSD": ("AUD", "USD"),
    "NZDUSD": ("NZD", "USD"),
    "EURGBP": ("EUR", "GBP"),
    "EURJPY": ("EUR", "JPY"),
    "GBPJPY": ("GBP", "JPY"),
    "AUDJPY": ("AUD", "JPY"),
    "CHFJPY": ("CHF", "JPY"),
}


# ------------------------------------------------------------------
# Variable slippage model
# ------------------------------------------------------------------
# HYPOTHÈSE DE MODÉLISATION — Approuvée 2026-03-24
# Backtest : spread calibré par paire (BASE_SPREAD_BY_PAIR) + slippage
# variable selon contexte (ouverture NYSE, news). Live : spread réel IB
# via get_live_spread() + buffer fixe (DEFAULT_MARKET_SLIPPAGE_PIPS).
# Ces deux méthodes sont des approximations non équivalentes.
# Toute comparaison PnL backtest ↔ live nécessite une correction du
# coût de transaction estimée à ~0.5 pip additionnels côté backtest.
# Référence : tasks/audits/resultats/audit_pipeline_alphaedge.md — BLOC 4 — P-03
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
# Overnight carry model (swing trades held multiple days)
# ------------------------------------------------------------------
def compute_overnight_carry(
    pair: str,
    direction: int,
    days_held: int,
    rates: dict[str, float],
    lot_size: float,
    pip_size: float,
) -> float:
    """Return total overnight carry in pips for a swing trade.

    Positive value means the carry adds to P&L (favourable rate
    differential); negative means it subtracts (unfavourable).

    Parameters
    ----------
    pair : str
        Currency pair symbol (e.g. ``"AUDJPY"``).
    direction : int
        Trade direction: ``1`` = LONG, ``-1`` = SHORT.
    days_held : int
        Number of calendar days the position was open.
    rates : dict[str, float]
        Annualised interest rates in percent per currency, e.g.
        ``{"AUD": 4.35, "JPY": 0.10}``.
    lot_size : float
        Position size in lots (reserved for future USD-denominated carry;
        pips calculation below is size-independent).
    pip_size : float
        Pip size for the pair (e.g. 0.0001 for EURUSD, 0.01 for USDJPY).

    Returns
    -------
    float
        Total carry in pips.  Returns ``0.0`` if the pair is unknown or
        either currency rate is missing from *rates*.
    """
    if days_held <= 0 or pip_size <= 0:
        return 0.0
    currencies = _PAIR_CURRENCIES.get(pair.upper())
    if not currencies:
        return 0.0
    base, quote = currencies
    if base not in rates or quote not in rates:
        return 0.0
    # Positive differential → LONG earns carry, SHORT pays carry.
    differential = rates[base] - rates[quote]  # annualised %
    daily_carry_pips = differential * direction / 100.0 / 365.0 / pip_size
    # lot_size: unused for pip calculation, available for future USD P&L variant
    _ = lot_size
    return daily_carry_pips * days_held


# ------------------------------------------------------------------
# Simulate a single trade to its exit
# ------------------------------------------------------------------
def _simulate_trade_exit(
    trade: TradeRecord,
    bars: list[dict[str, Any]],
    entry_bar_idx: int,
    carry_rates: dict[str, float] | None = None,
    max_lookahead: int | None = None,
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
    carry_rates : dict | None
        Central-bank rates for overnight carry accrual on multi-day holds.
    max_lookahead : int | None
        Maximum number of bars to search after entry. ``None`` = no limit
        (default). Set to ``1`` to simulate ``session_end_action="close"``.

    Returns
    -------
    TradeRecord
        The trade with exit fields populated.
    """
    future = bars[entry_bar_idx + 1 :]
    if max_lookahead is not None:
        future = future[:max_lookahead]
    if not future:
        return _close_trade(
            trade,
            bars[entry_bar_idx]["close"],
            bars[entry_bar_idx],
            "timeout",
            carry_rates,
        )

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
        return _close_trade(
            trade, future[-1]["close"], future[-1], "timeout", carry_rates
        )
    if first_sl < first_tp:
        return _close_trade(
            trade, trade.stop_loss, future[first_sl], "loss", carry_rates
        )
    if first_tp < first_sl:
        return _close_trade(
            trade, trade.take_profit, future[first_tp], "win", carry_rates
        )
    # Both hit on the same bar — use bar direction to decide which was first
    bar = future[first_sl]
    if _sl_hit_first(trade, bar):
        return _close_trade(trade, trade.stop_loss, bar, "loss", carry_rates)
    return _close_trade(trade, trade.take_profit, bar, "win", carry_rates)


# ------------------------------------------------------------------
# Fast exit simulation using pre-built NumPy arrays (zero-copy)
# ------------------------------------------------------------------
def _simulate_trade_exit_fast(
    trade: TradeRecord,
    bars: list[dict[str, Any]],
    entry_bar_idx: int,
    all_highs: np.ndarray,
    all_lows: np.ndarray,
    carry_rates: dict[str, float] | None = None,
    max_lookahead: int | None = None,
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
    carry_rates : dict | None
        Central-bank rates for overnight carry accrual on multi-day holds.
    max_lookahead : int | None
        Maximum number of bars to search after entry. ``None`` = no limit
        (default). Set to ``1`` to simulate ``session_end_action="close"``.

    Returns
    -------
    TradeRecord
        The trade with exit fields populated.
    """
    start = entry_bar_idx + 1
    end = len(bars)
    if max_lookahead is not None:
        end = min(end, start + max_lookahead)
    if start >= len(bars):
        return _close_trade(
            trade,
            bars[entry_bar_idx]["close"],
            bars[entry_bar_idx],
            "timeout",
            carry_rates,
        )

    highs = all_highs[start:end]  # O(1) NumPy view — no copy
    lows = all_lows[start:end]

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
        # No SL/TP hit within search window — close at last searched bar
        timeout_bar = bars[end - 1]
        return _close_trade(
            trade, timeout_bar["close"], timeout_bar, "timeout", carry_rates
        )
    if first_sl < first_tp:
        return _close_trade(
            trade, trade.stop_loss, bars[start + first_sl], "loss", carry_rates
        )
    if first_tp < first_sl:
        return _close_trade(
            trade, trade.take_profit, bars[start + first_tp], "win", carry_rates
        )
    # Both hit on the same bar
    bar = bars[start + first_sl]
    if _sl_hit_first(trade, bar):
        return _close_trade(trade, trade.stop_loss, bar, "loss", carry_rates)
    return _close_trade(trade, trade.take_profit, bar, "win", carry_rates)


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
    carry_rates: dict[str, float] | None = None,
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
    carry_rates : dict | None
        Central-bank rates for overnight carry computation. If provided and
        the trade was held multiple days, carry P&L is added to pnl_pips.

    Returns
    -------
    TradeRecord
        Updated trade record.
    """
    pip_size = PIP_SIZES.get(trade.pair, 0.0001)
    trade.exit_price = exit_price
    trade.exit_time = bar.get("datetime")
    trade.outcome = outcome

    # Overnight carry accrual for multi-day positions
    if carry_rates and trade.exit_time is not None:
        entry_dt = trade.entry_time
        exit_dt = trade.exit_time
        if hasattr(entry_dt, "date") and hasattr(exit_dt, "date"):
            days_held = (exit_dt.date() - entry_dt.date()).days
        else:
            days_held = 0
        if days_held > 0:
            trade.carry_pips = compute_overnight_carry(
                pair=trade.pair,
                direction=trade.direction,
                days_held=days_held,
                rates=carry_rates,
                lot_size=1.0,
                pip_size=pip_size,
            )

    # P&L in pips (accounting for spread cost and overnight carry)
    raw_pnl = (exit_price - trade.entry_price) * trade.direction
    trade.pnl_pips = (raw_pnl / pip_size) - trade.spread_cost_pips + trade.carry_pips
    # pip_value for micro lot (1 000 units); for JPY pairs this is in JPY
    # — acceptable approximation for offline backtest without live FX rates
    pip_value = 1000.0 * pip_size
    trade.pnl_usd = trade.pnl_pips * pip_value
    return trade
