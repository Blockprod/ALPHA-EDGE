# ============================================================
# PROJECT      : ALPHAEDGE — Swing Trading Bot
# FILE         : alphaedge/engine/position_manager.py
# DESCRIPTION  : Stateless position sizing and bracket order building
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — Momentum+Carry Forex Trading Bot: position sizing and order building."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from alphaedge.config.constants import MAX_LOTS, MIN_LOTS
from alphaedge.utils.logger import get_logger

if TYPE_CHECKING:
    # NOTE: import cycle with strategy.py mitigated by TYPE_CHECKING
    from alphaedge.config.loader import AppConfig
    from alphaedge.core.types import BracketOrderResult, PositionSizeResult
    from alphaedge.engine.strategy import CoreModules, StrategyState

logger = get_logger()


def _compute_atr_pips(
    bars: list[dict[str, Any]],
    pip_size: float,
    period: int,
) -> float:
    """Compute ATR(period) in pips from right-aligned daily bars."""
    if pip_size <= 0.0 or period <= 0 or len(bars) < 3:
        return 0.0

    end = len(bars) - 1
    start = max(1, end - period)
    trs: list[float] = []
    for i in range(start, end):
        high = float(bars[i]["high"])
        low = float(bars[i]["low"])
        prev_close = float(bars[i - 1]["close"])
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)

    if not trs:
        return 0.0
    return (sum(trs) / len(trs)) / pip_size


class PositionManager:
    """
    Stateless container for position sizing and bracket order building.

    All state is held in the ``StrategyState`` instance.  Core modules
    and config are passed per call so that ``SwingStrategy`` remains the
    single owner of those dependencies.
    """

    # ------------------------------------------------------------------
    # Position sizing
    # ------------------------------------------------------------------
    def size_position(
        self,
        state: StrategyState,
        modules: CoreModules,
        config: AppConfig,
        signal: dict[str, Any],
        pip_size: float,
        exchange_rate: float = 0.0,
        current_atr_pips: float = 0.0,
    ) -> PositionSizeResult | None:
        """
        Calculate and validate position size.

        Returns ``None`` when the resulting size is not valid (e.g. below
        minimum lot or equity too low).
        """
        equity = state.current_equity or state.starting_equity
        base_risk_pct = config.trading.risk_pct_by_pair.get(
            state.pair,
            config.trading.risk_pct,
        )
        effective_risk_pct = base_risk_pct
        atr_ref = config.trading.atr_ref_pips_by_pair.get(state.pair, 0.0)
        if atr_ref > 0.0 and current_atr_pips > 0.0:
            atr_scale = min(1.0, max(0.5, atr_ref / current_atr_pips))
            effective_risk_pct = base_risk_pct * atr_scale

        max_cap: float = getattr(config.trading, "max_lot_size", MAX_LOTS)
        pos_result: PositionSizeResult = modules.risk_manager.calculate_position_size(
            account_equity=equity,
            risk_pct=effective_risk_pct,
            sl_pips=signal["risk_pips"],
            pair=state.pair,
            pip_size=pip_size,
            lot_type=config.trading.lot_type,
            min_lots=MIN_LOTS,
            max_lots=max_cap,
            exchange_rate=exchange_rate,
        )
        if not pos_result["is_valid"]:
            logger.warning(f"ALPHAEDGE: Invalid position size for {state.pair}")
            return None
        if pos_result["lot_size"] > max_cap:
            logger.warning(
                f"ALPHAEDGE: {state.pair} lot_size {pos_result['lot_size']:.2f} "
                f"capped to max_lot_size={max_cap:.2f}"
            )
            pos_result["lot_size"] = max_cap
        return pos_result

    @staticmethod
    def estimate_current_atr_pips(
        daily_bars: list[dict[str, Any]],
        pip_size: float,
        atr_period: int,
    ) -> float:
        """Estimate current ATR in pips from available daily bars."""
        return _compute_atr_pips(daily_bars, pip_size, atr_period)

    # ------------------------------------------------------------------
    # Bracket order building
    # ------------------------------------------------------------------
    def build_validated_order(
        self,
        signal: dict[str, Any],
        lot_size: float,
        pip_size: float,
        spread_pips: float,
        modules: CoreModules,
        config: AppConfig,
    ) -> BracketOrderResult | None:
        """
        Build a bracket order and validate it.

        Returns ``None`` when the order is rejected (spread too wide,
        R:R too low, lot size out of range, etc.).
        """
        max_cap: float = getattr(config.trading, "max_lot_size", MAX_LOTS)
        bracket: BracketOrderResult = modules.order_manager.create_bracket_order(
            direction=signal["direction"],
            entry_price=signal["entry_price"],
            stop_loss=signal["stop_loss"],
            take_profit=signal["take_profit"],
            lot_size=lot_size,
            pip_size=pip_size,
            spread_pips=spread_pips,
            max_spread_pips=config.trading.max_spread_pips,
            min_rr=config.trading.rr_ratio * 0.9,
            min_lots=MIN_LOTS,
            max_lots=max_cap,
            adjust_for_spread=True,
        )
        if not bracket.get("is_valid", False):
            logger.warning(
                f"ALPHAEDGE: Order rejected — {bracket.get('rejection_reason')}"
            )
            return None
        return bracket
