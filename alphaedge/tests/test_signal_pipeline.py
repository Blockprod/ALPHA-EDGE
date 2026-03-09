# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_signal_pipeline.py
# DESCRIPTION  : Unit tests for SignalPipeline detection chain
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""Tests for SignalPipeline: FCR → Gap → Engulfing detection delegation."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from alphaedge.engine.signal_pipeline import SignalPipeline
from alphaedge.engine.strategy import StrategyState


def _make_state(**kw: Any) -> StrategyState:
    state = StrategyState(pair="EURUSD")
    state.m5_candles = kw.get("m5_candles", [{"close": 1.1000}])
    state.m1_candles = kw.get("m1_candles", [{"close": 1.1001}])
    state.fcr_result = kw.get("fcr_result", None)
    return state


def _make_modules(
    fcr_result: Any = None,
    gap_result: Any = None,
    eng_result: Any = None,
) -> MagicMock:
    modules = MagicMock()
    modules.fcr_detector.detect_fcr.return_value = fcr_result
    modules.gap_detector.detect_gap.return_value = gap_result
    modules.engulfing_detector.detect_engulfing.return_value = eng_result
    return modules


def _make_config(
    rr: float = 2.0,
    min_body: float = 0.5,
    max_wick: float = 0.5,
) -> MagicMock:
    cfg = MagicMock()
    cfg.trading.rr_ratio = rr
    cfg.trading.min_body_ratio = min_body
    cfg.trading.max_wick_ratio = max_wick
    return cfg


class TestSignalPipelineDetectFCR:
    """detect_fcr delegates to modules.fcr_detector and writes state."""

    def test_returns_none_when_no_fcr(self) -> None:
        pipeline = SignalPipeline()
        state = _make_state()
        modules = _make_modules(fcr_result=None)
        result = pipeline.detect_fcr(state, modules, pip_size=0.0001)
        assert result is None
        assert state.fcr_result is None

    def test_returns_and_stores_fcr_result(self) -> None:
        pipeline = SignalPipeline()
        state = _make_state()
        fcr = {"range_high": 1.1050, "range_low": 1.1000}
        modules = _make_modules(fcr_result=fcr)
        result = pipeline.detect_fcr(state, modules, pip_size=0.0001)
        assert result == fcr
        assert state.fcr_result == fcr

    def test_calls_detector_with_correct_candles(self) -> None:
        pipeline = SignalPipeline()
        candles = [{"open": 1.1, "close": 1.11}]
        state = _make_state(m5_candles=candles)
        modules = _make_modules()
        pipeline.detect_fcr(state, modules, pip_size=0.0001)
        call_kwargs = modules.fcr_detector.detect_fcr.call_args.kwargs
        assert call_kwargs["candles_data"] is candles


class TestSignalPipelineDetectGap:
    """detect_gap delegates to modules.gap_detector and writes state."""

    def test_returns_none_when_no_gap(self) -> None:
        pipeline = SignalPipeline()
        state = _make_state()
        modules = _make_modules(gap_result=None)
        result = pipeline.detect_gap(
            state, modules, pre_close=1.1000, session_open=1.1001
        )
        assert result is None
        assert state.gap_result is None

    def test_returns_and_stores_gap_result(self) -> None:
        pipeline = SignalPipeline()
        state = _make_state()
        gap = {"detected": True, "atr_ratio": 2.5}
        modules = _make_modules(gap_result=gap)
        result = pipeline.detect_gap(
            state, modules, pre_close=1.1000, session_open=1.1050
        )
        assert result == gap
        assert state.gap_result == gap


class TestSignalPipelineDetectEngulfing:
    """detect_engulfing guards on fcr_result and delegates to modules."""

    def test_returns_none_when_no_fcr(self) -> None:
        """When state.fcr_result is None, engulfing is not run."""
        pipeline = SignalPipeline()
        state = _make_state()  # fcr_result is None by default
        modules = _make_modules()
        cfg = _make_config()
        result = pipeline.detect_engulfing(state, modules, cfg, pip_size=0.0001)
        assert result is None
        modules.engulfing_detector.detect_engulfing.assert_not_called()

    def test_returns_result_when_fcr_available(self) -> None:
        pipeline = SignalPipeline()
        fcr = {"range_high": 1.1050, "range_low": 1.1000}
        state = _make_state(fcr_result=fcr)
        eng = {"detected": True, "signal": 1, "entry_price": 1.1055}
        modules = _make_modules(eng_result=eng)
        cfg = _make_config()
        result = pipeline.detect_engulfing(state, modules, cfg, pip_size=0.0001)
        assert result == eng
        assert state.signal_result == eng

    def test_passes_fcr_levels_to_detector(self) -> None:
        pipeline = SignalPipeline()
        fcr = {"range_high": 1.1100, "range_low": 1.0900}
        state = _make_state(fcr_result=fcr)
        modules = _make_modules()
        cfg = _make_config()
        pipeline.detect_engulfing(state, modules, cfg, pip_size=0.0001)
        call_kwargs = modules.engulfing_detector.detect_engulfing.call_args.kwargs
        assert call_kwargs["fcr_high"] == 1.1100
        assert call_kwargs["fcr_low"] == 1.0900
