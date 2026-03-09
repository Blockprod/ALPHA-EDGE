# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_gap_detector_zone.py
# DESCRIPTION  : Tests for gap zone boundary checks
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: gap detector tests — zone checks."""

from __future__ import annotations

import pytest

from alphaedge.core import gap_detector as gap_mod


class TestGapDetectorZone:
    """Tests for is_in_gap_zone function."""

    def test_price_inside_gap_zone(self) -> None:
        """Price within gap boundaries should return True."""
        result = gap_mod.is_in_gap_zone(
            price=1.08550,
            gap_high=1.08600,
            gap_low=1.08500,
            tolerance_pips=0.0,
            pip_size=0.0001,
        )

        assert result is True

    def test_price_outside_gap_zone(self) -> None:
        """Price far from gap boundaries should return False."""
        result = gap_mod.is_in_gap_zone(
            price=1.09000,
            gap_high=1.08600,
            gap_low=1.08500,
            tolerance_pips=5.0,
            pip_size=0.0001,
        )

        assert result is False

    def test_price_within_tolerance(self) -> None:
        """Price within tolerance buffer should return True."""
        # Price is 3 pips above gap_high, tolerance is 5 pips
        result = gap_mod.is_in_gap_zone(
            price=1.08603,
            gap_high=1.08600,
            gap_low=1.08500,
            tolerance_pips=5.0,
            pip_size=0.0001,
        )

        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
