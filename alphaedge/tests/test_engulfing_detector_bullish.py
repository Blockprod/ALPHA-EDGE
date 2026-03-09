# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_engulfing_detector_bullish.py
# DESCRIPTION  : Tests for bullish engulfing pattern detection
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: engulfing tests — bullish."""

from __future__ import annotations

from typing import Any

import pytest

from alphaedge.core import engulfing_detector as eng_mod


class TestEngulfingBullish:
    """Tests for bullish engulfing detection."""

    def test_bullish_engulfing_detected(
        self,
        sample_m1_candles_bullish_engulfing: list[dict[str, Any]],
        eurusd_pip_size: float,
    ) -> None:
        """Bullish engulfing closing above FCR high triggers long signal."""
        result = eng_mod.detect_engulfing(
            candles_data=sample_m1_candles_bullish_engulfing,
            fcr_high=1.08750,
            fcr_low=1.08400,
            rr_ratio=3.0,
            pip_size=eurusd_pip_size,
            volume_period=3,
            min_volume_ratio=1.0,
        )

        assert result is not None
        assert result["detected"] is True
        assert result["signal"] == 1  # Long
        assert result["entry_price"] == 1.08780
        assert result["stop_loss"] == 1.08590  # Below candle low

    def test_bullish_tp_at_3_to_1_rr(
        self,
        sample_m1_candles_bullish_engulfing: list[dict[str, Any]],
        eurusd_pip_size: float,
    ) -> None:
        """Take profit should be entry + (3 * risk) for longs."""
        result = eng_mod.detect_engulfing(
            candles_data=sample_m1_candles_bullish_engulfing,
            fcr_high=1.08750,
            fcr_low=1.08400,
            rr_ratio=3.0,
            pip_size=eurusd_pip_size,
            volume_period=3,
            min_volume_ratio=1.0,
        )

        assert result is not None
        risk = abs(result["entry_price"] - result["stop_loss"])
        expected_tp = result["entry_price"] + (3.0 * risk)
        assert abs(result["take_profit"] - expected_tp) < 1e-8

    def test_insufficient_candles_returns_none(
        self,
        eurusd_pip_size: float,
    ) -> None:
        """Detection should return None with fewer than 2 candles."""
        result = eng_mod.detect_engulfing(
            candles_data=[
                {
                    "open": 1.08500,
                    "high": 1.08600,
                    "low": 1.08400,
                    "close": 1.08550,
                    "volume": 100.0,
                },
            ],
            fcr_high=1.08600,
            fcr_low=1.08400,
            rr_ratio=3.0,
            pip_size=eurusd_pip_size,
            volume_period=3,
            min_volume_ratio=1.0,
        )

        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
