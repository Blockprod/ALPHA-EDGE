# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_engulfing_detector_bearish.py
# DESCRIPTION  : Tests for bearish engulfing pattern detection
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: engulfing tests — bearish."""

from __future__ import annotations

from typing import Any

import pytest

from alphaedge.core import engulfing_detector as eng_mod


class TestEngulfingBearish:
    """Tests for bearish engulfing detection."""

    def test_bearish_engulfing_detected(
        self,
        sample_m1_candles_bearish_engulfing: list[dict[str, Any]],
        eurusd_pip_size: float,
    ) -> None:
        """Bearish engulfing closing below FCR low triggers short signal."""
        result = eng_mod.detect_engulfing(
            candles_data=sample_m1_candles_bearish_engulfing,
            fcr_high=1.08600,
            fcr_low=1.08400,
            rr_ratio=3.0,
            pip_size=eurusd_pip_size,
            volume_period=3,
            min_volume_ratio=1.0,
        )

        assert result is not None
        assert result["detected"] is True
        assert result["signal"] == -1  # Short
        assert result["entry_price"] == 1.08350
        assert result["stop_loss"] == 1.08550  # Above candle high

    def test_bearish_tp_at_3_to_1_rr(
        self,
        sample_m1_candles_bearish_engulfing: list[dict[str, Any]],
        eurusd_pip_size: float,
    ) -> None:
        """Take profit should be entry - (3 * risk) for shorts."""
        result = eng_mod.detect_engulfing(
            candles_data=sample_m1_candles_bearish_engulfing,
            fcr_high=1.08600,
            fcr_low=1.08400,
            rr_ratio=3.0,
            pip_size=eurusd_pip_size,
            volume_period=3,
            min_volume_ratio=1.0,
        )

        assert result is not None
        risk = abs(result["entry_price"] - result["stop_loss"])
        expected_tp = result["entry_price"] - (3.0 * risk)
        assert abs(result["take_profit"] - expected_tp) < 1e-8

    def test_bearish_rejected_above_fcr_low(
        self,
        eurusd_pip_size: float,
    ) -> None:
        """Bearish engulfing closing above FCR low should not trigger."""
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
            # Bullish previous candle
            {
                "open": 1.08400,
                "high": 1.08500,
                "low": 1.08390,
                "close": 1.08480,
                "volume": 120.0,
            },
            # Bearish but closes at 1.08420 — ABOVE FCR low of 1.08400
            {
                "open": 1.08500,
                "high": 1.08550,
                "low": 1.08410,
                "close": 1.08420,
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
        )

        # Close is above FCR low — no signal
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
