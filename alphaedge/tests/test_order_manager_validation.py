# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_order_manager_validation.py
# DESCRIPTION  : Tests for order validation edge cases
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: order manager tests — validation."""

from __future__ import annotations

import pytest

from alphaedge.core import order_manager as order_mod  # type: ignore[attr-defined]


class TestOrderManagerValidation:
    """Tests for order validation edge cases."""

    def test_rejected_invalid_lot_size(self) -> None:
        """Order with lot size below minimum should be rejected."""
        result = order_mod.create_bracket_order(
            direction=-1,
            entry_price=1.08350,
            stop_loss=1.08550,
            take_profit=1.07750,
            lot_size=0.001,  # Below min_lots of 0.01
            pip_size=0.0001,
            spread_pips=1.0,
            max_spread_pips=2.0,
            min_rr=2.5,
            min_lots=0.01,
            max_lots=10.0,
            adjust_for_spread=False,
        )

        assert result["is_valid"] is False
        assert result["rejection_reason"] == "invalid_lot_size"

    def test_rejected_low_rr_ratio(self) -> None:
        """Order with RR below minimum should be rejected."""
        result = order_mod.create_bracket_order(
            direction=-1,
            entry_price=1.08350,
            stop_loss=1.08550,
            take_profit=1.08200,  # Only ~0.75:1 RR
            lot_size=0.10,
            pip_size=0.0001,
            spread_pips=1.0,
            max_spread_pips=2.0,
            min_rr=2.5,
            min_lots=0.01,
            max_lots=10.0,
            adjust_for_spread=False,
        )

        assert result["is_valid"] is False
        assert result["rejection_reason"] == "rr_below_minimum"

    def test_spread_adjustment_widens_sl(self) -> None:
        """Spread adjustment should widen SL away from entry."""
        result_no_adj = order_mod.create_bracket_order(
            direction=-1,
            entry_price=1.08350,
            stop_loss=1.08550,
            take_profit=1.07750,
            lot_size=0.10,
            pip_size=0.0001,
            spread_pips=1.5,
            max_spread_pips=2.0,
            min_rr=2.0,
            min_lots=0.01,
            max_lots=10.0,
            adjust_for_spread=False,
        )

        result_adj = order_mod.create_bracket_order(
            direction=-1,
            entry_price=1.08350,
            stop_loss=1.08550,
            take_profit=1.07750,
            lot_size=0.10,
            pip_size=0.0001,
            spread_pips=1.5,
            max_spread_pips=2.0,
            min_rr=2.0,
            min_lots=0.01,
            max_lots=10.0,
            adjust_for_spread=True,
        )

        # For SELL direction, spread-adjusted SL should be higher
        assert result_adj["is_valid"] is True
        assert result_no_adj["is_valid"] is True
        assert result_adj["stop_loss"] > result_no_adj["stop_loss"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
