# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/engine/session_lifecycle.py
# DESCRIPTION  : Session loop, order execution, and IB reconnect logic
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-09
# ============================================================
"""
Session lifecycle management for the FCR strategy.

Extracts the session loop, order execution, reconnection, and
state-persistence responsibilities from FCRStrategy so that
FCRStrategy becomes a thin orchestrator.
"""

from __future__ import annotations

import asyncio
import time
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from alphaedge.config.constants import (
    DEFAULT_MARKET_SLIPPAGE_PIPS,
    MAX_BAR_STALENESS_SECONDS,
    PIP_SIZES,
    RISK_CHECK_INTERVAL_IDLE,
    RISK_CHECK_INTERVAL_POSITION,
)
from alphaedge.engine.live_journal import append_live_trade_csv
from alphaedge.engine.live_types import LiveTradeRecord
from alphaedge.utils.alerting import (
    Alert,
    AlertEvent,
    AlertLevel,
    alert_ib_disconnected,
    alert_kill_switch,
)
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
    from alphaedge.engine.strategy import FCRStrategy, StrategyState

logger = get_logger()


class SessionLifecycle:
    """
    Manages the FCR strategy session loop, trade execution, and IB reconnection.

    Receives a reference to the parent ``FCRStrategy`` and accesses its
    dependencies (broker, executor, feeds, states, modules) via ``self._s``.
    """

    def __init__(self, strategy: FCRStrategy) -> None:
        self._s = strategy

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

        risk_mod = self._s._modules.risk_manager
        bracket["stop_loss"] = risk_mod.apply_slippage_buffer(
            stop_loss=bracket["stop_loss"],
            direction=bracket["direction"],
            slippage_pips=DEFAULT_MARKET_SLIPPAGE_PIPS,
            pip_size=pip_size,
        )

        order_mod = self._s._modules.order_manager
        bracket["units"] = order_mod.lots_to_units(
            bracket["lot_size"],
            self._s._config.trading.lot_type,
        )
        return bracket

    async def _submit_and_await_fill(
        self,
        state: StrategyState,
        bracket: dict[str, Any],
    ) -> list | None:
        """Place bracket order and wait for parent fill (10 s timeout)."""
        trades_placed = await self._s._executor.place_bracket_order(
            pair=state.pair,
            direction=bracket["direction"],
            quantity=bracket["units"],
            entry_price=bracket["entry_price"],
            stop_loss=bracket["stop_loss"],
            take_profit=bracket["take_profit"],
        )
        if not trades_placed:
            logger.error(f"ALPHAEDGE: Bracket order returned empty — {state.pair}")
            return None

        parent_trade = trades_placed[0]
        fill_event = getattr(parent_trade, "filledEvent", None)
        if fill_event is not None:
            try:
                await asyncio.wait_for(fill_event.wait(), timeout=10.0)
            except TimeoutError:
                logger.error(
                    f"ALPHAEDGE: Parent order not filled "
                    f"within 10s — {state.pair} — "
                    f"cancelling bracket"
                )
                asyncio.ensure_future(
                    self._s._alert_manager.send_async(
                        Alert(
                            event=AlertEvent.TRADE_EXECUTED,
                            level=AlertLevel.WARNING,
                            title=f"⏱️ Fill timeout — {state.pair}",
                            message="Order not filled within 10s. Bracket cancelled.",
                        )
                    )
                ).add_done_callback(self._on_task_done)
                await self._s._executor.cancel_all_orders()
                return None

        return trades_placed

    def _record_fill(
        self,
        state: StrategyState,
        trades_placed: list,
        bracket: dict[str, Any],
        signal: dict[str, Any],
        spread_pips: float,
        pip_size: float,
        exchange_rate: float,
    ) -> None:
        """Register fill callbacks and update in-memory position state."""
        entry_time = now_utc()
        parent = trades_placed[0]
        raw_fill = getattr(getattr(parent, "orderStatus", None), "avgFillPrice", None)
        fill_price = float(raw_fill) if raw_fill else bracket["entry_price"]
        slippage = abs(fill_price - bracket["entry_price"]) / pip_size

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

        for trade_obj in trades_placed:
            trade_obj.filledEvent += lambda _t, _pair=state.pair: self._on_trade_closed(
                _pair, _t
            )

        state.trades_today += 1
        self._s._global_trades_today += 1
        state.is_position_open = True
        self._persist_daily_state()

    # ------------------------------------------------------------------
    # Trade execution — orchestrator
    # ------------------------------------------------------------------
    async def _execute_signal(
        self,
        state: StrategyState,
        signal: dict[str, Any],
        pip_size: float,
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

            pos_result = self._s._size_position(state, signal, pip_size, exchange_rate)
            if pos_result is None:
                return False

            spread = await self._s._rt_feed.get_live_spread(state.pair)
            _t_spread_end = time.perf_counter_ns()
            if spread is None:
                logger.error(
                    f"ALPHAEDGE: Cannot verify spread for {state.pair} — signal SKIPPED"
                )
                return False
            spread_pips = spread / pip_size

            bracket = self._prepare_bracket(
                signal,
                pos_result["lot_size"],
                pip_size,
                spread_pips,
            )
            if bracket is None:
                return False

            _t_order = time.perf_counter_ns()
            trades_placed = await self._submit_and_await_fill(state, bracket)
            if trades_placed is None:
                return False

            self._record_fill(
                state,
                trades_placed,
                bracket,
                signal,
                spread_pips,
                pip_size,
                exchange_rate,
            )
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
                    state.is_position_open = False
                    logger.info(f"ALPHAEDGE: Position closed for {pair}")

                    record = state.live_record
                    if record is not None:
                        exit_time = now_utc()
                        pip_size = PIP_SIZES.get(pair, 0.0001)

                        raw_exit = None
                        if ib_trade is not None:
                            raw_exit = getattr(
                                getattr(ib_trade, "orderStatus", None),
                                "avgFillPrice",
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
                        pnl_usd = pnl_pips * pip_size * record.lot_size * 100_000

                        record.exit_price = exit_price
                        record.exit_time = exit_time
                        record.pnl_pips = round(pnl_pips, 2)
                        record.pnl_usd = round(pnl_usd, 2)
                        if not exit_price:
                            record.outcome = "unknown"
                        elif pnl_pips > 0:
                            record.outcome = "win"
                        elif pnl_pips == 0.0:
                            record.outcome = "breakeven"
                        else:
                            record.outcome = "loss"

                        append_live_trade_csv(record)

                        duration_s = (
                            int((exit_time - record.entry_time).total_seconds())
                            if record.entry_time
                            else "?"
                        )
                        logger.info(
                            "TRADE_CLOSE | pair={} | exit={} | pnl_pips={:+.1f}"
                            " | pnl_usd={:+.2f} | outcome={} | duration={}s",
                            pair,
                            exit_price,
                            record.pnl_pips,
                            record.pnl_usd,
                            record.outcome,
                            duration_s,
                        )
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
            success = await self._s._broker.reconnect(max_retries=3)
            if success:
                logger.info("ALPHAEDGE: Reconnected to IB Gateway")
                await self._reconcile_positions()
                await self._check_orphan_orders()
                # Re-subscribe to real-time feeds
                for pair in self._s._config.trading.pairs:
                    await self._s._rt_feed.subscribe(pair)
                logger.info("ALPHAEDGE: Real-time feeds re-subscribed after reconnect")
            else:
                # Last-resort orphan check if a partial reconnect occurred
                try:
                    await self._reconcile_positions()
                    await self._check_orphan_orders()
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

    async def _reconcile_positions(self) -> None:
        """Sync StrategyState with actual IB positions after reconnect."""
        try:
            positions = await self._s._executor.get_open_positions()
            traded_pairs = set(self._s._config.trading.pairs)

            # Build set of pairs that actually have open positions
            ib_open_pairs: set[str] = set()
            for pos in positions:
                contract = pos.contract
                pair_sym: str = getattr(
                    contract, "pair", getattr(contract, "symbol", "")
                )
                if pair_sym in traded_pairs and pos.position != 0:
                    ib_open_pairs.add(pair_sym)
                    logger.info(
                        f"ALPHAEDGE RECONCILE: {pair_sym} has open "
                        f"position qty={pos.position}"
                    )

            # Sync strategy state
            for pair, state in self._s._states.items():
                was_open = state.is_position_open
                state.is_position_open = pair in ib_open_pairs
                if was_open != state.is_position_open:
                    logger.warning(
                        f"ALPHAEDGE RECONCILE: {pair} position state "
                        f"corrected: {was_open} -> {state.is_position_open}"
                    )
        except Exception:
            logger.exception("ALPHAEDGE _reconcile_positions failed")

    async def _check_orphan_orders(self) -> None:
        """Detect orphan bracket orders after reconnection."""
        try:
            open_orders = await self._s._executor.get_open_orders()
            if not open_orders:
                logger.info("ALPHAEDGE ORPHAN CHECK: No open orders")
                return

            traded_pairs = set(self._s._config.trading.pairs)
            orphan_count = 0
            for order in open_orders:
                contract = getattr(order, "contract", None)
                if contract is None:
                    continue
                pair_sym: str = getattr(
                    contract, "pair", getattr(contract, "symbol", "")
                )
                if pair_sym in traded_pairs:
                    orphan_count += 1
                    logger.warning(
                        f"ALPHAEDGE ORPHAN: Open order on {pair_sym} — "
                        f"orderId={getattr(order, 'orderId', '?')} "
                        f"action={getattr(order, 'action', '?')} "
                        f"type={getattr(order, 'orderType', '?')}"
                    )

            if orphan_count > 0:
                logger.warning(
                    f"ALPHAEDGE ORPHAN CHECK: {orphan_count} open order(s) "
                    f"detected — review manually"
                )
            else:
                logger.info("ALPHAEDGE ORPHAN CHECK: No orphan orders")
        except Exception:
            logger.exception("ALPHAEDGE _check_orphan_orders failed")

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

        state = self._s._states.get(pair)
        if state is None:
            return

        state.m1_candles.append(candle)
        if len(state.m1_candles) > state.max_candles:
            state.m1_candles = state.m1_candles[-state.max_candles :]

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

        pip_size = PIP_SIZES.get(pair, 0.0001)

        # Skip if global trade limit reached across all pairs
        if (
            self._s._global_trades_today
            >= self._s._config.trading.max_trades_per_session
        ):
            return

        # Monitor spread spike while position is open
        if state.is_position_open:
            spread_task = asyncio.ensure_future(self._monitor_spread_spike(pair))
            spread_task.add_done_callback(self._on_task_done)
            return

        # News blackout check
        if self._s._news_filter.is_news_blackout(now_utc(), pair):
            return

        # Correlation check: block signal if a highly-correlated pair is open
        if self._s._correlation_matrix:
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

        # Per-pair risk cap: quick pre-check (without lock)
        open_pairs = [p for p, s in self._s._states.items() if s.is_position_open]
        risk_mod = self._s._modules.risk_manager
        pair_check: dict[str, Any] = risk_mod.check_pair_limit(
            pair=pair,
            open_pairs=open_pairs,
            max_open_pairs=1,
        )
        if not pair_check["allowed"]:
            return

        # The live pipeline is all-or-nothing: no FCR means no gap stage.
        if state.fcr_result is None:
            return

        # Detect gap/ATR spike on first M1 bars (once per session)
        if state.gap_result is None and len(state.m1_candles) >= 3:
            pre_close = state.m5_candles[-1]["close"] if state.m5_candles else 0.0
            session_open = state.m1_candles[0]["open"]
            gap = self._s._detect_gap(state, pre_close, session_open)
            if gap:
                logger.info(
                    f"ALPHAEDGE GAP: {pair} "
                    f"ratio={gap.get('atr_ratio', 0):.2f} "
                    f"detected={gap.get('detected', False)}"
                )

        # Skip engulfing detection if gap/ATR spike not confirmed
        if not state.gap_result or not state.gap_result.get("detected"):
            return

        # Detect engulfing signal on each new M1 bar
        _t_bar = time.perf_counter_ns()
        signal = self._s._detect_engulfing(state, pip_size)
        if signal and signal.get("detected"):
            _t_signal = time.perf_counter_ns()
            logger.debug(
                "LATENCE bar→signal: {:.1f}ms — {}",
                (_t_signal - _t_bar) / 1e6,
                pair,
            )
            logger.info(
                f"ALPHAEDGE SIGNAL: {pair} "
                f"{'SELL' if signal['signal'] == -1 else 'BUY'} "
                f"@ {signal['entry_price']}"
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
            return await self._execute_signal(state, signal, pip_size)
        except Exception:
            logger.exception(
                f"ALPHAEDGE _check_spread_and_execute failed: {state.pair}"
            )
            return False

    async def _monitor_spread_spike(self, pair: str) -> None:
        """Log WARNING if spread spikes beyond the configured multiplier."""
        try:
            pip_size = PIP_SIZES.get(pair, 0.0001)
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

            if open_count > 0:
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

            # Session summary
            for pair, state in self._s._states.items():
                logger.info(f"ALPHAEDGE SUMMARY: {pair} — trades={state.trades_today}")
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
        Check regime gate, detect FCR, and init state for each configured pair.

        Returns the list of active pairs that passed the regime filter.
        Also builds and stores the pairwise correlation matrix.
        """
        active_pairs: list[str] = []
        pair_closes: dict[str, list[float]] = {}
        for pair in self._s._config.trading.pairs:
            # Fetch pre-session M5 data for FCR and regime check
            m5_candles, pre_session_m1 = await self._s._fetch_pre_session_data(
                pair, session_start
            )
            pip_size = PIP_SIZES.get(pair, 0.0001)

            # Fetch daily bars for volatility regime (30 trading days)
            daily_bars = await self._s._hist_feed.fetch_bars(
                pair=pair,
                timeframe="1 day",
                duration="30 D",
                end_dt=session_start,
            )

            # Build today's partial bar from pre-session M5 data
            current_day_bar: dict[str, Any] = {}
            if m5_candles:
                current_day_bar = {
                    "high": max(c.get("high", 0.0) for c in m5_candles),
                    "low": min(c.get("low", 0.0) for c in m5_candles),
                }

            # Volatility regime gate: skip pair if session is too quiet/violent
            if daily_bars and current_day_bar:
                regime = check_volatility_regime(daily_bars, current_day_bar)
                if not regime.allowed:
                    logger.warning(
                        f"ALPHAEDGE REGIME: {pair} session SKIPPED "
                        f"\u2014 {regime.reason}"
                    )
                    continue

            # Init pair state and store candles
            state = self._s._init_pair_state(pair)
            state.starting_equity = starting_equity
            state.current_equity = live_equity
            state.m5_candles = m5_candles
            state.pre_session_m1_candles = pre_session_m1
            if persisted:
                state.trades_today = persisted.trades_today
                self._s._global_trades_today = persisted.trades_today

            # Collect closes for correlation matrix
            pair_closes[pair] = [c["close"] for c in m5_candles if "close" in c]

            # Detect FCR
            fcr = self._s._detect_fcr(state, pip_size)
            if fcr:
                logger.info(
                    f"ALPHAEDGE FCR: {pair} high={fcr['range_high']} "
                    f"low={fcr['range_low']}"
                )
            active_pairs.append(pair)

        self._s._correlation_matrix = build_correlation_matrix(pair_closes)
        return active_pairs

    # ------------------------------------------------------------------
    # Main session loop
    # ------------------------------------------------------------------
    async def run_session(self) -> None:
        """
        Run a single trading session for all configured pairs.

        This is the main entry point for the strategy.
        """
        logger.info(f"ALPHAEDGE session starting at {format_dual_time(now_utc())}")

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
            return

        # Connect to IB Gateway
        if not await self._s._broker.connect():
            logger.error("ALPHAEDGE: Cannot start — IB Gateway unavailable")
            return

        try:
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
            session_start, _session_end = get_session_window_utc()

            # Process each pair — regime gate, FCR detection, state init
            active_pairs = await self._init_session_pairs(
                starting_equity,
                live_equity,
                persisted,
                session_start,
            )

            # Reconcile position state with IB at startup
            await self._reconcile_positions()

            # Subscribe to real-time M1 data (only pairs that passed regime gate)
            self._s._rt_feed.on_bar(self._on_new_m1_bar)
            for pair in active_pairs:
                await self._s._rt_feed.subscribe(pair)

            # Wait for session to end, with adaptive risk check interval
            logger.info("ALPHAEDGE: Monitoring session...")
            risk_check_counter = 0
            while is_session_active() and not self._s._shutdown_requested:
                await asyncio.sleep(1.0)
                risk_check_counter += 1

                # Adaptive interval: 5s with open position, 30s idle
                interval = (
                    RISK_CHECK_INTERVAL_POSITION
                    if self._has_open_position()
                    else RISK_CHECK_INTERVAL_IDLE
                )
                if risk_check_counter >= interval:
                    risk_check_counter = 0
                    await self._check_daily_loss_shutdown()
        except Exception:
            logger.exception("ALPHAEDGE run_session error")
        finally:
            # Session-end position check before disconnect
            await self._handle_session_end()
            # Cleanup
            await self._s._rt_feed.unsubscribe_all()
            await self._s._broker.disconnect()
            logger.info(f"ALPHAEDGE session ended at {format_dual_time(now_utc())}")
