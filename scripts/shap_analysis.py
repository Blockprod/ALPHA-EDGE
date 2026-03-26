"""ALPHAEDGE — Offline SHAP feature importance analysis.

Trains a RandomForestClassifier on backtest trade records and computes
SHAP values to identify which parameters contribute to Sharpe.

OFFLINE ONLY — never import this from any engine/ module.

PREREQUISITES
-------------
1. A valid Momentum+Carry backtest CSV must exist (post-migration Audit #13).
2. Minimum 100 trades required (enforced via guard at startup).
3. Activate the virtual environment before running:
       .venv\\Scripts\\Activate.ps1
4. shap must be installed: pip install shap>=0.45.0

USAGE
-----
    python scripts/shap_analysis.py \\
        --csv reports/ALPHAEDGE_backtest_results.csv \\
        --output reports/shap_report_YYYY-MM-DD.md

OUTPUT
------
    reports/shap_report_YYYY-MM-DD.md  — feature importance table
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

_MIN_TRADES: int = 100

# Features expected in the backtest CSV that represent trading conditions.
# Adjust this list once the Momentum+Carry CSV schema is finalised.
_FEATURE_COLUMNS: list[str] = [
    "adx",
    "ema_delta_pct",
    "carry_diff",
    "atr_ratio",
    "day_of_week",
]

# Column that defines win (1) / loss (0)
_LABEL_COLUMN: str = "outcome"  # 1 = win, 0 = loss/breakeven


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SHAP feature importance analysis on ALPHAEDGE backtest results."
    )
    parser.add_argument(
        "--csv",
        default="reports/ALPHAEDGE_backtest_results.csv",
        help="Path to backtest results CSV.",
    )
    parser.add_argument(
        "--output",
        default=f"reports/shap_report_{date.today().isoformat()}.md",
        help="Output markdown report path.",
    )
    return parser.parse_args()


def _load_data(csv_path: Path) -> pd.DataFrame:
    """Load and validate the backtest CSV."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Backtest CSV not found: {csv_path}")
    df = pd.read_csv(csv_path)
    if len(df) < _MIN_TRADES:
        raise ValueError(
            f"Insufficient data for SHAP analysis: {len(df)} trades < "
            f"minimum {_MIN_TRADES}. Run more backtests first."
        )
    return df


def _build_feature_matrix(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series]:
    """Extract available feature columns and binary label."""
    available = [col for col in _FEATURE_COLUMNS if col in df.columns]
    if not available:
        raise ValueError(
            f"No feature columns found in CSV. Expected at least one of: "
            f"{_FEATURE_COLUMNS}. Found: {list(df.columns)}"
        )
    if _LABEL_COLUMN not in df.columns:
        # Fallback: derive from pnl_pips if outcome not present
        if "pnl_pips" in df.columns:
            df = df.copy()
            df[_LABEL_COLUMN] = (df["pnl_pips"] > 0).astype(int)
        else:
            raise ValueError(
                f"Label column '{_LABEL_COLUMN}' not found and 'pnl_pips' "
                "not available as fallback."
            )
    x = df[available].fillna(0.0)
    y = df[_LABEL_COLUMN].astype(int)
    return x, y


def _write_report(
    output_path: Path,
    feature_names: list[str],
    mean_abs_shap: list[float],
    n_trades: int,
) -> None:
    """Write SHAP importance table to a markdown file."""
    rows = sorted(
        zip(feature_names, mean_abs_shap),
        key=lambda t: t[1],
        reverse=True,
    )
    lines = [
        "# SHAP Feature Importance — ALPHAEDGE",
        f"**Generated**: {date.today().isoformat()}",
        f"**Trades analysed**: {n_trades}",
        "",
        "| Rank | Feature | Mean |SHAP| |",
        "|------|---------|------------|",
    ]
    for rank, (feat, shap_val) in enumerate(rows, 1):
        lines.append(f"| {rank} | `{feat}` | {shap_val:.6f} |")

    lines += [
        "",
        "---",
        "**Interpretation**: Higher mean |SHAP| = stronger contribution"
        " to win/loss prediction.",
        "Features with |SHAP| ≈ 0 may be candidates for removal from the model.",
        "",
        "> This analysis is offline only. "
        "Never integrate SHAP into the live signal pipeline.",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = _parse_args()
    csv_path = Path(args.csv)
    output_path = Path(args.output)

    print(f"ALPHAEDGE SHAP: loading {csv_path}")
    df = _load_data(csv_path)
    print(f"ALPHAEDGE SHAP: {len(df)} trades loaded")

    x, y = _build_feature_matrix(df)
    feature_names = list(x.columns)
    print(f"ALPHAEDGE SHAP: features = {feature_names}")

    # Lazy import so shap is only required when running this script
    try:
        import shap
        from sklearn.ensemble import RandomForestClassifier
    except ImportError as exc:
        print(
            f"ALPHAEDGE SHAP: missing dependency — {exc}. "
            "Run: pip install shap>=0.45.0 scikit-learn>=1.4.0"
        )
        sys.exit(1)

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(x.to_numpy(), y.to_numpy())

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(x.values)

    # For binary classification, shap_values is [neg_class, pos_class]
    # Use the positive class (win) SHAP values
    if isinstance(shap_values, list) and len(shap_values) == 2:
        sv = shap_values[1]
    else:
        sv = np.array(shap_values)

    mean_abs_shap = list(np.abs(sv).mean(axis=0))

    _write_report(output_path, feature_names, mean_abs_shap, len(df))
    print(f"ALPHAEDGE SHAP: report saved to {output_path}")

    # Print summary to stdout
    rows = sorted(zip(feature_names, mean_abs_shap), key=lambda t: t[1], reverse=True)
    print("\nFeature importance (mean |SHAP|):")
    for feat, val in rows:
        print(f"  {feat:25s} {val:.6f}")


if __name__ == "__main__":
    main()
