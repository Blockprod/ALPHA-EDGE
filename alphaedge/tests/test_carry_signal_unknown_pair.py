# ============================================================
# PROJECT      : ALPHAEDGE
# FILE         : alphaedge/tests/test_carry_signal_unknown_pair.py
# DESCRIPTION  : Guard: unknown pair or missing rate → is_valid=False
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-25
# ============================================================
"""ALPHAEDGE — Carry signal: unknown pair / missing rate → is_valid=False."""

from __future__ import annotations

import pytest

from alphaedge.engine.carry_signal import get_carry_bias

_RATES: dict[str, float] = {"AUD": 4.35, "JPY": 0.10, "USD": 5.25}


@pytest.mark.parametrize("pair", ["XYZABC", "", "INVALID", "BTC/USD"])
def test_unknown_pair_is_invalid(pair: str) -> None:
    result = get_carry_bias(pair, _RATES)
    assert result.is_valid is False
    assert result.direction == "NEUTRAL"
    assert result.differential == 0.0
    assert result.daily_carry_pips == 0.0


def test_missing_base_rate() -> None:
    """If base currency rate is absent → is_valid=False."""
    rates_no_aud = {"JPY": 0.10, "USD": 5.25}
    result = get_carry_bias("AUDJPY", rates_no_aud)
    assert result.is_valid is False


def test_missing_quote_rate() -> None:
    """If quote currency rate is absent → is_valid=False."""
    rates_no_jpy = {"AUD": 4.35, "USD": 5.25}
    result = get_carry_bias("AUDJPY", rates_no_jpy)
    assert result.is_valid is False


def test_empty_rates_dict() -> None:
    result = get_carry_bias("EURUSD", {})
    assert result.is_valid is False


def test_valid_pair_stays_valid() -> None:
    """Sanity: a known pair with full rates is still valid."""
    result = get_carry_bias("AUDJPY", _RATES)
    assert result.is_valid is True
