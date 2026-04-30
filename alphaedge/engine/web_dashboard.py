# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/engine/web_dashboard.py
# DESCRIPTION  : FastAPI web dashboard with REST + WebSocket
# AUTHOR       : ALPHAEDGE Dev Team
# PYTHON       : 3.11.9
# ============================================================
"""ALPHAEDGE — FastAPI web dashboard: REST API + WebSocket live feed."""

from __future__ import annotations

import asyncio
import hmac
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any, Protocol

from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, status
from fastapi.responses import HTMLResponse

from alphaedge.config.constants import PROJECT_TITLE, PROJECT_VERSION
from alphaedge.utils.logger import get_logger

logger = get_logger()


# ------------------------------------------------------------------
# WebSocket client protocol (allows testing with fake objects)
# ------------------------------------------------------------------
class WSClient(Protocol):
    """Structural type for any object that can send text over a socket."""

    async def send_text(self, data: str) -> None: ...


# ------------------------------------------------------------------
# Data models
# ------------------------------------------------------------------
@dataclass
class TradeHistoryEntry:
    """A single trade record for the web dashboard."""

    trade_id: int
    pair: str
    direction: str
    entry_price: float
    exit_price: float
    entry_time: str
    exit_time: str
    pnl_pips: float
    pnl_usd: float
    outcome: str


@dataclass
class EquityPoint:
    """A single point on the equity curve."""

    timestamp: str
    equity: float


@dataclass
class DashboardLogEntry:
    """A single runtime log line rendered by the web dashboard."""

    timestamp: str
    level: str
    source: str
    message: str
    cls: str


@dataclass
class DashboardState:
    """Complete dashboard state snapshot."""

    # ── Core (original) ──────────────────────────────────────────
    ib_connected: bool = False
    gateway_connected: bool = False
    session_active: bool = False
    utc_time: str = ""
    pairs: list[dict[str, Any]] = field(default_factory=list)
    position: dict[str, Any] = field(default_factory=dict)
    daily: dict[str, Any] = field(default_factory=dict)

    # ── Session timing ───────────────────────────────────────────
    next_session_utc: str = ""
    paris_time: str = ""

    # ── Equity & risk ────────────────────────────────────────────
    starting_equity: float = 0.0
    current_equity: float = 0.0
    daily_loss_limit_pct: float = 3.0
    daily_loss_used_pct: float = 0.0
    consecutive_losses: int = 0
    max_trades_remaining: int = -1

    # ── Signal pipeline per pair ─────────────────────────────────
    signal_pipeline: list[dict[str, Any]] = field(default_factory=list)

    # ── System health ────────────────────────────────────────────
    gateway_status: str = "unknown"
    gateway_uptime_s: int = 0
    last_reconcile_utc: str = ""
    reconcile_drift_usd: float = 0.0
    reconcile_has_critical: bool = False
    news_blackout_active: bool = False
    news_blackout_event: str = ""
    regime: str = "unknown"

    # ── Carry data ───────────────────────────────────────────────
    carry_rates: dict[str, Any] = field(default_factory=dict)

    # ── Operational log stream ───────────────────────────────────
    live_log: list[DashboardLogEntry] = field(default_factory=list)


# ------------------------------------------------------------------
# Token authentication
# ------------------------------------------------------------------
_api_token: str = ""
_MAX_LOG_LINES = 400
_LIVE_LOG_LIMIT = 120
_dashboard_log_sink_id: int | None = None


def configure_auth(token: str) -> None:
    """Set the API authentication token.

    Parameters
    ----------
    token:
        Secret token string for API access.
    """
    global _api_token  # noqa: PLW0603
    _api_token = token


def verify_token(token: str = Query(alias="token", default="")) -> str:
    """FastAPI dependency to verify the bearer token.

    Parameters
    ----------
    token:
        Token from query parameter.

    Returns
    -------
    The verified token string.

    Raises
    ------
    HTTPException
        If the token is invalid or missing.
    """
    if not _api_token:
        return token
    if not token or not hmac.compare_digest(token, _api_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token",
        )
    return token


