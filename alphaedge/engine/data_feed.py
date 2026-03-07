# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/engine/data_feed.py
# DESCRIPTION  : Async real-time and historical data feed from IB
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: IB market data feed handler."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

from ib_insync import BarData, Contract

from alphaedge.config.constants import IB_TIMEOUT_SECONDS, TF_M1, TF_M5
from alphaedge.engine.broker import BrokerConnection, build_forex_contract
from alphaedge.utils.logger import get_logger
from alphaedge.utils.timezone import get_tz_utc

logger = get_logger()


# ------------------------------------------------------------------
# Convert IB BarData to a candle dict
# ------------------------------------------------------------------
def _bar_to_dict(bar: BarData) -> dict[str, Any]:
    """
    Convert an IB BarData object to a standardized candle dict.

    Parameters
    ----------
    bar : BarData
        IB bar data object.

    Returns
    -------
    dict
        Candle dict with keys: open, high, low, close, volume, timestamp.
    """
    # Convert bar date to UTC epoch
    dt = bar.date
    if not dt.tzinfo:  # type: ignore[attr-defined]
        dt = dt.replace(tzinfo=get_tz_utc())  # type: ignore[call-arg]
    epoch = int(dt.timestamp())  # type: ignore[attr-defined]

    return {
        "open": float(bar.open),
        "high": float(bar.high),
        "low": float(bar.low),
        "close": float(bar.close),
        "volume": float(bar.volume),  # tick count for Forex
        "timestamp": epoch,
        "datetime": dt,
    }


# ------------------------------------------------------------------
# Convert a list of BarData to candle dicts
# ------------------------------------------------------------------
def _bars_to_dicts(bars: list[BarData]) -> list[dict[str, Any]]:
    """Convert a list of IB BarData objects to candle dicts."""
    return [_bar_to_dict(b) for b in bars]


# ------------------------------------------------------------------
# Historical data fetcher
# ------------------------------------------------------------------
class HistoricalDataFeed:
    """Fetches historical OHLCV data from IB Gateway."""

    def __init__(self, broker: BrokerConnection) -> None:
        """Initialize with a broker connection."""
        self._broker = broker

    async def _request_bars(
        self,
        contract: Contract,
        end_str: str,
        duration: str,
        timeframe: str,
        use_rth: bool,
    ) -> list[BarData] | None:
        """Send historical data request to IB Gateway."""
        return await asyncio.wait_for(
            self._broker.ib.reqHistoricalDataAsync(
                contract,
                endDateTime=end_str,
                durationStr=duration,
                barSizeSetting=timeframe,
                whatToShow="MIDPOINT",
                useRTH=use_rth,
                formatDate=2,
            ),
            timeout=IB_TIMEOUT_SECONDS,
        )

    async def fetch_bars(
        self,
        pair: str,
        timeframe: str,
        duration: str = "1 D",
        end_dt: datetime | None = None,
        use_rth: bool = False,
    ) -> list[dict[str, Any]]:
        """Fetch historical bars from IB for a given pair and timeframe."""
        self._broker._ensure_connected()
        await self._broker._throttler.acquire()

        try:
            contract = build_forex_contract(pair)
            end_str = "" if end_dt is None else end_dt.strftime("%Y%m%d-%H:%M:%S")

            bars = await self._request_bars(
                contract,
                end_str,
                duration,
                timeframe,
                use_rth,
            )

            if bars is None:
                logger.warning(f"ALPHAEDGE: No bars returned for {pair} {timeframe}")
                return []

            candles = _bars_to_dicts(bars)
            logger.debug(
                f"ALPHAEDGE fetched {len(candles)} {timeframe} bars for {pair}"
            )
            return candles
        except Exception:
            logger.exception(f"ALPHAEDGE fetch_bars failed: {pair} {timeframe}")
            return []

    async def fetch_m5_pre_session(
        self,
        pair: str,
        session_start_utc: datetime,
        lookback_minutes: int = 30,
    ) -> list[dict[str, Any]]:
        """
        Fetch M5 bars before NYSE session open for FCR detection.

        Parameters
        ----------
        pair : str
            Currency pair.
        session_start_utc : datetime
            UTC datetime of session start.
        lookback_minutes : int
            Minutes before session to fetch.

        Returns
        -------
        list[dict]
            M5 candle dicts.
        """
        return await self.fetch_bars(
            pair=pair,
            timeframe=TF_M5,
            duration=f"{lookback_minutes * 60} S",
            end_dt=session_start_utc,
        )

    async def fetch_m1_session(
        self,
        pair: str,
        session_start_utc: datetime,
        minutes: int = 60,
    ) -> list[dict[str, Any]]:
        """
        Fetch M1 bars during the NYSE session window.

        Parameters
        ----------
        pair : str
            Currency pair.
        session_start_utc : datetime
            UTC datetime of session start.
        minutes : int
            Number of minutes of session data to fetch.

        Returns
        -------
        list[dict]
            M1 candle dicts.
        """
        end_dt = session_start_utc + timedelta(minutes=minutes)
        return await self.fetch_bars(
            pair=pair,
            timeframe=TF_M1,
            duration=f"{minutes * 60} S",
            end_dt=end_dt,
        )


