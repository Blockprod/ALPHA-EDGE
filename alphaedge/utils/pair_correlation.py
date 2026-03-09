# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/utils/pair_correlation.py
# DESCRIPTION  : Multi-pair correlation analysis and risk adjustment
# AUTHOR       : ALPHAEDGE Dev Team
# PYTHON       : 3.11.9
# ============================================================
"""Multi-pair correlation: block correlated signals, adjust risk."""

from __future__ import annotations

import math
from dataclasses import dataclass

from alphaedge.config.constants import (
    CORRELATION_LOOKBACK_BARS,
    CORRELATION_RISK_DECAY,
    DEFAULT_MAX_CORRELATION,
)


# ------------------------------------------------------------------
# Data classes
# ------------------------------------------------------------------
@dataclass(frozen=True)
class CorrelationCheckResult:
    """Result of a signal correlation check."""

    allowed: bool
    reason: str
    max_rho: float
    blocking_pair: str


@dataclass(frozen=True)
class RiskAdjustmentResult:
    """Result of risk adjustment for correlated positions."""

    adjusted_risk_pct: float
    total_correlation: float
    n_correlated: int


# ------------------------------------------------------------------
# Return computation
# ------------------------------------------------------------------
def compute_returns(closes: list[float]) -> list[float]:
    """Compute simple returns from a list of close prices.

    Parameters
    ----------
    closes:
        Ordered close prices (oldest first).

    Returns
    -------
    List of (close[i] / close[i-1] - 1) values.
    """
    if len(closes) < 2:
        return []
    return [
        (closes[i] / closes[i - 1]) - 1.0
        for i in range(1, len(closes))
        if closes[i - 1] != 0.0
    ]


# ------------------------------------------------------------------
# Pearson correlation
# ------------------------------------------------------------------
def compute_correlation(returns_a: list[float], returns_b: list[float]) -> float:
    """Compute Pearson correlation coefficient between two return series.

    Parameters
    ----------
    returns_a:
        Return series for pair A.
    returns_b:
        Return series for pair B (must be same length as returns_a).

    Returns
    -------
    Pearson ρ in [-1, 1], or 0.0 if computation is not possible.
    """
    n = min(len(returns_a), len(returns_b))
    if n < 2:
        return 0.0

    a = returns_a[:n]
    b = returns_b[:n]

    mean_a = sum(a) / n
    mean_b = sum(b) / n

    cov = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n))
    var_a = sum((a[i] - mean_a) ** 2 for i in range(n))
    var_b = sum((b[i] - mean_b) ** 2 for i in range(n))

    denom = math.sqrt(var_a * var_b)
    if denom == 0.0:
        return 0.0

    return cov / denom


# ------------------------------------------------------------------
# Correlation matrix
# ------------------------------------------------------------------
def build_correlation_matrix(
    pair_closes: dict[str, list[float]],
    lookback: int = CORRELATION_LOOKBACK_BARS,
) -> dict[tuple[str, str], float]:
    """Build pairwise correlation matrix from close price series.

    Parameters
    ----------
    pair_closes:
        Mapping of pair symbol to list of close prices (oldest first).
    lookback:
        Number of most recent bars to use for correlation.

    Returns
    -------
    Dict mapping (pair_a, pair_b) → ρ for all unique pairs (a < b).
    """
    pairs = sorted(pair_closes.keys())
    pair_returns: dict[str, list[float]] = {}

    for pair in pairs:
        closes = pair_closes[pair][-lookback:] if lookback > 0 else pair_closes[pair]
        pair_returns[pair] = compute_returns(closes)

    matrix: dict[tuple[str, str], float] = {}
    for i, pair_a in enumerate(pairs):
        for pair_b in pairs[i + 1 :]:
            rho = compute_correlation(pair_returns[pair_a], pair_returns[pair_b])
            matrix[(pair_a, pair_b)] = rho
    return matrix


