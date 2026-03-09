# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_monte_carlo.py
# DESCRIPTION  : Tests for Monte Carlo drawdown estimation
# ============================================================
"""ALPHAEDGE — T3.6: Monte Carlo drawdown estimation tests."""

from __future__ import annotations

import os
import tempfile

import pytest

from alphaedge.engine.monte_carlo import (
    MonteCarloReport,
    _compute_max_drawdown_from_pnls,
    generate_drawdown_histogram,
    run_monte_carlo,
)


# ------------------------------------------------------------------
# _compute_max_drawdown_from_pnls
# ------------------------------------------------------------------
class TestComputeMaxDrawdownFromPnls:
    def test_empty_returns_zero(self) -> None:
        assert _compute_max_drawdown_from_pnls([]) == 0.0

    def test_all_wins_zero_drawdown(self) -> None:
        pnls = [100.0, 50.0, 200.0, 75.0]
        assert _compute_max_drawdown_from_pnls(pnls) == 0.0

    def test_single_loss(self) -> None:
        # Start 10000, lose 1000 → dd = 10%
        dd = _compute_max_drawdown_from_pnls([-1000.0], 10000.0)
        assert dd == pytest.approx(10.0)

    def test_recovery_tracks_peak(self) -> None:
        # 10000 → +500 = 10500 (peak) → -1050 = 9450 → dd = 10%
        pnls = [500.0, -1050.0]
        dd = _compute_max_drawdown_from_pnls(pnls, 10000.0)
        assert dd == pytest.approx(10.0)

    def test_multiple_drawdowns_takes_max(self) -> None:
        # 10000→+1000=11000→-1100=9900(dd=10%)→+2100=12000→-2400=9600(dd=20%)
        pnls = [1000.0, -1100.0, 2100.0, -2400.0]
        dd = _compute_max_drawdown_from_pnls(pnls, 10000.0)
        assert dd == pytest.approx(20.0)

    def test_starting_equity_respected(self) -> None:
        dd1 = _compute_max_drawdown_from_pnls([-500.0], 10000.0)
        dd2 = _compute_max_drawdown_from_pnls([-500.0], 5000.0)
        assert dd2 > dd1  # Same loss on smaller equity = larger drawdown


# ------------------------------------------------------------------
# run_monte_carlo
# ------------------------------------------------------------------
class TestRunMonteCarlo:
    def test_report_structure(self) -> None:
        pnls = [100.0, -50.0, 200.0, -80.0, 150.0, -120.0]
        report = run_monte_carlo(pnls, n_permutations=100, seed=42)
        assert isinstance(report, MonteCarloReport)
        assert report.n_permutations == 100
        assert len(report.drawdowns) == 100

    def test_10000_permutations(self) -> None:
        pnls = [50.0, -30.0, 80.0, -60.0, 40.0, -20.0, 70.0, -45.0]
        report = run_monte_carlo(pnls, n_permutations=10000, seed=42)
        assert report.n_permutations == 10000
        assert len(report.drawdowns) == 10000

    def test_percentiles_ordered(self) -> None:
        pnls = [100.0, -50.0, 200.0, -80.0, 150.0, -120.0, 60.0, -90.0]
        report = run_monte_carlo(pnls, n_permutations=1000, seed=42)
        assert report.drawdown_median <= report.drawdown_95th
        assert report.drawdown_95th <= report.drawdown_99th

    def test_all_positive_minimal_drawdown(self) -> None:
        pnls = [100.0, 200.0, 150.0, 300.0]
        report = run_monte_carlo(pnls, n_permutations=100, seed=42)
        assert report.drawdown_median == 0.0
        assert report.drawdown_95th == 0.0

    def test_seed_reproducibility(self) -> None:
        pnls = [100.0, -50.0, 200.0, -80.0]
        r1 = run_monte_carlo(pnls, n_permutations=200, seed=123)
        r2 = run_monte_carlo(pnls, n_permutations=200, seed=123)
        assert r1.drawdown_median == r2.drawdown_median
        assert r1.drawdown_95th == r2.drawdown_95th
        assert r1.drawdowns == r2.drawdowns

    def test_empty_pnls(self) -> None:
        report = run_monte_carlo([], n_permutations=100, seed=42)
        assert report.n_permutations == 0
        assert report.drawdowns == []

    def test_suggested_risk_positive(self) -> None:
        pnls = [100.0, -50.0, 200.0, -80.0, 150.0, -120.0]
        report = run_monte_carlo(pnls, n_permutations=100, seed=42)
        assert report.suggested_risk_pct > 0.0

    def test_suggested_risk_capped(self) -> None:
        # All wins → dd_95th = 0 → suggested = base_risk (capped at 5%)
        pnls = [100.0, 200.0]
        report = run_monte_carlo(pnls, n_permutations=100, base_risk_pct=1.0, seed=42)
        assert report.suggested_risk_pct <= 5.0

    def test_higher_losses_increase_drawdown(self) -> None:
        small_loss = [100.0, -10.0, 50.0, -5.0]
        big_loss = [100.0, -500.0, 50.0, -300.0]
        r1 = run_monte_carlo(small_loss, n_permutations=500, seed=42)
        r2 = run_monte_carlo(big_loss, n_permutations=500, seed=42)
        assert r2.drawdown_95th > r1.drawdown_95th


# ------------------------------------------------------------------
# generate_drawdown_histogram
# ------------------------------------------------------------------
class TestGenerateDrawdownHistogram:
    def test_generates_file(self) -> None:
        pnls = [100.0, -50.0, 200.0, -80.0, 150.0, -120.0]
        report = run_monte_carlo(pnls, n_permutations=100, seed=42)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_mc_hist.png")
            result = generate_drawdown_histogram(report, output_path=path)
            assert result == path
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0

    def test_empty_report_returns_empty_string(self) -> None:
        report = MonteCarloReport()
        result = generate_drawdown_histogram(report)
        assert result == ""

    def test_custom_output_path(self) -> None:
        pnls = [50.0, -30.0, 80.0, -60.0]
        report = run_monte_carlo(pnls, n_permutations=50, seed=42)
        with tempfile.TemporaryDirectory() as tmpdir:
            custom = os.path.join(tmpdir, "custom_mc.png")
            result = generate_drawdown_histogram(report, output_path=custom)
            assert result == custom
            assert os.path.exists(custom)
