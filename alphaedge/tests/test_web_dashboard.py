# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_web_dashboard.py
# DESCRIPTION  : Tests for FastAPI web dashboard
# ============================================================
"""ALPHAEDGE — T4.5: Web dashboard tests."""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import asdict
from typing import Any

import pytest
from fastapi.testclient import TestClient

from alphaedge.config.constants import PROJECT_VERSION
from alphaedge.engine.web_dashboard import (
    DashboardState,
    DashboardStore,
    EquityPoint,
    TradeHistoryEntry,
    broadcast_state,
    configure_auth,
    create_app,
    get_store,
    run_web_dashboard,
    set_store,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------
@pytest.fixture()
def store() -> DashboardStore:
    return DashboardStore()


@pytest.fixture()
def client(store: DashboardStore) -> TestClient:
    app = create_app(store=store)
    return TestClient(app)


@pytest.fixture()
def auth_client(store: DashboardStore) -> Generator[TestClient, None, None]:
    configure_auth("test-secret-token")
    app = create_app(store=store)
    yield TestClient(app)
    configure_auth("")  # reset


# ------------------------------------------------------------------
# Health endpoint
# ------------------------------------------------------------------
class TestHealthEndpoint:
    def test_health_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == PROJECT_VERSION

    def test_health_no_auth_required(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/health")
        assert resp.status_code == 200


# ------------------------------------------------------------------
# State endpoint
# ------------------------------------------------------------------
class TestStateEndpoint:
    def test_default_state(self, client: TestClient) -> None:
        resp = client.get("/api/state")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ib_connected"] is False
        assert data["pairs"] == []

    def test_updated_state(self, client: TestClient, store: DashboardStore) -> None:
        store.update_state(
            DashboardState(
                ib_connected=True,
                session_active=True,
                utc_time="2026-03-08T10:00:00Z",
                pairs=[{"pair": "EURUSD", "spread": 0.8}],
                position={"pair": "EURUSD", "pnl_usd": 50.0},
                daily={"trades_today": 1},
            )
        )
        resp = client.get("/api/state")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ib_connected"] is True
        assert data["session_active"] is True
        assert len(data["pairs"]) == 1
        assert data["position"]["pnl_usd"] == 50.0

    def test_state_requires_auth(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/api/state")
        assert resp.status_code == 401

    def test_state_with_valid_token(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/api/state?token=test-secret-token")
        assert resp.status_code == 200


# ------------------------------------------------------------------
# Trade history endpoint
# ------------------------------------------------------------------
class TestTradesEndpoint:
    def test_empty_trades(self, client: TestClient) -> None:
        resp = client.get("/api/trades")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_add_and_retrieve_trades(
        self, client: TestClient, store: DashboardStore
    ) -> None:
        for i in range(3):
            store.add_trade(
                TradeHistoryEntry(
                    trade_id=i + 1,
                    pair="EURUSD",
                    direction="BUY",
                    entry_price=1.0800 + i * 0.001,
                    exit_price=1.0830 + i * 0.001,
                    entry_time="2026-03-08T09:30:00Z",
                    exit_time="2026-03-08T09:45:00Z",
                    pnl_pips=3.0,
                    pnl_usd=30.0,
                    outcome="win",
                )
            )
        resp = client.get("/api/trades")
        assert resp.status_code == 200
        trades = resp.json()
        assert len(trades) == 3
        assert trades[0]["trade_id"] == 1

    def test_trades_limit(self, client: TestClient, store: DashboardStore) -> None:
        for i in range(10):
            store.add_trade(
                TradeHistoryEntry(
                    trade_id=i,
                    pair="EURUSD",
                    direction="BUY",
                    entry_price=1.08,
                    exit_price=1.09,
                    entry_time="",
                    exit_time="",
                    pnl_pips=10.0,
                    pnl_usd=100.0,
                    outcome="win",
                )
            )
        resp = client.get("/api/trades?limit=3")
        assert resp.status_code == 200
        trades = resp.json()
        assert len(trades) == 3
        # Should be the last 3
        assert trades[0]["trade_id"] == 7

    def test_trades_requires_auth(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/api/trades")
        assert resp.status_code == 401


# ------------------------------------------------------------------
# Equity curve endpoint
# ------------------------------------------------------------------
class TestEquityEndpoint:
    def test_empty_equity(self, client: TestClient) -> None:
        resp = client.get("/api/equity")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_equity_curve_data(self, client: TestClient, store: DashboardStore) -> None:
        for i in range(5):
            store.add_equity_point(
                EquityPoint(
                    timestamp=f"2026-03-08T09:{30 + i}:00Z",
                    equity=10000.0 + i * 50,
                )
            )
        resp = client.get("/api/equity")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 5
        assert data[0]["equity"] == 10000.0
        assert data[4]["equity"] == 10200.0

    def test_equity_limit(self, client: TestClient, store: DashboardStore) -> None:
        for i in range(20):
            store.add_equity_point(EquityPoint(timestamp=f"t{i}", equity=10000.0 + i))
        resp = client.get("/api/equity?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 5

    def test_equity_requires_auth(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/api/equity")
        assert resp.status_code == 401


# ------------------------------------------------------------------
# DashboardStore unit tests
# ------------------------------------------------------------------
class TestDashboardStore:
    def test_initial_state(self, store: DashboardStore) -> None:
        assert store.state.ib_connected is False
        assert store.state.pairs == []

    def test_update_state(self, store: DashboardStore) -> None:
        new_state = DashboardState(ib_connected=True, utc_time="now")
        store.update_state(new_state)
        assert store.state.ib_connected is True
        assert store.state.utc_time == "now"

    def test_trade_history_ordering(self, store: DashboardStore) -> None:
        for i in range(5):
            store.add_trade(
                TradeHistoryEntry(
                    trade_id=i,
                    pair="GBPUSD",
                    direction="SELL",
                    entry_price=1.30,
                    exit_price=1.29,
                    entry_time="",
                    exit_time="",
                    pnl_pips=10.0,
                    pnl_usd=100.0,
                    outcome="win",
                )
            )
        trades = store.get_trades(limit=3)
        assert len(trades) == 3
        assert trades[0].trade_id == 2

    def test_equity_curve_limit(self, store: DashboardStore) -> None:
        for i in range(100):
            store.add_equity_point(EquityPoint(timestamp=f"t{i}", equity=10000.0 + i))
        points = store.get_equity_curve(limit=10)
        assert len(points) == 10
        assert points[0].equity == 10090.0

    def test_ws_register_unregister(self, store: DashboardStore) -> None:
        # Use a mock WebSocket for unit test
        class FakeWS:
            async def send_text(self, data: str) -> None:
                pass

        ws = FakeWS()
        store.register_ws(ws)
        assert len(store.ws_clients) == 1
        store.unregister_ws(ws)
        assert len(store.ws_clients) == 0

    def test_unregister_nonexistent(self, store: DashboardStore) -> None:
        class FakeWS:
            async def send_text(self, data: str) -> None:
                pass

        ws = FakeWS()
        store.unregister_ws(ws)
        assert len(store.ws_clients) == 0


# ------------------------------------------------------------------
# Data models
# ------------------------------------------------------------------
class TestDataModels:
    def test_trade_history_entry_fields(self) -> None:
        t = TradeHistoryEntry(
            trade_id=1,
            pair="EURUSD",
            direction="BUY",
            entry_price=1.08,
            exit_price=1.09,
            entry_time="2026-03-08T09:30:00Z",
            exit_time="2026-03-08T09:45:00Z",
            pnl_pips=10.0,
            pnl_usd=100.0,
            outcome="win",
        )
        d = asdict(t)
        assert d["pair"] == "EURUSD"
        assert d["pnl_usd"] == 100.0

    def test_equity_point_fields(self) -> None:
        p = EquityPoint(timestamp="2026-03-08T10:00:00Z", equity=10500.0)
        d = asdict(p)
        assert d["timestamp"] == "2026-03-08T10:00:00Z"
        assert d["equity"] == 10500.0

    def test_dashboard_state_defaults(self) -> None:
        s = DashboardState()
        assert s.ib_connected is False
        assert s.session_active is False
        assert s.utc_time == ""
        assert s.pairs == []
        assert s.position == {}
        assert s.daily == {}

    def test_dashboard_state_serialization(self) -> None:
        s = DashboardState(
            ib_connected=True,
            pairs=[{"pair": "EURUSD"}],
            daily={"trades_today": 2},
        )
        d = asdict(s)
        assert d["ib_connected"] is True
        assert len(d["pairs"]) == 1


# ------------------------------------------------------------------
# Authentication
# ------------------------------------------------------------------
class TestAuthentication:
    def test_no_token_configured_allows_all(self, client: TestClient) -> None:
        resp = client.get("/api/state")
        assert resp.status_code == 200

    def test_wrong_token_rejected(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/api/state?token=wrong-token")
        assert resp.status_code == 401

    def test_correct_token_accepted(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/api/state?token=test-secret-token")
        assert resp.status_code == 200

    def test_empty_token_rejected_when_configured(
        self, auth_client: TestClient
    ) -> None:
        resp = auth_client.get("/api/state?token=")
        assert resp.status_code == 401


# ------------------------------------------------------------------
# WebSocket
# ------------------------------------------------------------------
class TestWebSocket:
    def test_ws_ping_pong(self, client: TestClient) -> None:
        with client.websocket_connect("/ws") as ws:
            ws.send_text("ping")
            data = ws.receive_text()
            assert data == "pong"

    def test_ws_rejected_without_token(self, store: DashboardStore) -> None:
        configure_auth("secret123")
        app = create_app(store=store)
        c = TestClient(app)
        with pytest.raises(Exception):
            with c.websocket_connect("/ws") as ws:
                ws.send_text("ping")
        configure_auth("")

    def test_ws_accepted_with_token(self, store: DashboardStore) -> None:
        configure_auth("secret123")
        app = create_app(store=store)
        c = TestClient(app)
        with c.websocket_connect("/ws?token=secret123") as ws:
            ws.send_text("ping")
            data = ws.receive_text()
            assert data == "pong"
        configure_auth("")


# ------------------------------------------------------------------
# broadcast_state
# ------------------------------------------------------------------
class TestBroadcastState:
    @pytest.mark.asyncio
    async def test_broadcast_no_clients(self, store: DashboardStore) -> None:
        # Should not raise
        await broadcast_state(store)

    @pytest.mark.asyncio
    async def test_broadcast_removes_dead_clients(self, store: DashboardStore) -> None:
        class DeadWS:
            async def send_text(self, data: str) -> None:
                raise ConnectionError("dead")

        store.register_ws(DeadWS())
        assert len(store.ws_clients) == 1
        await broadcast_state(store)
        assert len(store.ws_clients) == 0


# ------------------------------------------------------------------
# Module-level store get/set
# ------------------------------------------------------------------
class TestModuleLevelStore:
    def test_get_set_store(self) -> None:
        original = get_store()
        new = DashboardStore()
        set_store(new)
        assert get_store() is new
        set_store(original)  # restore


# ------------------------------------------------------------------
# run_web_dashboard loop
# ------------------------------------------------------------------
class TestRunWebDashboard:
    @pytest.mark.asyncio
    async def test_update_loop_populates_state(self) -> None:
        store = DashboardStore()
        call_count = 0

        async def mock_provider() -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise KeyboardInterrupt
            return {
                "ib_connected": True,
                "session_active": True,
                "pairs": [{"pair": "EURUSD"}],
                "position": {},
                "daily": {"equity": 10500.0, "trades_today": 1},
            }

        with pytest.raises(KeyboardInterrupt):
            await run_web_dashboard(
                state_provider=mock_provider,
                store=store,
                refresh_rate=0.01,
            )

        assert store.state.ib_connected is True
        assert len(store.get_equity_curve()) >= 1

    @pytest.mark.asyncio
    async def test_update_loop_handles_errors(self) -> None:
        store = DashboardStore()
        call_count = 0

        async def bad_provider() -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("test error")
            if call_count >= 2:
                raise KeyboardInterrupt
            return {}

        with pytest.raises(KeyboardInterrupt):
            await run_web_dashboard(
                state_provider=bad_provider,
                store=store,
                refresh_rate=0.01,
            )
        # Should have survived the first error
        assert call_count >= 2
