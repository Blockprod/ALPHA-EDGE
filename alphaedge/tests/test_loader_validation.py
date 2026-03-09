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

import io

import pytest
from loguru import logger

from alphaedge.config.loader import (
    TradingConfig,
    _check_ib_port,
    _validate_trading_config,
)


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


class TestPairValidation:
    """Tests for pair validation in _validate_trading_config."""

    def test_unknown_pair_raises(self) -> None:
        """Unknown pair symbol should raise ValueError."""
        cfg = TradingConfig(pairs=["EURUSD", "XYZABC"])
        with pytest.raises(ValueError, match="XYZABC"):
            _validate_trading_config(cfg)

    def test_valid_pairs_pass(self) -> None:
        """All known pairs should pass validation."""
        cfg = TradingConfig(pairs=["EURUSD", "GBPUSD", "USDJPY"])
        _validate_trading_config(cfg)  # Should not raise

    def test_empty_pairs_passes(self) -> None:
        """Empty pairs list is allowed (bot runs no pairs)."""
        cfg = TradingConfig(pairs=[])
        _validate_trading_config(cfg)  # Should not raise


class TestLotTypeValidation:
    """Tests for lot_type validation in _validate_trading_config."""

    def test_invalid_lot_type_raises(self) -> None:
        """Invalid lot_type should raise ValueError."""
        cfg = TradingConfig(lot_type="nano")
        with pytest.raises(ValueError, match="lot_type"):
            _validate_trading_config(cfg)

    def test_standard_lot_type_passes(self) -> None:
        cfg = TradingConfig(lot_type="standard")
        _validate_trading_config(cfg)

    def test_mini_lot_type_passes(self) -> None:
        cfg = TradingConfig(lot_type="mini")
        _validate_trading_config(cfg)

    def test_micro_lot_type_passes(self) -> None:
        cfg = TradingConfig(lot_type="micro")
        _validate_trading_config(cfg)


class TestIBPortWarning:
    """Tests for non-standard IB port warning."""

    def test_non_standard_port_logs_warning(self) -> None:
        """Port other than 4001/4002 should emit a WARNING."""
        sink = io.StringIO()
        handler_id = logger.add(sink, format="{level} {message}", level="DEBUG")
        try:
            _check_ib_port(7497)
        finally:
            logger.remove(handler_id)

        output = sink.getvalue()
        assert "WARNING" in output
        assert "7497" in output

    def test_standard_port_4001_no_warning(self) -> None:
        sink = io.StringIO()
        handler_id = logger.add(sink, format="{level} {message}", level="DEBUG")
        try:
            _check_ib_port(4001)
        finally:
            logger.remove(handler_id)
        assert "WARNING" not in sink.getvalue()

    def test_standard_port_4002_no_warning(self) -> None:
        sink = io.StringIO()
        handler_id = logger.add(sink, format="{level} {message}", level="DEBUG")
        try:
            _check_ib_port(4002)
        finally:
            logger.remove(handler_id)
        assert "WARNING" not in sink.getvalue()
