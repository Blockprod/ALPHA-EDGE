# ============================================================
# PROJECT      : ALPHAEDGE — Swing Trading Bot
# FILE         : alphaedge/engine/broker.py
# DESCRIPTION  : IB Gateway broker interface with auto-reconnect
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — Momentum+Carry Forex Trading Bot: IB Gateway broker connection."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Callable
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
    IB_CIRCUIT_BREAKER_RESET_SECONDS,
    IB_TIMEOUT_SECONDS,
    IB_TOKEN_BUCKET_BURST,
    IB_TOKEN_BUCKET_RATE,
)
from alphaedge.config.loader import IBConfig
from alphaedge.utils.logger import get_logger

logger = get_logger()

DisconnectHandler = Callable[[], object]


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
            _wait_ns = time.perf_counter_ns()
            await asyncio.sleep(wait_time)
            _waited_ms = (time.perf_counter_ns() - _wait_ns) / 1e6
            logging.getLogger(__name__).debug(
                "ALPHAEDGE throttler: waited %.1fms (tokens=%.2f)",
                _waited_ms,
                self._tokens,
            )

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
        self._throttler = RequestThrottler()
        self._connected = False
        self._consecutive_failures: int = 0
        self._cached_available_funds: float = 0.0
        self._circuit_breaker_opened_at: float = 0.0
        self._disconnect_handlers: list[DisconnectHandler] = []
        self._ib = self._build_ib_client()

    @property
    def is_connected(self) -> bool:
        """Return True if connected to IB Gateway."""
        return bool(self._ib.isConnected())

    @property
    def ib(self) -> IB:
        """Return the underlying ib_insync IB instance."""
        return self._ib

    def add_disconnect_handler(self, handler: DisconnectHandler) -> None:
        """Register a disconnect handler and bind it to the current IB client."""
        self._disconnect_handlers.append(handler)
        self._ib.disconnectedEvent += handler

    def _mark_connection_failure(
        self,
        message: str,
        *,
        log_exception: bool = False,
    ) -> bool:
        """Record a failed IB connection attempt and return False."""
        self._consecutive_failures += 1
        if self._consecutive_failures == IB_CIRCUIT_BREAKER_MAX_FAILURES:
            self._circuit_breaker_opened_at = time.monotonic()
        formatted = (
            f"{message} (failure {self._consecutive_failures}/"
            f"{IB_CIRCUIT_BREAKER_MAX_FAILURES})"
        )
        if log_exception:
            logger.exception(formatted)
        else:
            logger.error(formatted)
        self._connected = False
        return False

    def _build_ib_client(self) -> IB:
        """Create a fresh IB client and bind internal/external handlers."""
        ib_client = IB()
        ib_client.errorEvent += self._on_ib_error
        ib_client.disconnectedEvent += self._on_disconnect
        for handler in getattr(self, "_disconnect_handlers", []):
            ib_client.disconnectedEvent += handler
        return ib_client

    def _reset_ib_client(self) -> None:
        """Replace the current IB client with a fresh handler-bound instance."""
        self._ib = self._build_ib_client()

    async def connect(self) -> bool:
        """
        Establish connection to IB Gateway.

        Returns
        -------
        bool
            True if connection was successful.
        """
        if self._consecutive_failures >= IB_CIRCUIT_BREAKER_MAX_FAILURES:
            elapsed = time.monotonic() - self._circuit_breaker_opened_at
            if elapsed < IB_CIRCUIT_BREAKER_RESET_SECONDS:
                logger.critical(
                    "ALPHAEDGE circuit breaker OPEN after "
                    "%d consecutive failures — auto-reset in %.0fs",
                    self._consecutive_failures,
                    IB_CIRCUIT_BREAKER_RESET_SECONDS - elapsed,
                )
                return False
            logger.warning(
                "ALPHAEDGE: circuit breaker AUTO-RESET after %.0fs — retrying",
                elapsed,
            )
            self._consecutive_failures = 0
            self._circuit_breaker_opened_at = 0.0

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
            # Silence ib_insync's own console output (Timeout /
            # Error 162 lines) — our _on_ib_error handler takes over.
            logging.getLogger("ib_insync").setLevel(logging.CRITICAL)
            logger.info(
                f"ALPHAEDGE connected to IB Gateway "
                f"{self._config.host}:{self._config.port} "
                f"(paper={self._config.is_paper})"
            )
            return True
        except TimeoutError:
            return self._mark_connection_failure(
                "ALPHAEDGE IB Gateway connection timed out"
            )
        except (ConnectionError, OSError):
            return self._mark_connection_failure(
                "ALPHAEDGE IB Gateway connection transport failed",
                log_exception=True,
            )
        except Exception:
            return self._mark_connection_failure(
                "ALPHAEDGE IB Gateway connection failed unexpectedly",
                log_exception=True,
            )

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
            self._reset_ib_client()
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
        self._reset_ib_client()

    def _on_ib_error(  # pylint: disable=invalid-name
        self,
        reqId: int,  # noqa: N803
        errorCode: int,  # noqa: N803
        errorString: str,  # noqa: N803
        contract: Any,
    ) -> None:
        """Handle IB error events with appropriate severity logging."""
        # Informational status codes — not errors, suppress or debug only
        # 2100-2119: data farm connectivity (HMDS, HFARM, SFARM, etc.)
        # 2176: Pacing restriction lifted
        if 2100 <= errorCode <= 2176:
            logger.debug(f"ALPHAEDGE IB info {errorCode}: {errorString}")
            return

        if errorCode == 162:
            # After a request timeout, IB sends error 162 as a server-side
            # cancellation acknowledgement.  Log at DEBUG to avoid noise.
            logger.debug(f"ALPHAEDGE IB 162 (cancelled/pacing): {errorString}")
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
            contract_info = f" [{contract.symbol}]" if contract is not None else ""
            logger.warning(
                f"ALPHAEDGE IB error req={reqId} code={errorCode}"
                f"{contract_info}: {errorString}"
            )

    async def refresh_account_funds(self) -> None:
        """Refresh cached available funds from IB (call from risk-check loop)."""
        await self._throttler.acquire()
        _t0 = time.perf_counter_ns()
        account_values = await self._ib.accountSummaryAsync()
        logger.debug(
            f"LATENCE accountSummary={(time.perf_counter_ns() - _t0) / 1e6:.2f}ms"
        )
        for av in account_values:
            if av.tag == "AvailableFunds":
                self._cached_available_funds = float(av.value)
                return
        logger.warning("ALPHAEDGE: AvailableFunds tag not found in accountSummary")

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

    def _check_margin(
        self,
        quantity: int,
        entry_price: float,
        leverage_estimate: float = 50.0,
    ) -> bool:
        """Return True if available margin is sufficient for this trade.

        Uses a conservative estimate: nominal_value / leverage * 1.2 safety factor.
        Returns False on any failure (fail-closed) to avoid unsafe submissions.
        """
        available_funds = self._broker._cached_available_funds
        if available_funds <= 0.0:
            logger.warning("ALPHAEDGE: margin cache not initialized — trade blocked")
            return False
        required = (quantity * entry_price / leverage_estimate) * 1.2
        if available_funds < required:
            logger.warning(
                f"ALPHAEDGE: Insufficient margin — "
                f"available={available_funds:.2f} < required≈{required:.2f} "
                f"— trade SKIPPED"
            )
            return False
        return True

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

        if not self._check_margin(quantity, entry_price):
            return []

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
        except ValueError:
            logger.exception(
                f"ALPHAEDGE bracket order rejected before submission: {pair}"
            )
            return []
        except RuntimeError:
            logger.exception(f"ALPHAEDGE bracket order IB runtime failure: {pair}")
            return []
        except Exception:
            logger.exception(f"ALPHAEDGE bracket order failed unexpectedly: {pair}")
            return []

    async def cancel_all_orders(self) -> None:
        """Cancel all open orders."""
        self._broker._ensure_connected()
        try:
            self._broker.ib.reqGlobalCancel()
            logger.warning("ALPHAEDGE: All open orders cancelled")
        except RuntimeError:
            logger.exception("ALPHAEDGE cancel_all_orders IB runtime failure")
        except Exception:
            logger.exception("ALPHAEDGE cancel_all_orders failed unexpectedly")

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
        except RuntimeError:
            logger.exception("ALPHAEDGE get_open_positions IB runtime failure")
            return []
        except Exception:
            logger.exception("ALPHAEDGE get_open_positions failed unexpectedly")
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
        except RuntimeError:
            logger.exception("ALPHAEDGE get_open_orders IB runtime failure")
            return []
        except Exception:
            logger.exception("ALPHAEDGE get_open_orders failed unexpectedly")
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
            If NetLiquidation tag is not found in account summary after retries.
        """
        self._broker._ensure_connected()
        await self._throttler.acquire()

        # Retry up to 3 times with 2s delay — accountSummaryAsync() cache may be
        # empty right after connectAsync() before IB sends account data.
        _max_retries = 3
        for _attempt in range(_max_retries):
            try:
                account_values = await self._broker.ib.accountSummaryAsync()
                for av in account_values:
                    if av.tag == "NetLiquidation":
                        return float(av.value)
                if _attempt < _max_retries - 1:
                    logger.debug(
                        f"ALPHAEDGE get_account_equity: NetLiquidation not in cache "
                        f"(attempt {_attempt + 1}/{_max_retries}) — retrying in 2s"
                    )
                    await asyncio.sleep(2.0)
                    continue
                raise ValueError(
                    "ALPHAEDGE: NetLiquidation not found in account summary"
                )
            except ValueError as exc:
                if "NetLiquidation not found" in str(exc):
                    raise
                logger.exception(
                    "ALPHAEDGE get_account_equity invalid NetLiquidation value"
                )
                raise
            except RuntimeError:
                logger.exception("ALPHAEDGE get_account_equity IB runtime failure")
                raise
            except Exception:
                logger.exception("ALPHAEDGE get_account_equity failed unexpectedly")
                raise
        raise ValueError("ALPHAEDGE: NetLiquidation not found in account summary")


if __name__ == "__main__":
    logger.info("ALPHAEDGE — Broker module loaded (standalone test)")
    logger.info("  Requires IB Gateway running for full test.")

    # Test contract builder
    contract = build_forex_contract("EURUSD")
    logger.info(f"  Contract: {contract}")

    # Test throttler
    throttler = RequestThrottler()
    logger.info(f"  Throttler rate: {throttler._rate} req/s, burst: {throttler._burst}")
