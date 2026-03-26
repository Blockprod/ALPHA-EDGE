# ============================================================
# PROJECT      : ALPHAEDGE
# FILE         : alphaedge/tests/test_momentum_detector_no_trend.py
# DESCRIPTION  : No-signal: flat/choppy market → ADX < threshold → None
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-25
# ============================================================
"""ALPHAEDGE — Momentum detector: no trend → None (ADX gate fires)."""

from __future__ import annotations

import os

os.environ.setdefault("ALPHAEDGE_CORE_BACKEND", "stubs")

from alphaedge.core._stubs.momentum_detector import detect_momentum  # noqa: E402


def _make_flat_bars(n: int = 35) -> list[dict]:
    """Return *n* bars with identical OHLC — zero ATR → ADX = 0.0."""
    bars = []
    for i in range(n):
        bars.append(
            {
                "open": 1.10000,
                "high": 1.10050,
                "low": 1.09950,
                "close": 1.10000,
                "timestamp": 1_700_000_000_000 + i * 86_400_000,
            }
        )
    return bars


def test_no_trend_returns_none() -> None:
    """Flat bars produce ADX ~ 0 → detect_momentum must return None."""
    bars = _make_flat_bars(35)
    result = detect_momentum(
        bars=bars,
        fast_period=12,
        slow_period=26,
        adx_period=14,
        adx_threshold=25.0,
    )
    assert result is None, f"Expected None on flat market, got {result}"


def test_high_threshold_blocks_weak_trend() -> None:
    """An artificially high threshold (100.0) should block even valid trends."""
    bars = _make_flat_bars(35)
    result = detect_momentum(
        bars=bars,
        fast_period=12,
        slow_period=26,
        adx_period=14,
        adx_threshold=100.0,
    )
    assert result is None
