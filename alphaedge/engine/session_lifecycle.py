# ============================================================
# PROJECT      : ALPHAEDGE — Swing Trading Bot
# FILE         : alphaedge/engine/session_lifecycle.py
# DESCRIPTION  : Session loop, order execution, and IB reconnect logic
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-25
# ============================================================
"""
Session lifecycle management for the Swing strategy.

Extracts the session loop, order execution, reconnection, and
state-persistence responsibilities from SwingStrategy so that
SwingStrategy becomes a thin orchestrator.
"""

from __future__ import annotations

import asyncio
import os
import time
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from alphaedge.config.constants import (
    DEFAULT_PIP_SIZE,
    IB_FILL_TIMEOUT_SECONDS,
    MAX_BAR_STALENESS_SECONDS,
    PIP_SIZES,
    RISK_CHECK_INTERVAL_IDLE,
    RISK_CHECK_INTERVAL_POSITION,
)
from alphaedge.config.loader import load_carry_rates_from_file
from alphaedge.engine.broker_reconciler import (
    RECONCILE_INTERVAL_SECONDS,
    BrokerReconciler,
)
from alphaedge.engine.live_journal import append_live_trade_csv
from alphaedge.engine.live_types import LiveTradeRecord
from alphaedge.engine.momentum_window import slice_momentum_window
from alphaedge.engine.usd_exposure import would_amplify_usd_exposure
from alphaedge.utils.alerting import (
    Alert,
    AlertEvent,
    AlertLevel,
    alert_daily_summary,
    alert_ib_disconnected,
    alert_ib_reconnected,
    alert_kill_switch,
    alert_session_end_clean,
    alert_session_end_open,
    alert_signal_detected,
    alert_trade_closed,
    alert_trade_executed,
)
from alphaedge.utils.gw_manager import ensure_gateway_ready
from alphaedge.utils.logger import get_logger
from alphaedge.utils.pair_correlation import (
    build_correlation_matrix,
    check_signal_allowed,
)
from alphaedge.utils.state_persistence import (
    DailyState,
    load_daily_state,
    save_daily_state,
)
from alphaedge.utils.timezone import (
    format_dual_time,
    get_session_window_utc,
    is_dst_transition_week,
    is_session_active,
    now_utc,
)
from alphaedge.utils.volatility_regime import check_volatility_regime

if TYPE_CHECKING:
    # NOTE: import cycle with strategy.py mitigated by TYPE_CHECKING
    from alphaedge.engine.strategy import StrategyState, SwingStrategy

logger = get_logger()


def _is_usd_filter_enabled(value: Any) -> bool:
    """Return True only for explicit boolean true config values."""
    return isinstance(value, bool) and value


def _should_log_loss_streak_warning(
    consecutive_losses: int,
    loss_streak_pnl_usd: float,
    daily_loss_limit_usd: float,
) -> bool:
    """Return True when the configured warning condition is met."""
    if daily_loss_limit_usd <= 0.0:
        return False
    return consecutive_losses > 7 and loss_streak_pnl_usd < -(
        daily_loss_limit_usd * 0.5
    )


