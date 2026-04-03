"""Analyze configured vs realized risk-reward ratio from backtest trades."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class RRMetrics:
    """Computed RR metrics for one scope (overall or one pair)."""

    scope: str
    configured_rr: float
    realized_rr: float
    avg_win_pips: float
    avg_loss_pips_abs: float
    wins: int
    losses: int
    rr_gap: float
    rr_gap_pct: float


def _compute_metrics(scope: str, df: pd.DataFrame, configured_rr: float) -> RRMetrics:
    gains = pd.to_numeric(df.loc[df["pnl_pips"] > 0, "pnl_pips"], errors="coerce")
    losses = pd.to_numeric(df.loc[df["pnl_pips"] < 0, "pnl_pips"], errors="coerce")

    avg_win = float(gains.mean()) if len(gains) else 0.0
    avg_loss_abs = float(losses.abs().mean()) if len(losses) else 0.0
    realized_rr = (avg_win / avg_loss_abs) if avg_loss_abs > 0.0 else 0.0
    rr_gap = configured_rr - realized_rr
    rr_gap_pct = (rr_gap / configured_rr * 100.0) if configured_rr > 0.0 else 0.0

    return RRMetrics(
        scope=scope,
        configured_rr=configured_rr,
        realized_rr=realized_rr,
        avg_win_pips=avg_win,
        avg_loss_pips_abs=avg_loss_abs,
        wins=int(len(gains)),
        losses=int(len(losses)),
        rr_gap=rr_gap,
        rr_gap_pct=rr_gap_pct,
    )


def analyze_rr_ratio(
    trades_df: pd.DataFrame,
    configured_rr: float,
) -> dict[str, Any]:
    """Compute overall and per-pair realized RR from trade-level data."""
    if trades_df.empty:
        return {"overall": None, "per_pair": []}

    df = trades_df.copy()
    if "pnl_pips" not in df.columns:
        raise ValueError("Missing required column: pnl_pips")

    df["pnl_pips"] = pd.to_numeric(df["pnl_pips"], errors="coerce").fillna(0.0)

    overall = _compute_metrics("ALL", df, configured_rr)

    per_pair: list[RRMetrics] = []
    if "pair" in df.columns:
        for pair, group in df.groupby("pair"):
            per_pair.append(_compute_metrics(str(pair), group, configured_rr))

    return {
        "overall": overall,
        "per_pair": sorted(per_pair, key=lambda x: x.scope),
    }


def export_rr_analysis(
    analysis: dict[str, Any],
    output_csv: str,
    output_txt: str,
) -> None:
    """Export RR analysis to CSV and text summary."""
    records: list[dict[str, Any]] = []

    overall = analysis.get("overall")
    if overall is not None:
        records.append(overall.__dict__)

    for row in analysis.get("per_pair", []):
        records.append(row.__dict__)

    csv_path = Path(output_csv)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records).to_csv(csv_path, index=False)

    txt_path = Path(output_txt)
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("ALPHAEDGE RR RATIO ANALYSIS\n")
        f.write("=" * 72 + "\n\n")
        if overall is None:
            f.write("No data available\n")
            return

        f.write("Overall\n")
        f.write("-" * 72 + "\n")
        f.write(f"Configured RR: {overall.configured_rr:.2f}\n")
        f.write(f"Realized RR:   {overall.realized_rr:.4f}\n")
        f.write(f"Avg Win Pips:  {overall.avg_win_pips:.4f}\n")
        f.write(f"Avg Loss Pips: {overall.avg_loss_pips_abs:.4f}\n")
        f.write(f"Wins/Losses:   {overall.wins}/{overall.losses}\n")
        f.write(
            f"RR Gap:        {overall.rr_gap:+.4f} ({overall.rr_gap_pct:+.2f}%)\n\n"
        )

        f.write("Per Pair\n")
        f.write("-" * 72 + "\n")
        for item in analysis.get("per_pair", []):
            f.write(
                f"{item.scope:<8} rr={item.realized_rr:.4f} "
                f"gap={item.rr_gap:+.4f} ({item.rr_gap_pct:+.2f}%) "
                f"wins={item.wins} losses={item.losses}\n"
            )


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Analyze realized RR ratio")
    parser.add_argument(
        "--input",
        default="reports/ALPHAEDGE_backtest_results.csv",
        help="Input backtest trades CSV",
    )
    parser.add_argument(
        "--configured-rr",
        type=float,
        default=2.0,
        help="Configured RR to compare against",
    )
    parser.add_argument(
        "--output-csv",
        default=(
            "reports/"
            f"ALPHAEDGE_RR_RATIO_ANALYSIS_{datetime.now().strftime('%Y-%m-%d')}.csv"
        ),
        help="Output CSV path",
    )
    parser.add_argument(
        "--output-txt",
        default=(
            "reports/"
            f"ALPHAEDGE_RR_RATIO_ANALYSIS_{datetime.now().strftime('%Y-%m-%d')}.txt"
        ),
        help="Output TXT summary path",
    )

    args = parser.parse_args()

    trades_path = Path(args.input)
    if not trades_path.exists():
        raise FileNotFoundError(f"Input file not found: {trades_path}")

    trades_df = pd.read_csv(trades_path)
    analysis = analyze_rr_ratio(trades_df, configured_rr=args.configured_rr)
    export_rr_analysis(analysis, args.output_csv, args.output_txt)


if __name__ == "__main__":
    main()
