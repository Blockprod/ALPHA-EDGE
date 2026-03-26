# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_backtest_simulation_carry_unknown.py
# DESCRIPTION  : compute_overnight_carry — unknown pair / missing rate guards
# SCENARIO     : Unrecognised pair or incomplete rates → returns 0.0 safely
# PYTHON       : 3.11.9
# ============================================================
"""ALPHAEDGE — compute_overnight_carry: unknown pair / missing rate guards."""

from __future__ import annotations

from alphaedge.engine.backtest_simulation import compute_overnight_carry


class TestComputeOvernightCarryUnknown:
    """C-09 · Unknown pair and missing rate safety guards."""

    def test_unknown_pair_returns_zero(self) -> None:
        """An unrecognised pair symbol must return 0.0 without raising."""
        carry = compute_overnight_carry(
            pair="XYZABC",
            direction=1,
            days_held=3,
            rates={"XYZ": 2.0, "ABC": 1.0},
            lot_size=1.0,
            pip_size=0.0001,
        )
        assert carry == 0.0

    def test_missing_base_rate_returns_zero(self) -> None:
        """AUDJPY with AUD rate absent → 0.0 (no KeyError)."""
        carry = compute_overnight_carry(
            pair="AUDJPY",
            direction=1,
            days_held=5,
            rates={"JPY": 0.10},  # AUD missing
            lot_size=1.0,
            pip_size=0.01,
        )
        assert carry == 0.0

    def test_missing_quote_rate_returns_zero(self) -> None:
        """AUDJPY with JPY rate absent → 0.0 (no KeyError)."""
        carry = compute_overnight_carry(
            pair="AUDJPY",
            direction=1,
            days_held=5,
            rates={"AUD": 4.35},  # JPY missing
            lot_size=1.0,
            pip_size=0.01,
        )
        assert carry == 0.0

    def test_empty_rates_returns_zero(self) -> None:
        """Empty rates dict → 0.0."""
        carry = compute_overnight_carry(
            pair="EURUSD",
            direction=1,
            days_held=2,
            rates={},
            lot_size=1.0,
            pip_size=0.0001,
        )
        assert carry == 0.0

    def test_pair_case_insensitive(self) -> None:
        """Lowercase pair symbol must resolve correctly."""
        carry_upper = compute_overnight_carry(
            pair="AUDJPY",
            direction=1,
            days_held=1,
            rates={"AUD": 4.35, "JPY": 0.10},
            lot_size=1.0,
            pip_size=0.01,
        )
        carry_lower = compute_overnight_carry(
            pair="audjpy",
            direction=1,
            days_held=1,
            rates={"AUD": 4.35, "JPY": 0.10},
            lot_size=1.0,
            pip_size=0.01,
        )
        assert carry_upper == carry_lower
