# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_risk_manager_slippage.py
# DESCRIPTION  : Tests for slippage buffer application
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: risk manager tests — slippage."""

from __future__ import annotations

import pytest

from alphaedge.core import risk_manager as risk_mod


class TestRiskManagerSlippage:
    """Tests for apply_slippage_buffer function."""

    def test_slippage_widens_buy_sl_down(self) -> None:
        """For BUY, slippage should move SL further below entry."""
        adjusted = risk_mod.apply_slippage_buffer(
            stop_loss=1.08500,
            direction=1,  # BUY
            slippage_pips=2.0,
            pip_size=0.0001,
        )

        # SL should be lower (1.08500 - 0.0002 = 1.08480)
        expected = 1.08500 - (2.0 * 0.0001)
        assert abs(adjusted - expected) < 1e-10

    def test_slippage_widens_sell_sl_up(self) -> None:
        """For SELL, slippage should move SL further above entry."""
        adjusted = risk_mod.apply_slippage_buffer(
            stop_loss=1.08550,
            direction=-1,  # SELL
            slippage_pips=2.0,
            pip_size=0.0001,
        )

        # SL should be higher (1.08550 + 0.0002 = 1.08570)
        expected = 1.08550 + (2.0 * 0.0001)
        assert abs(adjusted - expected) < 1e-10

    def test_zero_slippage_unchanged(self) -> None:
        """Zero slippage should leave SL unchanged."""
        adjusted = risk_mod.apply_slippage_buffer(
            stop_loss=1.08500,
            direction=1,
            slippage_pips=0.0,
            pip_size=0.0001,
        )

        assert abs(adjusted - 1.08500) < 1e-10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
