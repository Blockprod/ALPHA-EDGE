# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_risk_manager_sizing.py
# DESCRIPTION  : Tests for position sizing calculations
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: risk manager tests — sizing."""

from __future__ import annotations

import pytest

from alphaedge.core import risk_manager as risk_mod  # type: ignore[attr-defined]


class TestRiskManagerSizing:
    """Tests for calculate_position_size function."""

    def test_position_size_1pct_risk(self) -> None:
        """1% risk on $10,000 with 20-pip SL should give valid lot size."""
        result = risk_mod.calculate_position_size(
            account_equity=10000.0,
            risk_pct=1.0,
            sl_pips=20.0,
            pair="EURUSD",
            pip_size=0.0001,
            lot_type="micro",
            min_lots=0.01,
            max_lots=100.0,
        )

        assert result["is_valid"] is True
        assert result["lot_size"] > 0
        # Risk amount should be $100 (1% of $10k)
        assert abs(result["risk_amount"] - 100.0) < 0.01

    def test_position_size_zero_sl_invalid(self) -> None:
        """Zero SL pips should produce invalid position size."""
        result = risk_mod.calculate_position_size(
            account_equity=10000.0,
            risk_pct=1.0,
            sl_pips=0.0,
            pair="EURUSD",
            pip_size=0.0001,
            lot_type="micro",
            min_lots=0.01,
            max_lots=10.0,
        )

        assert result["is_valid"] is False
        assert result["lot_size"] == 0.0

    def test_position_size_jpy_pair(self) -> None:
        """Position sizing should work correctly for JPY pairs."""
        result = risk_mod.calculate_position_size(
            account_equity=10000.0,
            risk_pct=1.0,
            sl_pips=30.0,
            pair="USDJPY",
            pip_size=0.01,
            lot_type="micro",
            min_lots=0.01,
            max_lots=10.0,
        )

        assert result["is_valid"] is True
        assert result["lot_size"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
