# ============================================================
# PROJECT      : ALPHAEDGE
# FILE         : alphaedge/tests/test_carry_signal_audjpy.py
# DESCRIPTION  : Happy-path: AUD/JPY high carry → direction="LONG"
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-25
# ============================================================
"""ALPHAEDGE — Carry signal: AUD/JPY bull carry detection."""

from __future__ import annotations

import pytest

from alphaedge.engine.carry_signal import CarrySignal, get_carry_bias

_RATES: dict[str, float] = {
    "AUD": 4.35,
    "JPY": 0.10,
    "USD": 5.25,
    "EUR": 3.65,
    "GBP": 5.00,
}


def test_audjpy_direction_long() -> None:
    result = get_carry_bias("AUDJPY", _RATES)
    assert result.is_valid is True
    assert result.direction == "LONG"


def test_audjpy_differential() -> None:
    result = get_carry_bias("AUDJPY", _RATES)
    assert abs(result.differential - 4.25) < 1e-9


def test_audjpy_daily_carry_positive() -> None:
    result = get_carry_bias("AUDJPY", _RATES)
    assert result.daily_carry_pips > 0.0


def test_audjpy_is_carry_signal_dataclass() -> None:
    result = get_carry_bias("AUDJPY", _RATES)
    assert isinstance(result, CarrySignal)


@pytest.mark.parametrize("pair", ["AUDJPY", "audjpy", "AudJpy"])
def test_case_insensitive(pair: str) -> None:
    result = get_carry_bias(pair, _RATES)
    assert result.is_valid is True
    assert result.direction == "LONG"