class SessionLifecycle:
    """
    Manages the Swing strategy session loop, trade execution, and IB reconnection.

    Receives a reference to the parent ``SwingStrategy`` and accesses its
    dependencies (broker, executor, feeds, states, modules) via ``self._s``.
    """

    def __init__(self, strategy: SwingStrategy) -> None:
        self._s = strategy
        self._reconciler = BrokerReconciler(self._s._executor)
        self._session_starting_equity: float = 0.0
        self._reconcile_counter: int = 0
        # Set to True just before broker.disconnect() in the normal session-end
        # flow, so _on_ib_disconnect can distinguish an expected closure from a
        # real mid-session network failure.
        self._session_closing: bool = False
        # Pairs that passed the regime gate for the current session.
        # Used by _handle_reconnection to avoid re-subscribing filtered-out pairs.
        self._active_pairs: list[str] = []
        # Last reconcile snapshot — exposed to web dashboard via get_live_state()
        self._last_reconcile_utc: str = ""
        self._last_reconcile_drift_usd: float = 0.0
        self._last_reconcile_has_critical: bool = False

    # ------------------------------------------------------------------
    # Graceful shutdown
    # ------------------------------------------------------------------
    async def graceful_shutdown(self) -> None:
        """Initiate graceful shutdown (called by signal handler)."""
        logger.warning("ALPHAEDGE: Graceful shutdown initiated (signal received)")
        self._s._shutdown_requested = True
        self._persist_daily_state()

    # ------------------------------------------------------------------
    # Trade execution — helpers
    # ------------------------------------------------------------------
    def _prepare_bracket(
        self,
        signal: dict[str, Any],
        lot_size: float,
        pip_size: float,
        spread_pips: float,
    ) -> dict[str, Any] | None:
        """Validate bracket order, apply slippage buffer, and compute units."""
        bracket = self._s._build_validated_order(
            signal,
            lot_size,
            pip_size,
            spread_pips,
        )
        if bracket is None:
            return None

        # Cast to mutable dict for slippage/units augmentation
        bracket_dict: dict[str, Any] = dict(bracket)

        risk_mod = self._s._modules.risk_manager
        bracket_dict["stop_loss"] = risk_mod.apply_slippage_buffer(
            stop_loss=bracket_dict["stop_loss"],
            direction=bracket_dict["direction"],
            slippage_pips=self._s._config.trading.slippage_buffer_pips,
            pip_size=pip_size,
        )

        order_mod = self._s._modules.order_manager
        bracket_dict["units"] = order_mod.lots_to_units(
            bracket_dict["lot_size"],
            self._s._config.trading.lot_type,
        )
        return bracket_dict

    async def _submit_and_await_fill(
        self,
        state: StrategyState,
        bracket: dict[str, Any],
    ) -> tuple[list, str] | None:
        """Place bracket order and poll IB for parent fill confirmation.

        Returns (trades_placed, fill_status) where fill_status is "full" or
        "partial", or None if the order was rejected / timed out.
        Polls orderStatus every 0.3 s up to IB_FILL_TIMEOUT_SECONDS.
        """
        trades_placed = await self._s._executor.place_bracket_order(
            pair=state.pair,
            direction=bracket["direction"],
            quantity=bracket["units"],
            entry_price=bracket["entry_price"],
            stop_loss=bracket["stop_loss"],
            take_profit=bracket["take_profit"],
        )
        if not trades_placed:
            logger.error("ALPHAEDGE: Bracket order returned empty — {}", state.pair)
            return None

        parent_trade = trades_placed[0]
        loop = asyncio.get_event_loop()
        deadline = loop.time() + IB_FILL_TIMEOUT_SECONDS
        # Yield once so other coroutines can observe _executing_pairs before we
        # monopolise the event loop through a synchronous-looking fast fill.
        await asyncio.sleep(0)

        while loop.time() < deadline:
            order_status = getattr(parent_trade, "orderStatus", None)
            status: str = getattr(order_status, "status", "") if order_status else ""

            if status == "Filled":
                remaining = float(getattr(order_status, "remaining", 0.0))
                if remaining > 0:
                    logger.critical(
                        "ALPHAEDGE: Partial fill — {} — remaining={} units"
                        " — cancelling all legs (Option A)",
                        state.pair,
                        remaining,
                    )
                    asyncio.ensure_future(
                        self._s._alert_manager.send_async(
                            Alert(
                                event=AlertEvent.TRADE_EXECUTED,
                                level=AlertLevel.CRITICAL,
                                title=f"⚠️ Partial fill — {state.pair} — CANCELLED",
                                message=(
                                    "Parent order partially filled "
                                    f"(remaining={remaining}). "
                                    "All legs cancelled. No open position."
                                ),
                            )
                        )
                    ).add_done_callback(self._on_task_done)
                    await self._s._executor.cancel_all_orders()
                    return None
                return (trades_placed, "full")

            if status in ("Cancelled", "Inactive", "ApiCancelled"):
                logger.critical(
                    "ALPHAEDGE: Parent order {} — {} — no position opened",
                    status,
                    state.pair,
                )
                asyncio.ensure_future(
                    self._s._alert_manager.send_async(
                        Alert(
                            event=AlertEvent.TRADE_EXECUTED,
                            level=AlertLevel.CRITICAL,
                            title=f"❌ Order {status} — {state.pair} — NO POSITION",
                            message=(
                                f"Bracket order {status} by IB. No position opened."
                            ),
                        )
                    )
                ).add_done_callback(self._on_task_done)
                await self._s._executor.cancel_all_orders()
                return None

            await asyncio.sleep(0.3)

        # Timeout — IB did not confirm fill within the deadline
        logger.error(
            "ALPHAEDGE: Fill timeout ({}s) — {} — cancelling bracket",
            IB_FILL_TIMEOUT_SECONDS,
            state.pair,
        )
        asyncio.ensure_future(
            self._s._alert_manager.send_async(
                Alert(
                    event=AlertEvent.TRADE_EXECUTED,
                    level=AlertLevel.WARNING,
                    title=f"⏱️ Fill timeout — {state.pair} — NO POSITION OPENED",
                    message=(
                        f"Order not filled within {IB_FILL_TIMEOUT_SECONDS}s."
                        " Bracket cancelled. No open position."
                    ),
                )
            )
        ).add_done_callback(self._on_task_done)
        await self._s._executor.cancel_all_orders()
        return None

    def _record_fill(
        self,
        state: StrategyState,
        trades_placed: list,
        bracket: dict[str, Any],
        signal: dict[str, Any],
        spread_pips: float,
        pip_size: float,
        exchange_rate: float,
        fill_status: str,
    ) -> None:
        """Register fill callbacks and update in-memory position state."""
        entry_time = now_utc()
        parent = trades_placed[0]
        raw_fill = getattr(getattr(parent, "orderStatus", None), "avgFillPrice", None)
        fill_price = float(raw_fill) if raw_fill else bracket["entry_price"]
        slippage = abs(fill_price - bracket["entry_price"]) / pip_size

        # P0-02: log a warning if fill deviated beyond the configured threshold
        max_slip = self._s._config.trading.max_entry_slippage_pips
        if slippage > max_slip:
            logger.warning(
                "ALPHAEDGE: High entry slippage — pair={} fill={} expected={}"
                " slip={:.1f} pips (max={:.1f})",
                state.pair,
                fill_price,
                bracket["entry_price"],
                slippage,
                max_slip,
            )

        state.live_record = LiveTradeRecord(
            pair=state.pair,
            direction=bracket["direction"],
            entry_price=bracket["entry_price"],
            fill_price=fill_price,
            stop_loss=bracket["stop_loss"],
            take_profit=bracket["take_profit"],
            lot_size=bracket["units"],
            sl_pips=signal["risk_pips"],
            spread_pips=spread_pips,
            exchange_rate=exchange_rate,
            entry_time=entry_time,
            slippage_pips=slippage,
            adx_at_entry=float(signal.get("adx", 0.0)),
            strength_at_entry=float(signal.get("strength", 0.0)),
            fill_status=fill_status,
        )
        logger.info(
            "TRADE_ENTRY | pair={} | dir={} | entry={} | fill={} | sl={} | tp={}"
            " | lots={} | sl_pips={:.1f} | spread={:.1f} | slip={:.2f}",
            state.pair,
            "LONG" if bracket["direction"] == 1 else "SHORT",
            bracket["entry_price"],
            fill_price,
            bracket["stop_loss"],
            bracket["take_profit"],
            bracket["units"],
            signal["risk_pips"],
            spread_pips,
            slippage,
        )

        # Only TP/SL child fills represent position closure events.
        for trade_obj in trades_placed[1:]:
            trade_obj.filledEvent += lambda _t, _pair=state.pair: self._on_trade_closed(
                _pair, _t
            )

        # Store bracket child order IDs to identify SL vs TP at close
        if len(trades_placed) >= 3:
            tp_order = getattr(trades_placed[1], "order", None)
            sl_order = getattr(trades_placed[2], "order", None)
            state._tp_order_id = int(getattr(tp_order, "orderId", 0))
            state._sl_order_id = int(getattr(sl_order, "orderId", 0))

        state.trades_today += 1
        self._s._global_trades_today += 1
        state.is_position_open = True
        # B-01-C: call synchronously so state is persisted before any
        # concurrent async path can overwrite it with a stale snapshot.
        self._persist_daily_state()

    # ------------------------------------------------------------------
    # Trade execution — orchestrator
    # ------------------------------------------------------------------
    async def _execute_signal(
        self,
        state: StrategyState,
        signal: dict[str, Any],
        pip_size: float,
        *,
        spread_pips: float | None = None,
    ) -> bool:
        """Execute a trade signal through IB Gateway."""
        try:
            # Fetch live rate for non-USD-quoted pairs (JPY)
            _t0 = time.perf_counter_ns()
            exchange_rate = 0.0
            if pip_size >= 0.001:
                mid = await self._s._rt_feed.get_mid_price(state.pair)
                if mid is None:
                    logger.error(
                        f"ALPHAEDGE: Cannot get mid price for {state.pair} "
                        f"— signal SKIPPED"
                    )
                    return False
                exchange_rate = mid

            pos_result = self._s._size_position(
                state,
                signal,
                pip_size,
                exchange_rate,
                current_atr_pips=state.current_atr_pips,
            )
            if pos_result is None:
                return False

            if spread_pips is None:
                spread = await self._s._rt_feed.get_live_spread(state.pair)
                _t_spread_end = time.perf_counter_ns()
                if spread is None:
                    logger.error(
                        "ALPHAEDGE: Cannot verify spread for "
                        f"{state.pair} — signal SKIPPED"
                    )
                    return False
                spread_pips = spread / pip_size
            else:
                _t_spread_end = time.perf_counter_ns()

            bracket = self._prepare_bracket(
                signal,
                pos_result["lot_size"],
                pip_size,
                spread_pips,
            )
            if bracket is None:
                return False

            _t_order = time.perf_counter_ns()
            asyncio.ensure_future(
                self._s._alert_manager.send_async(
                    alert_signal_detected(
                        pair=state.pair,
                        direction="LONG" if signal.get("direction") == 1 else "SHORT",
                    )
                )
            ).add_done_callback(self._on_task_done)
            trades_placed = await self._submit_and_await_fill(state, bracket)
            if trades_placed is None:
                return False
            ib_trades, fill_status = trades_placed

            self._record_fill(
                state,
                ib_trades,
                bracket,
                signal,
                spread_pips,
                pip_size,
                exchange_rate,
                fill_status,
            )
            asyncio.ensure_future(
                self._s._alert_manager.send_async(
                    alert_trade_executed(
                        pair=state.pair,
                        direction="LONG" if bracket["direction"] == 1 else "SHORT",
                        entry_price=bracket["entry_price"],
                        stop_loss=bracket["stop_loss"],
                        take_profit=bracket["take_profit"],
                        lot_size=float(bracket["units"]),
                    )
                )
            ).add_done_callback(self._on_task_done)
            logger.debug(
                "LATENCE spread={:.1f}ms order_submit={:.1f}ms total={:.1f}ms — {}",
                (_t_spread_end - _t0) / 1e6,
                (_t_order - _t_spread_end) / 1e6,
                (_t_order - _t0) / 1e6,
                state.pair,
            )
            return True
        except Exception:
            logger.exception(f"ALPHAEDGE _execute_signal failed: {state.pair}")
            return False

    def _on_trade_closed(self, pair: str, ib_trade: Any = None) -> None:
        """Reset position flag when a bracket child (SL/TP) fills."""

        async def _reset_position() -> None:
            async with self._s._trade_lock:
                state = self._s._states.get(pair)
                if state:
                    filled_id = getattr(
                        getattr(ib_trade, "order", None), "orderId", None
                    )
                    close_ids = {
                        int(v)
                        for v in (state._tp_order_id, state._sl_order_id)
                        if isinstance(v, int) and v > 0
                    }
                    if (
                        filled_id is not None
                        and close_ids
                        and int(filled_id) not in close_ids
                    ):
                        logger.debug(
                            "ALPHAEDGE: Ignoring non-closing fill event "
                            "for {} (orderId={})",
                            pair,
                            filled_id,
                        )
                        return

                    state.is_position_open = False
                    logger.info(f"ALPHAEDGE: Position closed for {pair}")

                    record = state.live_record
                    if record is not None:
                        exit_time = now_utc()
                        pip_size = PIP_SIZES.get(pair, DEFAULT_PIP_SIZE)

                        raw_exit = None
                        if ib_trade is not None:
                            raw_exit = getattr(
                                getattr(ib_trade, "orderStatus", None),
                                "avgFillPrice",
                                None,
                            )
                            # Fallback: last fill execution average price
                            if not raw_exit:
                                fills = getattr(ib_trade, "fills", None)
                                if fills:
                                    raw_exit = getattr(
                                        getattr(fills[-1], "execution", None),
                                        "avgPrice",
                                        None,
                                    )
                        exit_price = float(raw_exit) if raw_exit else 0.0

                        pnl_pips = (
                            (exit_price - record.entry_price)
                            * record.direction
                            / pip_size
                            if exit_price
                            else 0.0
                        )
                        raw_pnl = pnl_pips * pip_size * record.lot_size * 100_000
                        pnl_usd = (
                            raw_pnl / record.exchange_rate
                            if record.exchange_rate > 0.0
                            else raw_pnl
                        )

                        record.exit_price = exit_price
                        record.exit_time = exit_time
                        record.pnl_pips = round(pnl_pips, 2)
                        record.pnl_usd = round(pnl_usd, 2)
                        if not exit_price:
                            record.outcome = "unknown"
                        elif pnl_pips > 0:
                            record.outcome = "win"
                            state.wins_today += 1
                            state.consecutive_losses_count = 0
                            state.loss_streak_pnl_usd = 0.0
                        elif pnl_pips == 0.0:
                            record.outcome = "breakeven"
                            state.consecutive_losses_count = 0
                            state.loss_streak_pnl_usd = 0.0
                        else:
                            record.outcome = "loss"
                            state.losses_today += 1
                            state.consecutive_losses_count += 1
                            state.loss_streak_pnl_usd += record.pnl_usd

                            equity_base = (
                                state.current_equity
                                if state.current_equity > 0.0
                                else state.starting_equity
                            )
                            daily_loss_limit_usd = (
                                equity_base
                                * self._s._config.trading.max_daily_loss_pct
                                / 100.0
                            )
                            if _should_log_loss_streak_warning(
                                state.consecutive_losses_count,
                                state.loss_streak_pnl_usd,
                                daily_loss_limit_usd,
                            ):
                                warning_threshold = -(daily_loss_limit_usd * 0.5)
                                logger.warning(
                                    "ALPHAEDGE LOSS STREAK WARNING | ts={} | "
                                    "pair={} | consecutive_losses={} | "
                                    "loss_streak_pnl={:+.2f} USD | "
                                    "threshold={:+.2f} USD | Recovery: "
                                    "continue trading per protocol; no manual "
                                    "override unless daily limit is breached.",
                                    exit_time.isoformat(),
                                    pair,
                                    state.consecutive_losses_count,
                                    state.loss_streak_pnl_usd,
                                    warning_threshold,
                                )
                        state.pnl_usd_today += record.pnl_usd

                        # Determine exit reason from bracket child order ID.
                        # Cast filled_id to int — ib_insync may return an IB
                        # OrderId type that does not compare equal to a plain int.
                        filled_id_int = (
                            int(filled_id) if filled_id is not None else None
                        )
                        if filled_id_int is not None and (
                            state._tp_order_id or state._sl_order_id
                        ):
                            if (
                                state._tp_order_id > 0
                                and filled_id_int == state._tp_order_id
                            ):
                                record.exit_reason = "tp_hit"
                            elif (
                                state._sl_order_id > 0
                                and filled_id_int == state._sl_order_id
                            ):
                                record.exit_reason = "sl_hit"
                            else:
                                record.exit_reason = "unknown"
                        else:
                            record.exit_reason = "unknown"

                        # duration_s and pnl_eur before persisting
                        record.duration_s = (
                            (exit_time - record.entry_time).total_seconds()
                            if record.entry_time
                            else 0.0
                        )
                        _eur_usd = self._s._config.trading.eur_usd_rate
                        record.pnl_eur = (
                            round(record.pnl_usd / _eur_usd, 2)
                            if _eur_usd > 0.0
                            else record.pnl_usd
                        )

                        append_live_trade_csv(record)

                        logger.info(
                            "TRADE_CLOSE | pair={} | exit={} | pnl_pips={:+.1f}"
                            " | pnl_usd={:+.2f} | outcome={} | duration={:.0f}s",
                            pair,
                            exit_price,
                            record.pnl_pips,
                            record.pnl_usd,
                            record.outcome,
                            record.duration_s,
                        )
                        asyncio.ensure_future(
                            self._s._alert_manager.send_async(
                                alert_trade_closed(
                                    pair=pair,
                                    direction="LONG"
                                    if record.direction == 1
                                    else "SHORT",
                                    pnl_pips=record.pnl_pips,
                                    pnl_usd=record.pnl_usd,
                                    outcome=record.outcome,
                                )
                            )
                        ).add_done_callback(self._on_task_done)
                        state.live_record = None

                    # Persist state so open_pairs reflects the closed position
                    self._persist_daily_state()

        task = asyncio.ensure_future(_reset_position())
        task.add_done_callback(self._on_task_done)

    # ------------------------------------------------------------------
    # IB Disconnection Recovery
    # ------------------------------------------------------------------
    def _on_ib_disconnect(self) -> None:
        """Handle IB Gateway disconnection event."""
        # Log known open positions — gives operator visibility during reconnect
        open_pairs = [p for p, s in self._s._states.items() if s.is_position_open]
        if self._session_closing:
            # Expected closure triggered by the normal session-end flow.
            # Downgrade to DEBUG — this is not an incident.
            logger.debug(
                "ALPHAEDGE: IB Gateway disconnected (normal session close) "
                "— known open positions: {}",
                open_pairs if open_pairs else "none",
            )
            return
        logger.critical(
            "ALPHAEDGE: IB Gateway DISCONNECTED — known open positions: {}",
            open_pairs if open_pairs else "none",
        )
        asyncio.ensure_future(
            self._s._alert_manager.send_async(alert_ib_disconnected())
        ).add_done_callback(self._on_task_done)
        if self._s._reconnecting:
            return
        self._s._reconnecting = True
        task = asyncio.ensure_future(self._handle_reconnection())
        task.add_done_callback(self._on_task_done)

    async def _handle_reconnection(self) -> None:
        """Attempt reconnection and reconcile state if successful."""
        try:
            # Verify gateway process/API are alive before reconnecting
            gw_ok = await ensure_gateway_ready(self._s._config.ib)
            if not gw_ok:
                logger.critical(
                    "ALPHAEDGE: IB Gateway unreachable — aborting reconnect, "
                    "shutting down"
                )
                self._s._shutdown_requested = True
                return

            success = await self._s._broker.reconnect(max_retries=3)
            if success:
                logger.info("ALPHAEDGE: Reconnected to IB Gateway")
                await self._run_reconcile(self._session_starting_equity)
                # Re-subscribe only to pairs that passed the regime gate this session.
                # _active_pairs is populated by run_session — empty list means session
                # not yet started or already ended (no re-subscribe needed).
                for pair in self._active_pairs:
                    await self._s._rt_feed.subscribe(pair)
                logger.info("ALPHAEDGE: Real-time feeds re-subscribed after reconnect")
                # Restart heartbeat — _reset_ib_client() replaced the IB instance,
                # so the previous heartbeat task is orphaned on the old client.
                self._s._broker.start_heartbeat()
                asyncio.ensure_future(
                    self._s._alert_manager.send_async(alert_ib_reconnected())
                ).add_done_callback(self._on_task_done)
            else:
                # Last-resort orphan check if a partial reconnect occurred
                try:
                    await self._run_reconcile(self._session_starting_equity)
                except Exception:
                    logger.exception("ALPHAEDGE: Post-reconnect reconciliation failed")
                logger.critical(
                    "ALPHAEDGE: Reconnection FAILED after all retries — shutting down"
                )
                asyncio.ensure_future(
                    self._s._alert_manager.send_async(
                        Alert(
                            event=AlertEvent.IB_DISCONNECTED,
                            level=AlertLevel.CRITICAL,
                            title="IB Gateway Reconnection FAILED",
                            message=(
                                "Reconnection failed after all retries"
                                " \u2014 manual intervention required."
                            ),
                        )
                    )
                ).add_done_callback(self._on_task_done)
                self._s._shutdown_requested = True
        finally:
            self._s._reconnecting = False

    async def _run_reconcile(self, starting_equity: float = 0.0) -> None:
        """Run BrokerReconciler and dispatch alerts from the report."""
        report = await self._reconciler.reconcile(
            self._s._states,
            traded_pairs=set(self._s._config.trading.pairs),
            starting_equity=starting_equity,
        )
        # Update dashboard snapshot
        self._last_reconcile_utc = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._last_reconcile_drift_usd = report.pnl_drift_usd
        self._last_reconcile_has_critical = report.has_critical
        for pair in report.pairs_corrected:
            asyncio.ensure_future(
                self._s._alert_manager.send_async(
                    Alert(
                        event=AlertEvent.TRADE_EXECUTED,
                        level=AlertLevel.WARNING,
                        title=f"⚠️ Position discordance — {pair}",
                        message=(
                            f"State corrected after reconcile: "
                            f"is_position_open updated for {pair}. "
                            "Review open positions manually."
                        ),
                    )
                )
            ).add_done_callback(self._on_task_done)
        for pair in report.orphan_pairs:
            asyncio.ensure_future(
                self._s._alert_manager.send_async(
                    Alert(
                        event=AlertEvent.IB_DISCONNECTED,
                        level=AlertLevel.CRITICAL,
                        title=f"🚨 Orphan position — {pair}",
                        message=(
                            f"IB has an open position on {pair} "
                            "not tracked by the bot. Manual review required."
                        ),
                    )
                )
            ).add_done_callback(self._on_task_done)

    @staticmethod
    def _on_task_done(task: asyncio.Task[Any]) -> None:
        """Log unhandled exceptions from fire-and-forget tasks."""
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error("ALPHAEDGE async task failed", exc_info=exc)

    # ------------------------------------------------------------------
    # Real-time M1 bar handler
    # ------------------------------------------------------------------
    def _on_new_m1_bar(self, pair: str, candle: dict[str, Any]) -> None:
        """Handle incoming real-time M1 bar data."""
        if self._s._shutdown_requested:
            return
        # B-01-B: drop bar events while reconnection is in progress to avoid
        # accessing partially-reinitialised pair state (feeds re-subscribed
        # but state dict not yet fully reset).
        if self._s._reconnecting:
            return

        state = self._s._states.get(pair)
        if state is None:
            return

        _bar_dt = candle.get("datetime")
        if _bar_dt is not None:
            bar_age_s = (now_utc() - _bar_dt).total_seconds()
            if bar_age_s > MAX_BAR_STALENESS_SECONDS:
                logger.warning(
                    "ALPHAEDGE STALE BAR: {} \u2014 age={:.0f}s \u2014 skipping",
                    pair,
                    bar_age_s,
                )
                return

        pip_size = PIP_SIZES.get(pair, DEFAULT_PIP_SIZE)

        # Skip if global trade limit reached across all pairs
        if (
            self._s._global_trades_today
            >= self._s._config.trading.max_trades_per_session
        ):
            logger.debug(
                "ALPHAEDGE: Max trades/session reached ({}) — skipping {}",
                self._s._global_trades_today,
                pair,
            )
            return

        # Monitor spread spike while position is open
        if state.is_position_open:
            spread_task = asyncio.ensure_future(self._monitor_spread_spike(pair))
            spread_task.add_done_callback(self._on_task_done)
            return

        # News blackout check
        if self._s._news_filter.is_news_blackout(now_utc(), pair):
            return

        usd_filter_enabled = _is_usd_filter_enabled(
            getattr(self._s._config.trading, "usd_correlation_filter", False)
        )
        if (
            usd_filter_enabled
            and state.signal_result
            and state.signal_result.get("detected")
        ):
            incoming_direction = int(state.signal_result.get("direction") or 0)
            open_positions: list[tuple[str, int]] = []
            for open_pair, open_state in self._s._states.items():
                if not open_state.is_position_open:
                    continue
                record = open_state.live_record
                if record is None:
                    continue
                open_positions.append((open_pair, int(record.direction)))

            if would_amplify_usd_exposure(open_positions, pair, incoming_direction):
                logger.info(
                    "ALPHAEDGE USD FILTER: %s signal blocked — same-direction "
                    "USD amplification",
                    pair,
                )
                return
        elif self._s._correlation_matrix:
            # Pairwise matrix fallback (used when usd_correlation_filter is disabled).
            open_for_corr = [
                p for p, s in self._s._states.items() if s.is_position_open
            ]
            corr_result = check_signal_allowed(
                pair, open_for_corr, self._s._correlation_matrix
            )
            if not corr_result.allowed:
                logger.info(
                    f"ALPHAEDGE CORRELATION: {pair} signal blocked "
                    f"— {corr_result.reason}"
                )
                return

        # Per-pair risk cap: quick pre-check (without lock).
        # B-01-A: include _executing_pairs so a pair already reserved by
        # _atomic_check_and_execute (lock released, awaiting spread/fill)
        # is visible here and prevents scheduling a redundant task.
        open_pairs = [
            p for p, s in self._s._states.items() if s.is_position_open
        ] + list(self._s._executing_pairs)
        risk_mod = self._s._modules.risk_manager
        pair_check: dict[str, Any] = risk_mod.check_pair_limit(
            pair=pair,
            open_pairs=open_pairs,
            max_open_pairs=1,
        )
        if not pair_check["allowed"]:
            return

        # Gate: momentum signal must be active (confirmed at session start).
        if not state.signal_result or not state.signal_result.get("detected"):
            return

        direction: int = int(state.signal_result.get("direction") or 0)
        if direction == 0:
            return

        signal: dict[str, Any] = {
            "detected": True,
            "direction": direction,
            "entry_price": 0.0,
            "stop_loss": 0.0,
            "take_profit": 0.0,
            "risk_pips": 0.0,
            "strength": state.signal_result.get("strength", 0.0),
            "adx": state.signal_result.get("adx", 0.0),
        }
        logger.info(
            f"ALPHAEDGE SIGNAL: {pair} "
            f"{'SELL' if direction == -1 else 'BUY'} "
            f"(adx={signal['adx']:.1f})"
        )
        # Schedule atomic check + execution (re-checks under lock)
        exec_task: asyncio.Task[Any] = asyncio.ensure_future(
            self._atomic_check_and_execute(state, signal, pip_size)
        )
        exec_task.add_done_callback(self._on_task_done)

    async def _atomic_check_and_execute(
        self,
        state: StrategyState,
        signal: dict[str, Any],
        pip_size: float,
    ) -> bool:
        """Re-check pair/trade limits under lock, then execute."""
        async with self._s._trade_lock:
            # Guard against re-entrant execution for the same pair
            if state.pair in self._s._executing_pairs:
                return False
            # Virtual open_pairs: confirmed positions + currently executing
            open_pairs = [
                p for p, s in self._s._states.items() if s.is_position_open
            ] + list(self._s._executing_pairs)
            risk_mod = self._s._modules.risk_manager
            pair_check: dict[str, Any] = risk_mod.check_pair_limit(
                pair=state.pair,
                open_pairs=open_pairs,
                max_open_pairs=1,
            )
            if not pair_check["allowed"]:
                logger.info(
                    f"ALPHAEDGE LOCK: {state.pair} signal rejected — "
                    f"pair limit reached (re-check under lock)"
                )
                return False
            # Re-verify global trade count under lock
            if (
                self._s._global_trades_today
                >= self._s._config.trading.max_trades_per_session
            ):
                return False
            # Reserve this pair atomically before releasing lock
            self._s._executing_pairs.add(state.pair)
        # Lock released — long awaits happen outside the lock
        try:
            return await self._check_spread_and_execute(state, signal, pip_size)
        finally:
            self._s._executing_pairs.discard(state.pair)

    async def _check_spread_and_execute(
        self,
        state: StrategyState,
        signal: dict[str, Any],
        pip_size: float,
    ) -> bool:
        """Check spread is acceptable, then execute the signal."""
        try:
            spread = await self._s._rt_feed.get_live_spread(state.pair)
            if spread is None:
                logger.error(
                    f"ALPHAEDGE: Cannot verify spread for {state.pair} — signal SKIPPED"
                )
                return False
            spread_pips = spread / pip_size
            if spread_pips > self._s._config.trading.max_spread_pips:
                logger.info(
                    f"ALPHAEDGE SPREAD: {state.pair} spread={spread_pips:.1f} "
                    f"pips > max={self._s._config.trading.max_spread_pips} — "
                    f"signal skipped"
                )
                return False
            return await self._execute_signal(
                state, signal, pip_size, spread_pips=spread_pips
            )
        except Exception:
            logger.exception(
                f"ALPHAEDGE _check_spread_and_execute failed: {state.pair}"
            )
            return False

    async def _monitor_spread_spike(self, pair: str) -> None:
        """Log WARNING if spread spikes beyond the configured multiplier."""
        try:
            pip_size = PIP_SIZES.get(pair, DEFAULT_PIP_SIZE)
            spread = await self._s._rt_feed.get_live_spread(pair)
            if spread is None:
                return  # Cannot monitor — skip silently
            spread_pips = spread / pip_size
            threshold = (
                self._s._config.trading.max_spread_pips
                * self._s._config.trading.spread_spike_multiplier
            )
            if spread_pips > threshold:
                logger.warning(
                    f"ALPHAEDGE SPREAD SPIKE: {pair} spread={spread_pips:.1f} "
                    f"pips > {threshold:.1f} pips "
                    f"({self._s._config.trading.spread_spike_multiplier}× max) "
                    f"— position open"
                )
        except Exception:
            logger.exception(f"ALPHAEDGE _monitor_spread_spike failed: {pair}")

    # ------------------------------------------------------------------
    # Daily loss / session end
    # ------------------------------------------------------------------
    async def _check_daily_loss_shutdown(self) -> None:
        """Check daily loss limit and trigger shutdown if breached."""
        for state in self._s._states.values():
            if state.starting_equity <= 0:
                continue
            try:
                risk_result = await self._s._check_risk(state)
            except Exception:
                logger.exception("ALPHAEDGE daily-loss check failed")
                continue
            if risk_result.get("limit_breached"):
                logger.critical(
                    f"ALPHAEDGE: Daily loss limit breached — "
                    f"PnL {risk_result.get('daily_pnl_pct', 0):.2f}%. "
                    f"Shutting down."
                )
                asyncio.ensure_future(
                    self._s._alert_manager.send_async(
                        alert_kill_switch(
                            reason=str(risk_result.get("reason", "daily_loss_limit")),
                            daily_pnl_pct=float(risk_result.get("daily_pnl_pct", 0.0)),
                        )
                    )
                ).add_done_callback(self._on_task_done)
                self._s._shutdown_requested = True
                await self._s._executor.cancel_all_orders()

                # Persist shutdown state to survive restarts
                self._persist_daily_state(shutdown=True)

                return

    async def _handle_session_end(self) -> None:
        """Check for open positions at session end and handle them."""
        try:
            positions = await self._s._executor.get_open_positions()
            traded_pairs = set(self._s._config.trading.pairs)
            open_count = 0

            for pos in positions:
                contract = pos.contract
                pair_sym = getattr(contract, "pair", getattr(contract, "symbol", ""))
                if pair_sym in traded_pairs and pos.position != 0:
                    open_count += 1
                    logger.warning(
                        f"ALPHAEDGE SESSION END: Open position on "
                        f"{pair_sym} — qty={pos.position}"
                    )
                    asyncio.ensure_future(
                        self._s._alert_manager.send_async(
                            alert_session_end_open(
                                pair=pair_sym,
                                quantity=float(pos.position),
                            )
                        )
                    ).add_done_callback(self._on_task_done)

            if open_count > 0:
                # Journal any live_record for positions still open at session end
                for s_state in self._s._states.values():
                    if s_state.live_record is not None and s_state.is_position_open:
                        rec = s_state.live_record
                        now = now_utc()
                        rec.exit_time = now
                        rec.exit_reason = "session_end"
                        rec.outcome = "open_at_end"
                        rec.duration_s = (
                            (now - rec.entry_time).total_seconds()
                            if rec.entry_time
                            else 0.0
                        )
                        _eur_usd = self._s._config.trading.eur_usd_rate
                        rec.pnl_eur = (
                            round(rec.pnl_usd / _eur_usd, 2)
                            if _eur_usd > 0.0
                            else rec.pnl_usd
                        )
                        append_live_trade_csv(rec)
                        s_state.live_record = None
                        logger.info(
                            "TRADE_JOURNAL: session_end — {} journalised"
                            " (exit_price unknown — bracket remains on IB)",
                            rec.pair,
                        )

                action = self._s._config.trading.session_end_action
                if action == "close":
                    logger.warning(
                        "ALPHAEDGE SESSION END: Closing all positions at market"
                    )
                    await self._s._executor.cancel_all_orders()
                else:
                    logger.warning(
                        f"ALPHAEDGE SESSION END: {open_count} position(s) "
                        f"left open — bracket SL/TP active on IB"
                    )
            else:
                logger.info("ALPHAEDGE SESSION END: No open positions")
                asyncio.ensure_future(
                    self._s._alert_manager.send_async(alert_session_end_clean())
                ).add_done_callback(self._on_task_done)

            # Session summary
            for pair, state in self._s._states.items():
                logger.info(f"ALPHAEDGE SUMMARY: {pair} — trades={state.trades_today}")

            asyncio.ensure_future(
                self._s._alert_manager.send_async(
                    alert_daily_summary(
                        trades=self._s._global_trades_today,
                        wins=sum(s.wins_today for s in self._s._states.values()),
                        losses=sum(s.losses_today for s in self._s._states.values()),
                        pnl_usd=sum(s.pnl_usd_today for s in self._s._states.values()),
                    )
                )
            ).add_done_callback(self._on_task_done)
        except Exception:
            logger.exception("ALPHAEDGE _handle_session_end failed")

    def _has_open_position(self) -> bool:
        """Return True if any pair has an open position."""
        return any(s.is_position_open for s in self._s._states.values())

    def _persist_daily_state(self, *, shutdown: bool = False) -> None:
        """Persist current daily state to disk."""
        total_trades = self._s._global_trades_today
        open_pairs = [p for p, s in self._s._states.items() if s.is_position_open]
        # Use first state's starting_equity (same for all pairs)
        starting_eq = 0.0
        for s in self._s._states.values():
            if s.starting_equity > 0:
                starting_eq = s.starting_equity
                break

        daily = DailyState(
            date=date.today().isoformat(),
            starting_equity=starting_eq,
            trades_today=total_trades,
            shutdown_triggered=shutdown or self._s._shutdown_requested,
            open_pairs=open_pairs,
        )
        save_daily_state(daily)

    # ------------------------------------------------------------------
    # Session pair initialisation
    # ------------------------------------------------------------------
    async def _init_session_pairs(
        self,
        starting_equity: float,
        live_equity: float,
        persisted: DailyState | None,
        session_start: datetime,
    ) -> list[str]:
        """
        Check regime gate and init state for each configured pair.

        Returns the list of active pairs that passed the regime filter.
        Also builds and stores the pairwise correlation matrix.
        """
        active_pairs: list[str] = []
        pair_closes: dict[str, list[float]] = {}
        for pair in self._s._config.trading.pairs:
            pip_size = PIP_SIZES.get(pair, DEFAULT_PIP_SIZE)

            # Fetch daily bars for momentum signal and volatility regime.
            # Use lookback_days × 1.5 calendar days to account for weekends/holidays.
            # Example: 252 trading days × 1.5 ≈ 378 calendar days (~15 months).
            # IB rejects durations > 365 D — must use years instead.
            _lookback = self._s._config.trading.momentum_lookback_days
            _cal_days = int(_lookback * 1.5)
            _duration = (
                f"{(_cal_days + 364) // 365} Y" if _cal_days > 365 else f"{_cal_days} D"
            )
            daily_bars = await self._s._hist_feed.fetch_bars(
                pair=pair,
                timeframe="1 day",
                duration=_duration,
                end_dt=session_start,
            )

            # Use the most recent complete daily bar as current day context
            current_day_bar: dict[str, Any] = daily_bars[-1] if daily_bars else {}

            # Volatility regime gate: skip pair if session is too quiet/violent
            if daily_bars and current_day_bar and self._s._config.regime_gate_enabled:
                regime = check_volatility_regime(daily_bars[:-1], current_day_bar)
                if not regime.allowed:
                    logger.warning(
                        f"ALPHAEDGE REGIME: {pair} session SKIPPED "
                        f"\u2014 {regime.reason}"
                    )
                    continue

            # Init pair state
            state = self._s._init_pair_state(pair)
            state.starting_equity = starting_equity
            state.current_equity = live_equity
            lookback_days = int(
                getattr(self._s._config.trading, "momentum_lookback_days", 0)
            )
            state.daily_bars = slice_momentum_window(
                daily_bars,
                lookback_days,
            )
            state.current_atr_pips = (
                self._s._position_manager.estimate_current_atr_pips(
                    state.daily_bars,
                    pip_size,
                    self._s._config.trading.atr_period,
                )
            )
            if persisted:
                state.trades_today = persisted.trades_today
                self._s._global_trades_today = persisted.trades_today

            # Collect closes from daily bars for correlation matrix
            pair_closes[pair] = [c["close"] for c in daily_bars if "close" in c]

            # Detect momentum signal
            momentum = self._s._detect_momentum(state, pip_size)
            if momentum:
                logger.info(
                    f"ALPHAEDGE MOMENTUM: {pair} "
                    f"direction={momentum.get('direction', 0)} "
                    f"adx={momentum.get('adx', 0.0):.1f}"
                )
            active_pairs.append(pair)

        self._s._correlation_matrix = build_correlation_matrix(pair_closes)
        return active_pairs

    # ------------------------------------------------------------------
    # Pre-session wait
    # ------------------------------------------------------------------
    async def _wait_for_session_open(self) -> None:
        """Block until the NYSE session window opens, logging a countdown."""
        logger.debug("ALPHAEDGE: _wait_for_session_open starting (pid=%d)", os.getpid())
        while not self._s._shutdown_requested:
            now = now_utc()
            # Anchor to UTC noon to avoid the UTC-midnight / NY-prior-evening
            # timezone crossing (NY = UTC-4 EDT / UTC-5 EST):
            # midnight UTC ≈ 20:00 NY prior day → get_session_window_utc()
            # without an anchor returns yesterday's session, triggering a
            # spurious "session ended" branch and skipping today's session.
            utc_noon = now.replace(hour=12, minute=0, second=0, microsecond=0)
            session_start, session_end = get_session_window_utc(utc_noon)

            # Already inside the window — proceed immediately
            if session_start <= now < session_end:
                return

            if now >= session_end:
                # Session ended today — find the next weekday's session start.
                # Use utc_noon as anchor so get_session_window_utc receives a
                # datetime whose NY-converted date matches the UTC calendar date.
                next_candidate = utc_noon + timedelta(days=1)
                while next_candidate.weekday() >= 5:  # 5=Sat, 6=Sun
                    next_candidate += timedelta(days=1)
                next_start, _ = get_session_window_utc(next_candidate)
                wait_h = (next_start - now).total_seconds() / 3600
                # Log at first check and then every ~15 min to avoid flooding
                if now.minute % 15 == 0 or wait_h > 19.9:
                    logger.info(
                        f"ALPHAEDGE: Session ended for today. "
                        f"Next window in {wait_h:.1f}h "
                        f"({format_dual_time(next_start)})"
                    )
                await asyncio.sleep(60.0)
                continue

            # Before today's session_start
            wait_s = (session_start - now).total_seconds()
            if wait_s >= 60:
                logger.info(
                    f"ALPHAEDGE: Session opens in {wait_s / 60:.0f}min "
                    f"({format_dual_time(session_start)})"
                )
                await asyncio.sleep(min(wait_s - 30.0, 60.0))
            else:
                await asyncio.sleep(1.0)

    # ------------------------------------------------------------------
    # Main session loop
    # ------------------------------------------------------------------
    async def run_session(self) -> None:
        """
        Run a single trading session for all configured pairs.

        This is the main entry point for the strategy.
        """
        # Warn when EU and US DST offsets diverge (2nd–last Sunday of March)
        if is_dst_transition_week():
            logger.warning(
                "ALPHAEDGE WARNING: DST transition week detected — EU and US offsets "
                "differ by 1h. NYSE session is at 13:30-14:30 UTC but Paris shows "
                "CET (UTC+1) instead of CEST (UTC+2). Verify signal timing."
            )

        # Check persisted daily state before connecting
        persisted = load_daily_state()
        if persisted and persisted.shutdown_triggered:
            logger.critical(
                "ALPHAEDGE: Daily loss shutdown was triggered earlier "
                "today — refusing to start. Wait for next trading day."
            )
            self._s._shutdown_requested = True
            return

        # Ensure IB Gateway is running early — before waiting for session window.
        # On weekdays this detects a missing gateway immediately (and auto-
        # launches it if gateway_path is configured).  On weekends we skip
        # the early check entirely: the market is closed and IB Gateway must
        # NOT be launched.  _wait_for_session_open handles the Sat/Sun → Mon
        # transition, and the post-wait check below launches the gateway once
        # the next trading day arrives.
        if now_utc().weekday() < 5:  # Mon–Fri only
            if not await ensure_gateway_ready(self._s._config.ib):
                logger.critical(
                    "ALPHAEDGE: Cannot start — IB Gateway "
                    "not reachable after all retries"
                )
                return

        # Wait for the session window to open (do NOT connect to IB yet)
        await self._wait_for_session_open()
        if self._s._shutdown_requested:
            return

        # Post-wait gateway check: covers weekend starts (where the early
        # check was skipped) and confirms the gateway is still alive after
        # a potentially multi-hour wait.
        if not await ensure_gateway_ready(self._s._config.ib):
            logger.critical(
                "ALPHAEDGE: Cannot start — IB Gateway not reachable after all retries"
            )
            return

        # Log here — after _wait_for_session_open — so the message only appears
        # when we are actually inside the trading window, not 60s after session end.
        logger.info(
            f"ALPHAEDGE session starting at {format_dual_time(now_utc())} "
            f"| mode={'PAPER' if self._s._config.ib.is_paper else 'LIVE'}"
        )

        # Connect to IB Gateway
        if not await self._s._broker.connect():
            logger.error("ALPHAEDGE: Cannot start — IB Gateway unavailable")
            return

        # Activate heartbeat — detects silent TCP drops missed by disconnectedEvent
        self._s._broker.start_heartbeat()

        try:
            # Prime margin cache — must run before any order check
            await self._s._broker.refresh_account_funds()

            # Reload carry rates from file if configured (dynamic hot-reload)
            if self._s._config.trading.carry_rates_source == "file":
                try:
                    new_rates = load_carry_rates_from_file()
                    old_rates = self._s._config.trading.carry_rates
                    changed = {
                        k: (old_rates.get(k), v)
                        for k, v in new_rates.items()
                        if old_rates.get(k) != v
                    }
                    self._s._config.trading.carry_rates = new_rates
                    if changed:
                        changes_str = ", ".join(
                            f"{k}: {old:.2f}→{new:.2f}"
                            for k, (old, new) in changed.items()
                            if old is not None
                        )
                        additions_str = ", ".join(
                            f"{k}: +{new:.2f}"
                            for k, (old, new) in changed.items()
                            if old is None
                        )
                        detail = " | ".join(filter(None, [changes_str, additions_str]))
                        logger.warning(
                            "ALPHAEDGE carry rates reloaded from file — changes: %s",
                            detail,
                        )
                    else:
                        logger.info(
                            "ALPHAEDGE carry rates reloaded from file — no changes"
                        )
                except (FileNotFoundError, ValueError):
                    logger.exception(
                        "ALPHAEDGE: Failed to reload carry rates from file "
                        "— using config.yaml rates"
                    )

            # Get starting equity (use persisted value if restarting same day)
            live_equity = await self._s._executor.get_account_equity()
            if persisted and persisted.starting_equity > 0:
                starting_equity = persisted.starting_equity
                logger.info(
                    f"ALPHAEDGE: Restored persisted starting_equity="
                    f"{starting_equity:.2f} "
                    f"(trades_today={persisted.trades_today})"
                )
            else:
                starting_equity = live_equity
            self._session_starting_equity = starting_equity
            session_start, _session_end = get_session_window_utc()

            # Process each pair — regime gate, signal init
            active_pairs = await self._init_session_pairs(
                starting_equity,
                live_equity,
                persisted,
                session_start,
            )

            # Reconcile position state with IB at startup
            await self._run_reconcile(starting_equity)

            # Subscribe to real-time M1 data (only pairs that passed regime gate)
            self._active_pairs = active_pairs
            self._s._rt_feed.on_bar(self._on_new_m1_bar)
            for pair in active_pairs:
                await self._s._rt_feed.subscribe(pair)

            # Wait for session to end, with adaptive risk check interval
            logger.info("ALPHAEDGE: Monitoring session...")
            risk_check_counter = 0
            self._reconcile_counter = 0
            while is_session_active() and not self._s._shutdown_requested:
                await asyncio.sleep(1.0)
                risk_check_counter += 1
                self._reconcile_counter += 1

                # Adaptive interval: 5s with open position, 30s idle
                interval = (
                    RISK_CHECK_INTERVAL_POSITION
                    if self._has_open_position()
                    else RISK_CHECK_INTERVAL_IDLE
                )
                if risk_check_counter >= interval:
                    risk_check_counter = 0
                    await self._s._broker.refresh_account_funds()
                    await self._check_daily_loss_shutdown()

                # Periodic reconciliation every RECONCILE_INTERVAL_SECONDS
                if self._reconcile_counter >= RECONCILE_INTERVAL_SECONDS:
                    self._reconcile_counter = 0
                    await self._run_reconcile(self._session_starting_equity)
        except Exception:
            logger.exception("ALPHAEDGE run_session error")
        finally:
            # Session-end position check before disconnect
            await self._handle_session_end()
            # Cleanup
            await self._s._rt_feed.unsubscribe_all()
            await self._s._broker.stop_heartbeat()
            # Flag the closing BEFORE disconnect so _on_ib_disconnect
            # knows this is an expected shutdown, not a network failure.
            self._session_closing = True
            await self._s._broker.disconnect()
            self._session_closing = False
            logger.info(f"ALPHAEDGE session ended at {format_dual_time(now_utc())}")
