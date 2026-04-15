#!/usr/bin/env python
# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : scripts/analyze_wf_oos.py
# DESCRIPTION  : Offline walk-forward OOS diagnosis (B-03)
#                Loads cached daily bars, runs WF per pair,
#                tests ADX thresholds and spread scenarios.
#                NO IB Gateway required — uses BarDiskCache only.
# PYTHON       : 3.11.9
# USAGE        : python scripts/analyze_wf_oos.py
# ============================================================
"""B-03 — Offline walk-forward OOS edge diagnosis.

Runs run_walk_forward() directly on cached bars for EURUSD + USDJPY,
sweeping ADX threshold variants [30, 32, 35] and spread scenarios
[current, 50% lower, 50% higher] to quantify OOS edge sensitivity.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

# Allow running from repo root without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from alphaedge.config.loader import load_config
from alphaedge.engine.backtest_types import BacktestStats
from alphaedge.engine.data_feed import BarDiskCache
from alphaedge.engine.walk_forward import WalkForwardReport, run_walk_forward

# ---------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------
PAIRS = ["EURUSD", "USDJPY"]
ADX_THRESHOLDS = [30.0, 32.0, 35.0]
SPREAD_SCENARIOS: list[tuple[str, float]] = [
    ("base", 1.0),  # current assumptions
    ("half", 0.5),  # half spread → best case
    ("1.5x", 1.5),  # 50% wider → stress test
]

# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------
_SEP = "─" * 98
_HDR = (
    f"{'Pair':<8} {'ADX':>5} {'Spread':>8} "
    f"{'Wins':>5} {'Win%':>6} {'PF':>6} {'Sharpe':>7} "
    f"{'OOS Pips':>10} {'OOS USD':>10} "
    f"{'IS WR%':>7} {'IS PF':>6}"
)


def _fmt_stats(stats: BacktestStats) -> str:
    return (
        f"{stats.wins:>5} "
        f"{stats.winrate:>5.1f}% "
        f"{stats.profit_factor:>6.2f} "
        f"{stats.sharpe_ratio:>7.2f} "
        f"{stats.total_pnl_pips:>10.1f} "
        f"{stats.total_pnl_usd:>10.2f}"
    )


def _agg_is(wf_report: WalkForwardReport) -> BacktestStats:
    """Aggregate IS stats across all walk-forward windows."""
    report: WalkForwardReport = wf_report
    for wr in report.windows:
        # re-run is not needed — is in-memory trades are embedded in wr.train_stats
        # We only have stats, not raw trades, for IS from the aggregated report.
        # Use per-window train_stats for averages instead.
        _ = wr.train_stats  # noqa: F841
    return (
        BacktestStats()
    )  # placeholder — IS raw trades not retained by run_walk_forward


def main() -> None:
    config = load_config(Path("config.yaml"))
    cache = BarDiskCache()

    windows_config = (
        config.trading.walk_forward_train_months,
        config.trading.walk_forward_test_months,
        config.trading.walk_forward_step_months,
    )
    print(f"\n{'═' * 98}")
    print("  ALPHAEDGE — B-03 Walk-Forward OOS Diagnosis")
    print(
        f"  WF config: train={windows_config[0]}m"
        f"  test={windows_config[1]}m"
        f"  step={windows_config[2]}m"
    )
    print(f"{'═' * 98}")
    print(f"\n{_HDR}")
    print(_SEP)

    for pair in PAIRS:
        bars = cache.load(pair, "1 day")
        if not bars:
            print(f"[WARN] No cache for {pair} — skipping")
            continue

        for adx in ADX_THRESHOLDS:
            for spread_label, spread_mult in SPREAD_SCENARIOS:
                # Deep-copy config to avoid mutation across iterations
                cfg = copy.deepcopy(config)
                cfg.trading.momentum_adx_threshold = adx
                cfg.trading.cost_spread_multipliers = {
                    k: v * spread_mult
                    for k, v in cfg.trading.cost_spread_multipliers.items()
                }
                cfg.trading.cost_slippage_multipliers = dict(
                    cfg.trading.cost_slippage_multipliers
                )

                report = run_walk_forward(
                    bars,
                    pair,
                    cfg,
                    train_months=windows_config[0],
                    test_months=windows_config[1],
                    step_months=windows_config[2],
                )

                oos = report.aggregated_oos
                n_windows = len(report.windows)

                # Collect IS averages from per-window train_stats
                is_wr_vals = [wr.train_stats.winrate for wr in report.windows]
                is_pf_vals = [wr.train_stats.profit_factor for wr in report.windows]
                is_wr_avg = sum(is_wr_vals) / len(is_wr_vals) if is_wr_vals else 0.0
                is_pf_avg = sum(is_pf_vals) / len(is_pf_vals) if is_pf_vals else 0.0

                row = (
                    f"{pair:<8} {adx:>5.0f} {spread_label:>8} "
                    f"{oos.wins:>5} "
                    f"{oos.winrate:>5.1f}% "
                    f"{oos.profit_factor:>6.2f} "
                    f"{oos.sharpe_ratio:>7.2f} "
                    f"{oos.total_pnl_pips:>10.1f} "
                    f"{oos.total_pnl_usd:>10.2f} "
                    f"{is_wr_avg:>6.1f}% "
                    f"{is_pf_avg:>6.2f}"
                    f"  ({n_windows} windows)"
                )
                print(row)

        print(_SEP)

    # --- Per-window detail for current config (ADX=30, base spread) ---
    print(f"\n{'═' * 98}")
    print("  PER-WINDOW DETAIL  (ADX=30, base spread)")
    print(f"{'═' * 98}")

    for pair in PAIRS:
        bars = cache.load(pair, "1 day")
        if not bars:
            continue

        cfg = copy.deepcopy(config)
        cfg.trading.momentum_adx_threshold = 30.0

        report = run_walk_forward(
            bars,
            pair,
            cfg,
            train_months=windows_config[0],
            test_months=windows_config[1],
            step_months=windows_config[2],
        )

        print(f"\n  {pair}")
        win_hdr = (
            f"  {'#':<3} {'IS start':>10} {'OOS start':>10} "
            f"{'IS n':>5} {'IS WR%':>7} {'IS PF':>6} "
            f"{'OOS n':>6} {'OOS WR%':>8} {'OOS PF':>7} {'OOS pips':>9} {'OOS USD':>9}"
        )
        print(win_hdr)
        print("  " + "─" * 93)

        for i, wr in enumerate(report.windows, 1):
            w = wr.window
            tr = wr.train_stats
            ts = wr.test_stats
            degradation = ""
            if tr.profit_factor > 0:
                pf_deg = (ts.profit_factor - tr.profit_factor) / tr.profit_factor * 100
                wr_deg = ts.winrate - tr.winrate
                degradation = f"  ΔPF={pf_deg:+.0f}%  ΔWR={wr_deg:+.1f}pp"
            print(
                f"  {i:<3} {w.train_start.isoformat()[:7]:>10} "
                f"{w.test_start.isoformat()[:7]:>10} "
                f"{tr.total_trades:>5} {tr.winrate:>6.1f}% {tr.profit_factor:>6.2f} "
                f"{ts.total_trades:>6} {ts.winrate:>7.1f}% {ts.profit_factor:>7.2f} "
                f"{ts.total_pnl_pips:>9.1f} {ts.total_pnl_usd:>9.2f}"
                f"{degradation}"
            )

        agg = report.aggregated_oos
        print("  " + "─" * 93)
        print(
            f"  {'AGG':>3} {'':>10} {'':>10} "
            f"{'':>5} {'':>7} {'':>6} "
            f"{agg.total_trades:>6} {agg.winrate:>7.1f}% {agg.profit_factor:>7.2f} "
            f"{agg.total_pnl_pips:>9.1f} {agg.total_pnl_usd:>9.2f}"
        )

    # --- Cost sensitivity summary ---
    print(f"\n{'═' * 98}")
    print("  COST SENSITIVITY — OOS P&L USD delta vs base (ADX=30)")
    print(f"{'═' * 98}")
    print(f"  {'Pair':<8} {'Scenario':>10}  {'OOS USD':>10}  {'Delta vs base':>15}")
    print("  " + "─" * 50)

    for pair in PAIRS:
        bars = cache.load(pair, "1 day")
        if not bars:
            continue

        base_pnl: float | None = None
        for spread_label, spread_mult in SPREAD_SCENARIOS:
            cfg = copy.deepcopy(config)
            cfg.trading.momentum_adx_threshold = 30.0
            cfg.trading.cost_spread_multipliers = {
                k: v * spread_mult
                for k, v in cfg.trading.cost_spread_multipliers.items()
            }

            report = run_walk_forward(
                bars,
                pair,
                cfg,
                train_months=windows_config[0],
                test_months=windows_config[1],
                step_months=windows_config[2],
            )
            pnl = report.aggregated_oos.total_pnl_usd
            if base_pnl is None:
                base_pnl = pnl
                delta_str = "—"
            else:
                delta = pnl - base_pnl
                delta_str = f"{delta:+.2f}"
            print(f"  {pair:<8} {spread_label:>10}  {pnl:>10.2f}  {delta_str:>15}")

    print(f"{'═' * 98}\n")


if __name__ == "__main__":
    main()
