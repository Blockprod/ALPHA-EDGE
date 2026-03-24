# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : scripts/_eurusd_diag.py
# DESCRIPTION  : Diagnostic — EURUSD pipeline stage counts per session.
#                Sweeps min_atr_ratio on London Open to find optimal threshold.
# PYTHON       : 3.11.9
# ============================================================
"""ALPHAEDGE — EURUSD session + ATR threshold diagnostic.

Usage:
    python scripts/_eurusd_diag.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from alphaedge.config.constants import DEFAULT_ATR_PERIOD, DEFAULT_MIN_VOLUME_RATIO
from alphaedge.config.loader import SessionSpec, load_config
from alphaedge.core import (
    engulfing_detector,
    fcr_detector,
    gap_detector,
    order_manager,
    risk_manager,
)
from alphaedge.engine.backtest import _session_passes_fcr_quality_gate
from alphaedge.engine.backtest_filters import _group_bars_by_session
from alphaedge.engine.backtest_simulation import compute_variable_slippage
from alphaedge.engine.data_feed import BarDiskCache

# ------------------------------------------------------------------
# Load config + data
# ------------------------------------------------------------------
config = load_config()
cache = BarDiskCache()

PAIR = "EURUSD"
pip_size = 0.0001

print(f"Loading {PAIR} bars from cache…")
m1 = cache.load(PAIR, "1 min") or []
m5 = cache.load(PAIR, "5 mins") or []
print(f"  M1={len(m1):,}  M5={len(m5):,}")

SESSIONS = {
    "NYSE  (09:30-10:30 ET )": SessionSpec(9, 30, 10, 30, "America/New_York"),
    "London(08:00-09:00 UTC)": SessionSpec(8, 0, 9, 0, "UTC"),
}

# ------------------------------------------------------------------
# Config params
# ------------------------------------------------------------------
min_range_pips = config.trading.min_range_pips_by_pair.get(
    PAIR, config.trading.min_range_pips
)
fcr_cv_max = config.trading.fcr_range_cv_max
excluded_days = set(config.trading.excluded_days)
atr_period = config.trading.atr_period

# ATR thresholds to sweep on London Open
ATR_THRESHOLDS = [0.8, 1.0, 1.2, 1.4, 1.5, 1.6, 1.7, 1.8, 2.0]


def _count_pipeline(
    sessions: list[dict],
    min_atr: float,
) -> tuple[int, int, int, int, int, int, int]:
    """Count sessions surviving each pipeline stage, including validation.

    Returns: (total, bars, cv, fcr, gap, engulfing, validated)
    Mirrors _backtest_pair + _detect_session_gap + _validate_backtest_signal.
    """
    _m1_highs = np.array([b["high"] for b in m1], dtype=np.float64)  # noqa: F841
    n_total = n_bars = n_cv = n_fcr = n_gap = n_engulf = n_valid = 0
    for session in sessions:
        n_total += 1
        if excluded_days and session["date"].weekday() in excluded_days:
            continue
        m5_pre = session["m5_pre"]
        m1_idx = session["m1_indices"]
        if len(m5_pre) < 2 or len(m1_idx) < 4:
            continue
        n_bars += 1
        if not _session_passes_fcr_quality_gate(m5_pre, fcr_cv_max):
            continue
        n_cv += 1
        fcr_result = fcr_detector.detect_fcr(
            candles_data=m5_pre,
            min_range_pips=min_range_pips,
            pip_size=pip_size,
        )
        if not fcr_result:
            continue
        n_fcr += 1
        # Exact backtest logic: M5 close and 3 M1 bars
        m1_pre = session.get("m1_pre", [])
        first_3_m1 = [m1[i] for i in m1_idx[:3]]
        if not m1_pre or not first_3_m1 or not m5_pre:
            continue
        pre_close = m5_pre[-1]["close"]
        session_open = m1[m1_idx[0]]["open"]
        try:
            gap_result = gap_detector.detect_gap(
                pre_session_m1=m1_pre,
                session_m1=first_3_m1,
                pre_close=pre_close,
                session_open=session_open,
                atr_period=DEFAULT_ATR_PERIOD,
                min_atr_ratio=min_atr,
            )
        except Exception:  # noqa: BLE001
            continue
        if not gap_result or not gap_result.get("detected"):
            continue
        n_gap += 1
        # Engulfing + validation
        session_m1 = [m1[i] for i in m1_idx]
        for local_i in range(3, len(session_m1)):
            try:
                eng_result = engulfing_detector.detect_engulfing(
                    candles_data=session_m1[: local_i + 1],
                    fcr_high=fcr_result["range_high"],
                    fcr_low=fcr_result["range_low"],
                    rr_ratio=config.trading.rr_ratio,
                    pip_size=pip_size,
                    volume_period=config.trading.volume_period,
                    min_volume_ratio=DEFAULT_MIN_VOLUME_RATIO,
                )
            except Exception:  # noqa: BLE001
                continue
            if not eng_result:
                continue
            n_engulf += 1
            # Position sizing validation
            pos = risk_manager.calculate_position_size(
                account_equity=config.trading.starting_equity,
                risk_pct=config.trading.risk_pct,
                sl_pips=eng_result["risk_pips"],
                pair=PAIR,
                pip_size=pip_size,
                lot_type=config.trading.lot_type,
                min_lots=0.01,
                max_lots=config.trading.max_lot_size,
                exchange_rate=0.0,
            )
            if not pos.get("is_valid", False):
                break
            # Bracket validation
            bar_time = session_m1[local_i].get("datetime")
            spread_pips = compute_variable_slippage(bar_time, pair=PAIR)
            bracket = order_manager.create_bracket_order(
                direction=eng_result["signal"],
                entry_price=eng_result["entry_price"],
                stop_loss=eng_result["stop_loss"],
                take_profit=eng_result["take_profit"],
                lot_size=pos["lot_size"],
                pip_size=pip_size,
                spread_pips=spread_pips,
                max_spread_pips=config.trading.max_spread_pips,
                min_rr=config.trading.rr_ratio * 0.9,
                min_lots=0.01,
                max_lots=10.0,
                adjust_for_spread=True,
            )
            if bracket.get("is_valid", False):
                n_valid += 1
            break  # one signal per session max
    return n_total, n_bars, n_cv, n_fcr, n_gap, n_engulf, n_valid


# ------------------------------------------------------------------
# Run per session
# ------------------------------------------------------------------
print(f"\nParameters: min_range_pips={min_range_pips}, fcr_range_cv_max={fcr_cv_max}")
print(f"ATR thresholds tested: {ATR_THRESHOLDS}\n")

for sess_label, sess_spec in SESSIONS.items():
    sessions = _group_bars_by_session(m1, m5, session_spec=sess_spec)
    print("=" * 70)
    print(f"SESSION: {sess_label}  |  {len(sessions)} trading days")
    print("=" * 70)
    hdr = "  {:>8} {:>7} {:>6} {:>6} {:>6} {:>6} {:>6} {:>6}"
    print(hdr.format("atr_min", "total", "bars", "cv", "fcr", "gap", "eng", "valid"))
    sep = "  " + " ".join(["-" * w for w in [8, 7, 6, 6, 6, 6, 6, 6]])
    print(sep)
    for threshold in ATR_THRESHOLDS:
        counts = _count_pipeline(sessions, threshold)
        n_total, n_bars, n_cv, n_fcr, n_gap, n_eng, n_valid = counts
        marker = " ◄ current" if threshold == config.trading.min_atr_ratio else ""
        print(
            f"  {threshold:>8.1f} {n_total:>7} {n_bars:>6} {n_cv:>6}"
            f" {n_fcr:>6} {n_gap:>6} {n_eng:>6} {n_valid:>6}{marker}"
        )
    print()

print("→ Choose session + atr_min where gap column is ≥ 10 sessions.")
print("→ London Open + lower atr_ratio = more EURUSD signals.")
print("   Validate quality by running the full backtest after tuning.")
