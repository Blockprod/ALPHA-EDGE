# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_order_manager_bracket.py
# DESCRIPTION  : Tests for bracket order creation and validation
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: order manager tests — brackets."""

from __future__ import annotations

import pytest

from alphaedge.core import order_manager as order_mod


class TestOrderManagerBracket:
    """Tests for create_bracket_order function."""

    def test_valid_sell_bracket_order(self) -> None:
        """Valid SELL bracket order should pass all validations."""
        result = order_mod.create_bracket_order(
            direction=-1,
            entry_price=1.08350,
            stop_loss=1.08550,
            take_profit=1.07750,
            lot_size=0.10,
            pip_size=0.0001,
            spread_pips=1.0,
            max_spread_pips=2.0,
            min_rr=2.5,
            min_lots=0.01,
            max_lots=10.0,
            adjust_for_spread=True,
        )

        assert result["is_valid"] is True
        assert result["direction"] == -1
        assert result["risk_pips"] > 0
        assert result["reward_pips"] > 0

    def test_valid_buy_bracket_order(self) -> None:
        """Valid BUY bracket order should pass all validations."""
        result = order_mod.create_bracket_order(
            direction=1,
            entry_price=1.08780,
            stop_loss=1.08590,
            take_profit=1.09350,
            lot_size=0.05,
            pip_size=0.0001,
            spread_pips=0.8,
            max_spread_pips=2.0,
            min_rr=2.5,
            min_lots=0.01,
            max_lots=10.0,
            adjust_for_spread=False,
        )

        assert result["is_valid"] is True
        assert result["direction"] == 1

    def test_rejected_on_wide_spread(self) -> None:
        """Order should be rejected when spread exceeds max."""
        result = order_mod.create_bracket_order(
            direction=-1,
            entry_price=1.08350,
            stop_loss=1.08550,
            take_profit=1.07750,
            lot_size=0.10,
            pip_size=0.0001,
            spread_pips=3.5,
            max_spread_pips=2.0,
            min_rr=2.5,
            min_lots=0.01,
            max_lots=10.0,
            adjust_for_spread=True,
        )

        assert result["is_valid"] is False
        assert result["rejection_reason"] == "spread_too_wide"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
