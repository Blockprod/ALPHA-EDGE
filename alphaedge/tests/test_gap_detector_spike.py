# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_gap_detector_spike.py
# DESCRIPTION  : Tests for gap/volatility spike detection
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: gap detector tests — ATR spike."""

from __future__ import annotations

from typing import Any

import pytest

from alphaedge.core import gap_detector as gap_mod  # type: ignore[attr-defined]


class TestGapDetectorSpike:
    """Tests for gap detection with ATR spikes."""

    def test_gap_detected_on_atr_spike(
        self,
        pre_session_m1: list[dict[str, Any]],
        session_m1_spike: list[dict[str, Any]],
    ) -> None:
        """Gap should be detected when ATR ratio exceeds threshold."""
        result = gap_mod.detect_gap(
            pre_session_m1=pre_session_m1,
            session_m1=session_m1_spike,
            pre_close=1.08518,
            session_open=1.08520,
            atr_period=3,
            min_atr_ratio=1.5,
        )

        assert result["detected"] is True
        assert result["atr_ratio"] > 1.5

    def test_gap_not_detected_on_flat_session(
        self,
        pre_session_m1: list[dict[str, Any]],
        session_m1_flat: list[dict[str, Any]],
    ) -> None:
        """Gap should NOT be detected when session ATR is similar to baseline."""
        result = gap_mod.detect_gap(
            pre_session_m1=pre_session_m1,
            session_m1=session_m1_flat,
            pre_close=1.08518,
            session_open=1.08520,
            atr_period=3,
            min_atr_ratio=1.5,
        )

        assert result["detected"] is False

    def test_gap_direction_bullish(
        self,
        pre_session_m1: list[dict[str, Any]],
        session_m1_spike: list[dict[str, Any]],
    ) -> None:
        """Gap direction should be +1 when session opens above pre-close."""
        result = gap_mod.detect_gap(
            pre_session_m1=pre_session_m1,
            session_m1=session_m1_spike,
            pre_close=1.08400,
            session_open=1.08520,
            atr_period=3,
            min_atr_ratio=1.5,
        )

        assert result["direction"] == 1  # Bullish


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
