# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_fcr_detector_jpy.py
# DESCRIPTION  : Tests for FCR detection with JPY pip precision
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: FCR detector unit tests — JPY pairs."""

from __future__ import annotations

from typing import Any

import pytest

from alphaedge.core import fcr_detector as fcr_mod  # type: ignore[attr-defined]


# ------------------------------------------------------------------
# Test: FCR works correctly with JPY pip size (0.01)
# ------------------------------------------------------------------
class TestFCRDetectorJPY:
    """Tests for FCR detection on JPY pairs."""

    def test_fcr_detected_jpy_pair(
        self,
        usdjpy_pip_size: float,
    ) -> None:
        """FCR should correctly handle JPY 2-decimal pip size."""
        candles: list[dict[str, Any]] = [
            {
                "open": 150.500,
                "high": 150.700,
                "low": 150.300,
                "close": 150.600,
                "volume": 200.0,
                "timestamp": 1709200200,
            }
        ]

        result = fcr_mod.detect_fcr(
            candles_data=candles,
            min_range_pips=5.0,
            pip_size=usdjpy_pip_size,
        )

        assert result is not None
        assert result["detected"] is True
        # Range is 40 pips for JPY (0.400 / 0.01)
        assert result["range_high"] == 150.700
        assert result["range_low"] == 150.300

    def test_fcr_not_detected_jpy_small_range(
        self,
        usdjpy_pip_size: float,
    ) -> None:
        """FCR should reject JPY candles with range below threshold."""
        candles: list[dict[str, Any]] = [
            {
                "open": 150.500,
                "high": 150.520,
                "low": 150.490,
                "close": 150.510,
                "volume": 100.0,
                "timestamp": 1709200200,
            }
        ]

        result = fcr_mod.detect_fcr(
            candles_data=candles,
            min_range_pips=5.0,
            pip_size=usdjpy_pip_size,
        )

        # Range is 3 pips (0.030 / 0.01) — below 5 pip minimum
        assert result is None

    def test_fcr_range_size_correct_jpy(
        self,
        usdjpy_pip_size: float,
    ) -> None:
        """FCR range_size should be in price units (not pips)."""
        candles: list[dict[str, Any]] = [
            {
                "open": 150.500,
                "high": 150.800,
                "low": 150.200,
                "close": 150.600,
                "volume": 200.0,
                "timestamp": 1709200200,
            }
        ]

        result = fcr_mod.detect_fcr(
            candles_data=candles,
            min_range_pips=5.0,
            pip_size=usdjpy_pip_size,
        )

        assert result is not None
        expected_size = 150.800 - 150.200
        assert abs(result["range_size"] - expected_size) < 1e-10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