# ------------------------------------------------------------------
# State store
# ------------------------------------------------------------------
class DashboardStore:
    """Thread-safe in-memory store for dashboard data."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._state: DashboardState = DashboardState()
        self._trades: list[TradeHistoryEntry] = []
        self._equity_curve: list[EquityPoint] = []
        self._live_log: list[DashboardLogEntry] = []
        self._ws_clients: list[WSClient] = []

    @property
    def state(self) -> DashboardState:
        """Current dashboard state."""
        with self._lock:
            return replace(
                self._state,
                live_log=list(self._live_log[-_LIVE_LOG_LIMIT:]),
            )

    def update_state(self, state: DashboardState) -> None:
        """Update the dashboard state snapshot."""
        with self._lock:
            self._state = state

    def add_trade(self, trade: TradeHistoryEntry) -> None:
        """Append a trade to the history."""
        with self._lock:
            self._trades.append(trade)

    def replace_trades(self, trades: list[TradeHistoryEntry]) -> None:
        """Replace the full trade history snapshot."""
        with self._lock:
            self._trades = list(trades)

    def get_trades(self, limit: int = 50) -> list[TradeHistoryEntry]:
        """Return the most recent trades.

        Parameters
        ----------
        limit:
            Maximum number of trades to return.
        """
        with self._lock:
            return list(self._trades[-limit:])

    def add_equity_point(self, point: EquityPoint) -> None:
        """Append an equity curve point."""
        with self._lock:
            self._equity_curve.append(point)

    def get_equity_curve(self, limit: int = 500) -> list[EquityPoint]:
        """Return the most recent equity points.

        Parameters
        ----------
        limit:
            Maximum number of points to return.
        """
        with self._lock:
            return list(self._equity_curve[-limit:])

    def add_log(self, entry: DashboardLogEntry) -> None:
        """Append a runtime log line and trim the ring buffer."""
        with self._lock:
            self._live_log.append(entry)
            overflow = len(self._live_log) - _MAX_LOG_LINES
            if overflow > 0:
                del self._live_log[:overflow]

    def get_live_log(self, limit: int = _LIVE_LOG_LIMIT) -> list[DashboardLogEntry]:
        """Return the most recent dashboard log lines."""
        with self._lock:
            return list(self._live_log[-limit:])

    def register_ws(self, ws: WSClient) -> None:
        """Register a WebSocket client."""
        with self._lock:
            self._ws_clients.append(ws)

    def unregister_ws(self, ws: WSClient) -> None:
        """Remove a WebSocket client."""
        with self._lock:
            if ws in self._ws_clients:
                self._ws_clients.remove(ws)

    @property
    def ws_clients(self) -> list[WSClient]:
        """List of active WebSocket clients."""
        with self._lock:
            return list(self._ws_clients)


def _log_css_class(level_name: str) -> str:
    """Map a log level to the dashboard row CSS class."""
    level = level_name.upper()
    if level in {"ERROR", "CRITICAL"}:
        return "err"
    if level == "WARNING":
        return "warn"
    return "dbg"


def install_dashboard_log_sink(
    store: DashboardStore | None = None,
    level: str = "INFO",
) -> int:
    """Attach a Loguru sink that streams runtime logs into the dashboard."""
    global _dashboard_log_sink_id  # noqa: PLW0603

    if _dashboard_log_sink_id is not None:
        logger.remove(_dashboard_log_sink_id)

    target_store = store if store is not None else get_store()

    def _sink(message) -> None:
        record = message.record
        timestamp = record["time"].astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        source_name = str(record["name"]).split(".")[-1]
        source = f"{source_name}:{record['function']}"
        level_name = record["level"].name
        target_store.add_log(
            DashboardLogEntry(
                timestamp=timestamp,
                level=level_name,
                source=source,
                message=str(record["message"]),
                cls=_log_css_class(level_name),
            )
        )

    handler_id = logger.add(_sink, level=level, enqueue=True)
    _dashboard_log_sink_id = handler_id
    return handler_id


def remove_dashboard_log_sink() -> None:
    """Detach the runtime log sink used by the dashboard."""
    global _dashboard_log_sink_id  # noqa: PLW0603

    if _dashboard_log_sink_id is None:
        return

    logger.remove(_dashboard_log_sink_id)
    _dashboard_log_sink_id = None


# ------------------------------------------------------------------
# Module-level store instance
# ------------------------------------------------------------------
_store = DashboardStore()


def get_store() -> DashboardStore:
    """Return the module-level DashboardStore."""
    return _store


def set_store(store: DashboardStore) -> None:
    """Replace the module-level DashboardStore (for testing)."""
    global _store  # noqa: PLW0603
    _store = store


# ------------------------------------------------------------------
# FastAPI app factory
# ------------------------------------------------------------------
def create_app(store: DashboardStore | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Parameters
    ----------
    store:
        Optional DashboardStore instance. Uses module-level store if None.

    Returns
    -------
    Configured FastAPI application.
    """
    app = FastAPI(
        title=PROJECT_TITLE,
        version=PROJECT_VERSION,
        docs_url="/docs",
    )

    def _get_store() -> DashboardStore:
        return store if store is not None else get_store()

    # ---- Live dashboard UI ----
    _ui_path = Path(__file__).parent / "dashboard_ui.html"

    @app.get("/dashboard", include_in_schema=False)
    async def dashboard_ui() -> HTMLResponse:
        content = _ui_path.read_text(encoding="utf-8")
        return HTMLResponse(
            content=content,
            headers={"Cache-Control": "no-store, must-revalidate"},
        )

    @app.get("/", include_in_schema=False)
    async def root_redirect() -> HTMLResponse:
        content = _ui_path.read_text(encoding="utf-8")
        return HTMLResponse(
            content=content,
            headers={"Cache-Control": "no-store, must-revalidate"},
        )

    # ---- Health check ----
    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": PROJECT_VERSION}

    # ---- Dashboard state ----
    @app.get("/api/state")
    async def get_state(
        _token: str = Depends(verify_token),
    ) -> dict[str, Any]:
        s = _get_store()
        return asdict(s.state)

    # ---- Trade history ----
    @app.get("/api/trades")
    async def get_trades(
        limit: int = Query(default=50, ge=1, le=500),
        _token: str = Depends(verify_token),
    ) -> list[dict[str, Any]]:
        s = _get_store()
        return [asdict(t) for t in s.get_trades(limit)]

    # ---- Equity curve ----
    @app.get("/api/equity")
    async def get_equity(
        limit: int = Query(default=500, ge=1, le=5000),
        _token: str = Depends(verify_token),
    ) -> list[dict[str, Any]]:
        s = _get_store()
        return [asdict(p) for p in s.get_equity_curve(limit)]

    # ---- WebSocket live feed ----
    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket) -> None:
        # Validate token from query param
        token = websocket.query_params.get("token", "")
        if _api_token and not hmac.compare_digest(token, _api_token):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        await websocket.accept()
        s = _get_store()
        s.register_ws(websocket)
        try:
            while True:
                # Keep connection alive; client can send pings
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_text("pong")
        except Exception:
            pass
        finally:
            s.unregister_ws(websocket)

    return app


