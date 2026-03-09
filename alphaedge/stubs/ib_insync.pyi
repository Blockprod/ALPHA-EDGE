# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/stubs/ib_insync.pyi
# DESCRIPTION  : Minimal type stub for ib_insync — covers only
#                the API surface actually used in ALPHAEDGE.
#                Compliant with PEP 484. Python 3.11.9.
# AUTHOR       : ALPHAEDGE Dev Team
# LAST UPDATED : 2026-03-09
# ============================================================
# ruff: noqa: N802, N803, N815
# pylint: disable=invalid-name
"""Minimal ib_insync type stub for ALPHAEDGE (mypy --strict compatible).

Naming note: ib_insync uses camelCase for its public API (isConnected,
placeOrder, reqMktData, totalQuantity, etc.). This stub must mirror those
exact names — renaming them would break the type contract. N802/N803/N815
(Ruff) and C0103 (Pylint) are suppressed at file scope for this reason.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

# ------------------------------------------------------------------
# Event helper (ib_insync uses += for callback registration)
# ------------------------------------------------------------------
class Event:
    def __iadd__(self, handler: Any) -> Event: ...
    def __isub__(self, handler: Any) -> Event: ...

# ------------------------------------------------------------------
# Contract hierarchy
# ------------------------------------------------------------------
class Contract:
    secType: str
    symbol: str
    currency: str
    exchange: str
    localSymbol: str
    conId: int

class Forex(Contract):
    def __init__(
        self,
        pair: str = ...,
        exchange: str = ...,
        symbol: str = ...,
        currency: str = ...,
    ) -> None: ...

# ------------------------------------------------------------------
# Order hierarchy
# ------------------------------------------------------------------
class Order:
    orderId: int
    orderType: str
    totalQuantity: float
    lmtPrice: float
    auxPrice: float
    action: str
    tif: str
    parentId: int
    transmit: bool

class LimitOrder(Order):
    def __init__(
        self,
        action: str,
        totalQuantity: float,
        lmtPrice: float = ...,
    ) -> None: ...

class MarketOrder(Order):
    def __init__(
        self,
        action: str,
        totalQuantity: float,
    ) -> None: ...

class StopOrder(Order):
    def __init__(
        self,
        action: str,
        totalQuantity: float,
        auxPrice: float = ...,
    ) -> None: ...

# ------------------------------------------------------------------
# Trade / fill objects
# ------------------------------------------------------------------
class OrderStatus:
    status: str
    filled: float
    remaining: float
    avgFillPrice: float

class Trade:
    contract: Contract
    order: Order
    orderStatus: OrderStatus
    filledEvent: Event

# ------------------------------------------------------------------
# Account objects
# ------------------------------------------------------------------
class Position:
    account: str
    contract: Contract
    position: float
    avgCost: float

class AccountValue:
    account: str
    tag: str
    value: str
    currency: str

# ------------------------------------------------------------------
# Market-data objects
# ------------------------------------------------------------------
class Ticker:
    bid: float
    ask: float
    bidSize: float
    askSize: float
    last: float
    lastSize: float
    close: float
    open: float
    high: float
    low: float
    volume: float

# ------------------------------------------------------------------
# Bar objects
# ------------------------------------------------------------------
class BarData:
    # IB returns a datetime for intraday bars, a date for daily bars
    date: datetime | date
    open: float
    high: float
    low: float
    close: float
    volume: float
    barCount: int
    average: float
    hasGaps: bool

class RealTimeBarList(list[BarData]):
    updateEvent: Event

# ------------------------------------------------------------------
# Main IB class — only the methods called in ALPHAEDGE
# ------------------------------------------------------------------
class IB:
    errorEvent: Event
    disconnectedEvent: Event

    # Connection
    def isConnected(self) -> bool: ...
    async def connectAsync(
        self,
        host: str = ...,
        port: int = ...,
        clientId: int = ...,
        readonly: bool = ...,
    ) -> None: ...
    def disconnect(self) -> None: ...

    # Positions & orders
    def positions(self, account: str = ...) -> list[Position]: ...
    def openOrders(self) -> list[Order]: ...
    def placeOrder(self, contract: Contract, order: Order) -> Trade: ...
    def reqGlobalCancel(self) -> None: ...

    # Account data
    def accountSummary(self, account: str = ...) -> list[AccountValue]: ...

    # Historical data (async — called with await asyncio.wait_for)
    async def reqHistoricalDataAsync(
        self,
        contract: Contract,
        endDateTime: str = ...,
        durationStr: str = ...,
        barSizeSetting: str = ...,
        whatToShow: str = ...,
        useRTH: int | bool = ...,
        formatDate: int = ...,
        keepUpToDate: bool = ...,
        chartOptions: Any = ...,
        timeout: float = ...,
    ) -> list[BarData]: ...

    # Real-time market data
    def reqMktData(
        self,
        contract: Contract,
        genericTickList: str = ...,
        snapshot: bool = ...,
        regulatorySnapshot: bool = ...,
        mktDataOptions: Any = ...,
    ) -> Ticker: ...
    def ticker(self, contract: Contract) -> Ticker | None: ...

    # Real-time bars
    def reqRealTimeBars(
        self,
        contract: Contract,
        barSize: int = ...,
        whatToShow: str = ...,
        useRTH: bool = ...,
        realTimeBarsOptions: Any = ...,
    ) -> RealTimeBarList: ...
    def cancelRealTimeBars(self, bars: Any) -> None: ...
