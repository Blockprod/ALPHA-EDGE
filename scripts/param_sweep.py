# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : scripts/param_sweep.py
# DESCRIPTION  : Parameter sweep / grid-search for strategy tuning.
#                Loads cache once, runs _backtest_pair with varying
#                params via coordinate-descent, prints ranked results.
# PYTHON       : 3.11.9
# ============================================================
"""ALPHAEDGE — strategy parameter sweep (coordinate descent).

Usage:
    python scripts/param_sweep.py
"""

from __future__ import annotations

import copy
import itertools
import sys
import time
from pathlib import Path

# Make sure the project root is on sys.path when run directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alphaedge.config.loader import load_config
from alphaedge.engine.backtest import _backtest_pair
from alphaedge.engine.backtest_stats import _apply_equity_sizing, compute_stats
from alphaedge.engine.data_feed import BarDiskCache

# ------------------------------------------------------------------
# Config + data — loaded ONCE
# ------------------------------------------------------------------
print("Loading config and cache data…", flush=True)
_t0 = time.perf_counter()
_config = load_config()
_cache = BarDiskCache()
_PAIRS = _config.trading.pairs

_bars: dict[str, tuple[list, list]] = {}
for _pair in _PAIRS:
    _m1 = _cache.load(_pair, "1 min") or []
    _m5 = _cache.load(_pair, "5 mins") or []
    _bars[_pair] = (_m1, _m5)
    print(f"  {_pair} M1={len(_m1):,} M5={len(_m5):,}")

print(f"Data loaded in {time.perf_counter() - _t0:.1f}s\n", flush=True)


# ------------------------------------------------------------------
# Helper
# ------------------------------------------------------------------
def _run(
    min_atr_ratio: float,
    min_range_pips: float,
    min_volume_ratio: float,
    rr_ratio: float,
    min_body_ratio: float,
    max_wick_ratio: float,
    min_sl_pips: float = 0.0,
) -> dict:
    cfg = copy.deepcopy(_config)
    cfg.trading.rr_ratio = rr_ratio
    cfg.trading.min_body_ratio = min_body_ratio
    cfg.trading.max_wick_ratio = max_wick_ratio

    all_trades = []
    for pair in _PAIRS:
        m1, m5 = _bars[pair]
        trades = _backtest_pair(
            pair,
            m1,
            m5,
            cfg,
            min_atr_ratio=min_atr_ratio,
            min_range_pips=min_range_pips,
            min_volume_ratio=min_volume_ratio,
            min_sl_pips=min_sl_pips,
        )
        all_trades.extend(trades)

    if len(all_trades) < 20:
        return {}  # not enough data to be meaningful

    # Apply compound equity sizing BEFORE computing stats — required for
    # accurate pnl_usd, drawdown %, and sharpe_equity
    _apply_equity_sizing(all_trades, cfg.trading.starting_equity, cfg.trading.risk_pct)
    stats = compute_stats(all_trades, cfg.trading.starting_equity)
    return {
        "min_atr": min_atr_ratio,
        "min_rng": min_range_pips,
        "min_vol": min_volume_ratio,
        "rr": rr_ratio,
        "body": min_body_ratio,
        "wick": max_wick_ratio,
        "sl_mn": min_sl_pips,
        "n": stats.total_trades,
        "wr": stats.winrate,
        "pf": stats.profit_factor,
        "sh_p": stats.sharpe_ratio,  # pips-based (signal quality)
        "sh_$": stats.sharpe_equity,  # equity %-based (real return) ← sort key
        "dd": stats.max_drawdown_pct,
        "ret": stats.total_pnl_usd / cfg.trading.starting_equity * 100,
    }


def _print_header():
    print(
        f"{'atr':>5} {'rng':>5} {'vol':>5} {'rr':>4} {'body':>5} {'wick':>5} "
        f"{'sl_mn':>5} {'n':>5} {'wr%':>6} {'pf':>5} {'sh_p':>6} {'sh_$':>6} "
        f"{'dd%':>6} {'ret%':>6}"
    )
    print("-" * 86)


