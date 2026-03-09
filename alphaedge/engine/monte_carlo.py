# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/engine/monte_carlo.py
# DESCRIPTION  : Monte Carlo drawdown estimation via trade permutations
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-08
# ============================================================
"""ALPHAEDGE — T3.6: Monte Carlo drawdown estimation."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from alphaedge.utils.logger import get_logger

matplotlib.use("Agg")

logger = get_logger()


# ------------------------------------------------------------------
# Data structures
# ------------------------------------------------------------------
@dataclass
class MonteCarloReport:
    """Results of Monte Carlo drawdown simulation."""

    n_permutations: int = 0
    drawdown_median: float = 0.0
    drawdown_95th: float = 0.0
    drawdown_99th: float = 0.0
    drawdowns: list[float] = field(default_factory=list)
    suggested_risk_pct: float = 0.0


# ------------------------------------------------------------------
# Core simulation
# ------------------------------------------------------------------
def _compute_max_drawdown_from_pnls(
    pnl_sequence: list[float],
    starting_equity: float = 10000.0,
) -> float:
    """
    Compute max drawdown percentage from a sequence of P&L values.

    Parameters
    ----------
    pnl_sequence : list[float]
        Trade P&L in USD, in order.
    starting_equity : float
        Starting account equity.

    Returns
    -------
    float
        Max drawdown as a percentage.
    """
    equity = starting_equity
    peak = equity
    max_dd = 0.0

    for pnl in pnl_sequence:
        equity += pnl
        peak = max(peak, equity)
        if peak > 0:
            dd = ((peak - equity) / peak) * 100.0
            max_dd = max(max_dd, dd)

    return max_dd


def run_monte_carlo(
    trade_pnls: list[float],
    n_permutations: int = 10000,
    starting_equity: float = 10000.0,
    base_risk_pct: float = 1.0,
    seed: int | None = None,
) -> MonteCarloReport:
    """
    Run Monte Carlo simulation by permuting trade order.

    Parameters
    ----------
    trade_pnls : list[float]
        P&L values (in USD) for each trade.
    n_permutations : int
        Number of permutations to run (default 10000).
    starting_equity : float
        Starting account equity for drawdown calculation.
    base_risk_pct : float
        Current risk percentage per trade (used for calibration).
    seed : int | None
        Random seed for reproducibility.

    Returns
    -------
    MonteCarloReport
        Drawdown statistics and suggested risk calibration.
    """
    if not trade_pnls:
        return MonteCarloReport()

    rng = random.Random(seed)
    drawdowns: list[float] = []

    for _ in range(n_permutations):
        shuffled = trade_pnls.copy()
        rng.shuffle(shuffled)
        dd = _compute_max_drawdown_from_pnls(shuffled, starting_equity)
        drawdowns.append(dd)

    dd_sorted = sorted(drawdowns)
    dd_median = float(np.median(dd_sorted))
    idx_95 = int(len(dd_sorted) * 0.95)
    idx_99 = int(len(dd_sorted) * 0.99)
    dd_95th = dd_sorted[min(idx_95, len(dd_sorted) - 1)]
    dd_99th = dd_sorted[min(idx_99, len(dd_sorted) - 1)]

    # Calibrate risk: scale so that 95th percentile drawdown stays under
    # a target max drawdown (e.g. 15%).  suggested = base * (target / dd_95th)
    target_max_dd = 15.0
    if dd_95th > 0:
        suggested_risk = base_risk_pct * (target_max_dd / dd_95th)
        suggested_risk = min(suggested_risk, 5.0)  # Cap at 5%
    else:
        suggested_risk = base_risk_pct

    report = MonteCarloReport(
        n_permutations=n_permutations,
        drawdown_median=dd_median,
        drawdown_95th=dd_95th,
        drawdown_99th=dd_99th,
        drawdowns=drawdowns,
        suggested_risk_pct=round(suggested_risk, 2),
    )

    _log_monte_carlo_report(report)
    return report


# ------------------------------------------------------------------
# Histogram visualization
# ------------------------------------------------------------------
def generate_drawdown_histogram(
    report: MonteCarloReport,
    output_path: str = "monte_carlo_drawdown.png",
) -> str:
    """
    Generate histogram of drawdown distribution.

    Parameters
    ----------
    report : MonteCarloReport
        Monte Carlo simulation results.
    output_path : str
        File path for the saved histogram image.

    Returns
    -------
    str
        Path to the saved histogram image.
    """
    if not report.drawdowns:
        return ""

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(report.drawdowns, bins=50, color="#2196F3", edgecolor="black", alpha=0.7)
    ax.axvline(
        report.drawdown_median,
        color="green",
        linestyle="--",
        linewidth=2,
        label=f"Median: {report.drawdown_median:.2f}%",
    )
    ax.axvline(
        report.drawdown_95th,
        color="orange",
        linestyle="--",
        linewidth=2,
        label=f"95th pctl: {report.drawdown_95th:.2f}%",
    )
    ax.axvline(
        report.drawdown_99th,
        color="red",
        linestyle="--",
        linewidth=2,
        label=f"99th pctl: {report.drawdown_99th:.2f}%",
    )
    ax.set_xlabel("Max Drawdown (%)")
    ax.set_ylabel("Frequency")
    ax.set_title(
        f"Monte Carlo Drawdown Distribution ({report.n_permutations} permutations)"
    )
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)

    logger.info(f"ALPHAEDGE: MC drawdown histogram saved → {output_path}")
    return output_path


# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------
def _log_monte_carlo_report(report: MonteCarloReport) -> None:
    """Log Monte Carlo simulation results."""
    logger.info("=" * 60)
    logger.info("ALPHAEDGE — Monte Carlo Drawdown Analysis")
    logger.info("=" * 60)
    logger.info(f"  Permutations      : {report.n_permutations:,}")
    logger.info(f"  Drawdown Median   : {report.drawdown_median:.2f}%")
    logger.info(f"  Drawdown 95th pct : {report.drawdown_95th:.2f}%")
    logger.info(f"  Drawdown 99th pct : {report.drawdown_99th:.2f}%")
    logger.info(f"  Suggested Risk %  : {report.suggested_risk_pct:.2f}%")
    logger.info("=" * 60)

    if report.drawdown_95th > 20.0:
        logger.warning(
            f"ALPHAEDGE: MC 95th percentile drawdown {report.drawdown_95th:.2f}% "
            f"exceeds 20% — consider reducing risk per trade"
        )
