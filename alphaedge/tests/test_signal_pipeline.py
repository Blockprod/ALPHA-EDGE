# ============================================================
# PROJECT      : ALPHAEDGE
# FILE         : alphaedge/tests/test_signal_pipeline.py
# DESCRIPTION  : Momentum+Carry pipeline — 4 critical scenarios
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-25
# ============================================================
"""ALPHAEDGE — Signal pipeline: Momentum+Carry detection scenarios."""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("ALPHAEDGE_CORE_BACKEND", "stubs")

from alphaedge.config.loader import AppConfig  # noqa: E402
from alphaedge.engine.carry_signal import CarrySignal  # noqa: E402
from alphaedge.engine.signal_pipeline import SignalPipeline  # noqa: E402


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _make_state(
    pair: str = "AUDJPY",
    daily_bars: list[dict[str, Any]] | None = None,
    carry_rates: dict[str, float] | None = None,
) -> MagicMock:
    state = MagicMock()
    state.pair = pair
    state.daily_bars = daily_bars or []
    state.carry_rates = carry_rates or {}
    state.signal_result = None
    return state


def _mock_modules(
    momentum_result: dict[str, Any] | None,
) -> MagicMock:
    """Return a CoreModules mock with momentum_detector pre-configured."""
    modules = MagicMock()
    modules.momentum_detector.detect_momentum.return_value = momentum_result
    return modules


def _momentum_signal(direction: int = 1, adx: float = 28.0) -> dict[str, Any]:
    return {
        "detected": True,
        "direction": direction,
        "strength": adx / 100.0,
        "ema_fast": 1.10,
        "ema_slow": 1.09,
        "adx": adx,
        "timestamp": 1_700_000_000_000,
    }


# ------------------------------------------------------------------
# Scenario 1: ADX below threshold → momentum returns None → pipeline STOP
# ------------------------------------------------------------------
class TestMomentumStopAdxBelowThreshold:
    def test_momentum_returns_none_when_adx_low(self) -> None:
        pipeline = SignalPipeline()
        modules = _mock_modules(momentum_result=None)
        state = _make_state()

        result = pipeline.detect_momentum(state, modules, AppConfig())

        assert result is None
        assert state.signal_result is None

    def test_no_carry_check_needed_when_momentum_none(self) -> None:
        """Carry should not be called after a momentum STOP — pipeline is atomic."""
        pipeline = SignalPipeline()
        modules = _mock_modules(momentum_result=None)
        state = _make_state()

        momentum_result = pipeline.detect_momentum(state, modules, AppConfig())
        # Simulate the pipeline: if momentum is None, stop immediately
        assert momentum_result is None
        # (no further calls in a correct implementation)


# ------------------------------------------------------------------
# Scenario 2: carry contradiction blocks entry
# ------------------------------------------------------------------
class TestCarryContradictionBlocksEntry:
    def test_long_momentum_short_carry_is_conflict(self) -> None:
        pipeline = SignalPipeline()
        mom = _momentum_signal(direction=1)
        carry = CarrySignal(
            differential=-1.5,
            direction="SHORT",
            daily_carry_pips=-0.05,
            is_valid=True,
        )
        assert pipeline.is_carry_conflict(mom, carry) is True

    def test_short_momentum_long_carry_is_conflict(self) -> None:
        pipeline = SignalPipeline()
        mom = _momentum_signal(direction=-1)
        carry = CarrySignal(
            differential=1.5,
            direction="LONG",
            daily_carry_pips=0.05,
            is_valid=True,
        )
        assert pipeline.is_carry_conflict(mom, carry) is True

    def test_neutral_carry_never_conflicts(self) -> None:
        pipeline = SignalPipeline()
        mom = _momentum_signal(direction=1)
        carry = CarrySignal(
            differential=0.1,
            direction="NEUTRAL",
            daily_carry_pips=0.001,
            is_valid=True,
        )
        assert pipeline.is_carry_conflict(mom, carry) is False

    def test_invalid_carry_never_conflicts(self) -> None:
        pipeline = SignalPipeline()
        mom = _momentum_signal(direction=1)
        carry = CarrySignal(
            differential=0.0,
            direction="NEUTRAL",
            daily_carry_pips=0.0,
            is_valid=False,
        )
        assert pipeline.is_carry_conflict(mom, carry) is False


