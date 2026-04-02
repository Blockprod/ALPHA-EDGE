# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/tests/test_risk_manager_pair_limit.py
# DESCRIPTION  : Tests for per-pair limit enforcement
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-22
# ============================================================
"""ALPHAEDGE — Momentum+Carry Forex Trading Bot: risk manager tests — pair limit."""

from __future__ import annotations

import pytest

from alphaedge.core import risk_manager as risk_mod


class TestRiskManagerPairLimit:
    """Tests for check_pair_limit function."""

    def test_allows_new_pair_below_limit(self) -> None:
        """A new trade is allowed while open pair count stays below the cap."""
        result = risk_mod.check_pair_limit(
            pair="EURUSD",
            open_pairs=["USDJPY"],
            max_open_pairs=2,
        )

        assert result == {
            "allowed": True,
            "reason": None,
            "open_count": 1,
            "max_allowed": 2,
            "open_pairs": ["USDJPY"],
        }

    def test_rejects_when_max_pairs_reached(self) -> None:
        """A new trade is rejected once the open pair cap has been reached."""
        result = risk_mod.check_pair_limit(
            pair="GBPUSD",
            open_pairs=["EURUSD", "USDJPY"],
            max_open_pairs=2,
        )

        assert result == {
            "allowed": False,
            "reason": "max_pairs_reached",
            "open_count": 2,
            "max_allowed": 2,
            "open_pairs": ["EURUSD", "USDJPY"],
        }


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
