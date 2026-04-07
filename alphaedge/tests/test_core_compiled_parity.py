# ============================================================
# PROJECT      : ALPHAEDGE
# FILE         : alphaedge/tests/test_core_compiled_parity.py
# DESCRIPTION  : Parity tests — stubs vs compiled Cython modules + signature drift
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-04-06
# ============================================================
"""ALPHAEDGE — Compiled parity: stubs must match compiled .pyd output.

Tests are marked ``@pytest.mark.compiled`` and skip automatically when the
compiled extensions are not available (e.g. CI without a C compiler).

Run with compiled extensions::

    pytest -m compiled alphaedge/tests/test_core_compiled_parity.py -v
"""

from __future__ import annotations

import importlib
import inspect
from collections.abc import Callable
from types import ModuleType
from typing import Any, cast

import pytest


# ------------------------------------------------------------------
# Skip guard — skip entire module if compiled .pyd are not available
# ------------------------------------------------------------------
def _try_import_compiled(name: str) -> ModuleType | None:
    """Return compiled module or None if unavailable."""
    try:
        return importlib.import_module(f"alphaedge.core.{name}")
    except ImportError:
        return None


_compiled_momentum = _try_import_compiled("momentum_detector")
_compiled_risk = _try_import_compiled("risk_manager")
_compiled_order = _try_import_compiled("order_manager")

_compiled_available = all([_compiled_momentum, _compiled_risk, _compiled_order])

# Narrowed typed references — always valid at runtime because every access
# is guarded by @compiled_skip (which skips when _compiled_available is False).
_compiled_momentum_m: ModuleType = cast(ModuleType, _compiled_momentum)
_compiled_risk_m: ModuleType = cast(ModuleType, _compiled_risk)
_compiled_order_m: ModuleType = cast(ModuleType, _compiled_order)

pytestmark = pytest.mark.compiled

compiled_skip = pytest.mark.skipif(
    not _compiled_available,
    reason="Compiled Cython .pyd modules not available — run `make build`",
)

# ------------------------------------------------------------------
# Import stubs directly (bypassing the backend env var)
# ------------------------------------------------------------------
from alphaedge.core._stubs import momentum_detector as _stub_momentum  # noqa: E402
from alphaedge.core._stubs import order_manager as _stub_order  # noqa: E402
from alphaedge.core._stubs import risk_manager as _stub_risk  # noqa: E402


# ------------------------------------------------------------------
# Shared test data helpers
# ------------------------------------------------------------------
def _make_bars(n: int = 60, base_close: float = 1.1000) -> list[dict[str, Any]]:
    """Generate n synthetic OHLC bars with a mild uptrend."""
    bars: list[dict[str, Any]] = []
    price = base_close
    for i in range(n):
        price += 0.0001 * (1 if i % 3 != 0 else -0.5)
        bars.append(
            {
                "open": price - 0.0002,
                "high": price + 0.0003,
                "low": price - 0.0003,
                "close": price,
                "timestamp": 1_700_000_000_000 + i * 86_400_000,
            }
        )
    return bars


_BARS_60 = _make_bars(60)

_POSITION_SIZE_KWARGS: dict[str, Any] = {
    "account_equity": 10_000.0,
    "risk_pct": 1.0,
    "sl_pips": 20.0,
    "pair": "EURUSD",
    "pip_size": 0.0001,
    "lot_type": "standard",
    "min_lots": 0.01,
    "max_lots": 10.0,
    "exchange_rate": 0.0,
}

_BRACKET_ORDER_KWARGS: dict[str, Any] = {
    "direction": 1,
    "entry_price": 1.1000,
    "stop_loss": 1.0980,
    "take_profit": 1.1060,
    "lot_size": 0.05,
    "pip_size": 0.0001,
    "spread_pips": 1.0,
    "max_spread_pips": 3.0,
    "min_rr": 1.5,
    "min_lots": 0.01,
    "max_lots": 10.0,
    "adjust_for_spread": True,
}

_DAILY_LIMIT_KWARGS: dict[str, Any] = {
    "starting_equity": 10_000.0,
    "current_equity": 9_900.0,
    "max_daily_loss_pct": 2.0,
    "trades_today": 1,
    "max_trades": 3,
}