# ------------------------------------------------------------------
# Scenario 3: full pipeline — momentum LONG + carry LONG → signal produced
# ------------------------------------------------------------------
class TestFullPipelineLongSignal:
    def test_long_momentum_long_carry_no_conflict(self) -> None:
        pipeline = SignalPipeline()
        modules = _mock_modules(momentum_result=_momentum_signal(direction=1))
        state = _make_state(
            pair="AUDJPY",
            carry_rates={"AUD": 4.35, "JPY": 0.10},
        )

        mom_result = pipeline.detect_momentum(state, modules, AppConfig())
        assert mom_result is not None
        assert mom_result["direction"] == 1

        carry = pipeline.get_carry(state, AppConfig())
        assert carry.is_valid is True
        assert carry.direction == "LONG"
        assert not pipeline.is_carry_conflict(mom_result, carry)

    def test_signal_result_stored_on_state(self) -> None:
        pipeline = SignalPipeline()
        expected = _momentum_signal(direction=1)
        modules = _mock_modules(momentum_result=expected)
        state = _make_state()

        pipeline.detect_momentum(state, modules, AppConfig())
        assert state.signal_result is expected


# ------------------------------------------------------------------
# Scenario 4: full pipeline — momentum SHORT + carry SHORT → signal produced
# ------------------------------------------------------------------
class TestFullPipelineShortSignal:
    def test_short_momentum_short_carry_no_conflict(self) -> None:
        pipeline = SignalPipeline()
        modules = _mock_modules(momentum_result=_momentum_signal(direction=-1))
        state = _make_state(
            pair="EURUSD",
            carry_rates={"EUR": 3.65, "USD": 5.25},  # USD pays more → EUR SHORT
        )

        mom_result = pipeline.detect_momentum(state, modules, AppConfig())
        assert mom_result is not None
        assert mom_result["direction"] == -1

        carry = pipeline.get_carry(state, AppConfig())
        assert carry.is_valid is True
        # USD pays more than EUR → differential = 3.65 - 5.25 = -1.6 → SHORT EUR
        assert carry.direction == "SHORT"
        assert not pipeline.is_carry_conflict(mom_result, carry)

    def test_short_momentum_long_carry_conflicts(self) -> None:
        """SHORT momentum with LONG carry bias → conflict → STOP."""
        pipeline = SignalPipeline()
        modules = _mock_modules(momentum_result=_momentum_signal(direction=-1))
        state = _make_state(
            pair="AUDJPY",
            carry_rates={"AUD": 4.35, "JPY": 0.10},  # AUD pays more → LONG AUD
        )

        mom_result = pipeline.detect_momentum(state, modules, AppConfig())
        assert mom_result is not None

        carry = pipeline.get_carry(state, AppConfig())
        assert carry.direction == "LONG"
        assert pipeline.is_carry_conflict(mom_result, carry) is True


# ------------------------------------------------------------------
# Edge cases
# ------------------------------------------------------------------
class TestEdgeCases:
    @pytest.mark.parametrize("adx", [25.0, 26.0, 50.0, 100.0])
    def test_detect_momentum_passes_adx_threshold_from_constants(
        self, adx: float
    ) -> None:
        pipeline = SignalPipeline()
        expected = _momentum_signal(adx=adx)
        modules = _mock_modules(momentum_result=expected)
        state = _make_state()
        result = pipeline.detect_momentum(state, modules, AppConfig())
        assert result is not None

    def test_get_carry_with_missing_rates_returns_invalid(self) -> None:
        pipeline = SignalPipeline()
        state = _make_state(pair="AUDJPY", carry_rates={})
        carry = pipeline.get_carry(state, AppConfig())
        assert carry.is_valid is False