def _print_row(r: dict):
    print(
        f"{r['min_atr']:>5.1f} {r['min_rng']:>5.1f} {r['min_vol']:>5.2f} "
        f"{r['rr']:>4.1f} {r['body']:>5.2f} {r['wick']:>5.1f} "
        f"{r.get('sl_mn', 0.0):>5.1f} "
        f"{r['n']:>5d} {r['wr']:>6.1f} {r['pf']:>5.2f} "
        f"{r['sh_p']:>6.2f} {r['sh_$']:>+6.2f} "
        f"{r['dd']:>6.1f} {r.get('ret', 0.0):>+6.2f}"
    )


# ==================================================================
# ROUND 1 — Sweep min_atr_ratio × min_range_pips
#            (volume=1.2, rr=3.0, body=0.3, wick=2.0)
# ==================================================================
print("NOTE: Sorting by sh_$ (equity Sharpe = real risk-adjusted return).")
print("      sh_p = pips Sharpe (signal quality only, ignores spread cost).")
print()
print("=" * 86)
print("ROUND 1 — min_atr_ratio x min_range_pips")
print("=" * 86)
_print_header()

R1_ATR = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
R1_RANGE = [5.0, 8.0, 10.0, 12.0, 15.0]

r1_results: list[dict] = []
for atr, rng in itertools.product(R1_ATR, R1_RANGE):
    r = _run(atr, rng, 1.2, 3.0, 0.3, 2.0)
    if r:
        r1_results.append(r)
        _print_row(r)

r1_results.sort(key=lambda x: x["sh_$"], reverse=True)
best_r1 = r1_results[0] if r1_results else {}
best_atr = best_r1.get("min_atr", 1.5)
best_rng = best_r1.get("min_rng", 5.0)

print()
print(
    f">>> R1 best: min_atr={best_atr}, min_rng={best_rng} "
    f"(sh_$={best_r1.get('sh_$', 0):.2f}, pf={best_r1.get('pf', 0):.2f}, "
    f"wr={best_r1.get('wr', 0):.1f}%)"
)

# ==================================================================
# ROUND 2 — Sweep min_volume_ratio × rr_ratio
#            (best atr+range from R1; body=0.3, wick=2.0)
# ==================================================================
print()
print("=" * 86)
print("ROUND 2 — min_volume_ratio x rr_ratio")
print("=" * 86)
_print_header()

R2_VOL = [1.0, 1.2, 1.5, 1.8, 2.0, 2.5]
R2_RR = [2.0, 2.5, 3.0, 3.5, 4.0]

r2_results: list[dict] = []
for vol, rr in itertools.product(R2_VOL, R2_RR):
    r = _run(best_atr, best_rng, vol, rr, 0.3, 2.0)
    if r:
        r2_results.append(r)
        _print_row(r)

r2_results.sort(key=lambda x: x["sh_$"], reverse=True)
best_r2 = r2_results[0] if r2_results else best_r1
best_vol = best_r2.get("min_vol", 1.2)
best_rr = best_r2.get("rr", 3.0)

print()
print(
    f">>> R2 best: min_vol={best_vol}, rr={best_rr} "
    f"(sh_$={best_r2.get('sh_$', 0):.2f}, pf={best_r2.get('pf', 0):.2f}, "
    f"wr={best_r2.get('wr', 0):.1f}%)"
)

# ==================================================================
# ROUND 3 — Sweep min_body_ratio × max_wick_ratio
#            (best params from R1+R2)
# ==================================================================
print()
print("=" * 86)
print("ROUND 3 — min_body_ratio x max_wick_ratio")
print("=" * 86)
_print_header()

R3_BODY = [0.2, 0.3, 0.4, 0.5, 0.6]
R3_WICK = [1.0, 1.5, 2.0, 2.5, 3.0]

r3_results: list[dict] = []
for body, wick in itertools.product(R3_BODY, R3_WICK):
    r = _run(best_atr, best_rng, best_vol, best_rr, body, wick)
    if r:
        r3_results.append(r)
        _print_row(r)

r3_results.sort(key=lambda x: x["sh_$"], reverse=True)
best_r3 = r3_results[0] if r3_results else best_r2
best_body = best_r3.get("body", 0.3)
best_wick = best_r3.get("wick", 2.0)

