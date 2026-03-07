# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_risk_manager_daily.py
# DESCRIPTION  : Tests for daily loss limit checking
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: risk manager tests — daily limits."""

from __future__ import annotations

import pytest

from alphaedge.core import risk_manager as risk_mod  # type: ignore[attr-defined]


class TestRiskManagerDaily:
    """Tests for check_daily_limit function."""

    def test_limit_not_breached_in_profit(self) -> None:
        """Daily limit should not be breached when account is in profit."""
        result = risk_mod.check_daily_limit(
            starting_equity=10000.0,
            current_equity=10200.0,
            max_daily_loss_pct=3.0,
            trades_today=1,
            max_trades=2,
        )

        assert result["limit_breached"] is False
        assert result["can_trade"] is True
        assert result["daily_pnl"] == 200.0

    def test_limit_breached_on_large_loss(self) -> None:
        """Daily limit should be breached when loss exceeds threshold."""
        result = risk_mod.check_daily_limit(
            starting_equity=10000.0,
            current_equity=9600.0,  # -4% loss
            max_daily_loss_pct=3.0,
            trades_today=2,
            max_trades=5,
        )

        assert result["limit_breached"] is True
        assert result["can_trade"] is False
        assert result["daily_pnl_pct"] < -3.0

    def test_limit_breached_on_max_trades(self) -> None:
        """Daily limit should trigger when max trades reached."""
        result = risk_mod.check_daily_limit(
            starting_equity=10000.0,
            current_equity=10100.0,  # In profit
            max_daily_loss_pct=3.0,
            trades_today=2,
            max_trades=2,
        )

        assert result["limit_breached"] is True
        assert result["can_trade"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
