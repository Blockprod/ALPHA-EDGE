# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
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
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, status

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
class DashboardState:
    """Complete dashboard state snapshot."""

    ib_connected: bool = False
    session_active: bool = False
    utc_time: str = ""
    pairs: list[dict[str, Any]] = field(default_factory=list)
    position: dict[str, Any] = field(default_factory=dict)
    daily: dict[str, Any] = field(default_factory=dict)


# ------------------------------------------------------------------
# Token authentication
# ------------------------------------------------------------------
_api_token: str = ""


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
        self._state: DashboardState = DashboardState()
        self._trades: list[TradeHistoryEntry] = []
        self._equity_curve: list[EquityPoint] = []
        self._ws_clients: list[WSClient] = []

    @property
    def state(self) -> DashboardState:
        """Current dashboard state."""
        return self._state

    def update_state(self, state: DashboardState) -> None:
        """Update the dashboard state snapshot."""
        self._state = state

    def add_trade(self, trade: TradeHistoryEntry) -> None:
        """Append a trade to the history."""
        self._trades.append(trade)

    def get_trades(self, limit: int = 50) -> list[TradeHistoryEntry]:
        """Return the most recent trades.

        Parameters
        ----------
        limit:
            Maximum number of trades to return.
        """
        return self._trades[-limit:]

    def add_equity_point(self, point: EquityPoint) -> None:
        """Append an equity curve point."""
        self._equity_curve.append(point)

    def get_equity_curve(self, limit: int = 500) -> list[EquityPoint]:
        """Return the most recent equity points.

        Parameters
        ----------
        limit:
            Maximum number of points to return.
        """
        return self._equity_curve[-limit:]

    def register_ws(self, ws: WSClient) -> None:
        """Register a WebSocket client."""
        self._ws_clients.append(ws)

    def unregister_ws(self, ws: WSClient) -> None:
        """Remove a WebSocket client."""
        if ws in self._ws_clients:
            self._ws_clients.remove(ws)

    @property
    def ws_clients(self) -> list[WSClient]:
        """List of active WebSocket clients."""
        return list(self._ws_clients)


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
                ib_connected=raw.get("ib_connected", False),
                session_active=raw.get("session_active", False),
                utc_time=now_str,
                pairs=raw.get("pairs", []),
                position=raw.get("position", {}),
                daily=raw.get("daily", {}),
            )
            s.update_state(new_state)

            # Update equity curve if equity info available
            equity_val = raw.get("daily", {}).get("equity", 0.0)
            if equity_val > 0:
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