def get_correlation(
    pair_a: str,
    pair_b: str,
    matrix: dict[tuple[str, str], float],
) -> float:
    """Look up correlation between two pairs from a matrix.

    Handles key ordering automatically.
    """
    if pair_a == pair_b:
        return 1.0
    key = (min(pair_a, pair_b), max(pair_a, pair_b))
    return matrix.get(key, 0.0)


# ------------------------------------------------------------------
# Signal blocking
# ------------------------------------------------------------------
def check_signal_allowed(
    pair: str,
    open_pairs: list[str],
    correlation_matrix: dict[tuple[str, str], float],
    max_correlation: float = DEFAULT_MAX_CORRELATION,
) -> CorrelationCheckResult:
    """Check whether a new signal on *pair* should be blocked.

    A signal is blocked when correlation ρ with any currently open
    pair exceeds *max_correlation*.

    Parameters
    ----------
    pair:
        The pair where a new signal was detected.
    open_pairs:
        List of pairs that currently have open positions.
    correlation_matrix:
        Pre-computed pairwise correlation matrix.
    max_correlation:
        Maximum allowed absolute correlation.

    Returns
    -------
    CorrelationCheckResult indicating whether the signal is allowed.
    """
    if not open_pairs:
        return CorrelationCheckResult(
            allowed=True,
            reason="no_open_positions",
            max_rho=0.0,
            blocking_pair="",
        )

    worst_rho = 0.0
    worst_pair = ""

    for open_pair in open_pairs:
        if open_pair == pair:
            continue
        rho = abs(get_correlation(pair, open_pair, correlation_matrix))
        if rho > worst_rho:
            worst_rho = rho
            worst_pair = open_pair

    if worst_rho > max_correlation:
        return CorrelationCheckResult(
            allowed=False,
            reason=f"correlation_too_high ({pair}/{worst_pair} ρ={worst_rho:.3f})",
            max_rho=worst_rho,
            blocking_pair=worst_pair,
        )

    return CorrelationCheckResult(
        allowed=True,
        reason="correlation_acceptable",
        max_rho=worst_rho,
        blocking_pair="",
    )


# ------------------------------------------------------------------
# Risk adjustment
# ------------------------------------------------------------------
def adjust_risk_for_correlation(
    base_risk_pct: float,
    pair: str,
    open_pairs: list[str],
    correlation_matrix: dict[tuple[str, str], float],
    max_correlation: float = DEFAULT_MAX_CORRELATION,
    risk_decay: float = CORRELATION_RISK_DECAY,
) -> RiskAdjustmentResult:
    """Adjust risk percentage based on correlation with open positions.

    For each open pair with |ρ| > *max_correlation*, the base risk
    is multiplied by *risk_decay*.  Multiple correlated open positions
    compound the reduction.

    Parameters
    ----------
    base_risk_pct:
        Starting risk percentage (e.g. 1.0 for 1%).
    pair:
        The pair about to be traded.
    open_pairs:
        Currently open position pairs.
    correlation_matrix:
        Pre-computed pairwise correlation matrix.
    max_correlation:
        Threshold above which correlation triggers risk reduction.
    risk_decay:
        Multiplicative factor per correlated open pair (e.g. 0.5).

    Returns
    -------
    RiskAdjustmentResult with the adjusted risk and details.
    """
    if not open_pairs:
        return RiskAdjustmentResult(
            adjusted_risk_pct=base_risk_pct,
            total_correlation=0.0,
            n_correlated=0,
        )

    correlated_count = 0
    total_rho = 0.0

    for open_pair in open_pairs:
        if open_pair == pair:
            continue
        rho = abs(get_correlation(pair, open_pair, correlation_matrix))
        if rho > max_correlation:
            correlated_count += 1
            total_rho += rho

    adjusted = base_risk_pct * (risk_decay**correlated_count)

    return RiskAdjustmentResult(
        adjusted_risk_pct=round(adjusted, 6),
        total_correlation=round(total_rho, 6),
        n_correlated=correlated_count,
    )
