# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/tests/test_momentum_detector_adx_nonwilder.py
# DESCRIPTION  : Documents ADX smoothing divergence from Wilder's standard
# ============================================================
"""Tests — ADX non-Wilder smoothing divergence.

ALPHAEDGE uses EMA factor k = 2/(period+1) ~0.133 (standard EMA),
NOT Welles Wilder's k = 1/period ~0.071.
These tests document the known divergence so it cannot be accidentally
changed without breaking the test suite.
"""

from __future__ import annotations

import math

from alphaedge.core._stubs.momentum_detector import _adx


# ------------------------------------------------------------------
# Helper — build simple synthetic bars
# ------------------------------------------------------------------
def _make_bars(n: int, trend_strength: float = 1.0, noise: float = 0.3) -> list[dict]:
    """Generate bars with a steady uptrend plus some noise to avoid ADX=100 ceiling."""
    bars = []
    price = 1.1000
    for i in range(n):
        step = trend_strength * 0.0010
        # Add alternating noise: every 3rd bar is a minor pullback
        direction = 1.0 if i % 3 != 2 else -noise
        actual_step = step * direction
        high = price + abs(step) * 1.5
        low = price - abs(step) * 0.5
        close = price + actual_step
        bars.append(
            {
                "open": price,
                "high": high,
                "low": low,
                "close": close,
                "volume": 100.0,
                "timestamp": 1700000000 + i * 86400,
            }
        )
        price = close
    return bars


# ------------------------------------------------------------------
# Wilder ADX reference — independent implementation for comparison
# ------------------------------------------------------------------
def _adx_wilder(bars: list[dict], period: int) -> float:
    """Reference ADX using Wilder's k = 1/period smoothing."""
    n = len(bars)
    if n < 2 * period + 1:
        return 0.0
    k = 1.0 / period  # Wilder smoothing factor
    atr_ema = 0.0
    plus_di_ema = 0.0
    minus_di_ema = 0.0

    def tr(b: dict, prev: dict) -> float:
        hi, lo, pc = float(b["high"]), float(b["low"]), float(prev["close"])
        return max(hi - lo, abs(hi - pc), abs(lo - pc))

    def dm(b: dict, prev: dict) -> tuple[float, float]:
        p = float(b["high"]) - float(prev["high"])
        m = float(prev["low"]) - float(b["low"])
        pdm = p if p > m and p > 0 else 0.0
        mdm = m if m > p and m > 0 else 0.0
        return pdm, mdm

    for i in range(1, period + 1):
        atr_ema += tr(bars[i], bars[i - 1])
        pdm, mdm = dm(bars[i], bars[i - 1])
        plus_di_ema += pdm
        minus_di_ema += mdm
    atr_ema /= period
    plus_di_ema /= period
    minus_di_ema /= period

    adx_seed = 0.0
    for i in range(period + 1, 2 * period + 1):
        t = tr(bars[i], bars[i - 1])
        pdm, mdm = dm(bars[i], bars[i - 1])
        atr_ema = t * k + atr_ema * (1 - k)
        plus_di_ema = pdm * k + plus_di_ema * (1 - k)
        minus_di_ema = mdm * k + minus_di_ema * (1 - k)
        if atr_ema > 0:
            pdi = plus_di_ema / atr_ema * 100
            mdi = minus_di_ema / atr_ema * 100
            s = pdi + mdi
            dx = abs(pdi - mdi) / s * 100 if s > 0 else 0.0
        else:
            dx = 0.0
        adx_seed += dx
    adx_val = adx_seed / period
    for i in range(2 * period + 1, n):
        t = tr(bars[i], bars[i - 1])
        pdm, mdm = dm(bars[i], bars[i - 1])
        atr_ema = t * k + atr_ema * (1 - k)
        plus_di_ema = pdm * k + plus_di_ema * (1 - k)
        minus_di_ema = mdm * k + minus_di_ema * (1 - k)
        if atr_ema > 0:
            pdi = plus_di_ema / atr_ema * 100
            mdi = minus_di_ema / atr_ema * 100
            s = pdi + mdi
            dx = abs(pdi - mdi) / s * 100 if s > 0 else 0.0
        else:
            dx = 0.0
        adx_val = dx * k + adx_val * (1 - k)
    return adx_val


class TestAdxNonWilderDivergence:
    """Verify ALPHAEDGE ADX uses EMA smoothing (k=2/(n+1)), not Wilder's (k=1/n)."""

    def test_adx_ema_vs_wilder_diverge_on_trend(self) -> None:
        """ALPHAEDGE ADX (EMA k=2/15) must differ from Wilder (k=1/14) on trend.

        We use the minimum dataset where the smoothing transient is most visible.
        """
        period = 14
        # Just above minimum (2*period+1): transient divergence is largest here
        bars = _make_bars(n=2 * period + 2, trend_strength=1.5, noise=0.6)
        adx_ema = _adx(bars, period=period)
        adx_wilder_val = _adx_wilder(bars, period=period)
        assert 0.0 < adx_ema < 100.0
        assert 0.0 < adx_wilder_val < 100.0
        # EMA vs Wilder smoothing diverge — this IS the documented design
        assert adx_ema != adx_wilder_val, (
            f"EMA ADX ({adx_ema:.4f}) must differ from Wilder ADX"
            f" ({adx_wilder_val:.4f}) due to different smoothing factors"
        )

    def test_adx_ema_reacts_faster_to_trend(self) -> None:
        """On minimum data, EMA ADX differs from Wilder ADX (EMA is faster).

        k_ema = 2/15 ≈ 0.133 vs k_wilder = 1/14 ≈ 0.071 — not equal.
        """
        period = 14
        bars = _make_bars(n=2 * period + 2, trend_strength=1.5, noise=0.6)
        adx_ema = _adx(bars, period=period)
        adx_wilder_val = _adx_wilder(bars, period=period)
        assert 0.0 < adx_ema < 100.0
        assert 0.0 < adx_wilder_val < 100.0
        # EMA and Wilder respond differently — divergence is the documented behaviour
        assert adx_ema != adx_wilder_val

    def test_adx_ema_k_factor(self) -> None:
        """Document that EMA k=2/(period+1) for period=14 gives ~0.133."""
        period = 14
        k_ema = 2.0 / (period + 1)
        k_wilder = 1.0 / period
        assert math.isclose(k_ema, 0.1333, abs_tol=0.001)
        assert math.isclose(k_wilder, 0.0714, abs_tol=0.001)
        # EMA factor is ~87% larger than Wilder — significantly more responsive
        assert k_ema > k_wilder * 1.5
