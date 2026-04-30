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

import asyncio
from dataclasses import dataclass, field
from datetime import date as _date
from types import ModuleType
from typing import Any

from alphaedge.config.loader import AppConfig
from alphaedge.core.types import (
    BracketOrderResult,
    DailyLimitResult,
    MomentumSignal,
    PositionSizeResult,
)
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
from alphaedge.utils.logger import get_logger
from alphaedge.utils.news_filter import EconomicNewsFilter, build_news_filter

logger = get_logger()


# ------------------------------------------------------------------
# Strategy state container
# ------------------------------------------------------------------
@dataclass
class StrategyState:
    """Tracks the current state of the swing strategy."""

    pair: str = ""
    signal_result: MomentumSignal | None = None
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
    last_block_reason: str = ""


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

        # Last known volatility regime — updated each bar in _detect_momentum
        self._last_regime: str = "unknown"
        self._gateway_connected: bool = False
        self._gateway_status: str = "unknown"
        self._dashboard_trade_history: list[dict[str, str | int | float]] = []
        self._dashboard_trade_seq: int = 0

        # Wire IB disconnect event for auto-reconnection
        self._broker.add_disconnect_handler(self._lifecycle._on_ib_disconnect)

    def set_gateway_health(
        self,
        *,
        gateway_connected: bool,
        gateway_status: str | None = None,
    ) -> None:
        """Persist the latest known IB Gateway availability for the dashboard."""
        self._gateway_connected = gateway_connected
        self._gateway_status = gateway_status or (
            "healthy" if gateway_connected else "down"
        )

    def _virtual_current_equity(self) -> float:
        """Return configured starting capital plus realized PnL."""
        starting_equity = self._lifecycle._session_starting_equity
        if starting_equity <= 0.0:
            starting_equity = float(self._config.trading.starting_equity)

        total_pnl = sum(state.pnl_usd_today for state in self._states.values())
        current_equity = starting_equity + total_pnl
        if current_equity <= 0.0:
            return starting_equity
        return current_equity

    def _remember_dashboard_trade(self, record: LiveTradeRecord) -> None:
        """Store a normalized closed-trade snapshot for the web dashboard."""
        self._dashboard_trade_seq += 1
        self._dashboard_trade_history.append(
            {
                "trade_id": self._dashboard_trade_seq,
                "pair": record.pair,
                "direction": "LONG" if record.direction > 0 else "SHORT",
                "entry_price": record.fill_price
                if record.fill_price > 0
                else record.entry_price,
                "exit_price": record.exit_price,
                "entry_time": record.entry_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "exit_time": (
                    record.exit_time.strftime("%Y-%m-%dT%H:%M:%SZ")
                    if record.exit_time is not None
                    else ""
                ),
                "pnl_pips": record.pnl_pips,
                "pnl_usd": record.pnl_usd,
                "outcome": record.outcome,
            }
        )
        if len(self._dashboard_trade_history) > 200:
            self._dashboard_trade_history = self._dashboard_trade_history[-200:]

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
    ) -> MomentumSignal | None:
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
        if self._config.regime_gate_enabled:
            logger.info(f"ALPHAEDGE: regime={regime} pair={state.pair}")
        else:
            logger.debug(
                f"ALPHAEDGE: regime={regime} pair={state.pair} [gate disabled]"
            )
        result = self._signal_pipeline.detect_momentum(
            state, self._modules, self._config
        )
        # Cache regime for dashboard — updated even when signal is None
        self._last_regime = regime
        if result is None:
            logger.info(
                f"ALPHAEDGE: no momentum signal pair={state.pair} "
                f"(ADX/EMA criteria not met)"
            )
            state.signal_result = None
            return None

        # Carry conflict check: block signal when carry direction contradicts momentum.
        # Mirrors the carry filter applied in backtest._backtest_pair.
        if self._config.trading.carry_enabled:
            carry = self._signal_pipeline.get_carry(state, self._config)
            if self._signal_pipeline.is_carry_conflict(result, carry):
                logger.info(
                    f"ALPHAEDGE: carry conflict BLOCK pair={state.pair} "
                    f"momentum={result['direction']} carry={carry.direction}"
                )
                state.signal_result = None
                return None

        state.signal_result = result
        return result

    async def _check_risk(
        self,
        state: StrategyState,
    ) -> DailyLimitResult:
        """Check daily risk limits before placing a trade."""
        risk_mod = self._modules.risk_manager
        equity = self._virtual_current_equity()
        for pair_state in self._states.values():
            pair_state.current_equity = equity

        result: DailyLimitResult = risk_mod.check_daily_limit(
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
    ) -> PositionSizeResult | None:
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
    ) -> BracketOrderResult | None:
        """Build bracket order and validate. Returns None on rejection."""
        return self._position_manager.build_validated_order(
            signal, lot_size, pip_size, spread_pips, self._modules, self._config
        )

    def get_live_state(self) -> dict[str, Any]:
        """Return a snapshot of current live state for the web dashboard."""
        from datetime import timedelta
        from zoneinfo import ZoneInfo

        from alphaedge.utils.timezone import (
            get_session_window_utc,
            is_session_active,
            now_utc,
        )

        def _pair_snapshot(state: StrategyState) -> dict[str, Any]:
            record = state.live_record
            signal = state.signal_result
            current_price = 0.0
            open_pnl_usd = 0.0

            if record is not None and state.is_position_open:
                live_mid = self._rt_feed.peek_mid_price(state.pair)
                if live_mid is not None:
                    current_price = live_mid
                    raw_pnl = (
                        (live_mid - record.entry_price)
                        * record.direction
                        * record.lot_size
                        * 100_000
                    )
                    open_pnl_usd = (
                        raw_pnl / record.exchange_rate
                        if record.exchange_rate > 0.0
                        else raw_pnl
                    )

            direction = ""
            if record is not None:
                direction = "LONG" if record.direction > 0 else "SHORT"
            elif signal is not None:
                signal_direction = int(signal.get("direction", 0))
                if signal_direction > 0:
                    direction = "LONG"
                elif signal_direction < 0:
                    direction = "SHORT"

            return {
                "pair": state.pair,
                "is_position_open": state.is_position_open,
                "trades_today": state.trades_today,
                "pnl_usd_today": state.pnl_usd_today,
                "pnl_pips_today": record.pnl_pips if record is not None else 0.0,
                "direction": direction,
                "entry_price": record.entry_price if record is not None else 0.0,
                "stop_loss": record.stop_loss if record is not None else 0.0,
                "take_profit": record.take_profit if record is not None else 0.0,
                "lot_size": record.lot_size if record is not None else 0.0,
                "spread_pips": record.spread_pips if record is not None else 0.0,
                "adx": record.adx_at_entry if record is not None else 0.0,
                "strength": record.strength_at_entry if record is not None else 0.0,
                "fill_status": record.fill_status if record is not None else "",
                "current_price": current_price,
                "pnl_usd": round(open_pnl_usd, 2),
            }

        # If session not yet started, show configured pairs with zero values
        if self._states:
            pairs_info = [_pair_snapshot(s) for s in self._states.values()]
        else:
            pairs_info = [
                {
                    "pair": p,
                    "is_position_open": False,
                    "trades_today": 0,
                    "pnl_usd_today": 0.0,
                    "pnl_pips_today": 0.0,
                    "direction": "",
                    "entry_price": 0.0,
                    "stop_loss": 0.0,
                    "take_profit": 0.0,
                    "lot_size": 0.0,
                    "spread_pips": 0.0,
                    "adx": 0.0,
                    "strength": 0.0,
                    "fill_status": "",
                }
                for p in self._config.trading.pairs
            ]
        total_pnl = sum(s.pnl_usd_today for s in self._states.values())
        total_trades = sum(s.trades_today for s in self._states.values())
        total_wins = sum(s.wins_today for s in self._states.values())
        total_losses = sum(s.losses_today for s in self._states.values())

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

        # Paris / CET/CEST local time
        paris_tz = ZoneInfo("Europe/Paris")
        paris_time = now.astimezone(paris_tz).strftime("%Y-%m-%dT%H:%M:%S")

        # Equity
        starting_equity = self._lifecycle._session_starting_equity
        if starting_equity <= 0.0:
            starting_equity = float(self._config.trading.starting_equity)
        current_equity = self._virtual_current_equity()

        position: dict[str, Any] = {}
        for pair_info in pairs_info:
            if pair_info["is_position_open"]:
                position = {
                    "pair": pair_info["pair"],
                    "current_price": pair_info["current_price"],
                    "pnl_usd": pair_info["pnl_usd"],
                }
                break

        # Daily loss used
        daily_loss_pct = self._config.trading.max_daily_loss_pct
        if starting_equity > 0 and current_equity > 0:
            daily_loss_used_pct = max(
                0.0, (starting_equity - current_equity) / starting_equity * 100.0
            )
        else:
            daily_loss_used_pct = 0.0

        # Consecutive losses — worst single-pair streak
        consecutive_losses = max(
            (s.consecutive_losses_count for s in self._states.values()),
            default=0,
        )

        # Trades remaining
        max_trades = self._config.trading.max_trades_per_session
        max_trades_remaining = max(0, max_trades - self._global_trades_today)

        # Carry rates — aggregate across all active pair states
        carry_rates: dict[str, Any] = {}
        for s in self._states.values():
            if s.carry_rates:
                carry_rates[s.pair] = s.carry_rates

        # Signal pipeline per pair
        signal_pipeline = [
            {
                "pair": s.pair,
                "signal": s.signal_result["direction"] if s.signal_result else None,
                "adx": (
                    float(s.signal_result.get("adx", 0.0))
                    if s.signal_result is not None
                    else None
                ),
                "strength": (
                    float(s.signal_result.get("strength", 0.0))
                    if s.signal_result is not None
                    else None
                ),
                "spread": (
                    s.live_record.spread_pips if s.live_record is not None else None
                ),
                "atr": s.current_atr_pips if s.current_atr_pips > 0 else None,
                "carry_ok": None,
            }
            for s in self._states.values()
        ]

        # News blackout — check across all configured pairs
        news_blackout_active = any(
            self._news_filter.is_news_blackout(now, pair)
            for pair in self._config.trading.pairs
        )

        # Gateway
        broker_connected = self._broker.is_connected
        gateway_connected = bool(
            broker_connected or getattr(self, "_gateway_connected", False)
        )
        gateway_status = getattr(self, "_gateway_status", "unknown")
        if broker_connected and gateway_status in {"unknown", "down"}:
            gateway_status = "healthy"
        elif not gateway_connected and gateway_status == "unknown":
            gateway_status = "down"
        gateway_uptime_s = self._broker.uptime_seconds

        return {
            "ib_connected": broker_connected,
            "gateway_connected": gateway_connected,
            "session_active": is_session_active() and not self._shutdown_requested,
            "next_session_utc": next_session_utc,
            "paris_time": paris_time,
            "pairs": pairs_info,
            "position": position,
            "daily": {
                "total_pnl_usd": total_pnl,
                "total_trades": total_trades,
                "wins_today": total_wins,
                "losses_today": total_losses,
                "pnl_pct_today": (
                    (total_pnl / starting_equity * 100.0)
                    if starting_equity > 0
                    else 0.0
                ),
            },
            # Equity & risk
            "starting_equity": starting_equity,
            "current_equity": current_equity,
            "daily_loss_limit_pct": daily_loss_pct,
            "daily_loss_used_pct": daily_loss_used_pct,
            "consecutive_losses": consecutive_losses,
            "max_trades_remaining": max_trades_remaining,
            # Signal pipeline
            "signal_pipeline": signal_pipeline,
            # System health
            "gateway_status": gateway_status,
            "gateway_uptime_s": gateway_uptime_s,
            "last_reconcile_utc": self._lifecycle._last_reconcile_utc,
            "reconcile_drift_usd": self._lifecycle._last_reconcile_drift_usd,
            "reconcile_has_critical": self._lifecycle._last_reconcile_has_critical,
            "news_blackout_active": news_blackout_active,
            "news_blackout_event": "",
            "regime": self._last_regime,
            # Carry
            "carry_rates": carry_rates,
            # Dashboard collections
            "trade_history": list(self._dashboard_trade_history),
        }

    async def run_session(self) -> None:
        """Run a single trading session (delegates to SessionLifecycle)."""
        await self._lifecycle.run_session()
