# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/tests/test_backtest_simulation_carry_long.py
# DESCRIPTION  : compute_overnight_carry — LONG carry gain scenario
# SCENARIO     : AUD/JPY LONG with AUD 4.35% / JPY 0.10% → positive carry
# PYTHON       : 3.11.9
# ============================================================
"""ALPHAEDGE — compute_overnight_carry: LONG carry gain (AUDJPY)."""

from __future__ import annotations

import pytest

from alphaedge.engine.backtest_simulation import compute_overnight_carry


class TestComputeOvernightCarryLong:
    """C-09 · LONG carry gain scenario."""

    _RATES = {"AUD": 4.35, "JPY": 0.10}
    _PIP_SIZE = 0.01  # JPY pairs

    def test_long_audjpy_positive_carry(self) -> None:
        """LONG AUDJPY with AUD > JPY rate → carry in pips must be positive."""
        carry = compute_overnight_carry(
            pair="AUDJPY",
            direction=1,
            days_held=1,
            rates=self._RATES,
            lot_size=1.0,
            pip_size=self._PIP_SIZE,
        )
        assert carry > 0.0

    def test_long_carry_scales_with_days(self) -> None:
        """Carry over 5 days must be exactly 5× the single-day carry."""
        carry_1d = compute_overnight_carry(
            pair="AUDJPY",
            direction=1,
            days_held=1,
            rates=self._RATES,
            lot_size=1.0,
            pip_size=self._PIP_SIZE,
        )
        carry_5d = compute_overnight_carry(
            pair="AUDJPY",
            direction=1,
            days_held=5,
            rates=self._RATES,
            lot_size=1.0,
            pip_size=self._PIP_SIZE,
        )
        assert carry_5d == pytest.approx(carry_1d * 5, rel=1e-9)

    def test_long_carry_formula(self) -> None:
        """Verify the carry value against the expected formula."""
        differential = 4.35 - 0.10  # = 4.25 %
        expected = differential * 1 / 100.0 / 365.0 / self._PIP_SIZE * 3
        carry = compute_overnight_carry(
            pair="AUDJPY",
            direction=1,
            days_held=3,
            rates=self._RATES,
            lot_size=1.0,
            pip_size=self._PIP_SIZE,
        )
        assert carry == pytest.approx(expected, rel=1e-9)
