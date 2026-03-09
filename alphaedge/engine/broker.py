# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/engine/broker.py
# DESCRIPTION  : IB Gateway broker interface with auto-reconnect
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: IB Gateway broker connection."""

from __future__ import annotations

import asyncio
import random
import time
from typing import Any

from ib_insync import (
    IB,
    Contract,
    Forex,
    LimitOrder,
    MarketOrder,
    StopOrder,
    Trade,
)

from alphaedge.config.constants import (
    IB_CIRCUIT_BREAKER_MAX_FAILURES,
    IB_TIMEOUT_SECONDS,
    IB_TOKEN_BUCKET_BURST,
    IB_TOKEN_BUCKET_RATE,
)
from alphaedge.config.loader import IBConfig
from alphaedge.utils.logger import get_logger

logger = get_logger()


# ------------------------------------------------------------------
# Token-bucket rate limiter
# ------------------------------------------------------------------
class RequestThrottler:
    """
    Token-bucket rate limiter for IB pacing compliance.

    IB hard cap: 50 req/s.  We sustain 45 req/s with a burst of 10
    to keep a comfortable safety margin.  Tokens refill continuously
    at `rate` per second — no sudden 50-req avalanche possible.
    """

    def __init__(
        self,
        rate: float = IB_TOKEN_BUCKET_RATE,
        burst: int = IB_TOKEN_BUCKET_BURST,
    ) -> None:
        self._rate = rate  # tokens / second
        self._burst = burst  # max tokens in bucket
        self._tokens: float = float(burst)
        self._last_refill: float = time.monotonic()

    def _refill(self) -> None:
        """Add tokens proportional to elapsed time since last refill."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
        self._last_refill = now

    async def acquire(self) -> None:
        """Wait until one token is available, then consume it."""
        while True:
            self._refill()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return
            # Sleep until the next token is ready
            wait_time = (1.0 - self._tokens) / self._rate
            await asyncio.sleep(wait_time)

    def penalise(self) -> None:
        """Drain the bucket on a pacing violation (IB error 162)."""
        self._tokens = 0.0


