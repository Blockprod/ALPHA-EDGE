# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_engulfing_detector_volume.py
# DESCRIPTION  : Tests for engulfing volume confirmation filter
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: engulfing tests — volume filter."""

from __future__ import annotations

from typing import Any

import pytest

from alphaedge.core import engulfing_detector as eng_mod  # type: ignore[attr-defined]


class TestEngulfingVolume:
    """Tests for volume confirmation on engulfing patterns."""

    def test_rejected_on_low_volume(
        self,
        eurusd_pip_size: float,
    ) -> None:
        """Engulfing with volume below threshold should be rejected."""
        # Build candles where engulfing candle has LOW volume
        candles: list[dict[str, Any]] = [
            {
                "open": 1.08500,
                "high": 1.08520,
                "low": 1.08490,
                "close": 1.08510,
                "volume": 200.0,
            },
            {
                "open": 1.08510,
                "high": 1.08530,
                "low": 1.08500,
                "close": 1.08520,
                "volume": 210.0,
            },
            # Bullish prev
            {
                "open": 1.08400,
                "high": 1.08500,
                "low": 1.08390,
                "close": 1.08480,
                "volume": 220.0,
            },
            # Bearish engulfing with very LOW volume
            {
                "open": 1.08500,
                "high": 1.08550,
                "low": 1.08300,
                "close": 1.08350,
                "volume": 50.0,
            },
        ]

        result = eng_mod.detect_engulfing(
            candles_data=candles,
            fcr_high=1.08600,
            fcr_low=1.08400,
            rr_ratio=3.0,
            pip_size=eurusd_pip_size,
            volume_period=3,
            min_volume_ratio=1.5,  # Needs 1.5x average
        )

        # Volume is 50 vs avg ~210 → ratio ~0.24 < 1.5 → rejected
        assert result is None

    def test_accepted_on_high_volume(
        self,
        sample_m1_candles_bearish_engulfing: list[dict[str, Any]],
        eurusd_pip_size: float,
    ) -> None:
        """Engulfing with volume above threshold should be accepted."""
        result = eng_mod.detect_engulfing(
            candles_data=sample_m1_candles_bearish_engulfing,
            fcr_high=1.08600,
            fcr_low=1.08400,
            rr_ratio=3.0,
            pip_size=eurusd_pip_size,
            volume_period=3,
            min_volume_ratio=1.2,  # Needs 1.2x average
        )

        # Volume is 250 vs avg ~110 → ratio ~2.27 > 1.2 → accepted
        assert result is not None
        assert result["detected"] is True

    def test_volume_filter_skipped_on_zero_baseline(
        self,
        eurusd_pip_size: float,
    ) -> None:
        """If baseline volume is zero, volume filter should be skipped."""
        candles: list[dict[str, Any]] = [
            # Bullish prev
            {
                "open": 1.08400,
                "high": 1.08500,
                "low": 1.08390,
                "close": 1.08480,
                "volume": 0.0,
            },
            # Bearish engulfing
            {
                "open": 1.08500,
                "high": 1.08550,
                "low": 1.08300,
                "close": 1.08350,
                "volume": 0.0,
            },
        ]

        result = eng_mod.detect_engulfing(
            candles_data=candles,
            fcr_high=1.08600,
            fcr_low=1.08400,
            rr_ratio=3.0,
            pip_size=eurusd_pip_size,
            volume_period=3,
            min_volume_ratio=1.5,
        )

        # No baseline volume → filter skipped → pattern evaluated
        assert result is not None
        assert result["detected"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
