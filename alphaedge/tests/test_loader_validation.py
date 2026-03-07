# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_loader_validation.py
# DESCRIPTION  : Tests for config validation edge cases
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: config loader validation tests."""

from __future__ import annotations

import pytest

from alphaedge.config.loader import TradingConfig, _validate_trading_config


class TestLoaderValidation:
    """Tests for _validate_trading_config edge cases."""

    def test_risk_pct_zero_raises(self) -> None:
        """risk_pct of 0 should raise ValueError."""
        cfg = TradingConfig(risk_pct=0.0)
        with pytest.raises(ValueError, match="risk_pct"):
            _validate_trading_config(cfg)

    def test_risk_pct_negative_raises(self) -> None:
        """Negative risk_pct should raise ValueError."""
        cfg = TradingConfig(risk_pct=-1.0)
        with pytest.raises(ValueError, match="risk_pct"):
            _validate_trading_config(cfg)

    def test_risk_pct_above_max_raises(self) -> None:
        """risk_pct above 10 should raise ValueError."""
        cfg = TradingConfig(risk_pct=11.0)
        with pytest.raises(ValueError, match="risk_pct"):
            _validate_trading_config(cfg)

    def test_risk_pct_boundary_10_passes(self) -> None:
        """risk_pct of exactly 10 should pass validation."""
        cfg = TradingConfig(risk_pct=10.0)
        _validate_trading_config(cfg)  # Should not raise

    def test_rr_ratio_zero_raises(self) -> None:
        """rr_ratio of 0 should raise ValueError."""
        cfg = TradingConfig(rr_ratio=0.0)
        with pytest.raises(ValueError, match="rr_ratio"):
            _validate_trading_config(cfg)

    def test_max_daily_loss_pct_zero_raises(self) -> None:
        """max_daily_loss_pct of 0 should raise ValueError."""
        cfg = TradingConfig(max_daily_loss_pct=0.0)
        with pytest.raises(ValueError, match="max_daily_loss_pct"):
            _validate_trading_config(cfg)

    def test_max_trades_per_session_zero_raises(self) -> None:
        """max_trades_per_session of 0 should raise ValueError."""
        cfg = TradingConfig(max_trades_per_session=0)
        with pytest.raises(ValueError, match="max_trades_per_session"):
            _validate_trading_config(cfg)

    def test_max_spread_pips_zero_raises(self) -> None:
        """max_spread_pips of 0 should raise ValueError."""
        cfg = TradingConfig(max_spread_pips=0.0)
        with pytest.raises(ValueError, match="max_spread_pips"):
            _validate_trading_config(cfg)

    def test_valid_config_passes(self) -> None:
        """Default TradingConfig should pass validation."""
        cfg = TradingConfig()
        _validate_trading_config(cfg)  # Should not raise
