# ============================================================
# PROJECT      : ALPHAEDGE
# FILE         : alphaedge/tests/test_momentum_detector_insufficient.py
# DESCRIPTION  : Guard: fewer bars than min_bars required → None immediately
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-25
# ============================================================
"""ALPHAEDGE — Momentum detector: insufficient data → None."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("ALPHAEDGE_CORE_BACKEND", "stubs")

from alphaedge.core._stubs.momentum_detector import detect_momentum  # noqa: E402


def _make_bars(n: int) -> list[dict]:
    bars = []
    for i in range(n):
        close = 1.10000 + i * 0.00010
        bars.append(
            {
                "open": close - 0.00010,
                "high": close + 0.00020,
                "low": close - 0.00020,
                "close": close,
                "timestamp": 1_700_000_000_000 + i * 86_400_000,
            }
        )
    return bars


@pytest.mark.parametrize(
    "n_bars",
    [
        0,  # empty
        1,  # single bar
        10,  # well below min_bars (29 for adx_period=14, slow_period=26)
        28,  # one short of min_bars
    ],
)
def test_insufficient_bars_returns_none(n_bars: int) -> None:
    """All counts below min_bars must return None without raising."""
    bars = _make_bars(n_bars)
    result = detect_momentum(
        bars=bars,
        fast_period=12,
        slow_period=26,
        adx_period=14,
        adx_threshold=25.0,
    )
    assert result is None, f"Expected None for {n_bars} bars (min=29), got {result}"


def test_exactly_min_bars_does_not_raise() -> None:
    """Exactly min_bars (=29) must not raise — may return None or a signal."""
    bars = _make_bars(29)
    # We only assert no exception is raised
    detect_momentum(
        bars=bars,
        fast_period=12,
        slow_period=26,
        adx_period=14,
        adx_threshold=25.0,
    )
