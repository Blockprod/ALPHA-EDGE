# ============================================================
# PROJECT      : ALPHAEDGE — Swing Trading Bot
# FILE         : alphaedge/engine/backtest_filters.py
# DESCRIPTION  : Backtest session grouping and trade filter functions
# PYTHON       : 3.11.9
# ============================================================
"""ALPHAEDGE — Backtest trade filters: session grouping and correlation/limit filters.

Contains helper functions for grouping Daily bars into trading sessions and
applying post-simulation filters (USD correlation, global session limits).
Extracted from backtest.py to keep module size manageable.  All public
symbols are re-exported via backtest.py for backward compatibility.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from alphaedge.config.constants import (
    SESSION_END_HOUR,
    SESSION_END_MINUTE,
    SESSION_START_HOUR,
    SESSION_START_MINUTE,
)
from alphaedge.config.loader import SessionSpec
from alphaedge.engine.backtest_types import TradeRecord
from alphaedge.engine.usd_exposure import usd_direction
from alphaedge.utils.logger import get_logger

logger = get_logger()


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
# USD correlation filter
# ------------------------------------------------------------------
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
            d = usd_direction(t.pair, int(t.direction))
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


# ------------------------------------------------------------------
# Global session trade limit
# ------------------------------------------------------------------
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
