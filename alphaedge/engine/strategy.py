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
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from alphaedge.config.constants import (
    DEFAULT_ATR_PERIOD,
    DEFAULT_MIN_ATR_RATIO,
    DEFAULT_MIN_RANGE_PIPS,
    DEFAULT_MIN_VOLUME_RATIO,
    DEFAULT_VOLUME_PERIOD,
    MAX_LOTS,
    MIN_LOTS,
    PIP_SIZES,
)
from alphaedge.config.loader import AppConfig, load_config
from alphaedge.engine.broker import BrokerConnection, OrderExecutor
from alphaedge.engine.data_feed import HistoricalDataFeed, RealtimeDataFeed
from alphaedge.utils.logger import get_logger, setup_logging
from alphaedge.utils.timezone import (
    format_dual_time,
    get_session_window_utc,
    is_session_active,
    now_utc,
)

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
# Get pip size for a given pair
# ------------------------------------------------------------------
def _get_pip_size(pair: str) -> float:
    """
    Look up the pip size for a currency pair.

    Parameters
    ----------
    pair : str
        Currency pair (e.g., 'EURUSD').

    Returns
    -------
    float
        Pip size (0.0001 or 0.01 for JPY).
    """
    return PIP_SIZES.get(pair, 0.0001)


# ------------------------------------------------------------------
# Import Cython modules with fallback to pure-Python stubs
# ------------------------------------------------------------------
def _import_core_modules() -> tuple[Any, Any, Any, Any, Any]:
    """
    Import Cython core modules, falling back to stubs if not compiled.

    Returns
    -------
    tuple
        (fcr_detector, gap_detector, engulfing_detector,
         order_manager, risk_manager)
    """
    try:
        from alphaedge.core import (  # type: ignore[attr-defined]
            engulfing_detector,
            fcr_detector,
            gap_detector,
            order_manager,
            risk_manager,
        )

        logger.info("ALPHAEDGE: Cython core modules loaded successfully")
        return (
            fcr_detector,
            gap_detector,
            engulfing_detector,
            order_manager,
            risk_manager,
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

    def __init__(self, config: AppConfig) -> None:
        """Initialize the strategy with application config."""
        self._config = config
        self._broker = BrokerConnection(config.ib)
        self._executor = OrderExecutor(self._broker)
        self._hist_feed = HistoricalDataFeed(self._broker)
        self._rt_feed = RealtimeDataFeed(self._broker)
        self._states: dict[str, StrategyState] = {}
        self._modules = _import_core_modules()

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
        fcr_mod = self._modules[0]
        result: dict[str, Any] | None = fcr_mod.detect_fcr(
            candles_data=state.m5_candles,
            min_range_pips=DEFAULT_MIN_RANGE_PIPS,
            pip_size=pip_size,
        )
        state.fcr_result = result
        return result

    def _detect_gap(
        self,
        state: StrategyState,
        pre_close: float,
        session_open: float,
    ) -> dict[str, Any] | None:
        """Run gap/volatility-expansion detection."""
        gap_mod = self._modules[1]
        result: dict[str, Any] | None = gap_mod.detect_gap(
            pre_session_m1=state.m5_candles,
            session_m1=state.m1_candles,
            pre_close=pre_close,
            session_open=session_open,
            atr_period=DEFAULT_ATR_PERIOD,
            min_atr_ratio=DEFAULT_MIN_ATR_RATIO,
        )
        state.gap_result = result
        return result

    def _detect_engulfing(
        self,
        state: StrategyState,
        pip_size: float,
    ) -> dict[str, Any] | None:
        """Run engulfing detection on buffered M1 candles."""
        if state.fcr_result is None:
            return None

        eng_mod = self._modules[2]
        result: dict[str, Any] | None = eng_mod.detect_engulfing(
            candles_data=state.m1_candles,
            fcr_high=state.fcr_result["range_high"],
            fcr_low=state.fcr_result["range_low"],
            rr_ratio=self._config.trading.rr_ratio,
            pip_size=pip_size,
            volume_period=DEFAULT_VOLUME_PERIOD,
            min_volume_ratio=DEFAULT_MIN_VOLUME_RATIO,
        )
        state.signal_result = result
        return result

    async def _check_risk(
        self,
        state: StrategyState,
    ) -> dict[str, Any]:
        """Check daily risk limits before placing a trade."""
        risk_mod = self._modules[4]
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
        risk_mod = self._modules[4]
        equity = state.current_equity or state.starting_equity
        pos_result: dict[str, Any] = risk_mod.calculate_position_size(
            account_equity=equity,
            risk_pct=self._config.trading.risk_pct,
            sl_pips=signal["risk_pips"],
            pair=state.pair,
            pip_size=pip_size,
            lot_type=self._config.trading.lot_type,
            min_lots=MIN_LOTS,
            max_lots=MAX_LOTS,
            exchange_rate=exchange_rate,
        )
        if not pos_result["is_valid"]:
            logger.warning(f"ALPHAEDGE: Invalid position size for {state.pair}")
            return None
        return pos_result

    def _build_validated_order(
        self,
        signal: dict[str, Any],
        lot_size: float,
        pip_size: float,
        spread_pips: float,
    ) -> dict[str, Any] | None:
        """Build bracket order and validate. Returns None on rejection."""
        order_mod = self._modules[3]
        bracket: dict[str, Any] = order_mod.create_bracket_order(
            direction=signal["signal"],
            entry_price=signal["entry_price"],
            stop_loss=signal["stop_loss"],
            take_profit=signal["take_profit"],
            lot_size=lot_size,
            pip_size=pip_size,
            spread_pips=spread_pips,
            max_spread_pips=self._config.trading.max_spread_pips,
            min_rr=self._config.trading.rr_ratio * 0.9,
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

    async def _execute_signal(
        self,
        state: StrategyState,
        signal: dict[str, Any],
        pip_size: float,
    ) -> bool:
        """Execute a trade signal through IB Gateway."""
        # Fetch live rate for non-USD-quoted pairs (JPY)
        exchange_rate = 0.0
        if pip_size >= 0.001:
            exchange_rate = await self._rt_feed.get_mid_price(state.pair)

        pos_result = self._size_position(
            state,
            signal,
            pip_size,
            exchange_rate,
        )
        if pos_result is None:
            return False

        spread = await self._rt_feed.get_live_spread(state.pair)
        spread_pips = spread / pip_size

        bracket = self._build_validated_order(
            signal,
            pos_result["lot_size"],
            pip_size,
            spread_pips,
        )
        if bracket is None:
            return False

        order_mod = self._modules[3]
        units = order_mod.lots_to_units(
            bracket["lot_size"],
            self._config.trading.lot_type,
        )
        trades_placed = await self._executor.place_bracket_order(
            pair=state.pair,
            direction=bracket["direction"],
            quantity=units,
            entry_price=bracket["entry_price"],
            stop_loss=bracket["stop_loss"],
            take_profit=bracket["take_profit"],
        )

        # Register fill callback to reset position flag on SL/TP exit
        for trade_obj in trades_placed:
            trade_obj.filledEvent += lambda _t, _pair=state.pair: self._on_trade_closed(
                _pair
            )

        state.trades_today += 1
        state.is_position_open = True
        return True

    def _on_trade_closed(self, pair: str) -> None:
        """Reset position flag when a bracket child (SL/TP) fills."""
        state = self._states.get(pair)
        if state:
            state.is_position_open = False
            logger.info(f"ALPHAEDGE: Position closed for {pair}")

    def _on_new_m1_bar(self, pair: str, candle: dict[str, Any]) -> None:
        """Handle incoming real-time M1 bar data."""
        state = self._states.get(pair)
        if state is None:
            return

        state.m1_candles.append(candle)
        if len(state.m1_candles) > state.max_candles:
            state.m1_candles = state.m1_candles[-state.max_candles :]
        pip_size = _get_pip_size(pair)

        # Skip if trade limit reached or position open
        if state.trades_today >= self._config.trading.max_trades_per_session:
            return
        if state.is_position_open:
            return

        # Per-pair risk cap: max 1 pair open at a time
        open_pairs = [p for p, s in self._states.items() if s.is_position_open]
        risk_mod = self._modules[4]
        pair_check: dict[str, Any] = risk_mod.check_pair_limit(
            pair=pair,
            open_pairs=open_pairs,
            max_open_pairs=1,
        )
        if not pair_check["allowed"]:
            return

        # Detect engulfing signal on each new M1 bar
        signal = self._detect_engulfing(state, pip_size)
        if signal and signal.get("detected"):
            logger.info(
                f"ALPHAEDGE SIGNAL: {pair} "
                f"{'SELL' if signal['signal'] == -1 else 'BUY'} "
                f"@ {signal['entry_price']}"
            )
            # Schedule async execution
            asyncio.ensure_future(self._execute_signal(state, signal, pip_size))

    async def run_session(self) -> None:
        """
        Run a single trading session for all configured pairs.

        This is the main entry point for the strategy.
        """
        logger.info(f"ALPHAEDGE session starting at {format_dual_time(now_utc())}")

        # Connect to IB Gateway
        if not await self._broker.connect():
            logger.error("ALPHAEDGE: Cannot start — IB Gateway unavailable")
            return

        # Get starting equity
        starting_equity = await self._executor.get_account_equity()
        session_start, _session_end = get_session_window_utc()

        # Process each pair
        for pair in self._config.trading.pairs:
            state = self._init_pair_state(pair)
            state.starting_equity = starting_equity
            state.current_equity = starting_equity

            # Fetch pre-session M5 data for FCR
            state.m5_candles = await self._fetch_pre_session_data(
                pair,
                session_start,
            )
            pip_size = _get_pip_size(pair)

            # Detect FCR
            fcr = self._detect_fcr(state, pip_size)
            if fcr:
                logger.info(
                    f"ALPHAEDGE FCR: {pair} high={fcr['range_high']} "
                    f"low={fcr['range_low']}"
                )

        # Subscribe to real-time M1 data
        self._rt_feed.on_bar(self._on_new_m1_bar)
        for pair in self._config.trading.pairs:
            await self._rt_feed.subscribe(pair)

        # Wait for session to end
        logger.info("ALPHAEDGE: Monitoring session...")
        while is_session_active():
            await asyncio.sleep(1.0)

        # Cleanup
        await self._rt_feed.unsubscribe_all()
        await self._broker.disconnect()
        logger.info(f"ALPHAEDGE session ended at {format_dual_time(now_utc())}")


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
        confirm = input("Type 'YES' to confirm live trading: ")
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
    await strategy.run_session()


if __name__ == "__main__":
    asyncio.run(_main())
