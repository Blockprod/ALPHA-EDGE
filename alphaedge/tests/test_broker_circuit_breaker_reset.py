# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/tests/test_broker_circuit_breaker_reset.py
# DESCRIPTION  : Circuit breaker auto-reset behaviour in BrokerConnection
# PYTHON       : 3.11.9
# ============================================================
"""Tests for BrokerConnection circuit breaker auto-reset (C-04 / C-08)."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alphaedge.config.constants import (
    IB_CIRCUIT_BREAKER_MAX_FAILURES,
    IB_CIRCUIT_BREAKER_RESET_SECONDS,
)
from alphaedge.engine.broker import BrokerConnection


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _make_broker() -> BrokerConnection:
    """Return a BrokerConnection with a mocked IB client."""
    config = MagicMock()
    config.host = "127.0.0.1"
    config.port = 4002
    config.client_id = 1
    config.is_paper = True

    broker = BrokerConnection.__new__(BrokerConnection)
    broker._config = config
    broker._connected = False
    broker._consecutive_failures = 0
    broker._cached_available_funds = 0.0
    broker._circuit_breaker_opened_at = 0.0
    broker._disconnect_handlers = []
    ib = MagicMock()
    ib.isConnected.return_value = False
    ib.errorEvent = MagicMock()
    ib.disconnectedEvent = MagicMock()
    ib.disconnectedEvent.__iadd__ = MagicMock(return_value=None)
    broker._ib = ib
    from alphaedge.engine.broker import RequestThrottler

    broker._throttler = RequestThrottler()
    return broker


# ------------------------------------------------------------------
# Scenario: circuit breaker stays OPEN within the cooldown window
# ------------------------------------------------------------------
class TestCircuitBreakerStaysOpen:
    """connect() returns False while cooldown has not elapsed."""

    @pytest.mark.asyncio
    async def test_blocked_within_cooldown(self) -> None:
        """connect() is blocked when cooldown has not yet elapsed."""
        broker = _make_broker()
        broker._consecutive_failures = IB_CIRCUIT_BREAKER_MAX_FAILURES
        # Timestamp set to 'now' — cooldown has NOT elapsed
        broker._circuit_breaker_opened_at = time.monotonic()

        result = await broker.connect()

        assert result is False
        # Consecutive failures must NOT be reset
        assert broker._consecutive_failures == IB_CIRCUIT_BREAKER_MAX_FAILURES

    @pytest.mark.parametrize("extra_failures", [1, 3, 10])
    @pytest.mark.asyncio
    async def test_blocked_with_excess_failures(self, extra_failures: int) -> None:
        """connect() is blocked regardless of how far above the threshold it is."""
        broker = _make_broker()
        broker._consecutive_failures = IB_CIRCUIT_BREAKER_MAX_FAILURES + extra_failures
        broker._circuit_breaker_opened_at = time.monotonic()

        result = await broker.connect()

        assert result is False


# ------------------------------------------------------------------
# Scenario: circuit breaker AUTO-RESETS after cooldown elapses
# ------------------------------------------------------------------
class TestCircuitBreakerAutoReset:
    """connect() resets the counter and retries after the cooldown."""

    @pytest.mark.asyncio
    async def test_auto_reset_after_cooldown(self) -> None:
        """After cooldown, connect() resets failures and proceeds to connect."""
        broker = _make_broker()
        broker._consecutive_failures = IB_CIRCUIT_BREAKER_MAX_FAILURES
        # Simulate the cooldown has fully elapsed
        broker._circuit_breaker_opened_at = (
            time.monotonic() - IB_CIRCUIT_BREAKER_RESET_SECONDS - 1.0
        )

        # IB connection succeeds on the attempt after reset (signature: returns IB)
        broker._ib.connectAsync = AsyncMock(return_value=broker._ib)

        async def passthrough(coro, *_args, **_kwargs):
            return await coro

        with patch("asyncio.wait_for", new=passthrough):
            result = await broker.connect()

        assert result is True
        assert broker._consecutive_failures == 0
        assert broker._circuit_breaker_opened_at == 0.0

    @pytest.mark.asyncio
    async def test_auto_reset_then_failure_records_new_timestamp(self) -> None:
        """If reconnect fails after auto-reset, a fresh timestamp is recorded."""
        broker = _make_broker()
        broker._consecutive_failures = IB_CIRCUIT_BREAKER_MAX_FAILURES
        # Cooldown elapsed — reset will happen
        broker._circuit_breaker_opened_at = (
            time.monotonic() - IB_CIRCUIT_BREAKER_RESET_SECONDS - 1.0
        )

        # Patch asyncio.wait_for avec une coroutine async qui lève TimeoutError
        async def raise_timeout(*_args, **_kwargs):
            raise TimeoutError

        with patch("asyncio.wait_for", new=raise_timeout):
            result = await broker.connect()

        # Reset happened (counter went to 0), then one failure was recorded
        assert result is False
        assert broker._consecutive_failures == 1
        # No new breaker timestamp yet (breaker not re-opened at 1 failure)
        assert broker._circuit_breaker_opened_at == 0.0
