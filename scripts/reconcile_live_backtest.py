"""ALPHAEDGE — Script de réconciliation live/backtest.

Compare les trades live (reports/live_trades_*.csv) avec les résultats
backtest (reports/ALPHAEDGE_backtest_results.csv) et affiche un tableau
comparatif par paire.

Usage
-----
    python scripts/reconcile_live_backtest.py
    python scripts/reconcile_live_backtest.py --date 2026-03-24
    python scripts/reconcile_live_backtest.py --live-glob "reports/live_trades_*.csv"

Exit codes
----------
    0 — toutes les divergences sont dans les seuils acceptables
    1 — au moins une paire dépasse le seuil de divergence (|live_wr - bt_wr| > 0.15)
    2 — aucune donnée live trouvée (avertissement seulement)
"""

from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

WINRATE_DIVERGENCE_THRESHOLD = 0.15  # alert if |live_wr - bt_wr| > 15 pp


# ---------------------------------------------------------------------------
# CSV loading helpers (no pandas dependency — stdlib csv only)
# ---------------------------------------------------------------------------
def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    import csv

    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _load_live_trades(live_glob: str) -> list[dict[str, str]]:
    files = sorted(glob.glob(live_glob))
    rows: list[dict[str, str]] = []
    for fp in files:
        rows.extend(_load_csv_rows(Path(fp)))
    return rows


def _load_backtest_trades(bt_path: Path) -> list[dict[str, str]]:
    if not bt_path.exists():
        return []
    return _load_csv_rows(bt_path)


# ---------------------------------------------------------------------------
# Per-pair statistics
# ---------------------------------------------------------------------------
def _compute_stats(
    rows: list[dict[str, str]],
) -> dict[str, dict[str, float]]:
    """Return {pair: {winrate, avg_pnl_pips, avg_spread, n_trades}}"""
    from collections import defaultdict

    buckets: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        pair = row.get("pair", "UNKNOWN")
        buckets[pair].append(row)

    stats: dict[str, dict[str, float]] = {}
    for pair, trades in buckets.items():
        n = len(trades)
        wins = sum(1 for t in trades if t.get("outcome", "") == "win")
        pnl_pips = [float(t["pnl_pips"]) for t in trades if t.get("pnl_pips")]
        spreads = [float(t["spread_pips"]) for t in trades if t.get("spread_pips")]
        stats[pair] = {
            "n_trades": float(n),
            "winrate": wins / n if n else 0.0,
            "avg_pnl_pips": sum(pnl_pips) / len(pnl_pips) if pnl_pips else 0.0,
            "avg_spread": sum(spreads) / len(spreads) if spreads else 0.0,
        }
    return stats


# ---------------------------------------------------------------------------
# Display (Rich if available, plain text fallback)
# ---------------------------------------------------------------------------
def _print_table(
    live_stats: dict[str, dict[str, float]],
    bt_stats: dict[str, dict[str, float]],
    divergent_pairs: list[str],
) -> None:
    all_pairs = sorted(set(live_stats) | set(bt_stats))

    try:
        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(title="ALPHAEDGE — Réconciliation Live / Backtest")
        table.add_column("Pair", style="bold")
        table.add_column("Live N", justify="right")
        table.add_column("Live WR", justify="right")
        table.add_column("Live PnL", justify="right")
        table.add_column("Live Spread", justify="right")
        table.add_column("BT N", justify="right")
        table.add_column("BT WR", justify="right")
        table.add_column("BT PnL", justify="right")
        table.add_column("ΔWR", justify="right")
        table.add_column("Alert", justify="center")

        for pair in all_pairs:
            ls = live_stats.get(pair, {})
            bs = bt_stats.get(pair, {})
            delta_wr = abs(ls.get("winrate", 0.0) - bs.get("winrate", 0.0))
            alert = "⚠️" if pair in divergent_pairs else "✅"
            style = "red" if pair in divergent_pairs else ""
            table.add_row(
                pair,
                str(int(ls.get("n_trades", 0))),
                f"{ls.get('winrate', 0.0):.1%}",
                f"{ls.get('avg_pnl_pips', 0.0):+.1f}",
                f"{ls.get('avg_spread', 0.0):.1f}",
                str(int(bs.get("n_trades", 0))),
                f"{bs.get('winrate', 0.0):.1%}",
                f"{bs.get('avg_pnl_pips', 0.0):+.1f}",
                f"{delta_wr:.1%}",
                alert,
                style=style,
            )
        console.print(table)

    except ImportError:
        # Plain text fallback
        cols = "Pair       LiveN   LiveWR  LivePnL  BTN  BTWR  BTPnL   DWR  Alert"
        header = cols
        print(header)
        print("-" * len(header))
        for pair in all_pairs:
            ls = live_stats.get(pair, {})
            bs = bt_stats.get(pair, {})
            delta_wr = abs(ls.get("winrate", 0.0) - bs.get("winrate", 0.0))
            alert = "WARN" if pair in divergent_pairs else "OK"
            print(
                f"{pair:<10} "
                f"{int(ls.get('n_trades', 0)):>6} "
                f"{ls.get('winrate', 0.0):>8.1%} "
                f"{ls.get('avg_pnl_pips', 0.0):>+10.1f} "
                f"{int(bs.get('n_trades', 0)):>6} "
                f"{bs.get('winrate', 0.0):>8.1%} "
                f"{bs.get('avg_pnl_pips', 0.0):>+10.1f} "
                f"{delta_wr:>8.1%} "
                f"{alert:>6}"
            )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare ALPHAEDGE live trades vs backtest results."
    )
    parser.add_argument(
        "--date",
        metavar="YYYY-MM-DD",
        help="Restrict live trades to a specific date (default: all dates)",
    )
    parser.add_argument(
        "--live-glob",
        metavar="GLOB",
        default=str(WORKSPACE_ROOT / "reports" / "live_trades_*.csv"),
        help="Glob pattern for live trade CSV files",
    )
    parser.add_argument(
        "--backtest",
        metavar="PATH",
        default=str(WORKSPACE_ROOT / "reports" / "ALPHAEDGE_backtest_results.csv"),
        help="Path to backtest results CSV",
    )
    args = parser.parse_args()

    live_glob = args.live_glob
    if args.date:
        live_glob = str(WORKSPACE_ROOT / "reports" / f"live_trades_{args.date}.csv")

    print(f"Live glob  : {live_glob}")
    print(f"Backtest   : {args.backtest}")
    print()

    live_rows = _load_live_trades(live_glob)
    bt_rows = _load_backtest_trades(Path(args.backtest))

    if not live_rows:
        print("⚠️  Aucun trade live trouvé. Backtest uniquement.")
        return 2

    live_stats = _compute_stats(live_rows)
    bt_stats = _compute_stats(bt_rows)

    divergent_pairs = [
        pair
        for pair in live_stats
        if abs(live_stats[pair]["winrate"] - bt_stats.get(pair, {}).get("winrate", 0.0))
        > WINRATE_DIVERGENCE_THRESHOLD
    ]

    _print_table(live_stats, bt_stats, divergent_pairs)

    if divergent_pairs:
        print(
            f"\n⚠️  Divergence winrate > {WINRATE_DIVERGENCE_THRESHOLD:.0%} "
            f"sur : {', '.join(divergent_pairs)}"
        )
        return 1

    print("\n✅ Toutes les paires dans les seuils de tolérance.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
