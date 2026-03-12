"""Final optimisation for atr=2.0, rng=8.0 — writes to alphaedge/logs/opt.txt."""

import copy
import sys

sys.path.insert(0, ".")

import os

os.makedirs("alphaedge/logs", exist_ok=True)
_f = open("alphaedge/logs/opt.txt", "w", encoding="utf-8")


def w(s=""):
    print(s)
    print(s, file=_f)
    _f.flush()


from alphaedge.config.loader import load_config  # noqa: E402
from alphaedge.engine.backtest import _backtest_pair  # noqa: E402
from alphaedge.engine.backtest_stats import (  # noqa: E402
    _apply_equity_sizing,
    compute_stats,
)
from alphaedge.engine.data_feed import BarDiskCache  # noqa: E402

cfg = load_config()
cache = BarDiskCache()
pairs = cfg.trading.pairs
bars = {p: (cache.load(p, "1 min") or [], cache.load(p, "5 mins") or []) for p in pairs}


def run(atr, rng, vol, rr, body, wick):
    c = copy.deepcopy(cfg)
    c.trading.rr_ratio = rr
    c.trading.min_body_ratio = body
    c.trading.max_wick_ratio = wick
    t = []
    for p in pairs:
        m1, m5 = bars[p]
        t += _backtest_pair(
            p,
            m1,
            m5,
            c,
            min_atr_ratio=atr,
            min_range_pips=rng,
            min_volume_ratio=vol,
        )
    if len(t) < 8:
        return None
    _apply_equity_sizing(t, c.trading.starting_equity, c.trading.risk_pct)
    s = compute_stats(t, c.trading.starting_equity)
    return {
        "n": s.total_trades,
        "wr": s.winrate,
        "pf": s.profit_factor,
        "shp": s.sharpe_ratio,
        "she": s.sharpe_equity,
        "dd": s.max_drawdown_pct,
        "ret": s.total_pnl_usd / c.trading.starting_equity * 100,
    }


# ── R2: vol x rr ─────────────────────────────────────────────────────────────
w("R2: min_volume_ratio x rr_ratio  (base: atr=2.0 rng=8.0 body=0.30 wick=2.0)")
w("vol   rr    n    wr%    pf   sh_p  sh_$   dd%   ret%")
w("-" * 58)
best_she, best_r2 = -999.0, {}
for vol in [0.8, 1.0, 1.2, 1.5, 2.0]:
    for rr in [2.0, 2.5, 3.0, 3.5, 4.0]:
        r = run(2.0, 8.0, vol, rr, 0.30, 2.0)
        if r:
            w(
                f"{vol:4.1f} {rr:4.1f} {r['n']:4d} {r['wr']:6.1f}"
                f" {r['pf']:5.2f} {r['shp']:6.2f} {r['she']:+5.2f}"
                f" {r['dd']:6.1f} {r['ret']:+6.2f}"
            )
            if r["she"] > best_she:
                best_she = r["she"]
                best_r2 = {"vol": vol, "rr": rr, **r}
        else:
            w(f"{vol:4.1f} {rr:4.1f}   --")
best_vol = best_r2.get("vol", 1.2)
best_rr = best_r2.get("rr", 3.0)
w(f"\nR2 best: vol={best_vol}, rr={best_rr}  she={best_she:+.2f}")

# ── R3: body x wick ───────────────────────────────────────────────────────────
w()
w("R3: min_body_ratio x max_wick_ratio  (base: best R2 params)")
w("body  wick   n    wr%    pf   sh_p  sh_$   dd%   ret%")
w("-" * 58)
best_she3, best_r3 = -999.0, {}
for body in [0.10, 0.20, 0.30, 0.40]:
    for wick in [0.5, 1.0, 1.5, 2.0, 3.0]:
        r = run(2.0, 8.0, best_vol, best_rr, body, wick)
        if r:
            w(
                f"{body:5.2f} {wick:4.1f} {r['n']:4d} {r['wr']:6.1f}"
                f" {r['pf']:5.2f} {r['shp']:6.2f} {r['she']:+5.2f}"
                f" {r['dd']:6.1f} {r['ret']:+6.2f}"
            )
            if r["she"] > best_she3:
                best_she3 = r["she"]
                best_r3 = {"body": body, "wick": wick, **r}
        else:
            w(f"{body:5.2f} {wick:4.1f}   --")
best_body = best_r3.get("body", 0.30)
best_wick = best_r3.get("wick", 2.0)
w(f"\nR3 best: body={best_body}, wick={best_wick}  she={best_she3:+.2f}")

# ── Baseline comparison ───────────────────────────────────────────────────────
w()
w("=== FINAL RECOMMENDATIONS ===")
w("  volatility.min_atr_ratio  : 2.0")
w("  structure.min_range_pips  : 8.0")
w(f"  pattern.min_volume_ratio  : {best_vol}")
w(f"  trading.rr_ratio          : {best_rr}")
w(f"  engulfing.min_body_ratio  : {best_body}")
w(f"  engulfing.max_wick_ratio  : {best_wick}")
final = run(2.0, 8.0, best_vol, best_rr, best_body, best_wick)
if final:
    w(
        f"  -> n={final['n']}  WR={final['wr']:.1f}%  PF={final['pf']:.2f}"
        f"  sh_$={final['she']:+.2f}  ret={final['ret']:+.2f}%"
        f"  DD={final['dd']:.1f}%"
    )
w("=" * 40)
_f.close()
