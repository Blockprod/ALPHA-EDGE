# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/tests/test_backtest_simulation_carry_short.py
# DESCRIPTION  : compute_overnight_carry — SHORT carry cost scenario
# SCENARIO     : AUD/JPY SHORT with AUD 4.35% / JPY 0.10% → negative carry
# PYTHON       : 3.11.9
# ============================================================
"""ALPHAEDGE — compute_overnight_carry: SHORT carry cost (AUDJPY)."""

from __future__ import annotations

from alphaedge.engine.backtest_simulation import compute_overnight_carry


class TestComputeOvernightCarryShort:
    """C-09 · SHORT carry cost scenario."""

    _RATES = {"AUD": 4.35, "JPY": 0.10}
    _PIP_SIZE = 0.01  # JPY pairs

    def test_short_audjpy_negative_carry(self) -> None:
        """SHORT AUDJPY with AUD > JPY rate → carry must be negative (cost)."""
        carry = compute_overnight_carry(
            pair="AUDJPY",
            direction=-1,
            days_held=1,
            rates=self._RATES,
            lot_size=1.0,
            pip_size=self._PIP_SIZE,
        )
        assert carry < 0.0

    def test_short_carry_is_opposite_of_long(self) -> None:
        """SHORT carry must be the exact negative of the equivalent LONG carry."""
        carry_long = compute_overnight_carry(
            pair="AUDJPY",
            direction=1,
            days_held=5,
            rates=self._RATES,
            lot_size=1.0,
            pip_size=self._PIP_SIZE,
        )
        carry_short = compute_overnight_carry(
            pair="AUDJPY",
            direction=-1,
            days_held=5,
            rates=self._RATES,
            lot_size=1.0,
            pip_size=self._PIP_SIZE,
        )
        assert carry_short == -carry_long

    def test_zero_days_held_returns_zero(self) -> None:
        """days_held=0 must always return 0.0 regardless of other params."""
        carry = compute_overnight_carry(
            pair="AUDJPY",
            direction=-1,
            days_held=0,
            rates=self._RATES,
            lot_size=1.0,
            pip_size=self._PIP_SIZE,
        )
        assert carry == 0.0
