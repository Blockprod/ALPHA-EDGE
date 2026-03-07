# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_fcr_detector_scan.py
# DESCRIPTION  : Tests for FCR scan mode functionality
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: FCR detector unit tests — scan mode."""

from __future__ import annotations

from typing import Any

import pytest

from alphaedge.core import fcr_detector as fcr_mod  # type: ignore[attr-defined]


# ------------------------------------------------------------------
# Test: scan mode selects the widest-range FCR candle
# ------------------------------------------------------------------
class TestFCRDetectorScan:
    """Tests for the detect_fcr_scan function."""

    def test_scan_selects_widest_range(
        self,
        eurusd_pip_size: float,
    ) -> None:
        """Scan should return the candle with the largest range."""
        candles: list[dict[str, Any]] = [
            {
                "open": 1.08500,
                "high": 1.08600,
                "low": 1.08450,
                "close": 1.08550,
                "volume": 100.0,
                "timestamp": 1709200200,
            },
            {
                "open": 1.08550,
                "high": 1.08800,
                "low": 1.08400,
                "close": 1.08700,
                "volume": 200.0,
                "timestamp": 1709200500,
            },
            {
                "open": 1.08700,
                "high": 1.08750,
                "low": 1.08650,
                "close": 1.08720,
                "volume": 150.0,
                "timestamp": 1709200800,
            },
        ]

        result = fcr_mod.detect_fcr_scan(
            candles_data=candles,
            min_range_pips=5.0,
            pip_size=eurusd_pip_size,
            lookback=3,
        )

        assert result is not None
        # Second candle has the widest range (40 pips)
        assert result["range_high"] == 1.08800
        assert result["range_low"] == 1.08400

    def test_scan_respects_lookback(
        self,
        eurusd_pip_size: float,
    ) -> None:
        """Scan should only look back N candles."""
        candles: list[dict[str, Any]] = [
            # Wide-range candle outside lookback window
            {
                "open": 1.08000,
                "high": 1.09000,
                "low": 1.08000,
                "close": 1.08500,
                "volume": 300.0,
                "timestamp": 1709200000,
            },
            # Narrow candle within lookback=1
            {
                "open": 1.08500,
                "high": 1.08580,
                "low": 1.08420,
                "close": 1.08550,
                "volume": 100.0,
                "timestamp": 1709200300,
            },
        ]

        result = fcr_mod.detect_fcr_scan(
            candles_data=candles,
            min_range_pips=5.0,
            pip_size=eurusd_pip_size,
            lookback=1,
        )

        assert result is not None
        # Should only find the last candle (16-pip range)
        assert result["range_high"] == 1.08580

    def test_scan_returns_none_for_empty(
        self,
        eurusd_pip_size: float,
    ) -> None:
        """Scan should return None for empty input."""
        result = fcr_mod.detect_fcr_scan(
            candles_data=[],
            min_range_pips=5.0,
            pip_size=eurusd_pip_size,
            lookback=3,
        )

        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
