# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : scripts/_cv_sweep.py
# DESCRIPTION  : Focused sweep on fcr_range_cv_max.
#                Finds the optimal CV filter value per pair and globally.
#                Values tested: 0.0 (disabled) → 2.0 (permissive), 17 steps.
# PYTHON       : 3.11.9
# ============================================================
"""ALPHAEDGE — fcr_range_cv_max sweep.

Usage:
    python scripts/_cv_sweep.py
"""

from __future__ import annotations

import copy
import sys
import time
from pathlib import Path

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

_bars: dict[str, list] = {}
for _pair in _PAIRS:
    _daily = _cache.load(_pair, "1 day") or []
    _bars[_pair] = _daily
    print(f"  {_pair} daily={len(_daily):,}")

print(f"Data loaded in {time.perf_counter() - _t0:.1f}s\n", flush=True)

# ------------------------------------------------------------------
# CV values to test
# 0.0 = disabled (all sessions pass)
# 0.3 = very strict  (only very uniform consolidations)
# 0.5 = strict       (current value — suspect)
# 0.7 = moderate
# 1.0 = permissive
# 1.5 = very permissive
# 2.0 = almost all sessions pass
# ------------------------------------------------------------------
CV_VALUES = [0.0, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2, 1.5, 2.0]


# ------------------------------------------------------------------
# Runner — per-pair results for breakdown
# ------------------------------------------------------------------
def _run_all(cv: float) -> dict:
    cfg = copy.deepcopy(_config)
    cfg.trading.fcr_range_cv_max = cv

    all_trades = []
    pair_results: dict[str, dict] = {}

    for pair in _PAIRS:
        trades, _rejected = _backtest_pair(pair, _bars[pair], cfg)
        all_trades.extend(trades)
        if trades:
            _apply_equity_sizing(
                trades, cfg.trading.starting_equity, cfg.trading.risk_pct
            )
            s = compute_stats(trades, cfg.trading.starting_equity)
            pair_results[pair] = {
                "n": s.total_trades,
                "wr": s.winrate,
                "pf": s.profit_factor,
                "sh_$": s.sharpe_equity,
                "dd": s.max_drawdown_pct,
                "ret": s.total_pnl_usd / cfg.trading.starting_equity * 100,
            }
        else:
            pair_results[pair] = {
                "n": 0,
                "wr": 0.0,
                "pf": 0.0,
                "sh_$": 0.0,
                "dd": 0.0,
                "ret": 0.0,
            }

    # Global stats
    if len(all_trades) < 5:
        return {
            "cv": cv,
            "n": 0,
            "wr": 0.0,
            "pf": 0.0,
            "sh_$": -99.0,
            "dd": 100.0,
            "ret": -100.0,
            "pairs": pair_results,
        }

    _apply_equity_sizing(all_trades, cfg.trading.starting_equity, cfg.trading.risk_pct)
    s = compute_stats(all_trades, cfg.trading.starting_equity)
    return {
        "cv": cv,
        "n": s.total_trades,
        "wr": s.winrate,
        "pf": s.profit_factor,
        "sh_$": s.sharpe_equity,
        "dd": s.max_drawdown_pct,
        "ret": s.total_pnl_usd / cfg.trading.starting_equity * 100,
        "pairs": pair_results,
    }


# ------------------------------------------------------------------
# Sweep
# ------------------------------------------------------------------
print("=" * 80)
print("ALPHAEDGE — fcr_range_cv_max sweep")
print(f"Pairs : {', '.join(_PAIRS)}")
print(f"Values: {CV_VALUES}")
print("=" * 80)

# Header
header_cv = f"{'cv_max':>7}"
header_global = f"{'n':>5} {'wr%':>6} {'pf':>5} {'sh_$':>6} {'dd%':>6} {'ret%':>7}"
pair_headers = "  ".join(f"{p:>8}(n,sh_$)" for p in _PAIRS)
print(f"\n{header_cv}  {header_global}  {pair_headers}")
print("-" * 110)

results: list[dict] = []

for cv in CV_VALUES:
    t_start = time.perf_counter()
    r = _run_all(cv)
    elapsed = time.perf_counter() - t_start
    results.append(r)

    pair_cols = "  ".join(
        f"{r['pairs'].get(p, {}).get('n', 0):>4}T "
        f"{r['pairs'].get(p, {}).get('sh_$', 0.0):>+5.2f}"
        for p in _PAIRS
    )

    disabled = " ← DISABLED" if cv == 0.0 else ""
    print(
        f"{cv:>7.2f}  {r['n']:>5} {r['wr']:>6.1f} {r['pf']:>5.2f} "
        f"{r['sh_$']:>+6.2f} {r['dd']:>6.2f} {r['ret']:>+7.2f}%"
        f"  {pair_cols}  [{elapsed:.1f}s]{disabled}"
    )

# ------------------------------------------------------------------
# Ranked results (global Sharpe equity)
# ------------------------------------------------------------------
valid = [r for r in results if r["n"] >= 10]
valid.sort(key=lambda x: x["sh_$"], reverse=True)

print("\n" + "=" * 80)
print("RANKED RESULTS (n ≥ 10 trades, sorted by Sharpe equity)")
print("=" * 80)
print(
    f"{'rank':>4} {'cv_max':>7} {'n':>5} {'wr%':>6} {'pf':>5}"
    f" {'sh_$':>6} {'dd%':>6} {'ret%':>7}"
)
print("-" * 60)
for i, r in enumerate(valid[:10], 1):
    marker = " ◄ BEST" if i == 1 else ""
    print(
        f"{i:>4} {r['cv']:>7.2f} {r['n']:>5} {r['wr']:>6.1f} "
        f"{r['pf']:>5.2f} {r['sh_$']:>+6.2f} {r['dd']:>6.2f}"
        f" {r['ret']:>+7.2f}%{marker}"
    )

# ------------------------------------------------------------------
# Per-pair breakdown for best value
# ------------------------------------------------------------------
if valid:
    best = valid[0]
    print(f"\n{'=' * 80}")
    print(f"BEST VALUE: fcr_range_cv_max = {best['cv']}")
    print(f"{'=' * 80}")
    print(
        f"{'Pair':>8} {'N':>5} {'WR%':>6} {'PF':>5}"
        f" {'Sharpe$':>8} {'DD%':>6} {'Ret%':>7}"
    )
    print("-" * 50)
    for pair in _PAIRS:
        p = best["pairs"].get(pair, {})
        print(
            f"{pair:>8} {p.get('n', 0):>5} {p.get('wr', 0.0):>6.1f} "
            f"{p.get('pf', 0.0):>5.2f} {p.get('sh_$', 0.0):>+8.2f} "
            f"{p.get('dd', 0.0):>6.2f} {p.get('ret', 0.0):>+7.2f}%"
        )

    print("\n→ config.yaml update:")
    print(f"  fcr_range_cv_max: {best['cv']}")
    print("\nRun the backtest again after updating config.yaml to confirm.")