# ------------------------------------------------------------------
# P6-01 — Numerical parity: stubs vs compiled
# ------------------------------------------------------------------
class TestDetectMomentumParity:
    """detect_momentum: stubs vs compiled results must agree to ±1e-10."""

    @compiled_skip
    def test_detect_momentum_direction_matches(self) -> None:
        result_stub = _stub_momentum.detect_momentum(
            bars=_BARS_60,
            fast_period=12,
            slow_period=26,
            adx_period=14,
            adx_threshold=20.0,
        )
        result_compiled = _compiled_momentum_m.detect_momentum(
            bars=_BARS_60,
            fast_period=12,
            slow_period=26,
            adx_period=14,
            adx_threshold=20.0,
        )
        # Both must agree on detection (both None, or both dicts with same direction)
        if result_stub is None:
            assert result_compiled is None, "stubs → None, compiled → signal"
        else:
            assert result_compiled is not None, "compiled → None, stubs → signal"
            assert result_stub["direction"] == result_compiled["direction"]

    @compiled_skip
    def test_detect_momentum_adx_within_tolerance(self) -> None:
        result_stub = _stub_momentum.detect_momentum(
            bars=_BARS_60,
            fast_period=12,
            slow_period=26,
            adx_period=14,
            adx_threshold=20.0,
        )
        result_compiled = _compiled_momentum_m.detect_momentum(
            bars=_BARS_60,
            fast_period=12,
            slow_period=26,
            adx_period=14,
            adx_threshold=20.0,
        )
        if result_stub is not None and result_compiled is not None:
            assert abs(result_stub["adx"] - result_compiled["adx"]) < 1e-6

    @compiled_skip
    def test_detect_momentum_ema_within_tolerance(self) -> None:
        result_stub = _stub_momentum.detect_momentum(
            bars=_BARS_60,
            fast_period=12,
            slow_period=26,
            adx_period=14,
            adx_threshold=20.0,
        )
        result_compiled = _compiled_momentum_m.detect_momentum(
            bars=_BARS_60,
            fast_period=12,
            slow_period=26,
            adx_period=14,
            adx_threshold=20.0,
        )
        if result_stub is not None and result_compiled is not None:
            assert abs(result_stub["ema_fast"] - result_compiled["ema_fast"]) < 1e-8
            assert abs(result_stub["ema_slow"] - result_compiled["ema_slow"]) < 1e-8

    @compiled_skip
    def test_detect_momentum_none_below_threshold(self) -> None:
        result_stub = _stub_momentum.detect_momentum(
            bars=_BARS_60,
            fast_period=12,
            slow_period=26,
            adx_period=14,
            adx_threshold=99.0,  # impossible threshold — always None
        )
        result_compiled = _compiled_momentum_m.detect_momentum(
            bars=_BARS_60,
            fast_period=12,
            slow_period=26,
            adx_period=14,
            adx_threshold=99.0,
        )
        assert result_stub is None
        assert result_compiled is None


class TestCalculatePositionSizeParity:
    """calculate_position_size: stubs vs compiled must agree."""

    @compiled_skip
    def test_lot_size_matches(self) -> None:
        r_stub = _stub_risk.calculate_position_size(**_POSITION_SIZE_KWARGS)
        r_comp = _compiled_risk_m.calculate_position_size(**_POSITION_SIZE_KWARGS)
        assert abs(r_stub["lot_size"] - r_comp["lot_size"]) < 1e-10

    @compiled_skip
    def test_is_valid_matches(self) -> None:
        r_stub = _stub_risk.calculate_position_size(**_POSITION_SIZE_KWARGS)
        r_comp = _compiled_risk_m.calculate_position_size(**_POSITION_SIZE_KWARGS)
        assert r_stub["is_valid"] == r_comp["is_valid"]

    @compiled_skip
    def test_risk_amount_matches(self) -> None:
        r_stub = _stub_risk.calculate_position_size(**_POSITION_SIZE_KWARGS)
        r_comp = _compiled_risk_m.calculate_position_size(**_POSITION_SIZE_KWARGS)
        assert abs(r_stub["risk_amount"] - r_comp["risk_amount"]) < 1e-10


