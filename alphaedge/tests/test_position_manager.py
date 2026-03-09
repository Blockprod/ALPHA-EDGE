# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_position_manager.py
# DESCRIPTION  : Unit tests for PositionManager sizing and order building
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""Tests for PositionManager: position sizing and bracket order building."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from alphaedge.engine.position_manager import PositionManager
from alphaedge.engine.strategy import StrategyState


def _make_state(equity: float = 10_000.0) -> StrategyState:
    state = StrategyState(pair="EURUSD")
    state.starting_equity = equity
    state.current_equity = equity
    return state


def _make_modules(
    pos_result: dict[str, Any] | None = None,
    bracket_result: dict[str, Any] | None = None,
) -> MagicMock:
    modules = MagicMock()
    default_pos = {"is_valid": True, "lot_size": 0.1}
    modules.risk_manager.calculate_position_size.return_value = (
        pos_result if pos_result is not None else default_pos
    )
    default_bracket = {"is_valid": True, "direction": "BUY", "lot_size": 0.1}
    modules.order_manager.create_bracket_order.return_value = (
        bracket_result if bracket_result is not None else default_bracket
    )
    return modules


def _make_config(
    risk_pct: float = 1.0,
    lot_type: str = "micro",
    max_spread_pips: float = 3.0,
    rr_ratio: float = 2.0,
) -> MagicMock:
    cfg = MagicMock()
    cfg.trading.risk_pct = risk_pct
    cfg.trading.lot_type = lot_type
    cfg.trading.max_spread_pips = max_spread_pips
    cfg.trading.rr_ratio = rr_ratio
    return cfg


def _make_signal(risk_pips: float = 15.0) -> dict[str, Any]:
    return {
        "signal": 1,
        "entry_price": 1.1050,
        "stop_loss": 1.1035,
        "take_profit": 1.1080,
        "risk_pips": risk_pips,
    }


class TestPositionManagerSizePosition:
    """size_position delegates to risk_manager and returns None on invalid result."""

    def test_returns_valid_result(self) -> None:
        pm = PositionManager()
        state = _make_state(equity=10_000.0)
        modules = _make_modules(pos_result={"is_valid": True, "lot_size": 0.05})
        cfg = _make_config()
        result = pm.size_position(state, modules, cfg, _make_signal(), pip_size=0.0001)
        assert result is not None
        assert result["lot_size"] == 0.05

    def test_returns_none_when_invalid(self) -> None:
        pm = PositionManager()
        state = _make_state(equity=10_000.0)
        modules = _make_modules(pos_result={"is_valid": False, "lot_size": 0.0})
        cfg = _make_config()
        result = pm.size_position(state, modules, cfg, _make_signal(), pip_size=0.0001)
        assert result is None

    def test_uses_current_equity_when_set(self) -> None:
        pm = PositionManager()
        state = _make_state(equity=5_000.0)
        state.current_equity = 12_000.0
        modules = _make_modules()
        cfg = _make_config()
        pm.size_position(state, modules, cfg, _make_signal(), pip_size=0.0001)
        call_kwargs = modules.risk_manager.calculate_position_size.call_args.kwargs
        assert call_kwargs["account_equity"] == 12_000.0

    def test_uses_starting_equity_when_current_zero(self) -> None:
        pm = PositionManager()
        state = _make_state(equity=9_000.0)
        state.current_equity = 0.0
        modules = _make_modules()
        cfg = _make_config()
        pm.size_position(state, modules, cfg, _make_signal(), pip_size=0.0001)
        call_kwargs = modules.risk_manager.calculate_position_size.call_args.kwargs
        assert call_kwargs["account_equity"] == 9_000.0


class TestPositionManagerBuildOrder:
    """build_validated_order delegates to order_manager; None on rejection."""

    def test_returns_valid_bracket(self) -> None:
        pm = PositionManager()
        modules = _make_modules(bracket_result={"is_valid": True, "lot_size": 0.1})
        cfg = _make_config()
        result = pm.build_validated_order(
            _make_signal(), 0.1, 0.0001, 1.5, modules, cfg
        )
        assert result is not None
        assert result["is_valid"] is True

    def test_returns_none_when_rejected(self) -> None:
        pm = PositionManager()
        rejected = {"is_valid": False, "rejection_reason": "spread too wide"}
        modules = _make_modules(bracket_result=rejected)
        cfg = _make_config()
        result = pm.build_validated_order(
            _make_signal(), 0.1, 0.0001, 5.0, modules, cfg
        )
        assert result is None

    def test_passes_signal_direction(self) -> None:
        pm = PositionManager()
        modules = _make_modules()
        cfg = _make_config()
        signal = _make_signal()
        signal["signal"] = -1  # SELL
        pm.build_validated_order(signal, 0.1, 0.0001, 1.0, modules, cfg)
        call_kwargs = modules.order_manager.create_bracket_order.call_args.kwargs
        assert call_kwargs["direction"] == -1
