# ============================================================
# PROJECT      : ALPHAEDGE — Swing Trading Bot
# FILE         : alphaedge/engine/pipeline_protocol.py
# DESCRIPTION  : Protocol interface for the signal detection pipeline
# AUTHOR       : ALPHAEDGE Dev Team
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-04-06
# ============================================================
"""ALPHAEDGE — Protocol definition for SignalPipeline consumers (live + backtest)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from alphaedge.config.loader import AppConfig
    from alphaedge.engine.carry_signal import CarrySignal
    from alphaedge.engine.strategy import CoreModules, StrategyState


@runtime_checkable
class SignalPipelineProtocol(Protocol):
    """
    Structural interface for signal detection pipelines.

    Both the live ``SignalPipeline`` and any backtest adapter must satisfy
    this contract so that callers can be typed against the Protocol rather
    than the concrete class.

    All methods are stateless with respect to the pipeline instance —
    state is held entirely in the ``StrategyState`` (or proxy) passed in.
    """

    def detect_momentum(
        self,
        state: StrategyState,
        modules: CoreModules,
        config: AppConfig,
    ) -> dict[str, Any] | None:
        """
        Run ADX+EMA momentum detection on ``state.daily_bars``.

        Returns the signal dict (with ``detected: True``) or ``None``
        when ADX is below threshold.  Writes ``state.signal_result``
        as a side effect.
        """
        ...

    def get_carry(
        self,
        state: StrategyState,
        config: AppConfig,
    ) -> CarrySignal:
        """
        Compute carry directional bias for ``state.pair``.

        Uses ``state.carry_rates`` (falling back to
        ``config.trading.carry_rates``) and
        ``config.trading.carry_min_differential_pct``.
        """
        ...

    @staticmethod
    def is_carry_conflict(
        momentum_result: dict[str, Any],
        carry: CarrySignal,
    ) -> bool:
        """
        Return ``True`` when carry direction contradicts momentum direction.

        NEUTRAL carry never conflicts.
        """
        ...
