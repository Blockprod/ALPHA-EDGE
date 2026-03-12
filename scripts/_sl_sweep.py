"""Quick min_sl_pips sweep targeting the two best R1 param combos."""

import copy
import sys

sys.path.insert(0, ".")

_OUT = open("C:/Users/averr/sl_results.txt", "w", encoding="utf-8")


def _p(*args, **kw):  # print to stdout + file
    msg = " ".join(str(a) for a in args)
    print(msg)
    print(msg, file=_OUT)


from alphaedge.config.loader import load_config  # noqa: E402, I001
from alphaedge.engine.backtest import _backtest_pair  # noqa: E402
from alphaedge.engine.backtest_stats import _apply_equity_sizing, compute_stats  # noqa: E402
from alphaedge.engine.data_feed import BarDiskCache  # noqa: E402

cfg = load_config()
cache = BarDiskCache()
pairs = cfg.trading.pairs
bars = {p: (cache.load(p, "1 min") or [], cache.load(p, "5 mins") or []) for p in pairs}


def _run(atr, rng, vol, rr, body, wick, sl_mn=0.0):
    c = copy.deepcopy(cfg)
    c.trading.rr_ratio = rr
    c.trading.min_body_ratio = body
    c.trading.max_wick_ratio = wick
    trades = []
    for p in pairs:
        m1, m5 = bars[p]
        trades += _backtest_pair(
            p,
            m1,
            m5,
            c,
            min_atr_ratio=atr,
            min_range_pips=rng,
            min_volume_ratio=vol,
            min_sl_pips=sl_mn,
        )
    if len(trades) < 10:
        return None
    _apply_equity_sizing(trades, c.trading.starting_equity, c.trading.risk_pct)
    s = compute_stats(trades, c.trading.starting_equity)
    return {
        "n": s.total_trades,
        "wr": s.winrate,
        "pf": s.profit_factor,
        "sh_p": s.sharpe_ratio,
        "sh_e": s.sharpe_equity,
        "dd": s.max_drawdown_pct,
        "ret": s.total_pnl_usd / c.trading.starting_equity * 100,
    }


HDR = "sl_mn    n    wr%    pf   sh_p  sh_$    dd%   ret%"
FMT = (
    "{sl:5.1f} {n:4d} {wr:6.1f} {pf:5.2f} {shp:6.2f} {she:+5.2f} {dd:6.1f} {ret:+6.2f}"
)

SL_VALS = [0.0, 5.0, 8.0, 10.0, 12.0, 15.0, 18.0, 20.0, 25.0]

for label, atr, rng, rr in [
    ("atr=2.0 rng=8.0  (R1 top sh_$, n=22)", 2.0, 8.0, 3.0),
    ("atr=1.5 rng=10.0 (R1 decent n, sh_$=+0.12, n=57)", 1.5, 10.0, 3.0),
    ("atr=1.0 rng=15.0 (R1 tightest range, sh_$=-0.26, n=36)", 1.0, 15.0, 3.0),
    ("atr=1.5 rng=10.0 rr=3.5 (current config)", 1.5, 10.0, 3.5),
]:
    _p(f"\n=== {label} ===")
    _p(HDR)
    for sl in SL_VALS:
        r = _run(atr, rng, 1.2, rr, 0.3, 2.0, sl)
        if r:
            _p(
                FMT.format(
                    sl=sl,
                    n=r["n"],
                    wr=r["wr"],
                    pf=r["pf"],
                    shp=r["sh_p"],
                    she=r["sh_e"],
                    dd=r["dd"],
                    ret=r["ret"],
                )
            )
        else:
            _p(f"{sl:5.1f}   -- (n<10, skip)")

_OUT.close()
