# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_backtest_execution_validation.py
# DESCRIPTION  : Backtest execution validation parity with live filters
# PYTHON       : 3.11.9
# ============================================================
"""Tests for backtest-side sizing and bracket validation."""

from __future__ import annotations

from unittest.mock import MagicMock

from alphaedge.config.loader import AppConfig, IBConfig, TradingConfig
from alphaedge.engine.backtest import _validate_backtest_signal


def _make_config() -> AppConfig:
    return AppConfig(
        ib=IBConfig(is_paper=True),
        trading=TradingConfig(
            pairs=["EURUSD"],
            risk_pct=3.0,
            rr_ratio=2.0,
            max_spread_pips=2.0,
            max_lot_size=1.0,
            lot_type="micro",
            starting_equity=10000.0,
        ),
    )


def _make_signal() -> dict[str, float | int]:
    return {
        "signal": 1,
        "entry_price": 1.1000,
        "stop_loss": 1.0980,
        "take_profit": 1.1040,
        "risk_pips": 20.0,
    }


class TestValidateBacktestSignal:
    def test_returns_none_when_position_size_invalid(self) -> None:
        cfg = _make_config()
        risk_mod = MagicMock()
        order_mod = MagicMock()
        risk_mod.calculate_position_size.return_value = {
            "is_valid": False,
            "lot_size": 0.0,
        }

        result = _validate_backtest_signal(
            "EURUSD",
            _make_signal(),
            cfg,
            0.0001,
            1.0,
            risk_mod,
            order_mod,
        )

        assert result is None
        order_mod.create_bracket_order.assert_not_called()

    def test_returns_none_when_bracket_order_invalid(self) -> None:
        cfg = _make_config()
        risk_mod = MagicMock()
        order_mod = MagicMock()
        risk_mod.calculate_position_size.return_value = {
            "is_valid": True,
            "lot_size": 0.10,
        }
        order_mod.create_bracket_order.return_value = {
            "is_valid": False,
            "rejection_reason": "spread_too_wide",
        }

        result = _validate_backtest_signal(
            "EURUSD",
            _make_signal(),
            cfg,
            0.0001,
            2.5,
            risk_mod,
            order_mod,
        )

        assert result is None

    def test_returns_adjusted_signal_when_valid(self) -> None:
        cfg = _make_config()
        risk_mod = MagicMock()
        order_mod = MagicMock()
        risk_mod.calculate_position_size.return_value = {
            "is_valid": True,
            "lot_size": 0.10,
        }
        order_mod.create_bracket_order.return_value = {
            "is_valid": True,
            "stop_loss": 1.0978,
            "take_profit": 1.1040,
            "risk_pips": 22.0,
            "reward_pips": 40.0,
        }

        result = _validate_backtest_signal(
            "EURUSD",
            _make_signal(),
            cfg,
            0.0001,
            1.2,
            risk_mod,
            order_mod,
        )

        assert result is not None
        assert result["signal"]["stop_loss"] == 1.0978
        assert result["signal"]["risk_pips"] == 22.0
        assert result["spread_pips"] == 1.2
