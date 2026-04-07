# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/tests/test_broker_reconciliation.py
# DESCRIPTION  : P1-05 — BrokerReconciler unit tests
# ============================================================
"""P1-05: BrokerReconciler — position sync, orphan detection, P&L drift."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from alphaedge.engine.broker_reconciler import (
    BrokerExecutorProtocol,
    BrokerReconciler,
    ReconciliationReport,
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _mock_position(pair: str, qty: float) -> MagicMock:
    pos = MagicMock()
    pos.position = qty
    pos.contract.pair = pair
    pos.contract.symbol = pair
    return pos


def _mock_order(pair: str) -> MagicMock:
    order = MagicMock()
    order.contract.pair = pair
    order.contract.symbol = pair
    order.orderId = 42
    order.action = "BUY"
    order.orderType = "MKT"
    return order


def _make_executor(
    positions: list[Any] | None = None,
    orders: list[Any] | None = None,
    equity: float = 0.0,
) -> MagicMock:
    executor = MagicMock()
    executor.get_open_positions = AsyncMock(return_value=positions or [])
    executor.get_open_orders = AsyncMock(return_value=orders or [])
    executor.get_account_equity = AsyncMock(return_value=equity)
    return executor


@dataclass
class _FakeState:
    """Minimal StrategyState stand-in for testing."""

    pair: str = ""
    is_position_open: bool = False
    pnl_usd_today: float = 0.0
    daily_bars: list[Any] = field(default_factory=list)


# ==================================================================
# Tests — position sync (P1-01 / P1-02)
# ==================================================================
class TestPositionSync:
    """Reconciler corrects is_position_open based on live IB positions."""

    @pytest.mark.asyncio()
    async def test_open_position_sets_flag(self) -> None:
        """IB reports open position → is_position_open corrected to True."""
        executor = _make_executor(positions=[_mock_position("EURUSD", 100_000)])
        states: dict[str, _FakeState] = {
            "EURUSD": _FakeState(pair="EURUSD", is_position_open=False)
        }
        reconciler = BrokerReconciler(cast(BrokerExecutorProtocol, executor))

        report = await reconciler.reconcile(states)

        assert states["EURUSD"].is_position_open is True
        assert "EURUSD" in report.pairs_corrected

    @pytest.mark.asyncio()
    async def test_closed_position_clears_flag(self) -> None:
        """IB reports no open positions → is_position_open corrected to False."""
        executor = _make_executor(positions=[])
        states: dict[str, _FakeState] = {
            "EURUSD": _FakeState(pair="EURUSD", is_position_open=True)
        }
        reconciler = BrokerReconciler(cast(BrokerExecutorProtocol, executor))

        report = await reconciler.reconcile(states)

        assert states["EURUSD"].is_position_open is False
        assert "EURUSD" in report.pairs_corrected

    @pytest.mark.asyncio()
    async def test_already_consistent_no_correction(self) -> None:
        """State already matches IB → pairs_corrected is empty."""
        executor = _make_executor(positions=[_mock_position("EURUSD", 100_000)])
        states: dict[str, _FakeState] = {
            "EURUSD": _FakeState(pair="EURUSD", is_position_open=True)
        }
        reconciler = BrokerReconciler(cast(BrokerExecutorProtocol, executor))

        report = await reconciler.reconcile(states)

        assert states["EURUSD"].is_position_open is True
        assert report.pairs_corrected == []

    @pytest.mark.asyncio()
    async def test_zero_qty_position_ignored(self) -> None:
        """IB position with qty=0 is treated as no position."""
        executor = _make_executor(positions=[_mock_position("EURUSD", 0)])
        states: dict[str, _FakeState] = {
            "EURUSD": _FakeState(pair="EURUSD", is_position_open=True)
        }
        reconciler = BrokerReconciler(cast(BrokerExecutorProtocol, executor))

        report = await reconciler.reconcile(states)

        assert states["EURUSD"].is_position_open is False
        assert "EURUSD" in report.pairs_corrected


# ==================================================================
# Tests — orphan detection (P1-01 / P1-02)
# ==================================================================
class TestOrphanDetection:
    """Reconciler detects positions and orders unknown to the bot."""

    @pytest.mark.asyncio()
    async def test_orphan_position_detected(self) -> None:
        """Unknown pair with IB position → reported as orphan, has_critical True."""
        executor = _make_executor(positions=[_mock_position("GBPJPY", 50_000)])
        states: dict[str, _FakeState] = {
            "EURUSD": _FakeState(pair="EURUSD", is_position_open=False)
        }
        reconciler = BrokerReconciler(cast(BrokerExecutorProtocol, executor))

        report = await reconciler.reconcile(
            states,
            traded_pairs={"EURUSD"},
        )

        assert "GBPJPY" in report.orphan_pairs
        assert report.has_critical is True
        assert report.pairs_corrected == []

    @pytest.mark.asyncio()
    async def test_orphan_order_counted(self) -> None:
        """Open order on tracked pair is counted as orphan_order_count."""
        executor = _make_executor(
            positions=[],
            orders=[_mock_order("EURUSD")],
        )
        states: dict[str, _FakeState] = {
            "EURUSD": _FakeState(pair="EURUSD", is_position_open=False)
        }
        reconciler = BrokerReconciler(cast(BrokerExecutorProtocol, executor))

        report = await reconciler.reconcile(
            states,
            traded_pairs={"EURUSD"},
        )

        assert report.orphan_order_count == 1
        assert report.has_critical is False  # only orphan positions are critical

    @pytest.mark.asyncio()
    async def test_no_orphans_clean_report(self) -> None:
        """Clean state yields empty orphan fields and has_critical False."""
        executor = _make_executor(positions=[], orders=[])
        states: dict[str, _FakeState] = {
            "EURUSD": _FakeState(pair="EURUSD", is_position_open=False)
        }
        reconciler = BrokerReconciler(cast(BrokerExecutorProtocol, executor))

        report = await reconciler.reconcile(states)

        assert report.orphan_pairs == []
        assert report.orphan_order_count == 0
        assert report.has_critical is False


# ==================================================================
# Tests — P&L drift (P1-04)
# ==================================================================
class TestPnlDrift:
    """Reconciler detects P&L divergence between local state and IB equity."""

    @pytest.mark.asyncio()
    async def test_no_drift_when_consistent(self) -> None:
        """Local P&L matches IB delta → drift near zero."""
        starting_equity = 10_000.0
        local_pnl = 50.0
        live_equity = starting_equity + local_pnl  # exact match

        executor = _make_executor(positions=[], equity=live_equity)
        states: dict[str, _FakeState] = {
            "EURUSD": _FakeState(pair="EURUSD", pnl_usd_today=local_pnl)
        }
        reconciler = BrokerReconciler(cast(BrokerExecutorProtocol, executor))

        report = await reconciler.reconcile(
            states,
            starting_equity=starting_equity,
        )

        assert report.pnl_drift_usd == pytest.approx(0.0, abs=0.01)
        assert report.pnl_drift_pct == pytest.approx(0.0, abs=0.01)

    @pytest.mark.asyncio()
    async def test_drift_detected_above_threshold(self) -> None:
        """P&L drift > 1% starting_equity → pnl_drift_pct > 1.0."""
        starting_equity = 10_000.0
        local_pnl = 0.0  # bot thinks P&L is 0
        live_equity = 10_200.0  # IB equity is up $200 (2% drift)

        executor = _make_executor(positions=[], equity=live_equity)
        states: dict[str, _FakeState] = {
            "EURUSD": _FakeState(pair="EURUSD", pnl_usd_today=local_pnl)
        }
        reconciler = BrokerReconciler(cast(BrokerExecutorProtocol, executor))

        report = await reconciler.reconcile(
            states,
            starting_equity=starting_equity,
        )

        assert report.pnl_drift_usd == pytest.approx(200.0, abs=0.01)
        assert report.pnl_drift_pct == pytest.approx(2.0, abs=0.01)

    @pytest.mark.asyncio()
    async def test_pnl_drift_skipped_when_no_starting_equity(self) -> None:
        """starting_equity=0 → equity not fetched, drift fields stay zero."""
        executor = _make_executor(equity=12_000.0)
        states: dict[str, _FakeState] = {}
        reconciler = BrokerReconciler(cast(BrokerExecutorProtocol, executor))

        report = await reconciler.reconcile(states)

        executor.get_account_equity.assert_not_called()
        assert report.pnl_drift_usd == 0.0
        assert report.pnl_drift_pct == 0.0

    @pytest.mark.asyncio()
    async def test_multi_pair_pnl_summed(self) -> None:
        """Local P&L is summed across all pairs before computing drift."""
        starting_equity = 10_000.0
        live_equity = 10_000.0 + 30.0  # IB sees +$30

        executor = _make_executor(positions=[], equity=live_equity)
        states: dict[str, _FakeState] = {
            "EURUSD": _FakeState(pair="EURUSD", pnl_usd_today=20.0),
            "USDJPY": _FakeState(pair="USDJPY", pnl_usd_today=10.0),
        }
        reconciler = BrokerReconciler(cast(BrokerExecutorProtocol, executor))

        report = await reconciler.reconcile(
            states,
            starting_equity=starting_equity,
        )

        # local_pnl = 30, ib_pnl = 30 → drift = 0
        assert report.pnl_drift_usd == pytest.approx(0.0, abs=0.01)


# ==================================================================
# Tests — exception resilience
# ==================================================================
class TestExceptionResilience:
    """Reconciler handles IB call failures gracefully."""

    @pytest.mark.asyncio()
    async def test_position_sync_failure_returns_empty_report(self) -> None:
        """get_open_positions raises → report has empty corrected/orphan lists."""
        executor = MagicMock()
        executor.get_open_positions = AsyncMock(side_effect=ConnectionError("IB down"))
        executor.get_open_orders = AsyncMock(return_value=[])

        states: dict[str, _FakeState] = {
            "EURUSD": _FakeState(pair="EURUSD", is_position_open=True)
        }
        reconciler = BrokerReconciler(cast(BrokerExecutorProtocol, executor))

        report = await reconciler.reconcile(states)

        # Must not raise; state unchanged; report is empty
        assert states["EURUSD"].is_position_open is True
        assert report.pairs_corrected == []
        assert report.orphan_pairs == []

    @pytest.mark.asyncio()
    async def test_orphan_order_failure_does_not_abort(self) -> None:
        """get_open_orders raises → position sync still completes."""
        executor = _make_executor(positions=[_mock_position("EURUSD", 100_000)])
        executor.get_open_orders = AsyncMock(side_effect=RuntimeError("timeout"))

        states: dict[str, _FakeState] = {
            "EURUSD": _FakeState(pair="EURUSD", is_position_open=False)
        }
        reconciler = BrokerReconciler(cast(BrokerExecutorProtocol, executor))

        report = await reconciler.reconcile(states)

        # Position sync still completed despite order check failure
        assert states["EURUSD"].is_position_open is True
        assert "EURUSD" in report.pairs_corrected


# ==================================================================
# Tests — ReconciliationReport dataclass contract
# ==================================================================
class TestReconciliationReport:
    """ReconciliationReport defaults and field semantics."""

    def test_defaults_are_clean(self) -> None:
        """Default report represents a clean reconciliation pass."""
        report = ReconciliationReport()

        assert report.pairs_corrected == []
        assert report.orphan_pairs == []
        assert report.orphan_order_count == 0
        assert report.pnl_drift_usd == 0.0
        assert report.pnl_drift_pct == 0.0
        assert report.has_critical is False

    def test_has_critical_true_when_orphan(self) -> None:
        """has_critical is True when orphan_pairs is non-empty (set explicitly)."""
        report = ReconciliationReport(orphan_pairs=["GBPJPY"], has_critical=True)
        assert report.has_critical is True
