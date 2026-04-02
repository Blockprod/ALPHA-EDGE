# ============================================================
# PROJECT      : ALPHAEDGE
# FILE         : alphaedge/engine/signal_pipeline.py
# DESCRIPTION  : Stateless Momentum + Carry detection chain
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-25
# ============================================================
"""ALPHAEDGE — Momentum + Carry signal detection pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from alphaedge.config.constants import (
    DEFAULT_MOMENTUM_FAST_PERIOD,
    DEFAULT_MOMENTUM_SLOW_PERIOD,
)
from alphaedge.engine.carry_signal import CarrySignal, get_carry_bias
from alphaedge.utils.logger import get_logger

logger = get_logger()

if TYPE_CHECKING:
    # NOTE: import cycle with strategy.py mitigated by TYPE_CHECKING
    from alphaedge.config.loader import AppConfig
    from alphaedge.engine.strategy import CoreModules, StrategyState


def _is_carry_conflict(
    momentum_result: dict[str, Any],
    carry: CarrySignal,
) -> bool:
    """Return True when carry direction contradicts momentum direction.

    NEUTRAL carry never conflicts — it is treated as a permissive state.
    """
    if not carry.is_valid or carry.direction == "NEUTRAL":
        return False
    mom_dir: int = int(momentum_result.get("direction", 0))
    if mom_dir == 1 and carry.direction == "SHORT":
        return True
    if mom_dir == -1 and carry.direction == "LONG":
        return True
    return False


class SignalPipeline:
    """
    Stateless Momentum → Carry → Regime detection chain.

    All state is held in the ``StrategyState`` instance.  Core modules and
    config are passed per call so that ``SwingStrategy`` remains the single
    owner of those dependencies.

    Pipeline (all-or-nothing):
        Step 1  momentum_detector.detect_momentum(daily_bars)
                    → dict | None  [STOP if None — ADX gate]
        Step 2  carry_signal.get_carry_bias(pair, rates)
                    → CarrySignal  [STOP if contradiction with momentum]
        Step 3  risk_manager.calculate_position_size()       [unchanged]
        Step 4  order_manager.create_bracket_order()         [unchanged]
    """

    # ------------------------------------------------------------------
    # Step 1 — Momentum detection
    # ------------------------------------------------------------------
    def detect_momentum(
        self,
        state: StrategyState,
        modules: CoreModules,
        config: AppConfig,
    ) -> dict[str, Any] | None:
        """
        Run momentum detection on the Daily bars stored in *state*.

        Reads ``fast_period``, ``slow_period``, ``adx_period``,
        ``adx_threshold`` from ``config.trading`` if available,
        falling back to module-level constants.

        Writes ``state.signal_result`` and returns the result dict,
        or ``None`` when ADX is below threshold.
        """
        trading = config.trading
        fast = getattr(trading, "momentum_fast_period", DEFAULT_MOMENTUM_FAST_PERIOD)
        slow = getattr(trading, "momentum_slow_period", DEFAULT_MOMENTUM_SLOW_PERIOD)
        adx_p = trading.momentum_adx_period
        adx_t = trading.momentum_adx_threshold

        daily_bars: list[dict[str, Any]] = getattr(state, "daily_bars", [])

        result: dict[str, Any] | None = modules.momentum_detector.detect_momentum(
            bars=daily_bars,
            fast_period=fast,
            slow_period=slow,
            adx_period=adx_p,
            adx_threshold=adx_t,
        )
        if result is None:
            logger.debug(
                "ALPHAEDGE MOMENTUM: %s — ADX below threshold "
                "(adx_threshold=%.1f, adx_period=%d) — signal rejected",
                state.pair,
                adx_t,
                adx_p,
            )
        state.signal_result = result
        return result

    # ------------------------------------------------------------------
    # Step 2 — Carry bias
    # ------------------------------------------------------------------
    def get_carry(
        self,
        state: StrategyState,
        config: AppConfig,
    ) -> CarrySignal:
        """
        Compute the carry directional bias for *state.pair*.

        Reads ``state.carry_rates`` (a ``dict[str, float]`` of annualised
        central-bank rates per currency).  If the attribute is missing,
        falls back to an empty dict which causes ``is_valid=False``.
        """
        rates: dict[str, float] = (
            getattr(state, "carry_rates", {}) or config.trading.carry_rates
        )
        return get_carry_bias(
            pair=state.pair,
            rates=rates,
            min_differential=config.trading.carry_min_differential_pct,
        )

    # ------------------------------------------------------------------
    # Conflict check helper (public for tests)
    # ------------------------------------------------------------------
    @staticmethod
    def is_carry_conflict(
        momentum_result: dict[str, Any],
        carry: CarrySignal,
    ) -> bool:
        """Return True when carry direction contradicts momentum direction."""
        return _is_carry_conflict(momentum_result, carry)