# ------------------------------------------------------------------
# Broadcast helper
# ------------------------------------------------------------------
async def broadcast_state(store: DashboardStore) -> None:
    """Push current state to all connected WebSocket clients.

    Parameters
    ----------
    store:
        The DashboardStore containing state and client list.
    """
    if not store.ws_clients:
        return

    payload = json.dumps(asdict(store.state))
    disconnected: list[WSClient] = []

    for ws in store.ws_clients:
        try:
            await ws.send_text(payload)
        except Exception:
            disconnected.append(ws)

    for ws in disconnected:
        store.unregister_ws(ws)


# ------------------------------------------------------------------
# Live update loop (integrates with strategy engine)
# ------------------------------------------------------------------
async def run_web_dashboard(
    state_provider: Callable[[], Any],
    store: DashboardStore | None = None,
    refresh_rate: float = 1.0,
) -> None:
    """Run the dashboard state update loop.

    This coroutine periodically calls *state_provider* to get
    fresh state, updates the store, and broadcasts to WebSocket
    clients.  The FastAPI server should be running separately
    (e.g. via uvicorn).

    Parameters
    ----------
    state_provider:
        Async callable returning a dict matching DashboardState fields.
    refresh_rate:
        Update interval in seconds.
    store:
        DashboardStore to update. Uses module-level store if None.
    """
    s = store if store is not None else get_store()
    logger.info(f"Web dashboard update loop starting (refresh={refresh_rate}s)")

    while True:
        try:
            raw = await state_provider()
            now_str = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

            new_state = DashboardState(
                # ── Core ──
                ib_connected=raw.get("ib_connected", False),
                gateway_connected=raw.get("gateway_connected", False),
                session_active=raw.get("session_active", False),
                utc_time=now_str,
                pairs=raw.get("pairs", []),
                position=raw.get("position", {}),
                daily=raw.get("daily", {}),
                # ── Session timing ──
                next_session_utc=raw.get("next_session_utc", ""),
                paris_time=raw.get("paris_time", ""),
                # ── Equity & risk ──
                starting_equity=raw.get("starting_equity", 0.0),
                current_equity=raw.get("current_equity", 0.0),
                daily_loss_limit_pct=raw.get("daily_loss_limit_pct", 3.0),
                daily_loss_used_pct=raw.get("daily_loss_used_pct", 0.0),
                consecutive_losses=raw.get("consecutive_losses", 0),
                max_trades_remaining=raw.get("max_trades_remaining", 0),
                # ── Signal pipeline ──
                signal_pipeline=raw.get("signal_pipeline", []),
                # ── System health ──
                gateway_status=raw.get("gateway_status", "unknown"),
                gateway_uptime_s=raw.get("gateway_uptime_s", 0),
                last_reconcile_utc=raw.get("last_reconcile_utc", ""),
                reconcile_drift_usd=raw.get("reconcile_drift_usd", 0.0),
                reconcile_has_critical=raw.get("reconcile_has_critical", False),
                news_blackout_active=raw.get("news_blackout_active", False),
                news_blackout_event=raw.get("news_blackout_event", ""),
                regime=raw.get("regime", "unknown"),
                # ── Carry ──
                carry_rates=raw.get("carry_rates", {}),
            )
            s.update_state(new_state)

            trade_history_raw = raw.get("trade_history", [])
            s.replace_trades(
                [TradeHistoryEntry(**trade) for trade in trade_history_raw]
            )

            # Update equity curve if equity info available
            equity_val = float(
                raw.get("current_equity", 0.0)
                or raw.get("daily", {}).get("equity", 0.0)
                or raw.get("starting_equity", 0.0)
            )
            last_point = s.get_equity_curve(limit=1)
            last_equity = last_point[0].equity if last_point else None
            if equity_val > 0 and equity_val != last_equity:
                s.add_equity_point(EquityPoint(timestamp=now_str, equity=equity_val))

            await broadcast_state(s)

        except Exception as exc:
            logger.error(f"Web dashboard update error: {exc}")

        await asyncio.sleep(refresh_rate)


# ------------------------------------------------------------------
# Server launcher
# ------------------------------------------------------------------
def start_server(
    host: str = "127.0.0.1",
    port: int = 8080,
    token: str = "",
) -> None:
    """Start the uvicorn server (blocking).

    Parameters
    ----------
    host:
        Bind address. Default ``127.0.0.1`` (local only).
    port:
        Bind port.
    token:
        API authentication token. Empty = no auth.
    """
    import uvicorn

    if token:
        configure_auth(token)

    logger.info(f"Starting web dashboard on {host}:{port}")
    app = create_app()
    uvicorn.run(app, host=host, port=port, log_level="warning")
