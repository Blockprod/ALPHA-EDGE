# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_pair_correlation.py
# DESCRIPTION  : Tests for multi-pair correlation module
# ============================================================
"""ALPHAEDGE — T4.4: Pair correlation tests."""

from __future__ import annotations

from alphaedge.config.constants import (
    CORRELATION_LOOKBACK_BARS,
    CORRELATION_RISK_DECAY,
    DEFAULT_MAX_CORRELATION,
)
from alphaedge.utils.pair_correlation import (
    adjust_risk_for_correlation,
    build_correlation_matrix,
    check_signal_allowed,
    compute_correlation,
    compute_returns,
    get_correlation,
)


# ------------------------------------------------------------------
# Constants sanity checks
# ------------------------------------------------------------------
class TestConstants:
    def test_max_correlation_default(self) -> None:
        assert DEFAULT_MAX_CORRELATION == 0.7

    def test_risk_decay_default(self) -> None:
        assert CORRELATION_RISK_DECAY == 0.5

    def test_lookback_bars_default(self) -> None:
        assert CORRELATION_LOOKBACK_BARS == 100


# ------------------------------------------------------------------
# compute_returns
# ------------------------------------------------------------------
class TestComputeReturns:
    def test_basic_returns(self) -> None:
        closes = [100.0, 110.0, 121.0]
        r = compute_returns(closes)
        assert len(r) == 2
        assert abs(r[0] - 0.1) < 1e-10
        assert abs(r[1] - 0.1) < 1e-10

    def test_empty_list(self) -> None:
        assert compute_returns([]) == []

    def test_single_price(self) -> None:
        assert compute_returns([100.0]) == []

    def test_two_prices(self) -> None:
        r = compute_returns([100.0, 105.0])
        assert len(r) == 1
        assert abs(r[0] - 0.05) < 1e-10

    def test_negative_return(self) -> None:
        r = compute_returns([100.0, 90.0])
        assert len(r) == 1
        assert abs(r[0] - (-0.1)) < 1e-10

    def test_zero_price_skipped(self) -> None:
        """Division by zero should be skipped."""
        r = compute_returns([0.0, 100.0, 110.0])
        assert len(r) == 1
        assert abs(r[0] - 0.1) < 1e-10


# ------------------------------------------------------------------
# compute_correlation
# ------------------------------------------------------------------
class TestComputeCorrelation:
    def test_perfect_positive(self) -> None:
        a = [0.01, 0.02, 0.03, 0.04, 0.05]
        b = [0.02, 0.04, 0.06, 0.08, 0.10]
        rho = compute_correlation(a, b)
        assert abs(rho - 1.0) < 1e-10

    def test_perfect_negative(self) -> None:
        a = [0.01, 0.02, 0.03, 0.04, 0.05]
        b = [-0.01, -0.02, -0.03, -0.04, -0.05]
        rho = compute_correlation(a, b)
        assert abs(rho - (-1.0)) < 1e-10

    def test_zero_correlation_constant(self) -> None:
        """Constant series has zero variance → returns 0.0."""
        a = [0.01, 0.02, 0.03, 0.04]
        b = [0.05, 0.05, 0.05, 0.05]
        rho = compute_correlation(a, b)
        assert rho == 0.0

    def test_too_few_values(self) -> None:
        assert compute_correlation([0.01], [0.02]) == 0.0

    def test_empty_lists(self) -> None:
        assert compute_correlation([], []) == 0.0

    def test_different_lengths_uses_min(self) -> None:
        a = [0.01, 0.02, 0.03, 0.04, 0.05]
        b = [0.02, 0.04, 0.06]
        rho = compute_correlation(a, b)
        assert abs(rho - 1.0) < 1e-10

    def test_uncorrelated(self) -> None:
        """Orthogonal-ish series should produce near-zero correlation."""
        a = [1.0, -1.0, 1.0, -1.0]
        b = [1.0, 1.0, -1.0, -1.0]
        rho = compute_correlation(a, b)
        assert abs(rho) < 1e-10