# ------------------------------------------------------------------
# Broker connection manager
# ------------------------------------------------------------------
class BrokerConnection:
    """
    Manages IB Gateway connection with circuit breaker and exponential
    backoff reconnection.

    Circuit breaker opens after IB_CIRCUIT_BREAKER_MAX_FAILURES
    consecutive failures — prevents infinite retry loops.
    """

    def __init__(self, config: IBConfig) -> None:
        """Initialize broker with IB configuration."""
        self._config = config
        self._ib = IB()
        self._throttler = RequestThrottler()
        self._connected = False
        self._consecutive_failures: int = 0

    @property
    def is_connected(self) -> bool:
        """Return True if connected to IB Gateway."""
        return bool(self._ib.isConnected())

    @property
    def ib(self) -> IB:
        """Return the underlying ib_insync IB instance."""
        return self._ib

    async def connect(self) -> bool:
        """
        Establish connection to IB Gateway.

        Returns
        -------
        bool
            True if connection was successful.
        """
        if self._consecutive_failures >= IB_CIRCUIT_BREAKER_MAX_FAILURES:
            logger.critical(
                f"ALPHAEDGE circuit breaker OPEN after "
                f"{self._consecutive_failures} consecutive failures — "
                "manual intervention required"
            )
            return False

        try:
            await asyncio.wait_for(
                self._ib.connectAsync(
                    host=self._config.host,
                    port=self._config.port,
                    clientId=self._config.client_id,
                    readonly=False,
                ),
                timeout=IB_TIMEOUT_SECONDS,
            )
            self._connected = True
            self._consecutive_failures = 0
            self._ib.errorEvent += self._on_ib_error
            self._ib.disconnectedEvent += self._on_disconnect
            logger.info(
                f"ALPHAEDGE connected to IB Gateway "
                f"{self._config.host}:{self._config.port} "
                f"(paper={self._config.is_paper})"
            )
            return True
        except Exception:
            self._consecutive_failures += 1
            logger.exception(
                f"ALPHAEDGE IB Gateway connection failed "
                f"(failure {self._consecutive_failures}/"
                f"{IB_CIRCUIT_BREAKER_MAX_FAILURES})"
            )
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Disconnect from IB Gateway gracefully."""
        if self._ib.isConnected():
            self._ib.disconnect()
            self._connected = False
            logger.info("ALPHAEDGE disconnected from IB Gateway")

    async def reconnect(self, max_retries: int = 3) -> bool:
        """
        Attempt to reconnect with exponential backoff + jitter.

        Delays: 2s → 4s → 8s (capped at 30s), each ±10% jitter.
        """
        for attempt in range(1, max_retries + 1):
            await self.disconnect()
            base_delay = min(2**attempt, 30.0)
            jitter = base_delay * 0.1 * random.uniform(-1.0, 1.0)
            delay = base_delay + jitter
            logger.warning(
                f"ALPHAEDGE reconnect attempt {attempt}/{max_retries} "
                f"— waiting {delay:.1f}s"
            )
            await asyncio.sleep(delay)
            if await self.connect():
                return True
        logger.error("ALPHAEDGE reconnection failed after all retries")
        return False

    def _on_disconnect(self) -> None:
        """Fired by ib_insync when the connection drops unexpectedly."""
        logger.warning(
            f"ALPHAEDGE IB disconnected unexpectedly "
            f"({self._config.host}:{self._config.port}) — "
            "next _ensure_connected() call will reconnect"
        )
        self._connected = False
        self._ib = IB()  # fresh instance — old one is dead

    def _on_ib_error(  # pylint: disable=invalid-name
        self,
        reqId: int,  # noqa: N803
        errorCode: int,  # noqa: N803
        errorString: str,  # noqa: N803
        contract: Any,
    ) -> None:
        """Handle IB error events with appropriate severity logging."""
        if errorCode == 162:
            logger.warning(
                f"ALPHAEDGE IB PACING: Historical data pacing violation — {errorString}"
            )
            self._throttler.penalise()
        elif errorCode == 200:
            logger.error(f"ALPHAEDGE IB: No security definition — {errorString}")
        elif errorCode == 321:
            logger.error(f"ALPHAEDGE IB: Server validation error — {errorString}")
        elif errorCode == 504:
            logger.critical(f"ALPHAEDGE IB: Not connected — {errorString}")
        elif errorCode in (1100, 1101, 1102):
            logger.critical(
                f"ALPHAEDGE IB CONNECTION: code={errorCode} — {errorString}"
            )
        else:
            logger.warning(f"ALPHAEDGE IB error {errorCode}: {errorString}")

    def _ensure_connected(self) -> None:
        """Raise if not currently connected."""
        if not self._ib.isConnected():
            raise ConnectionError("ALPHAEDGE: Not connected to IB Gateway")


# ------------------------------------------------------------------
# Forex contract builder
# ------------------------------------------------------------------
def build_forex_contract(pair: str) -> Contract:
    """
    Build an IB Forex contract for IDEALPRO exchange.

    Parameters
    ----------
    pair : str
        Currency pair (e.g., 'EURUSD').

    Returns
    -------
    Contract
        IB Forex contract.
    """
    # Split pair into base/quote (e.g., 'EURUSD' → 'EUR', 'USD')
    base = pair[:3]
    quote = pair[3:]
    return Forex(pair=base + quote, exchange="IDEALPRO")


# ------------------------------------------------------------------
# Order submission helper
# ------------------------------------------------------------------
class OrderExecutor:
    """Handles bracket order submission to IB Gateway."""

    def __init__(self, broker: BrokerConnection) -> None:
        """Initialize with a broker connection."""
        self._broker = broker
        self._throttler = broker._throttler

    def _submit_bracket(
        self,
        contract: Contract,
        action: str,
        quantity: int,
        take_profit: float,
        stop_loss: float,
    ) -> list[Trade]:
        """Build and submit bracket orders (Market entry + SL/TP) to IB."""
        reverse_action = "SELL" if action == "BUY" else "BUY"

        # Parent: Market order for immediate fill
        parent = MarketOrder(action, quantity)
        parent.transmit = False

        # Take-profit: Limit child
        tp_order = LimitOrder(reverse_action, quantity, take_profit)
        tp_order.parentId = parent.orderId
        tp_order.transmit = False

        # Stop-loss: Stop child
        sl_order = StopOrder(reverse_action, quantity, stop_loss)
        sl_order.parentId = parent.orderId
        sl_order.transmit = True  # Last child transmits all

        trades: list[Trade] = []
        for order in [parent, tp_order, sl_order]:
            trade = self._broker.ib.placeOrder(contract, order)
            trades.append(trade)
        return trades

    async def place_bracket_order(
        self,
        pair: str,
        direction: int,
        quantity: int,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
    ) -> list[Trade]:
        """Place a bracket order (entry + SL + TP) via IB Gateway."""
        self._broker._ensure_connected()
        await self._throttler.acquire()

        try:
            contract = build_forex_contract(pair)
            action = "BUY" if direction == 1 else "SELL"

            trades = self._submit_bracket(
                contract,
                action,
                quantity,
                take_profit,
                stop_loss,
            )

            logger.info(
                f"ALPHAEDGE bracket order placed: {pair} {action} "
                f"qty={quantity} entry={entry_price} "
                f"SL={stop_loss} TP={take_profit}"
            )
            return trades
        except Exception:
            logger.exception(f"ALPHAEDGE bracket order failed: {pair}")
            return []

    async def cancel_all_orders(self) -> None:
        """Cancel all open orders."""
        self._broker._ensure_connected()
        try:
            self._broker.ib.reqGlobalCancel()
            logger.warning("ALPHAEDGE: All open orders cancelled")
        except Exception:
            logger.exception("ALPHAEDGE cancel_all_orders failed")

    async def get_open_positions(self) -> list[Any]:
        """
        Get all current open positions.

        Returns
        -------
        list
            List of IB Position objects.
        """
        self._broker._ensure_connected()
        await self._throttler.acquire()
        try:
            return list(self._broker.ib.positions())
        except Exception:
            logger.exception("ALPHAEDGE get_open_positions failed")
            return []

    async def get_open_orders(self) -> list[Any]:
        """
        Get all currently open orders.

        Returns
        -------
        list
            List of IB Order objects.
        """
        self._broker._ensure_connected()
        await self._throttler.acquire()
        try:
            return list(self._broker.ib.openOrders())
        except Exception:
            logger.exception("ALPHAEDGE get_open_orders failed")
            return []

    async def get_account_equity(self) -> float:
        """
        Get current account net liquidation value.

        Returns
        -------
        float
            Account equity in base currency.

        Raises
        ------
        ValueError
            If NetLiquidation tag is not found in account summary.
        """
        self._broker._ensure_connected()
        await self._throttler.acquire()

        try:
            account_values = self._broker.ib.accountSummary()
            for av in account_values:
                if av.tag == "NetLiquidation":
                    return float(av.value)
            raise ValueError("ALPHAEDGE: NetLiquidation not found in account summary")
        except ValueError:
            raise
        except Exception:
            logger.exception("ALPHAEDGE get_account_equity failed")
            raise


if __name__ == "__main__":
    print("ALPHAEDGE — Broker module loaded (standalone test)")
    print("  Requires IB Gateway running for full test.")

    # Test contract builder
    contract = build_forex_contract("EURUSD")
    print(f"  Contract: {contract}")

    # Test throttler
    throttler = RequestThrottler()
    print(f"  Throttler rate: {throttler._rate} req/s, burst: {throttler._burst}")
