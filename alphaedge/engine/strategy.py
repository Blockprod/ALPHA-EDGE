# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/engine/strategy.py
# DESCRIPTION  : FCR multi-timeframe strategy orchestrator
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: main strategy engine."""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys
from dataclasses import dataclass, field
from datetime import datetime
from types import ModuleType
from typing import Any

from alphaedge.config.loader import AppConfig, load_config
from alphaedge.engine.broker import BrokerConnection, OrderExecutor
from alphaedge.engine.data_feed import HistoricalDataFeed, RealtimeDataFeed
from alphaedge.engine.position_manager import PositionManager
from alphaedge.engine.session_lifecycle import SessionLifecycle
from alphaedge.engine.signal_pipeline import SignalPipeline
from alphaedge.utils.logger import get_logger, setup_logging
from alphaedge.utils.news_filter import EconomicNewsFilter, build_news_filter

logger = get_logger()


# ------------------------------------------------------------------
# Strategy state container
# ------------------------------------------------------------------
@dataclass
class StrategyState:
    """Tracks the current state of the FCR strategy."""

    pair: str = ""
    fcr_result: dict[str, Any] | None = None
    gap_result: dict[str, Any] | None = None
    signal_result: dict[str, Any] | None = None
    trades_today: int = 0
    starting_equity: float = 0.0
    current_equity: float = 0.0
    is_position_open: bool = False
    m5_candles: list[dict[str, Any]] = field(default_factory=list)
    m1_candles: list[dict[str, Any]] = field(default_factory=list)
    max_candles: int = 200


# ------------------------------------------------------------------
# Named container for Cython core modules
# ------------------------------------------------------------------
@dataclass(frozen=True)
class CoreModules:
    """Named container for Cython/stub core modules."""

    fcr_detector: ModuleType
    gap_detector: ModuleType
    engulfing_detector: ModuleType
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
            engulfing_detector,
            fcr_detector,
            gap_detector,
            order_manager,
            risk_manager,
        )

        logger.info("ALPHAEDGE: Cython core modules loaded successfully")
        return CoreModules(
            fcr_detector=fcr_detector,
            gap_detector=gap_detector,
            engulfing_detector=engulfing_detector,
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
# FCR Strategy Engine
# ------------------------------------------------------------------
class FCRStrategy:
    """
    Main FCR multi-timeframe strategy orchestrator.

    Coordinates M5 FCR detection, M1 gap/engulfing signals,
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
        self._global_trades_today: int = (
            0  # Global counter across all pairs — reset each session
        )
        self._correlation_matrix: dict[tuple[str, str], float] = {}

        # SRP components — detection and sizing logic
        self._signal_pipeline = SignalPipeline()
        self._position_manager = PositionManager()

        # Session loop, execution, reconnect logic
        self._lifecycle = SessionLifecycle(self)

        # Wire IB disconnect event for auto-reconnection
        self._broker.ib.disconnectedEvent += self._lifecycle._on_ib_disconnect

    async def graceful_shutdown(self) -> None:
        """Initiate graceful shutdown (called by signal handler)."""
        await self._lifecycle.graceful_shutdown()

    def _init_pair_state(self, pair: str) -> StrategyState:
        """Create a fresh strategy state for a pair."""
        state = StrategyState(pair=pair)
        self._states[pair] = state
        return state

    async def _fetch_pre_session_data(
        self,
        pair: str,
        session_start: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch M5 candles before session open for FCR scan."""
        return await self._hist_feed.fetch_m5_pre_session(
            pair=pair,
            session_start_utc=session_start,
            lookback_minutes=30,
        )

    def _detect_fcr(
        self,
        state: StrategyState,
        pip_size: float,
    ) -> dict[str, Any] | None:
        """Run FCR detection on buffered M5 candles."""
        return self._signal_pipeline.detect_fcr(state, self._modules, pip_size)

    def _detect_gap(
        self,
        state: StrategyState,
        pre_close: float,
        session_open: float,
    ) -> dict[str, Any] | None:
        """Run gap/volatility-expansion detection."""
        return self._signal_pipeline.detect_gap(
            state, self._modules, pre_close, session_open
        )

    def _detect_engulfing(
        self,
        state: StrategyState,
        pip_size: float,
    ) -> dict[str, Any] | None:
        """Run engulfing detection on buffered M1 candles."""
        return self._signal_pipeline.detect_engulfing(
            state, self._modules, self._config, pip_size
        )

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
    ) -> dict[str, Any] | None:
        """Calculate and validate position size. Returns None on failure."""
        return self._position_manager.size_position(
            state, self._modules, self._config, signal, pip_size, exchange_rate
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

    async def run_session(self) -> None:
        """Run a single trading session (delegates to SessionLifecycle)."""
        await self._lifecycle.run_session()


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------
def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="ALPHAEDGE — FCR Forex Trading Bot")
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


async def _main() -> None:
    """Async main entry point."""
    args = _parse_args()

    # ⚠️ WARNING: Live trading involves real money risk
    if args.mode == "live":
        print("=" * 60)
        print("⚠️  WARNING: LIVE TRADING MODE")
        print("⚠️  Real money is at risk. Proceed with extreme caution.")
        print("=" * 60)
        try:
            confirm = input("Type 'YES' to confirm live trading: ")
        except (EOFError, KeyboardInterrupt):
            print("\nALPHAEDGE: Live trading cancelled (no interactive input).")
            sys.exit(1)
        if confirm != "YES":
            print("ALPHAEDGE: Live trading cancelled.")
            sys.exit(0)

    setup_logging()
    config = load_config(config_path=args.config)

    if args.mode == "paper":
        config.ib.is_paper = True
        config.ib.port = 4002
        print("=" * 60)
        print("📝  ALPHAEDGE — PAPER TRADING MODE")
        print("📝  No real money at risk. IB Gateway port 4002.")
        print("=" * 60)

    strategy = FCRStrategy(config)

    # Install signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT,):
        loop.add_signal_handler(
            sig,
            lambda: asyncio.ensure_future(strategy.graceful_shutdown()),
        )
    # SIGTERM not supported on Windows
    try:
        loop.add_signal_handler(
            signal.SIGTERM,
            lambda: asyncio.ensure_future(strategy.graceful_shutdown()),
        )
    except NotImplementedError:
        pass  # Windows — SIGTERM not available

    await strategy.run_session()


if __name__ == "__main__":
    asyncio.run(_main())
