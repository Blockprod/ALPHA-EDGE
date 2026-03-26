# ============================================================
# PROJECT      : ALPHAEDGE
# FILE         : alphaedge/tests/test_carry_signal_neutral.py
# DESCRIPTION  : No-signal: differential < min_differential → NEUTRAL
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-25
# ============================================================
"""ALPHAEDGE — Carry signal: near-zero differential → NEUTRAL."""

from __future__ import annotations

import pytest

from alphaedge.engine.carry_signal import get_carry_bias

# EUR vs GBP: very small differential → sits below the 0.5% threshold
_TIGHT_RATES: dict[str, float] = {
    "EUR": 3.65,
    "GBP": 3.90,  # differential = -0.25% → within ±0.5% → NEUTRAL
    "USD": 5.25,
}

_ZERO_RATES: dict[str, float] = {
    "EUR": 3.65,
    "USD": 3.65,  # differential = 0.0 → NEUTRAL
}


def test_neutral_direction_small_differential() -> None:
    result = get_carry_bias("EURGBP", _TIGHT_RATES)
    assert result.is_valid is True
    assert result.direction == "NEUTRAL"
    assert abs(result.differential) < 0.5


def test_neutral_direction_zero_differential() -> None:
    result = get_carry_bias("EURUSD", _ZERO_RATES)
    assert result.is_valid is True
    assert result.direction == "NEUTRAL"
    assert result.differential == 0.0


@pytest.mark.parametrize("threshold", [0.1, 0.5, 1.0, 2.0])
def test_threshold_controls_neutral(threshold: float) -> None:
    """Differential of exactly 0.0 is always NEUTRAL regardless of threshold."""
    result = get_carry_bias("EURUSD", _ZERO_RATES, min_differential=threshold)
    assert result.direction == "NEUTRAL"


def test_short_bias_when_negative_differential() -> None:
    rates = {"EUR": 3.65, "GBP": 5.50}  # differential = -1.85 → SHORT
    result = get_carry_bias("EURGBP", rates)
    assert result.is_valid is True
    assert result.direction == "SHORT"
    assert result.differential < -0.5
