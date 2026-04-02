# ============================================================
# PROJECT      : ALPHAEDGE
# FILE         : alphaedge/tests/test_usd_exposure_filter.py
# DESCRIPTION  : USD exposure filter parity helpers (live/backtest)
# PYTHON       : 3.11.9
# ============================================================
"""Tests for shared USD exposure mapping and amplification checks."""

from __future__ import annotations

from alphaedge.engine.usd_exposure import usd_direction, would_amplify_usd_exposure


def test_usd_direction_for_usd_quote_pair() -> None:
    assert usd_direction("EURUSD", 1) == -1
    assert usd_direction("EURUSD", -1) == 1


def test_usd_direction_for_usd_base_pair() -> None:
    assert usd_direction("USDJPY", 1) == 1
    assert usd_direction("USDJPY", -1) == -1


def test_would_amplify_blocks_same_net_usd_direction() -> None:
    open_positions = [("EURUSD", 1)]  # net USD short (-1)
    assert would_amplify_usd_exposure(open_positions, "GBPUSD", 1) is True


def test_would_amplify_allows_hedging_direction() -> None:
    open_positions = [("EURUSD", 1)]  # net USD short (-1)
    assert would_amplify_usd_exposure(open_positions, "USDJPY", 1) is False