# ------------------------------------------------------------------
# Real-time tick data streamer
# ------------------------------------------------------------------
class RealtimeDataFeed:
    """Streams real-time M1 bar data from IB Gateway."""

    def __init__(self, broker: BrokerConnection) -> None:
        """Initialize with a broker connection."""
        self._broker = broker
        self._subscriptions: dict[str, Any] = {}
        self._bar_callbacks: list[Any] = []

    def on_bar(self, callback: Any) -> None:
        """
        Register a callback for new bar events.

        Parameters
        ----------
        callback : callable
            Function to call with (pair, candle_dict) on each bar.
        """
        self._bar_callbacks.append(callback)

    async def subscribe(self, pair: str) -> None:
        """
        Subscribe to real-time 5-second bars for a pair.

        Parameters
        ----------
        pair : str
            Currency pair to subscribe to.
        """
        self._broker._ensure_connected()
        await self._broker._throttler.acquire()

        try:
            contract = build_forex_contract(pair)

            # Request real-time bars (5-second granularity)
            bars = self._broker.ib.reqRealTimeBars(
                contract,
                barSize=5,
                whatToShow="MIDPOINT",
                useRTH=False,
            )
            self._subscriptions[pair] = bars

            # Set up bar update handler
            bars.updateEvent += lambda bars, has_new: self._on_bar_update(
                pair, bars, has_new
            )
            logger.info(f"ALPHAEDGE subscribed to real-time bars: {pair}")
        except Exception:
            logger.exception(f"ALPHAEDGE subscribe failed: {pair}")

    def _on_bar_update(
        self,
        pair: str,
        bars: Any,
        has_new: bool,
    ) -> None:
        """Handle incoming bar updates from IB."""
        if not has_new or not bars:
            return

        candle = _bar_to_dict(bars[-1])
        for callback in self._bar_callbacks:
            callback(pair, candle)

    async def unsubscribe(self, pair: str) -> None:
        """
        Unsubscribe from real-time bars for a pair.

        Parameters
        ----------
        pair : str
            Currency pair to unsubscribe from.
        """
        if pair in self._subscriptions:
            self._broker.ib.cancelRealTimeBars(self._subscriptions[pair])
            del self._subscriptions[pair]
            logger.info(f"ALPHAEDGE unsubscribed from: {pair}")

    async def unsubscribe_all(self) -> None:
        """Unsubscribe from all real-time data streams."""
        pairs = list(self._subscriptions.keys())
        for pair in pairs:
            await self.unsubscribe(pair)

    async def get_live_spread(self, pair: str) -> float:
        """
        Get the current bid/ask spread for a pair.

        Parameters
        ----------
        pair : str
            Currency pair.

        Returns
        -------
        float
            Current spread in price (not pips).
        """
        self._broker._ensure_connected()
        await self._broker._throttler.acquire()

        try:
            contract = build_forex_contract(pair)
            self._broker.ib.reqMktData(contract)
            await asyncio.sleep(1.0)  # Allow data to arrive

            ticker = self._broker.ib.ticker(contract)
            if ticker and ticker.bid > 0 and ticker.ask > 0:
                return ticker.ask - ticker.bid
            return 0.0
        except Exception:
            logger.exception(f"ALPHAEDGE get_live_spread failed: {pair}")
            return 0.0

    async def get_mid_price(self, pair: str) -> float:
        """
        Get the current mid price for a pair.

        Parameters
        ----------
        pair : str
            Currency pair.

        Returns
        -------
        float
            Mid price ((bid + ask) / 2), or 0.0 if unavailable.
        """
        self._broker._ensure_connected()
        await self._broker._throttler.acquire()

        try:
            contract = build_forex_contract(pair)
            self._broker.ib.reqMktData(contract)
            await asyncio.sleep(1.0)

            ticker = self._broker.ib.ticker(contract)
            if ticker and ticker.bid > 0 and ticker.ask > 0:
                return (ticker.bid + ticker.ask) / 2.0
            return 0.0
        except Exception:
            logger.exception(f"ALPHAEDGE get_mid_price failed: {pair}")
            return 0.0


if __name__ == "__main__":
    print("ALPHAEDGE — Data Feed module loaded (standalone test)")
    print("  Requires IB Gateway running for full test.")
    print("  Supported timeframes: M1, M5")
    print("  Data type: MIDPOINT (Forex)")
