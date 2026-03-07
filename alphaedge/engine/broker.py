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
import time
from typing import Any

from ib_insync import (
    IB,
    Contract,
    Forex,
    Trade,
)

from alphaedge.config.constants import (
    IB_MAX_REQUESTS_PER_10S,
    IB_PACING_WINDOW_SECONDS,
)
from alphaedge.config.loader import IBConfig
from alphaedge.utils.logger import get_logger

logger = get_logger()


# ------------------------------------------------------------------
# Request throttler for IB pacing violations
# ------------------------------------------------------------------
class RequestThrottler:
    """
    Rate limiter to avoid IB pacing violations.

    Max 50 requests per 10 seconds.
    """

    def __init__(
        self,
        max_requests: int = IB_MAX_REQUESTS_PER_10S,
        window_seconds: float = IB_PACING_WINDOW_SECONDS,
    ) -> None:
        """Initialize the throttler with limits."""
        self._max_requests = max_requests
        self._window = window_seconds
        self._timestamps: list[float] = []

    def _prune_old_timestamps(self) -> None:
        """Remove timestamps older than the pacing window."""
        cutoff = time.monotonic() - self._window
        self._timestamps = [t for t in self._timestamps if t > cutoff]

    async def acquire(self) -> None:
        """Wait until a request slot is available."""
        while True:
            self._prune_old_timestamps()
            if len(self._timestamps) < self._max_requests:
                self._timestamps.append(time.monotonic())
                return
            # Wait for the oldest request to expire
            wait_time = self._timestamps[0] + self._window - time.monotonic()
            if wait_time > 0:
                await asyncio.sleep(wait_time)


# ------------------------------------------------------------------
# Broker connection manager
# ------------------------------------------------------------------
class BrokerConnection:
    """
    Manages IB Gateway connection with auto-reconnect.

    Uses ib_insync for all broker communication.
    """

    def __init__(self, config: IBConfig) -> None:
        """Initialize broker with IB configuration."""
        self._config = config
        self._ib = IB()  # type: ignore[no-untyped-call]
        self._throttler = RequestThrottler()
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Return True if connected to IB Gateway."""
        return self._ib.isConnected()

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
        try:
            await self._ib.connectAsync(
                host=self._config.host,
                port=self._config.port,
                clientId=self._config.client_id,
                readonly=False,
            )
            self._connected = True
            logger.info(
                f"ALPHAEDGE connected to IB Gateway "
                f"{self._config.host}:{self._config.port} "
                f"(paper={self._config.is_paper})"
            )
            return True
        except Exception:
            logger.exception("ALPHAEDGE IB Gateway connection failed")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Disconnect from IB Gateway gracefully."""
        if self._ib.isConnected():
            self._ib.disconnect()  # type: ignore[no-untyped-call]
            self._connected = False
            logger.info("ALPHAEDGE disconnected from IB Gateway")

    async def reconnect(self, max_retries: int = 3) -> bool:
        """
        Attempt to reconnect to IB Gateway.

        Parameters
        ----------
        max_retries : int
            Maximum number of reconnection attempts.

        Returns
        -------
        bool
            True if reconnection was successful.
        """
        for attempt in range(1, max_retries + 1):
            logger.warning(f"ALPHAEDGE reconnect attempt {attempt}/{max_retries}")
            await self.disconnect()
            await asyncio.sleep(2.0 * attempt)  # Exponential backoff
            if await self.connect():
                return True
        logger.error("ALPHAEDGE reconnection failed after all retries")
        return False

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

    async def place_bracket_order(
        self,
        pair: str,
        direction: int,
        quantity: int,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
    ) -> list[Trade]:
        """
        Place a bracket order (entry + SL + TP) via IB Gateway.

        Parameters
        ----------
        pair : str
            Currency pair.
        direction : int
            1 for BUY, -1 for SELL.
        quantity : int
            Number of currency units.
        entry_price : float
            Limit entry price.
        stop_loss : float
            Stop loss price.
        take_profit : float
            Take profit price.

        Returns
        -------
        list[Trade]
            List of IB Trade objects for the bracket.
        """
        self._broker._ensure_connected()
        await self._throttler.acquire()

        contract = build_forex_contract(pair)
        action = "BUY" if direction == 1 else "SELL"

        # Build bracket orders
        bracket = self._broker.ib.bracketOrder(
            action=action,
            quantity=quantity,
            limitPrice=entry_price,
            takeProfitPrice=take_profit,
            stopLossPrice=stop_loss,
        )

        trades: list[Trade] = []
        for order in bracket:
            trade = self._broker.ib.placeOrder(contract, order)
            trades.append(trade)

        logger.info(
            f"ALPHAEDGE bracket order placed: {pair} {action} "
            f"qty={quantity} entry={entry_price} "
            f"SL={stop_loss} TP={take_profit}"
        )
        return trades

    async def cancel_all_orders(self) -> None:
        """Cancel all open orders."""
        self._broker._ensure_connected()
        self._broker.ib.reqGlobalCancel()  # type: ignore[no-untyped-call]
        logger.warning("ALPHAEDGE: All open orders cancelled")

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
        return self._broker.ib.positions()

    async def get_account_equity(self) -> float:
        """
        Get current account net liquidation value.

        Returns
        -------
        float
            Account equity in base currency.
        """
        self._broker._ensure_connected()
        await self._throttler.acquire()

        account_values = self._broker.ib.accountSummary()
        for av in account_values:
            if av.tag == "NetLiquidation":
                return float(av.value)
        return 0.0


if __name__ == "__main__":
    print("ALPHAEDGE — Broker module loaded (standalone test)")
    print("  Requires IB Gateway running for full test.")

    # Test contract builder
    contract = build_forex_contract("EURUSD")
    print(f"  Contract: {contract}")

    # Test throttler
    throttler = RequestThrottler()
    print(f"  Throttler max: {throttler._max_requests} per {throttler._window}s")