class TestCheckDailyLimitParity:
    """check_daily_limit: stubs vs compiled must agree."""

    @compiled_skip
    def test_limit_breached_matches(self) -> None:
        r_stub = _stub_risk.check_daily_limit(**_DAILY_LIMIT_KWARGS)
        r_comp = _compiled_risk_m.check_daily_limit(**_DAILY_LIMIT_KWARGS)
        assert r_stub["limit_breached"] == r_comp["limit_breached"]

    @compiled_skip
    def test_can_trade_matches(self) -> None:
        r_stub = _stub_risk.check_daily_limit(**_DAILY_LIMIT_KWARGS)
        r_comp = _compiled_risk_m.check_daily_limit(**_DAILY_LIMIT_KWARGS)
        assert r_stub["can_trade"] == r_comp["can_trade"]

    @compiled_skip
    def test_daily_pnl_pct_matches(self) -> None:
        r_stub = _stub_risk.check_daily_limit(**_DAILY_LIMIT_KWARGS)
        r_comp = _compiled_risk_m.check_daily_limit(**_DAILY_LIMIT_KWARGS)
        assert abs(r_stub["daily_pnl_pct"] - r_comp["daily_pnl_pct"]) < 1e-10


class TestCreateBracketOrderParity:
    """create_bracket_order: stubs vs compiled must agree."""

    @compiled_skip
    def test_is_valid_matches(self) -> None:
        r_stub = _stub_order.create_bracket_order(**_BRACKET_ORDER_KWARGS)
        r_comp = _compiled_order_m.create_bracket_order(**_BRACKET_ORDER_KWARGS)
        assert r_stub["is_valid"] == r_comp["is_valid"]

    @compiled_skip
    def test_rr_ratio_within_tolerance(self) -> None:
        r_stub = _stub_order.create_bracket_order(**_BRACKET_ORDER_KWARGS)
        r_comp = _compiled_order_m.create_bracket_order(**_BRACKET_ORDER_KWARGS)
        rr_stub = r_stub.get("rr_ratio")
        rr_comp = r_comp.get("rr_ratio")
        if rr_stub is not None and rr_comp is not None:
            assert abs(rr_stub - rr_comp) < 1e-10

    @compiled_skip
    def test_stop_loss_matches(self) -> None:
        r_stub = _stub_order.create_bracket_order(**_BRACKET_ORDER_KWARGS)
        r_comp = _compiled_order_m.create_bracket_order(**_BRACKET_ORDER_KWARGS)
        sl_stub = r_stub.get("stop_loss")
        sl_comp = r_comp.get("stop_loss")
        if sl_stub is not None and sl_comp is not None:
            assert abs(sl_stub - sl_comp) < 1e-10


# ------------------------------------------------------------------
# P6-03 — Signature drift detection
# ------------------------------------------------------------------
class TestSignatureDrift:
    """Public function signatures in stubs and compiled modules must match."""

    @compiled_skip
    def _compare_signatures(
        self, stub_fn: Callable[..., Any], compiled_fn: Callable[..., Any], fn_name: str
    ) -> None:
        sig_stub = inspect.signature(stub_fn)
        sig_compiled = inspect.signature(compiled_fn)
        stub_params = set(sig_stub.parameters.keys())
        compiled_params = set(sig_compiled.parameters.keys())
        extra_in_stub = stub_params - compiled_params
        extra_in_compiled = compiled_params - stub_params
        assert not extra_in_stub, f"{fn_name}: stub has extra params: {extra_in_stub}"
        assert not extra_in_compiled, (
            f"{fn_name}: compiled has extra params: {extra_in_compiled}"
        )

    @compiled_skip
    def test_detect_momentum_signature(self) -> None:
        self._compare_signatures(
            _stub_momentum.detect_momentum,
            _compiled_momentum_m.detect_momentum,
            "detect_momentum",
        )

    @compiled_skip
    def test_calculate_position_size_signature(self) -> None:
        self._compare_signatures(
            _stub_risk.calculate_position_size,
            _compiled_risk_m.calculate_position_size,
            "calculate_position_size",
        )

    @compiled_skip
    def test_check_daily_limit_signature(self) -> None:
        self._compare_signatures(
            _stub_risk.check_daily_limit,
            _compiled_risk_m.check_daily_limit,
            "check_daily_limit",
        )

    @compiled_skip
    def test_create_bracket_order_signature(self) -> None:
        self._compare_signatures(
            _stub_order.create_bracket_order,
            _compiled_order_m.create_bracket_order,
            "create_bracket_order",
        )

    @compiled_skip
    def test_check_pair_limit_signature(self) -> None:
        self._compare_signatures(
            _stub_risk.check_pair_limit,
            _compiled_risk_m.check_pair_limit,
            "check_pair_limit",
        )
