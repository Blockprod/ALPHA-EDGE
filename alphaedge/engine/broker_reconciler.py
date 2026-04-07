# ============================================================
# PROJECT      : ALPHAEDGE — Swing Trading Bot
# FILE         : alphaedge/engine/broker_reconciler.py
# DESCRIPTION  : BrokerReconciler — sync local state with IB positions
# AUTHOR       : ALPHAEDGE Dev Team
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-04-07
# ============================================================
"""ALPHAEDGE — BrokerReconciler: sync StrategyState with IB live positions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from alphaedge.utils.logger import get_logger

logger = get_logger()

RECONCILE_INTERVAL_SECONDS: int = 300
"""Periodic reconciliation cadence in seconds (default: 5 min)."""


@runtime_checkable
class BrokerExecutorProtocol(Protocol):
    """Minimal interface required by BrokerReconciler from OrderExecutor."""

    async def get_open_positions(self) -> list[Any]: ...
    async def get_open_orders(self) -> list[Any]: ...
    async def get_account_equity(self) -> float: ...


@runtime_checkable
class ReconcilableState(Protocol):
    """Minimal mutable state interface required by BrokerReconciler."""

    is_position_open: bool
    pnl_usd_today: float


@dataclass
class ReconciliationReport:
    """Result of a single broker reconciliation pass."""

    pairs_corrected: list[str] = field(default_factory=list)
    """Pairs whose ``is_position_open`` was corrected to match IB state."""

    orphan_pairs: list[str] = field(default_factory=list)
    """Pairs with an open IB position not tracked by the bot."""

    orphan_order_count: int = 0
    """Open IB orders on tracked pairs that were unexpected."""

    pnl_drift_usd: float = 0.0
    """Absolute difference between local P&L sum and IB daily P&L estimate (USD)."""

    pnl_drift_pct: float = 0.0
    """``pnl_drift_usd / starting_equity * 100``."""

    has_critical: bool = False
    """True when an orphan position is found (requires immediate manual review)."""


class BrokerReconciler:
    """
    Reconciles local StrategyState against live IB positions.

    Responsibilities:
    1. Sync ``is_position_open`` for every tracked pair.
    2. Detect orphan positions (IB holds a position the bot does not know about).
    3. Count orphan orders (open orders on tracked pairs that should not exist).
    4. Detect P&L drift vs IB account equity (optional, requires starting_equity > 0).
    """

    def __init__(self, executor: BrokerExecutorProtocol) -> None:
        self._executor = executor

    async def reconcile(
        self,
        states: Mapping[str, ReconcilableState],
        traded_pairs: set[str] | None = None,
        starting_equity: float = 0.0,
    ) -> ReconciliationReport:
        """
        Run a full reconciliation pass and return a structured report.

        Parameters
        ----------
        states:
            Per-pair StrategyState mapping.  ``is_position_open`` is mutated
            in-place wherever a divergence is detected.
        traded_pairs:
            Set of pair symbols the bot is configured to trade.
            Defaults to the keys of *states*.
        starting_equity:
            Session starting equity.  When > 0, a P&L drift check is
            performed against live IB account equity.  Pass 0.0 to skip.
        """
        if traded_pairs is None:
            traded_pairs = set(states.keys())

        pairs_corrected: list[str] = []
        orphan_pairs: list[str] = []
        orphan_order_count = 0
        pnl_drift_usd = 0.0
        pnl_drift_pct = 0.0

        # ------------------------------------------------------------------
        # Step 1: Position sync
        # ------------------------------------------------------------------
        try:
            positions = await self._executor.get_open_positions()
            ib_open_pairs: set[str] = set()
            for pos in positions:
                contract = pos.contract
                pair_sym: str = getattr(
                    contract, "pair", getattr(contract, "symbol", "")
                )
                if pos.position != 0:
                    if pair_sym in traded_pairs:
                        ib_open_pairs.add(pair_sym)
                        logger.info(
                            "ALPHAEDGE RECONCILE: %s — open position qty=%s",
                            pair_sym,
                            pos.position,
                        )
                    else:
                        orphan_pairs.append(pair_sym)
                        logger.critical(
                            "ALPHAEDGE RECONCILE: Orphan position — %s qty=%s "
                            "(not tracked by bot) — manual review required",
                            pair_sym,
                            pos.position,
                        )

            for pair, state in states.items():
                was_open = state.is_position_open
                state.is_position_open = pair in ib_open_pairs
                if was_open != state.is_position_open:
                    pairs_corrected.append(pair)
                    logger.warning(
                        "ALPHAEDGE RECONCILE: %s position corrected %s → %s",
                        pair,
                        was_open,
                        state.is_position_open,
                    )
        except Exception:
            logger.exception("ALPHAEDGE BrokerReconciler: position sync failed")

        # ------------------------------------------------------------------
        # Step 2: Orphan orders
        # ------------------------------------------------------------------
        try:
            open_orders = await self._executor.get_open_orders()
            for order in open_orders:
                contract = getattr(order, "contract", None)
                if contract is None:
                    continue
                pair_sym = getattr(contract, "pair", getattr(contract, "symbol", ""))
                if pair_sym in traded_pairs:
                    orphan_order_count += 1
                    logger.warning(
                        "ALPHAEDGE RECONCILE: Orphan order — %s "
                        "orderId=%s action=%s type=%s",
                        pair_sym,
                        getattr(order, "orderId", "?"),
                        getattr(order, "action", "?"),
                        getattr(order, "orderType", "?"),
                    )
            if not open_orders:
                logger.info("ALPHAEDGE RECONCILE: No orphan orders")
        except Exception:
            logger.exception("ALPHAEDGE BrokerReconciler: orphan orders check failed")

        # ------------------------------------------------------------------
        # Step 3: P&L drift (optional)
        # ------------------------------------------------------------------
        if starting_equity > 0.0:
            try:
                live_equity = await self._executor.get_account_equity()
                if live_equity > 0.0:
                    ib_pnl = live_equity - starting_equity
                    local_pnl = sum(s.pnl_usd_today for s in states.values())
                    pnl_drift_usd = abs(ib_pnl - local_pnl)
                    pnl_drift_pct = (pnl_drift_usd / starting_equity) * 100.0
                    if pnl_drift_pct > 1.0:
                        logger.warning(
                            "ALPHAEDGE RECONCILE: P&L drift %.2f%% "
                            "(local=%.2f IB_delta=%.2f drift_usd=%.2f)",
                            pnl_drift_pct,
                            local_pnl,
                            ib_pnl,
                            pnl_drift_usd,
                        )
            except Exception:
                logger.exception("ALPHAEDGE BrokerReconciler: P&L drift check failed")

        return ReconciliationReport(
            pairs_corrected=pairs_corrected,
            orphan_pairs=orphan_pairs,
            orphan_order_count=orphan_order_count,
            pnl_drift_usd=pnl_drift_usd,
            pnl_drift_pct=pnl_drift_pct,
            has_critical=len(orphan_pairs) > 0,
        )
