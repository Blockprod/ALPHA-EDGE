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
from datetime import date
from typing import TYPE_CHECKING, Any

from alphaedge.config.constants import (
    DEFAULT_MARKET_SLIPPAGE_PIPS,
    PIP_SIZES,
    RISK_CHECK_INTERVAL_IDLE,
    RISK_CHECK_INTERVAL_POSITION,
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


def _get_pip_size(pair: str) -> float:
    """Return pip size for a currency pair (0.0001 default, 0.01 for JPY)."""
    return PIP_SIZES.get(pair, 0.0001)


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
    # Trade execution
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
            )
            if pos_result is None:
                return False

            spread = await self._s._rt_feed.get_live_spread(state.pair)
            if spread is None:
                logger.error(
                    f"ALPHAEDGE: Cannot verify spread for {state.pair} — signal SKIPPED"
                )
                return False
            spread_pips = spread / pip_size

            bracket = self._s._build_validated_order(
                signal,
                pos_result["lot_size"],
                pip_size,
                spread_pips,
            )
            if bracket is None:
                return False

            # Widen SL for market order slippage
            risk_mod = self._s._modules.risk_manager
            bracket["stop_loss"] = risk_mod.apply_slippage_buffer(
                stop_loss=bracket["stop_loss"],
                direction=bracket["direction"],
                slippage_pips=DEFAULT_MARKET_SLIPPAGE_PIPS,
                pip_size=pip_size,
            )

            order_mod = self._s._modules.order_manager
            units = order_mod.lots_to_units(
                bracket["lot_size"],
                self._s._config.trading.lot_type,
            )
            trades_placed = await self._s._executor.place_bracket_order(
                pair=state.pair,
                direction=bracket["direction"],
                quantity=units,
                entry_price=bracket["entry_price"],
                stop_loss=bracket["stop_loss"],
                take_profit=bracket["take_profit"],
            )

            if not trades_placed:
                logger.error(f"ALPHAEDGE: Bracket order returned empty — {state.pair}")
                return False

            # Wait for parent order fill with timeout
            parent_trade = trades_placed[0]
            fill_event = getattr(parent_trade, "filledEvent", None)
            if fill_event is not None:
                try:
                    await asyncio.wait_for(
                        fill_event.wait(),
                        timeout=10.0,
                    )
                except TimeoutError:
                    logger.error(
                        f"ALPHAEDGE: Parent order not filled "
                        f"within 10s — {state.pair} — "
                        f"cancelling bracket"
                    )
                    await self._s._executor.cancel_all_orders()
                    return False

            # Register fill callback to reset position flag on SL/TP exit
            for trade_obj in trades_placed:
                trade_obj.filledEvent += lambda _t, _pair=state.pair: (
                    self._on_trade_closed(_pair)
                )

            state.trades_today += 1
            self._s._global_trades_today += 1
            state.is_position_open = True

            # Persist state after each trade
            self._persist_daily_state()

            return True
        except Exception:
            logger.exception(f"ALPHAEDGE _execute_signal failed: {state.pair}")
            return False

    def _on_trade_closed(self, pair: str) -> None:
        """Reset position flag when a bracket child (SL/TP) fills."""

        async def _reset_position() -> None:
            async with self._s._trade_lock:
                state = self._s._states.get(pair)
                if state:
                    state.is_position_open = False
                    logger.info(f"ALPHAEDGE: Position closed for {pair}")
                    # Persist state so open_pairs reflects the closed position
                    self._persist_daily_state()

        task = asyncio.ensure_future(_reset_position())
        task.add_done_callback(self._on_task_done)

    # ------------------------------------------------------------------
    # IB Disconnection Recovery
    # ------------------------------------------------------------------
    def _on_ib_disconnect(self) -> None:
        """Handle IB Gateway disconnection event."""
        logger.critical("ALPHAEDGE: IB Gateway DISCONNECTED")
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
                logger.critical(
                    "ALPHAEDGE: Reconnection FAILED after all retries — shutting down"
                )
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
        pip_size = _get_pip_size(pair)

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
        signal = self._s._detect_engulfing(state, pip_size)
        if signal and signal.get("detected"):
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
            # Re-verify pair limit under lock (authoritative check)
            open_pairs = [p for p, s in self._s._states.items() if s.is_position_open]
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
            return await self._check_spread_and_execute(state, signal, pip_size)

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
            pip_size = _get_pip_size(pair)
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
                logger.warning(
                    f"ALPHAEDGE: Daily loss limit breached — "
                    f"PnL {risk_result.get('daily_pnl_pct', 0):.2f}%. "
                    f"Shutting down."
                )
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
    # Main session loop
    # ------------------------------------------------------------------
    async def run_session(self) -> None:  # pylint: disable=too-many-branches,too-many-statements
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

            # Process each pair — volatility regime gate + FCR detection
            active_pairs: list[str] = []
            pair_closes: dict[str, list[float]] = {}
            for pair in self._s._config.trading.pairs:
                # Fetch pre-session M5 data for FCR and regime check
                m5_candles = await self._s._fetch_pre_session_data(pair, session_start)
                pip_size = _get_pip_size(pair)

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
                            f"— {regime.reason}"
                        )
                        continue

                # Init pair state and store candles
                state = self._s._init_pair_state(pair)
                state.starting_equity = starting_equity
                state.current_equity = live_equity
                state.m5_candles = m5_candles
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

            # Build pairwise correlation matrix from pre-session closes
            self._s._correlation_matrix = build_correlation_matrix(pair_closes)

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
