# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_order_manager_lots.py
# DESCRIPTION  : Tests for lot-to-units conversion
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: order manager tests — lot conversion."""

from __future__ import annotations

import pytest

from alphaedge.core import order_manager as order_mod  # type: ignore[attr-defined]


class TestOrderManagerLots:
    """Tests for lots_to_units conversion."""

    def test_standard_lot_conversion(self) -> None:
        """1 standard lot = 100,000 units."""
        units = order_mod.lots_to_units(1.0, "standard")
        assert units == 100000

    def test_mini_lot_conversion(self) -> None:
        """1 mini lot = 10,000 units."""
        units = order_mod.lots_to_units(1.0, "mini")
        assert units == 10000

    def test_micro_lot_conversion(self) -> None:
        """0.1 micro lot = 100 units."""
        units = order_mod.lots_to_units(0.1, "micro")
        assert units == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