# ------------------------------------------------------------------
# build_correlation_matrix
# ------------------------------------------------------------------
class TestBuildCorrelationMatrix:
    def _make_closes(self, base: float, n: int, step: float) -> list[float]:
        return [base + i * step for i in range(n)]

    def test_two_pairs_perfectly_correlated(self) -> None:
        closes_a = self._make_closes(1.0800, 50, 0.0001)
        closes_b = self._make_closes(1.3000, 50, 0.0002)
        matrix = build_correlation_matrix(
            {"EURUSD": closes_a, "GBPUSD": closes_b}, lookback=50
        )
        assert ("EURUSD", "GBPUSD") in matrix
        assert matrix[("EURUSD", "GBPUSD")] > 0.99

    def test_three_pairs_matrix_keys(self) -> None:
        closes = {
            "AUDUSD": self._make_closes(0.6500, 30, 0.0001),
            "EURUSD": self._make_closes(1.0800, 30, 0.0001),
            "GBPUSD": self._make_closes(1.3000, 30, 0.0001),
        }
        matrix = build_correlation_matrix(closes, lookback=30)
        assert len(matrix) == 3  # C(3,2) = 3
        assert ("AUDUSD", "EURUSD") in matrix
        assert ("AUDUSD", "GBPUSD") in matrix
        assert ("EURUSD", "GBPUSD") in matrix

    def test_lookback_truncation(self) -> None:
        """Only the last `lookback` bars should be used."""
        # First 50 bars diverge, last 10 converge
        closes_a = [1.0 + i * 0.001 for i in range(50)] + [
            2.0 + i * 0.001 for i in range(10)
        ]
        closes_b = [1.0 - i * 0.001 for i in range(50)] + [
            2.0 + i * 0.001 for i in range(10)
        ]
        matrix = build_correlation_matrix({"A": closes_a, "B": closes_b}, lookback=10)
        assert matrix[("A", "B")] > 0.99

    def test_single_pair_empty_matrix(self) -> None:
        matrix = build_correlation_matrix({"EURUSD": [1.08, 1.09, 1.10]}, lookback=100)
        assert matrix == {}

    def test_empty_input(self) -> None:
        matrix = build_correlation_matrix({}, lookback=100)
        assert matrix == {}


# ------------------------------------------------------------------
# get_correlation
# ------------------------------------------------------------------
class TestGetCorrelation:
    def test_same_pair(self) -> None:
        assert get_correlation("EURUSD", "EURUSD", {}) == 1.0

    def test_forward_key(self) -> None:
        matrix = {("EURUSD", "GBPUSD"): 0.85}
        assert get_correlation("EURUSD", "GBPUSD", matrix) == 0.85

    def test_reverse_key(self) -> None:
        matrix = {("EURUSD", "GBPUSD"): 0.85}
        assert get_correlation("GBPUSD", "EURUSD", matrix) == 0.85

    def test_missing_key(self) -> None:
        assert get_correlation("EURUSD", "USDJPY", {}) == 0.0


