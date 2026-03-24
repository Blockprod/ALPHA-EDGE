"""Quick debug: print rejection reason for first 5 EURUSD signals."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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

cfg = load_config()
cache = BarDiskCache()
PAIR = "EURUSD"
pip_size = 0.0001
m1 = cache.load(PAIR, "1 min") or []
m5 = cache.load(PAIR, "5 mins") or []
print(f"M1={len(m1):,}  M5={len(m5):,}")

spec = SessionSpec(8, 0, 9, 0, "UTC")  # London Open
sessions = _group_bars_by_session(m1, m5, session_spec=spec)

found = 0
for session in sessions:
    m5_pre = session["m5_pre"]
    m1_idx = session["m1_indices"]
    if len(m5_pre) < 2 or len(m1_idx) < 4:
        continue
    if not _session_passes_fcr_quality_gate(m5_pre, 0.5):
        continue
    fcr_result = fcr_detector.detect_fcr(
        candles_data=m5_pre, min_range_pips=8.0, pip_size=pip_size
    )
    if not fcr_result:
        continue
    first_3 = [m1[i] for i in m1_idx[:3]]
    m1_pre = session.get("m1_pre", [])
    if not m1_pre or not first_3:
        continue
    gap_result = gap_detector.detect_gap(
        pre_session_m1=m1_pre,
        session_m1=first_3,
        pre_close=m5_pre[-1]["close"],
        session_open=m1[m1_idx[0]]["open"],
        atr_period=DEFAULT_ATR_PERIOD,
        min_atr_ratio=1.0,
    )
    if not gap_result or not gap_result.get("detected"):
        continue
    session_m1 = [m1[i] for i in m1_idx]
    for li in range(3, len(session_m1)):
        eng = engulfing_detector.detect_engulfing(
            candles_data=session_m1[: li + 1],
            fcr_high=fcr_result["range_high"],
            fcr_low=fcr_result["range_low"],
            rr_ratio=cfg.trading.rr_ratio,
            pip_size=pip_size,
            volume_period=cfg.trading.volume_period,
            min_volume_ratio=DEFAULT_MIN_VOLUME_RATIO,
        )
        if not eng:
            continue
        pos = risk_manager.calculate_position_size(
            account_equity=cfg.trading.starting_equity,
            risk_pct=cfg.trading.risk_pct,
            sl_pips=eng["risk_pips"],
            pair=PAIR,
            pip_size=pip_size,
            lot_type=cfg.trading.lot_type,
            min_lots=0.01,
            max_lots=cfg.trading.max_lot_size,
            exchange_rate=0.0,
        )
        bar_time = session_m1[li].get("datetime")
        spread = compute_variable_slippage(bar_time, pair=PAIR)
        bracket = order_manager.create_bracket_order(
            direction=eng["signal"],
            entry_price=eng["entry_price"],
            stop_loss=eng["stop_loss"],
            take_profit=eng["take_profit"],
            lot_size=pos.get("lot_size", 0),
            pip_size=pip_size,
            spread_pips=spread,
            max_spread_pips=cfg.trading.max_spread_pips,
            min_rr=cfg.trading.rr_ratio * 0.9,
            min_lots=0.01,
            max_lots=10.0,
            adjust_for_spread=True,
        )
        print(f"\nDay {session['date']}  bar={li}  risk_pips={eng['risk_pips']:.2f}")
        print(f"  spread={spread:.2f}  max_spread={cfg.trading.max_spread_pips}")
        print(f"  pos_size → is_valid={pos.get('is_valid')}  lot={pos.get('lot_size')}")
        print(f"             full={pos}")
        print(f"  bracket  → is_valid={bracket.get('is_valid')}")
        print(f"             rejection={bracket.get('rejection_reason')}")
        print(f"             full={bracket}")
        found += 1
        break
    if found >= 5:
        break

print(f"\n{'=' * 60}")
print(f"Signals printed: {found}")