print()
print(
    f">>> R3 best: body={best_body}, wick={best_wick} "
    f"(sh_$={best_r3.get('sh_$', 0):.2f}, pf={best_r3.get('pf', 0):.2f}, "
    f"wr={best_r3.get('wr', 0):.1f}%)"
)

# ==================================================================
# ROUND 4 — Sweep min_sl_pips  (spread/SL ratio control)
#            (best params from R1+R2+R3)
# ==================================================================
print()
print("=" * 86)
print("ROUND 4 — min_sl_pips  [spread cost control: reject signals with SL < X pips]")
print("=" * 86)
_print_header()

# avg sl=9 pips, spread~1.5 pips. Force spread < 30/20/15/10% of SL.
R4_MINSL = [0.0, 5.0, 8.0, 10.0, 12.0, 15.0, 18.0, 20.0]

r4_results: list[dict] = []
for sl_mn in R4_MINSL:
    r = _run(
        best_atr,
        best_rng,
        best_vol,
        best_rr,
        best_body,
        best_wick,
        min_sl_pips=sl_mn,
    )
    if r:
        r4_results.append(r)
        _print_row(r)

r4_results.sort(key=lambda x: x["sh_$"], reverse=True)
best_r4 = r4_results[0] if r4_results else best_r3
best_sl_mn = best_r4.get("sl_mn", 0.0)

print()
print(
    f">>> R4 best: min_sl_pips={best_sl_mn} "
    f"(sh_$={best_r4.get('sh_$', 0):.2f}, pf={best_r4.get('pf', 0):.2f}, "
    f"wr={best_r4.get('wr', 0):.1f}%, ret={best_r4.get('ret', 0):.2f}%)"
)

# ==================================================================
# FINAL — Top 15 overall (all rounds merged & re-ranked by sh_$)
# ==================================================================
all_results = r1_results + r2_results + r3_results + r4_results
all_results.sort(key=lambda x: x["sharpe"], reverse=True)
# Deduplicate exact-same param combos
seen: set[tuple] = set()
unique: list[dict] = []
for r in all_results:
    key = (
        r["min_atr"],
        r["min_rng"],
        r["min_vol"],
        r["rr"],
        r["body"],
        r["wick"],
        r.get("sl_mn", 0.0),
    )
    if key not in seen:
        seen.add(key)
        unique.append(r)
unique.sort(key=lambda x: x["sh_$"], reverse=True)
# Filter to combos with enough trades for statistical significance
unique_sig = [r for r in unique if r["n"] >= 50]
print()
print("=" * 86)
print("TOP 15 (ALL rounds, sorted by sh_$ = equity Sharpe, n>=50)")
print("=" * 86)
_print_header()
for r in (unique_sig or unique)[:15]:
    _print_row(r)

print()
print("TOP 5 (ALL rounds, all n, best sh_$ -- may include small samples):")
_print_header()
for r in unique[:5]:
    _print_row(r)

best = (unique_sig or unique)[0] if (unique_sig or unique) else {}
print()
print("=" * 86)
print("RECOMMENDED PARAMETERS:")
print(f"  volatility.min_atr_ratio  : {best.get('min_atr', 1.5)}")
print(f"  structure.min_range_pips  : {best.get('min_rng', 5.0)}")
print(f"  pattern.min_volume_ratio  : {best.get('min_vol', 1.2)}")
print(f"  trading.rr_ratio          : {best.get('rr', 3.0)}")
print(f"  engulfing.min_body_ratio  : {best.get('body', 0.3)}")
print(f"  engulfing.max_wick_ratio  : {best.get('wick', 2.0)}")
print(f"  execution.min_sl_pips     : {best.get('sl_mn', 0.0)}")
print(
    f"  -> sh_$={best.get('sh_$', 0):.2f}  sh_p={best.get('sh_p', 0):.2f}  "
    f"PF={best.get('pf', 0):.2f}  WR={best.get('wr', 0):.1f}%  "
    f"N={best.get('n', 0)}  DD={best.get('dd', 0):.1f}%  "
    f"ret={best.get('ret', 0):.2f}%"
)
print("=" * 86)
print(f"\nTotal sweep time: {time.perf_counter() - _t0:.0f}s")
