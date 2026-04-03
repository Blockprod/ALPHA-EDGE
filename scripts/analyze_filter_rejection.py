"""Analyze filter rejection logs to diagnose signal silence periods.

Purpose: Understand why certain periods have no trades (e.g., 61-day silence).
Maps rejection logs to filter cascade effects.

Usage:
    python -m scripts.analyze_filter_rejection <rejection_logs_csv>
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from alphaedge.utils.logger import get_logger

logger = get_logger()


def analyze_silent_periods(
    rejection_logs_df: pd.DataFrame,
    min_silence_days: int = 14,
) -> dict[str, Any]:
    """
    Identify silent periods (no trades) and analyze rejection causes.

    Parameters
    ----------
    rejection_logs_df : pd.DataFrame
        DataFrame with columns such as date, pair, direction,
        rejection_reason, and primary_filter.
    min_silence_days : int
        Minimum consecutive days without trades to flag as "silent period".

    Returns
    -------
    dict
        Analysis results with:
        - silent_periods: list of silent-period summaries
        - filter_contribution: % of rejections per filter during silence
    """
    if rejection_logs_df.empty:
        logger.warning("No rejection logs to analyze")
        return {}

    # Convert date to datetime
    rejection_logs_df["date"] = pd.to_datetime(rejection_logs_df["date"])
    rejection_logs_df = rejection_logs_df.sort_values("date")

    # Find all dates with rejections
    rejection_dates = set(rejection_logs_df["date"].dt.date)

    # Find date ranges with no trades (gaps >= min_silence_days)
    if len(rejection_logs_df) == 0:
        return {}

    min_date = rejection_logs_df["date"].min().date()
    max_date = rejection_logs_df["date"].max().date()
    all_dates = pd.date_range(min_date, max_date, freq="D").date

    silent_periods = []
    current_silence_start = None
    current_silence_duration = 0

    for date in all_dates:
        if date not in rejection_dates:
            if current_silence_start is None:
                current_silence_start = date
                current_silence_duration = 1
            else:
                current_silence_duration += 1
        else:
            if (
                current_silence_start is not None
                and current_silence_duration >= min_silence_days
            ):
                # Record silent period
                silence_end = date - timedelta(days=1)

                # Filter rejections during this period
                period_rejections = rejection_logs_df[
                    (rejection_logs_df["date"].dt.date >= current_silence_start)
                    & (rejection_logs_df["date"].dt.date <= silence_end)
                ]

                filter_counts = (
                    period_rejections["primary_filter"].value_counts().to_dict()
                )

                silent_periods.append(
                    {
                        "start_date": current_silence_start.isoformat(),
                        "end_date": silence_end.isoformat(),
                        "duration_days": current_silence_duration,
                        "total_rejections_during_silence": len(period_rejections),
                        "filter_breakdown": filter_counts,
                    }
                )

            current_silence_start = None
            current_silence_duration = 0

    # Global filter contribution analysis
    filter_stats = (
        rejection_logs_df.groupby("primary_filter")
        .agg(
            {
                "pair": "count",  # total rejections
                "rejection_reason": lambda x: "|".join(x.unique()),
            }
        )
        .rename(columns={"pair": "rejection_count"})
        .reset_index()
    )

    total_rejections = len(rejection_logs_df)
    filter_stats["pct_of_total"] = (
        filter_stats["rejection_count"] / total_rejections * 100
    ).round(2)

    return {
        "silent_periods": silent_periods,
        "filter_statistics": filter_stats.to_dict("records"),
        "total_rejections_analyzed": total_rejections,
        "max_silence_days": max(
            [p["duration_days"] for p in silent_periods], default=0
        ),
    }


def export_analysis_report(
    analysis: dict[str, Any],
    output_path: str = "reports/SIGNAL_SILENCE_ANALYSIS.txt",
) -> None:
    """Export filter analysis report to file."""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("ALPHAEDGE — SIGNAL SILENCE ANALYSIS REPORT\n")
        f.write("=" * 80 + "\n\n")

        # Silent periods
        silent_count = len(analysis.get("silent_periods", []))
        f.write(f"SILENT PERIODS (>=14 days, {silent_count} found):\n")
        f.write("-" * 80 + "\n")
        for period in analysis.get("silent_periods", []):
            silence_rejections = period["total_rejections_during_silence"]
            f.write(
                f"  {period['start_date']} → {period['end_date']} "
                f"({period['duration_days']} days)\n"
            )
            f.write(f"    Total rejections during silence: {silence_rejections}\n")
            f.write("    Filter breakdown:\n")
            for filt, count in sorted(
                period["filter_breakdown"].items(), key=lambda x: x[1], reverse=True
            ):
                f.write(f"      {filt}: {count}\n")
            f.write("\n")

        # Global statistics
        f.write("\nFILTER CONTRIBUTION (Global):\n")
        f.write("-" * 80 + "\n")
        for stat in sorted(
            analysis.get("filter_statistics", []),
            key=lambda x: x["rejection_count"],
            reverse=True,
        ):
            rejection_count = stat["rejection_count"]
            pct_of_total = stat["pct_of_total"]
            f.write(
                f"  {stat['primary_filter']:<20} "
                f"{rejection_count:>5} rejections ({pct_of_total:>5.1f}%)\n"
            )
            f.write(f"    Reasons: {stat['rejection_reason']}\n")

        total_rejections = analysis.get("total_rejections_analyzed", 0)
        f.write(f"\nTotal rejections analyzed: {total_rejections}\n")
        f.write(f"Longest silence: {analysis.get('max_silence_days', 0)} days\n\n")

        f.write("=" * 80 + "\n")
        f.write("RECOMMENDATIONS:\n")
        f.write("=" * 80 + "\n")
        f.write(
            "1. If ADX gate dominates (>60%), consider lowering "
            "adx_threshold in config.yaml\n"
        )
        f.write(
            "2. If carry conflict dominates (>40%), review "
            "carry_min_differential setting\n"
        )
        f.write(
            "3. If regime gate dominates (>50%), consider disabling "
            "regime_gate or tuning threshold\n"
        )
        f.write(
            "4. If ML filter dominates, consider retraining or reducing "
            "model confidence threshold\n"
        )

    logger.info(f"Signal silence analysis exported to {output_path}")


def export_filter_rejection_analysis_csv(
    analysis: dict[str, Any],
    output_path: str,
) -> None:
    """Export a flat CSV summary for silent periods and filter contributions."""
    records: list[dict[str, Any]] = []

    for period in analysis.get("silent_periods", []):
        breakdown = period.get("filter_breakdown", {})
        if breakdown:
            for filter_name, filter_count in breakdown.items():
                records.append(
                    {
                        "section": "silent_period",
                        "start_date": period.get("start_date", ""),
                        "end_date": period.get("end_date", ""),
                        "duration_days": period.get("duration_days", 0),
                        "total_rejections": period.get(
                            "total_rejections_during_silence", 0
                        ),
                        "filter_name": filter_name,
                        "filter_count": filter_count,
                        "filter_pct_of_total": "",
                        "rejection_reasons": "",
                    }
                )
        else:
            records.append(
                {
                    "section": "silent_period",
                    "start_date": period.get("start_date", ""),
                    "end_date": period.get("end_date", ""),
                    "duration_days": period.get("duration_days", 0),
                    "total_rejections": period.get(
                        "total_rejections_during_silence", 0
                    ),
                    "filter_name": "",
                    "filter_count": 0,
                    "filter_pct_of_total": "",
                    "rejection_reasons": "",
                }
            )

    for stat in analysis.get("filter_statistics", []):
        records.append(
            {
                "section": "filter_global",
                "start_date": "",
                "end_date": "",
                "duration_days": "",
                "total_rejections": analysis.get("total_rejections_analyzed", 0),
                "filter_name": stat.get("primary_filter", ""),
                "filter_count": stat.get("rejection_count", 0),
                "filter_pct_of_total": stat.get("pct_of_total", 0.0),
                "rejection_reasons": stat.get("rejection_reason", ""),
            }
        )

    df = pd.DataFrame(records)
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_file, index=False)
    logger.info(f"Filter rejection CSV analysis exported to {output_path}")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze filter rejection logs for signal silence diagnosis."
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        default="reports/ALPHAEDGE_rejection_logs.csv",
        help=(
            "Path to rejection logs CSV (default: reports/ALPHAEDGE_rejection_logs.csv)"
        ),
    )
    parser.add_argument(
        "--output",
        "-o",
        default="reports/SIGNAL_SILENCE_ANALYSIS.txt",
        help="Output report path",
    )
    parser.add_argument(
        "--csv-output",
        default=(
            "reports/"
            f"FILTER_REJECTION_ANALYSIS_{datetime.now().strftime('%Y-%m-%d')}.csv"
        ),
        help="Output CSV path for filter rejection analysis summary",
    )
    parser.add_argument(
        "--min-silence-days",
        type=int,
        default=14,
        help="Minimum consecutive days without trades to flag (default: 14)",
    )

    args = parser.parse_args()

    if not Path(args.input_file).exists():
        logger.error(f"Input file not found: {args.input_file}")
        sys.exit(1)

    try:
        df = pd.read_csv(args.input_file)
        logger.info(f"Loaded {len(df)} rejection logs from {args.input_file}")
    except Exception as e:
        logger.error(f"Failed to load CSV: {e}")
        sys.exit(1)

    analysis = analyze_silent_periods(df, min_silence_days=args.min_silence_days)
    export_analysis_report(analysis, output_path=args.output)
    export_filter_rejection_analysis_csv(analysis, output_path=args.csv_output)
    logger.info("Signal silence analysis complete")


if __name__ == "__main__":
    main()
