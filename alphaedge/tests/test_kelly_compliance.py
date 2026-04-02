"""Test suite for Kelly Criterion compliance validation (C-ST-02)."""

import pytest

from alphaedge.engine.backtest_stats import validate_kelly_compliance


class TestKellyCriterionValidation:
    """Validate Kelly Criterion compliance for ALPHAEDGE risk management."""

    def test_alphaedge_baseline_compliance(self):
        """Test compliance on baseline backtest metrics (N=579).

        Baseline: WR = 46.11%, PF = 1.454, risk_pct = 0.67%
        Expected: Kelly f* ≈ 14.40%, Quarter-Kelly ≈ 3.60%, 0.67% << 3.60%
        """
        result = validate_kelly_compliance(
            risk_pct=0.67,
            wr=0.4611,
            pf=1.454,
            tolerance_factor=4,
        )

        assert result["is_compliant"] is True
        assert result["kelly_fraction"] == pytest.approx(0.1440, abs=0.001)
        assert result["kelly_fractional"] == pytest.approx(0.0360, abs=0.0005)
        assert result["margin_pct"] == pytest.approx(2.93, abs=0.05)

    def test_quarter_kelly_threshold(self):
        """Test that risk_pct is ~18.6% of quarter-Kelly (highly conservative)."""
        result = validate_kelly_compliance(
            risk_pct=0.67,
            wr=0.4611,
            pf=1.454,
            tolerance_factor=4,
        )

        threshold = result["kelly_fractional"] * 100
        ratio = (result["risk_pct"] / threshold) * 100

        assert ratio == pytest.approx(18.6, abs=0.5)
        assert result["margin_pct"] > 2.5

    def test_half_kelly_conservative_comparison(self):
        """Verify ALPHAEDGE is extremely conservative vs half-Kelly."""
        result = validate_kelly_compliance(
            risk_pct=0.67,
            wr=0.4611,
            pf=1.454,
            tolerance_factor=2,
        )

        half_kelly = result["kelly_fractional"] * 100
        assert result["risk_pct"] < half_kelly
        margin_vs_half = ((half_kelly - result["risk_pct"]) / half_kelly) * 100
        assert margin_vs_half > 90

    def test_strict_kelly_massive_buffer(self):
        """Verify >95% margin vs strict Kelly (f*)."""
        result = validate_kelly_compliance(
            risk_pct=0.67,
            wr=0.4611,
            pf=1.454,
            tolerance_factor=1,
        )

        strict_kelly = result["kelly_fractional"] * 100
        margin_vs_strict = ((strict_kelly - result["risk_pct"]) / strict_kelly) * 100
        assert margin_vs_strict > 94

    def test_worst_case_wr_42_percent(self):
        """Worst-case: WR drops to IC95 lower bound (42.05%)."""
        result = validate_kelly_compliance(
            risk_pct=0.67,
            wr=0.42,
            pf=1.454,
            tolerance_factor=4,
        )

        assert result["is_compliant"] is True
        assert result["margin_pct"] >= 1.0

    def test_worst_case_pf_drops_to_ruin(self):
        """Worst-case: PF drops to breakeven level (1.30)."""
        result = validate_kelly_compliance(
            risk_pct=0.67,
            wr=0.4611,
            pf=1.30,
            tolerance_factor=4,
        )

        assert result["is_compliant"] is True
        assert result["margin_pct"] > 0.4

    def test_zero_risk_always_compliant(self):
        """Boundary: Zero risk is always compliant."""
        result = validate_kelly_compliance(
            risk_pct=0.0,
            wr=0.35,
            pf=0.9,
            tolerance_factor=4,
        )

        assert result["is_compliant"] is True
        assert result["margin_pct"] >= 0

    def test_losing_system_kelly_zero(self):
        """Edge case: Losing system (WR = 40%, PF = 0.9)."""
        result = validate_kelly_compliance(
            risk_pct=0.67,
            wr=0.40,
            pf=0.90,
            tolerance_factor=4,
        )

        assert result["kelly_fraction"] <= 0
        assert result["is_compliant"] is False

    def test_breakeven_system_minimal_kelly(self):
        """Edge case: Breakeven system (WR = 50%, PF = 1.0)."""
        result = validate_kelly_compliance(
            risk_pct=0.67,
            wr=0.50,
            pf=1.0,
            tolerance_factor=4,
        )

        assert result["kelly_fraction"] == pytest.approx(0.0, abs=0.01)

    def test_high_edge_generous_kelly(self):
        """Favorable scenario: Strong edge (WR = 55%, PF = 2.0)."""
        result = validate_kelly_compliance(
            risk_pct=0.67,
            wr=0.55,
            pf=2.0,
            tolerance_factor=4,
        )

        assert result["is_compliant"] is True
        assert result["kelly_fraction"] == pytest.approx(0.275, abs=0.01)
        assert result["margin_pct"] > 6

    def test_return_dict_structure(self):
        """Verify return dictionary structure and value types."""
        result = validate_kelly_compliance(
            risk_pct=0.67,
            wr=0.4611,
            pf=1.454,
            tolerance_factor=4,
        )

        required_keys = {
            "kelly_fraction",
            "kelly_fractional",
            "risk_pct",
            "is_compliant",
            "margin_pct",
        }
        assert set(result.keys()) == required_keys

        assert isinstance(result["kelly_fraction"], float)
        assert isinstance(result["kelly_fractional"], float)
        assert isinstance(result["risk_pct"], float)
        assert isinstance(result["is_compliant"], bool)
        assert isinstance(result["margin_pct"], float)

        assert 0 <= result["kelly_fraction"] <= 1.0
        assert result["risk_pct"] >= 0
        assert result["margin_pct"] >= -10

    def test_compliance_status_message_format(self):
        """Verify compliance result can be formatted as log message."""
        result = validate_kelly_compliance(
            risk_pct=0.67,
            wr=0.4611,
            pf=1.454,
            tolerance_factor=4,
        )

        status = "CONFORME" if result["is_compliant"] else "NON-CONFORME"
        msg = (
            f"Kelly Validation: risk_pct={result['risk_pct']}% "
            f"vs threshold={result['kelly_fractional'] * 100:.2f}% "
            f"({status})"
        )

        assert "CONFORME" in msg
        assert isinstance(msg, str)
