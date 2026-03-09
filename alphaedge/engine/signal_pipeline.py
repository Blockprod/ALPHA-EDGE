# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/engine/signal_pipeline.py
# DESCRIPTION  : Stateless FCR → Gap → Engulfing detection chain
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: signal detection pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from alphaedge.config.constants import (
    DEFAULT_ATR_PERIOD,
    DEFAULT_MIN_ATR_RATIO,
    DEFAULT_MIN_RANGE_PIPS,
    DEFAULT_MIN_VOLUME_RATIO,
    DEFAULT_VOLUME_PERIOD,
)

if TYPE_CHECKING:
    from alphaedge.config.loader import AppConfig
    from alphaedge.engine.strategy import CoreModules, StrategyState


class SignalPipeline:
    """
    Stateless FCR → Gap → Engulfing detection chain.

    All state is held in the ``StrategyState`` instance.  Core modules and
    config are passed per call so that ``FCRStrategy`` remains the single
    owner of those dependencies.
    """

    # ------------------------------------------------------------------
    # FCR detection
    # ------------------------------------------------------------------
    def detect_fcr(
        self,
        state: StrategyState,
        modules: CoreModules,
        pip_size: float,
    ) -> dict[str, Any] | None:
        """
        Run FCR detection on the pre-session M5 candles stored in *state*.

        Writes ``state.fcr_result`` and returns the result.
        """
        result: dict[str, Any] | None = modules.fcr_detector.detect_fcr(
            candles_data=state.m5_candles,
            min_range_pips=DEFAULT_MIN_RANGE_PIPS,
            pip_size=pip_size,
        )
        state.fcr_result = result
        return result

    # ------------------------------------------------------------------
    # Gap / ATR-spike detection
    # ------------------------------------------------------------------
    def detect_gap(
        self,
        state: StrategyState,
        modules: CoreModules,
        pre_close: float,
        session_open: float,
    ) -> dict[str, Any] | None:
        """
        Run gap / volatility-expansion detection.

        Writes ``state.gap_result`` and returns the result.
        """
        result: dict[str, Any] | None = modules.gap_detector.detect_gap(
            pre_session_m1=state.m5_candles,
            session_m1=state.m1_candles,
            pre_close=pre_close,
            session_open=session_open,
            atr_period=DEFAULT_ATR_PERIOD,
            min_atr_ratio=DEFAULT_MIN_ATR_RATIO,
        )
        state.gap_result = result
        return result

    # ------------------------------------------------------------------
    # Engulfing detection
    # ------------------------------------------------------------------
    def detect_engulfing(
        self,
        state: StrategyState,
        modules: CoreModules,
        config: AppConfig,
        pip_size: float,
    ) -> dict[str, Any] | None:
        """
        Run engulfing-candle detection on the M1 candles stored in *state*.

        Returns ``None`` immediately when no FCR result is available.
        Writes ``state.signal_result`` and returns the result.
        """
        if state.fcr_result is None:
            return None

        result: dict[str, Any] | None = modules.engulfing_detector.detect_engulfing(
            candles_data=state.m1_candles,
            fcr_high=state.fcr_result["range_high"],
            fcr_low=state.fcr_result["range_low"],
            rr_ratio=config.trading.rr_ratio,
            pip_size=pip_size,
            volume_period=DEFAULT_VOLUME_PERIOD,
            min_volume_ratio=DEFAULT_MIN_VOLUME_RATIO,
            min_body_ratio=config.trading.min_body_ratio,
            max_wick_ratio=config.trading.max_wick_ratio,
        )
        state.signal_result = result
        return result
