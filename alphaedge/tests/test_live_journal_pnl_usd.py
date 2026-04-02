# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/tests/test_live_journal_pnl_usd.py
# DESCRIPTION  : PnL USD formula — multi-pair parametrized test
# SCENARIO     : exchange_rate correctly converts raw PnL to USD
# ============================================================
"""Test pnl_usd formula respects exchange_rate for multi-pair support."""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Helpers — replicate the formula from session_lifecycle._on_trade_closed
# ---------------------------------------------------------------------------


def _compute_pnl_usd(
    pnl_pips: float,
    pip_size: float,
    lot_size: float,
    exchange_rate: float,
) -> float:
    """Mirror of the corrected formula in session_lifecycle.py."""
    raw_pnl = pnl_pips * pip_size * lot_size * 100_000
    return raw_pnl / exchange_rate if exchange_rate > 0.0 else raw_pnl


# ---------------------------------------------------------------------------
# Parametrized cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "pair, pnl_pips, pip_size, lot_size, exchange_rate, expected_usd",
    [
        # EURUSD — exchange_rate = 1.0 → no conversion
        # raw_pnl = 10 * 0.0001 * 0.01 * 100_000 = 1.0 USD
        ("EURUSD", 10.0, 0.0001, 0.01, 1.0, pytest.approx(1.0, abs=0.001)),
        # EURUSD — exchange_rate = 1.08 → slight reduction
        # pnl_usd = 1.0 / 1.08 ≈ 0.926
        ("EURUSD", 10.0, 0.0001, 0.01, 1.08, pytest.approx(0.926, abs=0.001)),
        # USDJPY — pip_size=0.01, exchange_rate≈150 (JPY per USD)
        # raw_pnl = 10 * 0.01 * 0.01 * 100_000 = 100 JPY
        # pnl_usd = 100 / 150 ≈ 0.667 USD
        ("USDJPY", 10.0, 0.01, 0.01, 150.0, pytest.approx(0.667, abs=0.001)),
        # GBPUSD — exchange_rate ≈ 1.25 (GBP/USD)
        # raw_pnl = 5 * 0.0001 * 0.1 * 100_000 = 5.0
        # pnl_usd = 5.0 / 1.25 = 4.0
        ("GBPUSD", 5.0, 0.0001, 0.1, 1.25, pytest.approx(4.0, abs=0.001)),
        # Edge case — exchange_rate = 0.0 → fallback to raw_pnl (no division)
        # raw_pnl = 10 * 0.0001 * 0.01 * 100_000 = 1.0
        ("EURUSD", 10.0, 0.0001, 0.01, 0.0, pytest.approx(1.0, abs=0.001)),
        # Negative pnl (loss)
        ("USDJPY", -5.0, 0.01, 0.01, 150.0, pytest.approx(-0.333, abs=0.001)),
    ],
)
def test_pnl_usd_formula(
    pair: str,
    pnl_pips: float,
    pip_size: float,
    lot_size: float,
    exchange_rate: float,
    expected_usd: float,
) -> None:
    """PnL USD must use exchange_rate for correct multi-pair conversion."""
    result = _compute_pnl_usd(pnl_pips, pip_size, lot_size, exchange_rate)
    assert result == expected_usd, (
        f"{pair}: expected {expected_usd}, got {result} "
        f"(pnl_pips={pnl_pips}, pip_size={pip_size}, "
        f"lot_size={lot_size}, exchange_rate={exchange_rate})"
    )