# ------------------------------------------------------------------
# check_signal_allowed
# ------------------------------------------------------------------
class TestCheckSignalAllowed:
    def test_no_open_positions(self) -> None:
        result = check_signal_allowed("EURUSD", [], {})
        assert result.allowed is True
        assert result.reason == "no_open_positions"
        assert result.max_rho == 0.0

    def test_blocked_high_correlation(self) -> None:
        matrix = {("EURUSD", "GBPUSD"): 0.85}
        result = check_signal_allowed("EURUSD", ["GBPUSD"], matrix, max_correlation=0.7)
        assert result.allowed is False
        assert "correlation_too_high" in result.reason
        assert result.blocking_pair == "GBPUSD"
        assert abs(result.max_rho - 0.85) < 1e-10

    def test_allowed_low_correlation(self) -> None:
        matrix = {("EURUSD", "USDJPY"): 0.3}
        result = check_signal_allowed("EURUSD", ["USDJPY"], matrix, max_correlation=0.7)
        assert result.allowed is True
        assert result.reason == "correlation_acceptable"
        assert abs(result.max_rho - 0.3) < 1e-10

    def test_exact_threshold_allowed(self) -> None:
        """ρ exactly at threshold should be allowed (> not >=)."""
        matrix = {("EURUSD", "GBPUSD"): 0.7}
        result = check_signal_allowed("EURUSD", ["GBPUSD"], matrix, max_correlation=0.7)
        assert result.allowed is True

    def test_negative_correlation_blocks(self) -> None:
        """Negative ρ with |ρ| > threshold should block."""
        matrix = {("EURUSD", "USDCHF"): -0.85}
        result = check_signal_allowed("EURUSD", ["USDCHF"], matrix, max_correlation=0.7)
        assert result.allowed is False
        assert abs(result.max_rho - 0.85) < 1e-10

    def test_multiple_open_worst_blocks(self) -> None:
        """If one of several open pairs exceeds threshold, signal is blocked."""
        matrix = {
            ("EURUSD", "GBPUSD"): 0.85,
            ("EURUSD", "USDJPY"): 0.2,
        }
        result = check_signal_allowed(
            "EURUSD", ["GBPUSD", "USDJPY"], matrix, max_correlation=0.7
        )
        assert result.allowed is False
        assert result.blocking_pair == "GBPUSD"

    def test_same_pair_in_open_ignored(self) -> None:
        """If the signal pair is already in open_pairs, ignore it."""
        matrix = {("EURUSD", "GBPUSD"): 0.4}
        result = check_signal_allowed(
            "EURUSD", ["EURUSD", "GBPUSD"], matrix, max_correlation=0.7
        )
        assert result.allowed is True
        assert abs(result.max_rho - 0.4) < 1e-10

    def test_custom_threshold(self) -> None:
        matrix = {("AUDUSD", "NZDUSD"): 0.55}
        result = check_signal_allowed("AUDUSD", ["NZDUSD"], matrix, max_correlation=0.5)
        assert result.allowed is False


