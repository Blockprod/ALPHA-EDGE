# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_fcr_detector_detect.py
# DESCRIPTION  : Tests for FCR detection basic functionality
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: FCR detector unit tests — detection."""

from __future__ import annotations

from typing import Any

import pytest

# Python wrapper import — works without Cython compilation
from alphaedge.core import fcr_detector as fcr_mod  # type: ignore[attr-defined]


# ------------------------------------------------------------------
# Test: FCR detected on valid M5 candle with sufficient range
# ------------------------------------------------------------------
class TestFCRDetectorDetect:
    """Tests for the detect_fcr function."""

    def test_fcr_detected_valid_range(
        self,
        sample_m5_candles: list[dict[str, Any]],
        eurusd_pip_size: float,
    ) -> None:
        """FCR should be detected when last M5 candle has range >= min_range_pips."""
        result = fcr_mod.detect_fcr(
            candles_data=sample_m5_candles,
            min_range_pips=5.0,
            pip_size=eurusd_pip_size,
        )

        assert result is not None
        assert result["detected"] is True
        assert result["range_high"] == sample_m5_candles[-1]["high"]
        assert result["range_low"] == sample_m5_candles[-1]["low"]
        assert result["range_size"] > 0

    def test_fcr_not_detected_small_range(
        self,
        eurusd_pip_size: float,
    ) -> None:
        """FCR should return None when candle range is below min_range_pips."""
        # Candle with only 2-pip range
        tiny_candles: list[dict[str, Any]] = [
            {
                "open": 1.08500,
                "high": 1.08510,
                "low": 1.08490,
                "close": 1.08505,
                "volume": 100.0,
                "timestamp": 1709200200,
            }
        ]

        result = fcr_mod.detect_fcr(
            candles_data=tiny_candles,
            min_range_pips=5.0,
            pip_size=eurusd_pip_size,
        )

        assert result is None

    def test_fcr_not_detected_empty_list(
        self,
        eurusd_pip_size: float,
    ) -> None:
        """FCR should return None for an empty candle list."""
        result = fcr_mod.detect_fcr(
            candles_data=[],
            min_range_pips=5.0,
            pip_size=eurusd_pip_size,
        )

        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
