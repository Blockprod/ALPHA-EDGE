# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/tests/test_ml_filter_live_status.py
# DESCRIPTION  : Tests for ML shim live-integration status markers
# PYTHON       : 3.11.9
# ============================================================
"""Verify the public ML shim explicitly declares its live status."""

from __future__ import annotations

from alphaedge.engine import ml_filter


class TestMlFilterLiveStatus:
    def test_module_declares_not_live_integrated(self) -> None:
        assert ml_filter.LIVE_PIPELINE_INTEGRATED is False
        assert (
            "not wired into the live trading pipeline" in ml_filter.DEPRECATION_MESSAGE
        )
