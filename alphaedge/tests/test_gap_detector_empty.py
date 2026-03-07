# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_gap_detector_empty.py
# DESCRIPTION  : Tests for gap detection edge cases
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: gap detector tests — edge cases."""

from __future__ import annotations

from typing import Any

import pytest

from alphaedge.core import gap_detector as gap_mod  # type: ignore[attr-defined]


class TestGapDetectorEdgeCases:
    """Tests for gap detection with edge-case inputs."""

    def test_empty_pre_session_data(self) -> None:
        """Gap detection with empty pre-session data should not crash."""
        result = gap_mod.detect_gap(
            pre_session_m1=[],
            session_m1=[
                {
                    "open": 1.08520,
                    "high": 1.08600,
                    "low": 1.08450,
                    "close": 1.08580,
                    "volume": 300.0,
                },
            ],
            pre_close=1.08518,
            session_open=1.08520,
            atr_period=3,
            min_atr_ratio=1.5,
        )

        # No baseline ATR → ratio is 0 → no gap detected
        assert result["detected"] is False
        assert result["atr_ratio"] == 0.0

    def test_bearish_gap_direction(self) -> None:
        """Direction should be -1 when session opens below pre-close."""
        pre_m1: list[dict[str, Any]] = [
            {
                "open": 1.08500,
                "high": 1.08510,
                "low": 1.08495,
                "close": 1.08505,
                "volume": 80.0,
            },
        ]
        session_m1: list[dict[str, Any]] = [
            {
                "open": 1.08300,
                "high": 1.08500,
                "low": 1.08200,
                "close": 1.08350,
                "volume": 500.0,
            },
        ]

        result = gap_mod.detect_gap(
            pre_session_m1=pre_m1,
            session_m1=session_m1,
            pre_close=1.08505,
            session_open=1.08300,
            atr_period=1,
            min_atr_ratio=1.5,
        )

        assert result["direction"] == -1  # Bearish

    def test_zero_atr_ratio_on_zero_baseline(self) -> None:
        """ATR ratio should be 0 when baseline candles have zero range."""
        zero_range_candles: list[dict[str, Any]] = [
            {
                "open": 1.08500,
                "high": 1.08500,
                "low": 1.08500,
                "close": 1.08500,
                "volume": 100.0,
            },
        ]

        result = gap_mod.detect_gap(
            pre_session_m1=zero_range_candles,
            session_m1=zero_range_candles,
            pre_close=1.08500,
            session_open=1.08500,
            atr_period=1,
            min_atr_ratio=1.5,
        )

        assert result["atr_ratio"] == 0.0
        assert result["detected"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