# ------------------------------------------------------------------
# adjust_risk_for_correlation
# ------------------------------------------------------------------
class TestAdjustRiskForCorrelation:
    def test_no_open_positions(self) -> None:
        result = adjust_risk_for_correlation(1.0, "EURUSD", [], {})
        assert result.adjusted_risk_pct == 1.0
        assert result.n_correlated == 0

    def test_one_correlated_pair(self) -> None:
        matrix = {("EURUSD", "GBPUSD"): 0.85}
        result = adjust_risk_for_correlation(
            1.0, "EURUSD", ["GBPUSD"], matrix, max_correlation=0.7, risk_decay=0.5
        )
        assert abs(result.adjusted_risk_pct - 0.5) < 1e-6
        assert result.n_correlated == 1

    def test_two_correlated_pairs(self) -> None:
        matrix = {
            ("AUDUSD", "EURUSD"): 0.80,
            ("AUDUSD", "GBPUSD"): 0.75,
        }
        result = adjust_risk_for_correlation(
            1.0,
            "AUDUSD",
            ["EURUSD", "GBPUSD"],
            matrix,
            max_correlation=0.7,
            risk_decay=0.5,
        )
        # 1.0 * 0.5^2 = 0.25
        assert abs(result.adjusted_risk_pct - 0.25) < 1e-6
        assert result.n_correlated == 2

    def test_uncorrelated_no_reduction(self) -> None:
        matrix = {("EURUSD", "USDJPY"): 0.3}
        result = adjust_risk_for_correlation(
            1.0, "EURUSD", ["USDJPY"], matrix, max_correlation=0.7, risk_decay=0.5
        )
        assert result.adjusted_risk_pct == 1.0
        assert result.n_correlated == 0

    def test_mixed_correlated_uncorrelated(self) -> None:
        matrix = {
            ("EURUSD", "GBPUSD"): 0.85,
            ("EURUSD", "USDJPY"): 0.2,
        }
        result = adjust_risk_for_correlation(
            1.0,
            "EURUSD",
            ["GBPUSD", "USDJPY"],
            matrix,
            max_correlation=0.7,
            risk_decay=0.5,
        )
        # Only GBPUSD is correlated → 1.0 * 0.5^1 = 0.5
        assert abs(result.adjusted_risk_pct - 0.5) < 1e-6
        assert result.n_correlated == 1

    def test_custom_risk_decay(self) -> None:
        matrix = {("EURUSD", "GBPUSD"): 0.9}
        result = adjust_risk_for_correlation(
            2.0,
            "EURUSD",
            ["GBPUSD"],
            matrix,
            max_correlation=0.7,
            risk_decay=0.75,
        )
        assert abs(result.adjusted_risk_pct - 1.5) < 1e-6

    def test_total_correlation_sum(self) -> None:
        matrix = {
            ("AUDUSD", "EURUSD"): 0.80,
            ("AUDUSD", "GBPUSD"): 0.75,
        }
        result = adjust_risk_for_correlation(
            1.0,
            "AUDUSD",
            ["EURUSD", "GBPUSD"],
            matrix,
            max_correlation=0.7,
            risk_decay=0.5,
        )
        assert abs(result.total_correlation - 1.55) < 1e-6

    def test_same_pair_ignored(self) -> None:
        matrix = {("EURUSD", "GBPUSD"): 0.4}
        result = adjust_risk_for_correlation(
            1.0, "EURUSD", ["EURUSD"], matrix, max_correlation=0.7, risk_decay=0.5
        )
        assert result.adjusted_risk_pct == 1.0
        assert result.n_correlated == 0


# ------------------------------------------------------------------
# Integration: end-to-end with build_correlation_matrix
# ------------------------------------------------------------------
class TestIntegration:
    def test_correlated_pairs_blocked(self) -> None:
        """EURUSD and GBPUSD trending together → signal blocked."""
        n = 60
        closes_eu = [1.0800 + i * 0.0002 for i in range(n)]
        closes_gb = [1.3000 + i * 0.0003 for i in range(n)]

        matrix = build_correlation_matrix(
            {"EURUSD": closes_eu, "GBPUSD": closes_gb}, lookback=50
        )
        result = check_signal_allowed("EURUSD", ["GBPUSD"], matrix)
        assert result.allowed is False

    def test_uncorrelated_pairs_allowed(self) -> None:
        """EURUSD and USDJPY with independent movement → allowed."""
        import random

        rng = random.Random(42)
        n = 120
        closes_eu = [1.0800 + i * 0.0001 for i in range(n)]
        closes_jpy: list[float] = [110.00]
        for _ in range(n - 1):
            closes_jpy.append(closes_jpy[-1] + rng.choice([-0.05, 0.05]))

        matrix = build_correlation_matrix(
            {"EURUSD": closes_eu, "USDJPY": closes_jpy}, lookback=100
        )
        result = check_signal_allowed("EURUSD", ["USDJPY"], matrix)
        assert result.allowed is True

    def test_risk_adjusted_end_to_end(self) -> None:
        """Risk reduced when opening on correlated pair."""
        n = 60
        closes = {
            "EURUSD": [1.0800 + i * 0.0002 for i in range(n)],
            "GBPUSD": [1.3000 + i * 0.0003 for i in range(n)],
            "USDJPY": [110.0 + i * 0.01 * ((-1) ** i) for i in range(n)],
        }
        matrix = build_correlation_matrix(closes, lookback=50)
        result = adjust_risk_for_correlation(1.0, "EURUSD", ["GBPUSD"], matrix)
        assert result.adjusted_risk_pct < 1.0
        assert result.n_correlated >= 1
