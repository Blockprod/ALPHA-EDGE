# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_engulfing_detector_quality.py
# DESCRIPTION  : Tests for engulfing quality filters (body/wick)
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-08
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: engulfing tests — quality filters."""

from __future__ import annotations

from typing import Any

import pytest

from alphaedge.core import engulfing_detector as eng_mod


class TestEngulfingQuality:
    """Tests for engulfing body-size and wick-ratio quality filters."""

    def test_trivial_body_rejected(
        self,
        eurusd_pip_size: float,
    ) -> None:
        """Engulfing with body < 30% of FCR range is rejected."""
        # FCR range = 1.08600 - 1.08400 = 0.00200
        # Body = 1.08400 - 1.08395 = 0.00005 → ratio 0.025 < 0.3
        candles: list[dict[str, Any]] = [
            {
                "open": 1.08500,
                "high": 1.08520,
                "low": 1.08490,
                "close": 1.08510,
                "volume": 100.0,
            },
            {
                "open": 1.08510,
                "high": 1.08530,
                "low": 1.08500,
                "close": 1.08520,
                "volume": 110.0,
            },
            # Bullish prev
            {
                "open": 1.08390,
                "high": 1.08410,
                "low": 1.08385,
                "close": 1.08400,
                "volume": 120.0,
            },
            # Bearish engulfing — trivial 0.5 pip body
            {
                "open": 1.08400,
                "high": 1.08405,
                "low": 1.08390,
                "close": 1.08395,
                "volume": 250.0,
            },
        ]

        result = eng_mod.detect_engulfing(
            candles_data=candles,
            fcr_high=1.08600,
            fcr_low=1.08400,
            rr_ratio=3.0,
            pip_size=eurusd_pip_size,
            volume_period=3,
            min_volume_ratio=1.0,
            min_body_ratio=0.3,
            max_wick_ratio=2.0,
        )

        assert result is None

    def test_excessive_wick_rejected(
        self,
        eurusd_pip_size: float,
    ) -> None:
        """Engulfing with wick > 2x body is rejected."""
        # Body = 1.08500 - 1.08350 = 0.00150
        # Upper wick = 1.08700 - 1.08500 = 0.00200
        # Lower wick = 1.08350 - 1.08100 = 0.00250
        # Total wick = 0.00450 → ratio 3.0 > 2.0
        candles: list[dict[str, Any]] = [
            {
                "open": 1.08500,
                "high": 1.08520,
                "low": 1.08490,
                "close": 1.08510,
                "volume": 100.0,
            },
            {
                "open": 1.08510,
                "high": 1.08530,
                "low": 1.08500,
                "close": 1.08520,
                "volume": 110.0,
            },
            # Bullish prev
            {
                "open": 1.08400,
                "high": 1.08500,
                "low": 1.08390,
                "close": 1.08480,
                "volume": 120.0,
            },
            # Bearish engulfing with extreme wicks
            {
                "open": 1.08500,
                "high": 1.08700,
                "low": 1.08100,
                "close": 1.08350,
                "volume": 250.0,
            },
        ]

        result = eng_mod.detect_engulfing(
            candles_data=candles,
            fcr_high=1.08600,
            fcr_low=1.08400,
            rr_ratio=3.0,
            pip_size=eurusd_pip_size,
            volume_period=3,
            min_volume_ratio=1.0,
            min_body_ratio=0.3,
            max_wick_ratio=2.0,
        )

        assert result is None

    def test_quality_passes_with_good_candle(
        self,
        sample_m1_candles_bearish_engulfing: list[dict[str, Any]],
        eurusd_pip_size: float,
    ) -> None:
        """A well-formed engulfing passes both quality filters."""
        result = eng_mod.detect_engulfing(
            candles_data=sample_m1_candles_bearish_engulfing,
            fcr_high=1.08600,
            fcr_low=1.08400,
            rr_ratio=3.0,
            pip_size=eurusd_pip_size,
            volume_period=3,
            min_volume_ratio=1.0,
            min_body_ratio=0.3,
            max_wick_ratio=2.0,
        )

        assert result is not None
        assert result["detected"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
