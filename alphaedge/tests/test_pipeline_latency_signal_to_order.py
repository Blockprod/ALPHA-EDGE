# ============================================================
# PROJECT      : ALPHAEDGE
# FILE         : alphaedge/tests/test_pipeline_latency_signal_to_order.py
# DESCRIPTION  : Latency contract — signal → order pipeline < 100 ms
#                Uses pure-Python stubs (no IB Gateway required).
# PYTHON       : 3.11.9
# ============================================================
"""Latency test : detect_momentum → calculate_position_size → create_bracket_order.

Ensures the CPU-bound portion of the signal pipeline executes in < 100 ms.
All calls use _stubs/ so no Cython build nor IB Gateway is required.
"""

from __future__ import annotations

import time

import pytest

from alphaedge.core._stubs.momentum_detector import detect_momentum
from alphaedge.core._stubs.order_manager import create_bracket_order
from alphaedge.core._stubs.risk_manager import calculate_position_size

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PIP_SIZE = 0.0001
_LOT_TYPE = "standard"


def _make_bars(n: int = 60) -> list[dict[str, float | int]]:
    """Build *n* synthetic M5 OHLC bars (trending upward)."""
    bars = []
    base = 1.0800
    for i in range(n):
        close = base + i * 0.0001
        bar = {
            "open": close - 0.00005,
            "high": close + 0.00010,
            "low": close - 0.00010,
            "close": close,
            "timestamp": 1_700_000_000_000 + i * 300_000,
        }
        bars.append(bar)
    return bars


# ---------------------------------------------------------------------------
# Latency test
# ---------------------------------------------------------------------------


class TestPipelineLatencySignalToOrder:
    """Signal → order pipeline must complete in < 100 ms (CPU-bound only)."""

    THRESHOLD_MS = 100.0

    def test_pipeline_latency_under_100ms(self) -> None:
        bars = _make_bars(60)

        t0 = time.perf_counter()

        # Step 1 — Momentum detection
        signal = detect_momentum(
            bars=bars,
            fast_period=12,
            slow_period=26,
            adx_period=14,
            adx_threshold=20.0,  # lowered to guarantee detection with synthetic data
        )
        assert signal is not None, "No momentum signal detected — check synthetic bars"
        assert signal["detected"] is True

        # Step 2 — Position sizing
        entry = bars[-1]["close"]
        direction = signal["direction"]
        stop_loss = entry - 0.0020 if direction == 1 else entry + 0.0020
        take_profit = entry + 0.0040 if direction == 1 else entry - 0.0040
        sl_pips = abs(entry - stop_loss) / _PIP_SIZE

        size_result = calculate_position_size(
            account_equity=10_000.0,
            risk_pct=1.0,
            sl_pips=sl_pips,
            pair="EURUSD",
            pip_size=_PIP_SIZE,
            lot_type=_LOT_TYPE,
            min_lots=0.01,
            max_lots=10.0,
            exchange_rate=0.0,
        )
        assert size_result["is_valid"], f"Position size invalid: {size_result}"

        # Step 3 — Bracket order creation
        order_result = create_bracket_order(
            direction=direction,
            entry_price=float(entry),
            stop_loss=stop_loss,
            take_profit=take_profit,
            lot_size=size_result["lot_size"],
            pip_size=_PIP_SIZE,
            spread_pips=1.0,
            max_spread_pips=3.0,
            min_rr=1.5,
            min_lots=0.01,
            max_lots=10.0,
            adjust_for_spread=True,
        )
        assert order_result["is_valid"], f"Order invalid: {order_result}"

        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        assert elapsed_ms < self.THRESHOLD_MS, (
            f"Pipeline too slow: {elapsed_ms:.2f} ms >= {self.THRESHOLD_MS} ms"
        )

    @pytest.mark.parametrize("n_bars", [30, 60, 120])
    def test_pipeline_latency_scales_with_bar_count(self, n_bars: int) -> None:
        """Even with more bars, pipeline stays under 100 ms."""
        bars = _make_bars(n_bars)

        t0 = time.perf_counter()

        signal = detect_momentum(
            bars=bars,
            fast_period=12,
            slow_period=26,
            adx_period=14,
            adx_threshold=20.0,
        )

        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        # detect_momentum alone must stay < 100 ms regardless of bar count
        assert elapsed_ms < self.THRESHOLD_MS, (
            f"detect_momentum too slow with {n_bars} bars: {elapsed_ms:.2f} ms"
        )
        _ = signal  # result used to avoid optimisation
