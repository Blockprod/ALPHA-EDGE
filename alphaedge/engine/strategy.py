# ============================================================
# PROJECT      : ALPHAEDGE — Swing Trading Bot
# FILE         : alphaedge/engine/strategy.py
# DESCRIPTION  : Daily/H4 Momentum+Carry strategy orchestrator
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-25
# ============================================================
"""ALPHAEDGE — Swing Trading Bot: main strategy engine."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import signal
import sys
from dataclasses import dataclass, field
from datetime import date as _date
from types import ModuleType
from typing import Any

from alphaedge.config.constants import IB_LIVE_PORT, IB_PAPER_PORT
from alphaedge.config.loader import AppConfig, load_config
from alphaedge.engine.broker import BrokerConnection, OrderExecutor
from alphaedge.engine.data_feed import HistoricalDataFeed, RealtimeDataFeed
from alphaedge.engine.live_types import LiveTradeRecord

# NOTE: import cycle mitigated by TYPE_CHECKING in position_manager,
# signal_pipeline, session_lifecycle
from alphaedge.engine.position_manager import PositionManager
from alphaedge.engine.regime_filter import DailyRegimeFilter
from alphaedge.engine.session_lifecycle import SessionLifecycle
from alphaedge.engine.signal_pipeline import SignalPipeline
from alphaedge.utils.alerting import AlertManager, build_alert_config
from alphaedge.utils.logger import get_logger, setup_logging
from alphaedge.utils.news_filter import EconomicNewsFilter, build_news_filter

logger = get_logger()


def _stdout(message: str) -> None:
    """Emit user-facing CLI messages without using print()."""
    sys.stdout.write(f"{message}\n")


def _stderr(message: str) -> None:
    """Emit user-facing CLI error messages without using print()."""
    sys.stderr.write(f"{message}\n")


# ------------------------------------------------------------------
# Strategy state container
# ------------------------------------------------------------------
@dataclass
class StrategyState:
    """Tracks the current state of the swing strategy."""

    pair: str = ""
    signal_result: dict[str, Any] | None = None
    trades_today: int = 0
    wins_today: int = 0
    losses_today: int = 0
    pnl_usd_today: float = 0.0
    consecutive_losses_count: int = 0
    loss_streak_pnl_usd: float = 0.0
    starting_equity: float = 0.0
    current_equity: float = 0.0
    is_position_open: bool = False
    max_candles: int = 200
    live_record: LiveTradeRecord | None = None
    # Bracket order IDs — used to identify SL/TP fills in _on_trade_closed
    _tp_order_id: int = 0
    _sl_order_id: int = 0
    # Daily/H4 momentum strategy fields
    daily_bars: list[dict[str, Any]] = field(default_factory=list)
    carry_rates: dict[str, float] = field(default_factory=dict)
    pip_size: float = 0.0
    current_atr_pips: float = 0.0


# ------------------------------------------------------------------
# Named container for Cython core modules
# ------------------------------------------------------------------
@dataclass(frozen=True)
class CoreModules:
    """Named container for Cython/stub core modules."""

    momentum_detector: ModuleType
    order_manager: ModuleType
    risk_manager: ModuleType


# ------------------------------------------------------------------
# Import Cython modules with fallback to pure-Python stubs
# ------------------------------------------------------------------
def _import_core_modules() -> CoreModules:
    """
    Import Cython core modules, falling back to stubs if not compiled.

    Returns
    -------
    CoreModules
        Named container with all five core detector/manager modules.
    """
    try:
        from alphaedge.core import (
            get_backend_name,
            get_fallback_modules,
            momentum_detector,
            order_manager,
            risk_manager,
        )

        backend_name = get_backend_name()
        fallback_modules = get_fallback_modules()
        if fallback_modules:
            logger.warning(
                f"ALPHAEDGE: core backend={backend_name} with fallback on "
                f"{', '.join(fallback_modules)}"
            )
        else:
            logger.info(f"ALPHAEDGE: core backend={backend_name}")
        return CoreModules(
            momentum_detector=momentum_detector,
            order_manager=order_manager,
            risk_manager=risk_manager,
        )
    except ImportError:
        logger.warning(
            "ALPHAEDGE: Cython modules not compiled — "
            "run 'python setup.py build_ext --inplace'"
        )
        raise


# ------------------------------------------------------------------
# Swing Strategy Engine
# ------------------------------------------------------------------
class SwingStrategy:
    """
    Main Daily/H4 Momentum+Carry strategy orchestrator.

    Coordinates Daily momentum detection, carry bias filtering,
    risk management, and order execution.
    """

    def __init__(
        self,
        config: AppConfig,
        broker: BrokerConnection | None = None,
        historical_feed: HistoricalDataFeed | None = None,
        realtime_feed: RealtimeDataFeed | None = None,
        core_modules: CoreModules | None = None,
    ) -> None:
        """Initialize the strategy with application config.

        Parameters
        ----------
        config : AppConfig
            Application configuration.
        broker : BrokerConnection | None
            Optional pre-built broker (for testing). Created from config if None.
        historical_feed : HistoricalDataFeed | None
            Optional pre-built historical feed (for testing).
        realtime_feed : RealtimeDataFeed | None
            Optional pre-built realtime feed (for testing).
        core_modules : CoreModules | None
            Optional pre-loaded core modules (for testing).
        """
        self._config = config
        self._broker = broker or BrokerConnection(config.ib)
        self._executor = OrderExecutor(self._broker)
        self._hist_feed = historical_feed or HistoricalDataFeed(self._broker)
        self._rt_feed = realtime_feed or RealtimeDataFeed(self._broker)
        self._states: dict[str, StrategyState] = {}
        self._modules = core_modules or _import_core_modules()
        self._shutdown_requested = False
        self._reconnecting = False
        self._news_filter: EconomicNewsFilter = build_news_filter(
            config.news_filter_raw,
        )
        self._trade_lock = asyncio.Lock()
        self._executing_pairs: set[str] = set()  # pairs with order in flight
        self._global_trades_today: int = (
            0  # Global counter across all pairs — reset each session
        )
        self._correlation_matrix: dict[tuple[str, str], float] = {}

        # SRP components — detection and sizing logic
        self._signal_pipeline = SignalPipeline()
        self._position_manager = PositionManager()

        # Regime filter — observation mode only (logs regime, never blocks trades)
        self._regime_filter: DailyRegimeFilter = DailyRegimeFilter()

        # Alert manager — dispatches Telegram/Discord notifications
        self._alert_manager: AlertManager = AlertManager(
            build_alert_config(config.alerting_raw)
        )

        # Session loop, execution, reconnect logic
        self._lifecycle = SessionLifecycle(self)

        # Wire IB disconnect event for auto-reconnection
        self._broker.add_disconnect_handler(self._lifecycle._on_ib_disconnect)

    async def graceful_shutdown(self) -> None:
        """Initiate graceful shutdown (called by signal handler)."""
        await self._lifecycle.graceful_shutdown()

    def _init_pair_state(self, pair: str) -> StrategyState:
        """Create a fresh strategy state for a pair."""
        state = StrategyState(pair=pair)
        self._states[pair] = state
        return state

    def _detect_momentum(
        self,
        state: StrategyState,
        pip_size: float,
    ) -> dict[str, Any] | None:
        """Run the momentum+carry signal pipeline for the given pair state."""
        # Observation-only regime log — does NOT block the trade
        state.pip_size = pip_size
        regime_filter = getattr(self, "_regime_filter", None)
        regime = "unknown"
        if regime_filter is not None:
            regime = regime_filter.predict(_date.today(), state.daily_bars[-20:])
        if self._config.regime_gate_enabled and regime == self._config.regime_block_on:
            logger.info(
                f"ALPHAEDGE: regime gate BLOCK pair={state.pair} regime={regime}"
            )
            return None
        logger.info(f"ALPHAEDGE: regime={regime} pair={state.pair}")
        result = self._signal_pipeline.detect_momentum(
            state, self._modules, self._config
        )
        if result is None:
            state.signal_result = None
            return None

        # Carry conflict check: block signal when carry direction contradicts momentum.
        # Mirrors the carry filter applied in backtest._backtest_pair.
        if self._config.trading.carry_enabled:
            carry = self._signal_pipeline.get_carry(state, self._config)
            if self._signal_pipeline.is_carry_conflict(result, carry):
                logger.info(
                    "ALPHAEDGE: carry conflict BLOCK pair=%s momentum=%s carry=%s",
                    state.pair,
                    result.get("direction"),
                    carry.direction,
                )
                state.signal_result = None
                return None

        state.signal_result = result
        return result

    async def _check_risk(
        self,
        state: StrategyState,
    ) -> dict[str, Any]:
        """Check daily risk limits before placing a trade."""
        risk_mod = self._modules.risk_manager
        equity = await self._executor.get_account_equity()
        state.current_equity = equity

        result: dict[str, Any] = risk_mod.check_daily_limit(
            starting_equity=state.starting_equity,
            current_equity=equity,
            max_daily_loss_pct=self._config.trading.max_daily_loss_pct,
            trades_today=state.trades_today,
            max_trades=self._config.trading.max_trades_per_session,
        )
        return result

    def _size_position(
        self,
        state: StrategyState,
        signal: dict[str, Any],
        pip_size: float,
        exchange_rate: float = 0.0,
        current_atr_pips: float = 0.0,
    ) -> dict[str, Any] | None:
        """Calculate and validate position size. Returns None on failure."""
        return self._position_manager.size_position(
            state,
            self._modules,
            self._config,
            signal,
            pip_size,
            exchange_rate,
            current_atr_pips,
        )

    def _build_validated_order(
        self,
        signal: dict[str, Any],
        lot_size: float,
        pip_size: float,
        spread_pips: float,
    ) -> dict[str, Any] | None:
        """Build bracket order and validate. Returns None on rejection."""
        return self._position_manager.build_validated_order(
            signal, lot_size, pip_size, spread_pips, self._modules, self._config
        )

    def get_live_state(self) -> dict[str, Any]:
        """Return a snapshot of current live state for the web dashboard."""
        from datetime import timedelta

        from alphaedge.utils.timezone import (
            get_session_window_utc,
            is_session_active,
            now_utc,
        )

        # If session not yet started, show configured pairs with zero values
        if self._states:
            pairs_info = [
                {
                    "pair": s.pair,
                    "is_position_open": s.is_position_open,
                    "trades_today": s.trades_today,
                    "pnl_usd_today": s.pnl_usd_today,
                }
                for s in self._states.values()
            ]
        else:
            pairs_info = [
                {
                    "pair": p,
                    "is_position_open": False,
                    "trades_today": 0,
                    "pnl_usd_today": 0.0,
                }
                for p in self._config.trading.pairs
            ]
        total_pnl = sum(s.pnl_usd_today for s in self._states.values())
        total_trades = sum(s.trades_today for s in self._states.values())

        # Compute next session start time
        now = now_utc()
        session_start, session_end = get_session_window_utc(now)
        if now >= session_end:
            next_day = now + timedelta(days=1)
            while next_day.weekday() >= 5:
                next_day += timedelta(days=1)
            session_start, _ = get_session_window_utc(next_day)
        next_session_utc = (
            session_start.strftime("%Y-%m-%dT%H:%M:%SZ") if session_start > now else ""
        )

        return {
            "ib_connected": self._broker.is_connected,
            "session_active": is_session_active() and not self._shutdown_requested,
            "next_session_utc": next_session_utc,
            "pairs": pairs_info,
            "position": {},
            "daily": {
                "total_pnl_usd": total_pnl,
                "total_trades": total_trades,
            },
        }

    async def run_session(self) -> None:
        """Run a single trading session (delegates to SessionLifecycle)."""
        await self._lifecycle.run_session()


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------
def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="ALPHAEDGE — Momentum+Carry")
    parser.add_argument(
        "--mode",
        choices=["paper", "live"],
        default="paper",
        help="Trading mode (default: paper)",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config.yaml",
    )
    return parser.parse_args()


def _apply_cli_mode(config: AppConfig, mode: str) -> None:
    """Apply an explicit CLI trading mode to the loaded config."""
    if mode == "paper":
        config.ib.is_paper = True
        config.ib.port = IB_PAPER_PORT
        config.mode = "paper"
        return

    # Guard: ALPHAEDGE_PAPER=true ENV takes precedence over CLI --mode live.
    # This prevents switching to live mode when the ENV guard is active.
    env_paper = os.getenv("ALPHAEDGE_PAPER", "true").strip().lower()
    if env_paper == "true":
        _stderr(
            "ERROR: ALPHAEDGE_PAPER=true is set in environment. "
            "Cannot switch to live mode via --mode live. "
            "Unset ALPHAEDGE_PAPER (or set it to 'false') to enable live trading."
        )
        raise SystemExit(1)

    config.ib.is_paper = False
    config.ib.port = IB_LIVE_PORT
    config.mode = "live"


async def _main() -> None:
    """Async main entry point."""
    args = _parse_args()

    # ⚠️ WARNING: Live trading involves real money risk
    if args.mode == "live":
        _stdout("=" * 60)
        _stdout("⚠️  WARNING: LIVE TRADING MODE")
        _stdout("⚠️  Real money is at risk. Proceed with extreme caution.")
        _stdout("=" * 60)
        try:
            confirm = input("Type 'YES' to confirm live trading: ")
        except (EOFError, KeyboardInterrupt):
            _stdout("\nALPHAEDGE: Live trading cancelled (no interactive input).")
            sys.exit(1)
        if confirm != "YES":
            _stdout("ALPHAEDGE: Live trading cancelled.")
            sys.exit(0)

    setup_logging()
    config = load_config(config_path=args.config)
    _apply_cli_mode(config, args.mode)

    if args.mode == "paper":
        _stdout("=" * 60)
        _stdout("📝  ALPHAEDGE — PAPER TRADING MODE")
        _stdout(f"📝  No real money at risk. IB Gateway port {IB_PAPER_PORT}.")
        _stdout("=" * 60)
    else:
        _stdout("=" * 60)
        _stdout("⚠️  ALPHAEDGE — LIVE TRADING MODE")
        _stdout(f"⚠️  IB Gateway live port {IB_LIVE_PORT} selected.")
        _stdout("=" * 60)

    strategy = SwingStrategy(config)

    # Install signal handlers for graceful shutdown
    # add_signal_handler is not supported on Windows — use try/except for all signals
    loop = asyncio.get_running_loop()

    # Route asyncio callback exceptions through loguru instead of raw stderr writes.
    # This prevents _ProactorBaseWritePipeTransport._loop_writing AssertionError
    # caused by asyncio writing exception tracebacks directly to sys.stderr while
    # the ProactorEventLoop pipe transport is busy with another write (Windows race).
    def _asyncio_exception_handler(
        lp: asyncio.AbstractEventLoop, context: dict
    ) -> None:
        exc = context.get("exception")
        # Suppress the known Windows ProactorEventLoop pipe-write race — harmless.
        if isinstance(exc, AssertionError) and "_write_fut" in str(exc):
            return
        msg = context.get("message", "Unknown asyncio error")
        if exc is not None:
            logger.error(f"Asyncio callback exception: {msg}", exc_info=exc)
        else:
            logger.error(f"Asyncio error: {msg} | {context}")

    loop.set_exception_handler(_asyncio_exception_handler)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(
                sig,
                lambda: asyncio.ensure_future(strategy.graceful_shutdown()),
            )
        except NotImplementedError:
            pass  # Windows — signal handlers not supported via asyncio loop

    # Optional web dashboard (FastAPI REST + WebSocket)
    _dashboard_task: asyncio.Task[None] | None = None
    if config.dashboard_raw.get("enabled", False):
        import threading

        from alphaedge.engine.web_dashboard import (
            configure_auth,
            run_web_dashboard,
            start_server,
        )

        dash_host: str = str(config.dashboard_raw.get("host", "127.0.0.1"))
        dash_port: int = int(config.dashboard_raw.get("port", 8080))
        dash_token: str = str(config.dashboard_raw.get("api_token", ""))
        if dash_token:
            configure_auth(dash_token)

        threading.Thread(
            target=start_server,
            args=(dash_host, dash_port),
            daemon=True,
            name="alphaedge-web-dashboard",
        ).start()
        logger.info(f"Web dashboard: http://{dash_host}:{dash_port}/docs")

        async def _get_dashboard_state() -> dict[str, Any]:
            return strategy.get_live_state()

        _dashboard_task = asyncio.create_task(
            run_web_dashboard(_get_dashboard_state, refresh_rate=2.0),
            name="web-dashboard-loop",
        )

    try:
        while not strategy._shutdown_requested:
            await strategy.run_session()
            if strategy._shutdown_requested:
                break
            # Brief pause between sessions (daily loss shutdown resets next day)
            logger.info("ALPHAEDGE: Session complete — waiting for next session window")
            await asyncio.sleep(60.0)
    finally:
        if _dashboard_task is not None:
            _dashboard_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await _dashboard_task


if __name__ == "__main__":
    # ── Windows ProactorEventLoop pipe-write race condition fix ──
    # On Windows, asyncio uses ProactorEventLoop which can trigger a harmless
    # AssertionError in _loop_writing when two concurrent writes hit the same
    # stderr pipe transport (e.g. loguru + uvicorn + asyncio's own error logger).
    # This monkey-patch catches the assertion at the source — before asyncio
    # formats a traceback and tries to write it to stderr (which would trigger
    # the same race again). Affects ALL event loops in ALL threads.
    import asyncio.proactor_events as _pev

    _TransportClass = getattr(_pev, "_ProactorBaseWritePipeTransport")
    _original_loop_writing = getattr(_TransportClass, "_loop_writing")

    def _patched_loop_writing(
        self: object, f: object = None, data: object = None
    ) -> None:
        try:
            _original_loop_writing(self, f, data)
        except AssertionError:
            # Harmless: two futures overlapped on the same pipe transport.
            # The write still succeeds — the assertion is a stale-future check.
            pass

    setattr(_TransportClass, "_loop_writing", _patched_loop_writing)

    asyncio.run(_main())
