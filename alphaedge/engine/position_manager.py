# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/engine/position_manager.py
# DESCRIPTION  : Stateless position sizing and bracket order building
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: position sizing and order building."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from alphaedge.config.constants import MAX_LOTS, MIN_LOTS
from alphaedge.utils.logger import get_logger

if TYPE_CHECKING:
    from alphaedge.config.loader import AppConfig
    from alphaedge.engine.strategy import CoreModules, StrategyState

logger = get_logger()


class PositionManager:
    """
    Stateless container for position sizing and bracket order building.

    All state is held in the ``StrategyState`` instance.  Core modules
    and config are passed per call so that ``FCRStrategy`` remains the
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
    ) -> dict[str, Any] | None:
        """
        Calculate and validate position size.

        Returns ``None`` when the resulting size is not valid (e.g. below
        minimum lot or equity too low).
        """
        equity = state.current_equity or state.starting_equity
        pos_result: dict[str, Any] = modules.risk_manager.calculate_position_size(
            account_equity=equity,
            risk_pct=config.trading.risk_pct,
            sl_pips=signal["risk_pips"],
            pair=state.pair,
            pip_size=pip_size,
            lot_type=config.trading.lot_type,
            min_lots=MIN_LOTS,
            max_lots=MAX_LOTS,
            exchange_rate=exchange_rate,
        )
        if not pos_result["is_valid"]:
            logger.warning(f"ALPHAEDGE: Invalid position size for {state.pair}")
            return None
        return pos_result

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
    ) -> dict[str, Any] | None:
        """
        Build a bracket order and validate it.

        Returns ``None`` when the order is rejected (spread too wide,
        R:R too low, lot size out of range, etc.).
        """
        bracket: dict[str, Any] = modules.order_manager.create_bracket_order(
            direction=signal["signal"],
            entry_price=signal["entry_price"],
            stop_loss=signal["stop_loss"],
            take_profit=signal["take_profit"],
            lot_size=lot_size,
            pip_size=pip_size,
            spread_pips=spread_pips,
            max_spread_pips=config.trading.max_spread_pips,
            min_rr=config.trading.rr_ratio * 0.9,
            min_lots=MIN_LOTS,
            max_lots=MAX_LOTS,
            adjust_for_spread=True,
        )
        if not bracket.get("is_valid", False):
            logger.warning(
                f"ALPHAEDGE: Order rejected — {bracket.get('rejection_reason')}"
            )
            return None
        return bracket
