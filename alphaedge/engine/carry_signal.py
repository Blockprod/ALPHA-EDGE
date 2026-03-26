# ============================================================
# PROJECT      : ALPHAEDGE
# FILE         : alphaedge/engine/carry_signal.py
# DESCRIPTION  : Carry bias computation for Momentum+Carry strategy
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-25
# ============================================================
"""ALPHAEDGE — Carry signal (Lustig 2011): directional bias from rate differentials."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from alphaedge.config.constants import DEFAULT_CARRY_MIN_DIFFERENTIAL

# Mapping of FX pair symbol → (base_currency, quote_currency)
_PAIR_CURRENCIES: dict[str, tuple[str, str]] = {
    "EURUSD": ("EUR", "USD"),
    "GBPUSD": ("GBP", "USD"),
    "USDJPY": ("USD", "JPY"),
    "AUDUSD": ("AUD", "USD"),
    "NZDUSD": ("NZD", "USD"),
    "USDCAD": ("USD", "CAD"),
    "USDCHF": ("USD", "CHF"),
    "EURJPY": ("EUR", "JPY"),
    "GBPJPY": ("GBP", "JPY"),
    "EURGBP": ("EUR", "GBP"),
    "AUDJPY": ("AUD", "JPY"),
    "CHFJPY": ("CHF", "JPY"),
}

# Approximate lot size (units of base currency) for 1 micro lot
_MICRO_LOT_UNITS: float = 1_000.0
# Trading days per year (used for daily carry approximation)
_TRADING_DAYS_PER_YEAR: float = 252.0


@dataclass(frozen=True)
class CarrySignal:
    """Carry bias for a single FX pair.

    Attributes
    ----------
    differential:
        base_rate - quote_rate (annualised, %).
        Positive → base currency pays more → LONG bias.
    direction:
        "LONG"    if differential > DEFAULT_CARRY_MIN_DIFFERENTIAL
        "SHORT"   if differential < -DEFAULT_CARRY_MIN_DIFFERENTIAL
        "NEUTRAL" otherwise
    daily_carry_pips:
        Estimated carry per calendar day per micro lot (pips).
        Positive = gain for the holder.
    is_valid:
        False when the pair is unrecognised or a rate is missing.
    """

    differential: float
    direction: Literal["LONG", "SHORT", "NEUTRAL"]
    daily_carry_pips: float
    is_valid: bool


def get_carry_bias(
    pair: str,
    rates: dict[str, float],
    *,
    min_differential: float = DEFAULT_CARRY_MIN_DIFFERENTIAL,
) -> CarrySignal:
    """Compute the carry directional bias for *pair*.

    Parameters
    ----------
    pair:
        FX pair symbol (e.g. ``"AUDJPY"``).
    rates:
        Annualised central-bank rates per currency, in percent.
        Example: ``{"AUD": 4.35, "JPY": 0.10, "USD": 5.25, "EUR": 3.65}``.
    min_differential:
        Minimum absolute differential to declare a bias (default 0.5%).

    Returns
    -------
    CarrySignal
        ``is_valid=False`` when the pair is unknown or a rate is missing.
    """
    currencies = _PAIR_CURRENCIES.get(pair.upper())
    if currencies is None:
        return CarrySignal(
            differential=0.0,
            direction="NEUTRAL",
            daily_carry_pips=0.0,
            is_valid=False,
        )

    base_ccy, quote_ccy = currencies
    base_rate = rates.get(base_ccy)
    quote_rate = rates.get(quote_ccy)

    if base_rate is None or quote_rate is None:
        return CarrySignal(
            differential=0.0,
            direction="NEUTRAL",
            daily_carry_pips=0.0,
            is_valid=False,
        )

    differential = base_rate - quote_rate

    if differential > min_differential:
        direction: Literal["LONG", "SHORT", "NEUTRAL"] = "LONG"
    elif differential < -min_differential:
        direction = "SHORT"
    else:
        direction = "NEUTRAL"

    # Approximate daily carry in pips:
    # (differential / 100) / trading_days × micro_lot_units
    # For EURUSD-type pairs the pip value is ~$0.10/micro-lot;
    # here we compute in base-currency pips (currency-agnostic estimate).
    daily_carry_pips = (
        (differential / 100.0) / _TRADING_DAYS_PER_YEAR * _MICRO_LOT_UNITS
    )

    return CarrySignal(
        differential=differential,
        direction=direction,
        daily_carry_pips=round(daily_carry_pips, 4),
        is_valid=True,
    )
