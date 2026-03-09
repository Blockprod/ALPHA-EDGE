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

from alphaedge.config.constants import (
    IB_HIST_TIMEOUT_SECONDS,
    IB_TIMEOUT_SECONDS,
    TF_M1,
    TF_M5,
)
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
    raw_date = bar.date
    if isinstance(raw_date, datetime):
        dt = raw_date if raw_date.tzinfo else raw_date.replace(tzinfo=get_tz_utc())
    else:
        # Plain date — assume midnight UTC
        dt = datetime(raw_date.year, raw_date.month, raw_date.day, tzinfo=get_tz_utc())
    epoch = int(dt.timestamp())

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
# M1 bar aggregator — converts 5-second bars into M1 candles
# ------------------------------------------------------------------
class M1BarAggregator:
    """
    Aggregates 5-second real-time bars into complete M1 candles.

    Accumulates incoming 5s bars and emits a single M1 candle
    when the minute boundary is crossed.
    """

    def __init__(self) -> None:
        """Initialize the aggregator with empty buffers."""
        self._buffer: dict[str, list[dict[str, Any]]] = {}
        self._current_minute: dict[str, int] = {}

    def _get_minute(self, candle: dict[str, Any]) -> int:
        """Extract the minute timestamp (floored) from a candle."""
        ts: int = candle["timestamp"]
        return ts - (ts % 60)

    def _build_m1(self, bars: list[dict[str, Any]]) -> dict[str, Any]:
        """Build a single M1 candle from accumulated 5s bars."""
        return {
            "open": bars[0]["open"],
            "high": max(b["high"] for b in bars),
            "low": min(b["low"] for b in bars),
            "close": bars[-1]["close"],
            "volume": sum(b["volume"] for b in bars),
            "timestamp": bars[0]["timestamp"] - (bars[0]["timestamp"] % 60),
            "datetime": bars[0]["datetime"],
        }

    def process(
        self,
        pair: str,
        bar_5s: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Process an incoming 5-second bar.

        Returns a completed M1 candle when the minute boundary
        is crossed, otherwise returns None.
        """
        bar_minute = self._get_minute(bar_5s)

        if pair not in self._current_minute:
            # First bar for this pair — start accumulating
            self._current_minute[pair] = bar_minute
            self._buffer[pair] = [bar_5s]
            return None

        if bar_minute == self._current_minute[pair]:
            # Same minute — keep accumulating
            self._buffer[pair].append(bar_5s)
            return None

        # Minute boundary crossed — emit completed M1 candle
        completed_bars = self._buffer[pair]
        m1_candle = self._build_m1(completed_bars)

        # Start new minute
        self._current_minute[pair] = bar_minute
        self._buffer[pair] = [bar_5s]

        return m1_candle

    def flush(self, pair: str) -> dict[str, Any] | None:
        """Flush remaining bars for a pair as a partial M1 candle."""
        if pair in self._buffer and self._buffer[pair]:
            m1_candle = self._build_m1(self._buffer[pair])
            self._buffer[pair] = []
            if pair in self._current_minute:
                del self._current_minute[pair]
            return m1_candle
        return None

    def reset(self) -> None:
        """Clear all buffers."""
        self._buffer.clear()
        self._current_minute.clear()


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
            timeout=IB_HIST_TIMEOUT_SECONDS,
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

    async def fetch_bars_chunked(
        self,
        pair: str,
        timeframe: str,
        start_dt: datetime,
        end_dt: datetime,
    ) -> list[dict[str, Any]]:
        """
        Fetch historical bars in chunks to respect IB per-request duration limits.

        IB limits per request:
        - 1 min  bars → max 7 calendar days
        - 5 mins bars → max 30 calendar days

        Parameters
        ----------
        pair : str
            Currency pair (e.g., 'EURUSD').
        timeframe : str
            IB bar size string (e.g., '1 min', '5 mins').
        start_dt : datetime
            Earliest bar datetime (UTC).
        end_dt : datetime
            Latest bar datetime (UTC, usually now).

        Returns
        -------
        list[dict]
            Sorted, deduplicated candle dicts covering [start_dt, end_dt].
        """
        # IB per-request limits
        if "1 min" in timeframe:
            chunk_days = 7
        elif "5 min" in timeframe:
            chunk_days = 30
        else:
            chunk_days = 365

        all_candles: list[dict[str, Any]] = []
        current_end = end_dt
        max_retries = 3
        retry_delay = 15.0  # seconds between retries on timeout

        while current_end > start_dt:
            remaining = (current_end - start_dt).days
            days = min(chunk_days, remaining) if remaining > 0 else chunk_days
            if days <= 0:
                break

            chunk: list[dict[str, Any]] = []
            for attempt in range(1, max_retries + 1):
                chunk = await self.fetch_bars(
                    pair=pair,
                    timeframe=timeframe,
                    duration=f"{days} D",
                    end_dt=current_end,
                )
                if chunk:
                    break
                if attempt < max_retries:
                    logger.warning(
                        f"ALPHAEDGE chunk retry {attempt}/{max_retries}: "
                        f"{pair} {timeframe} ending {current_end.date()}"
                    )
                    await asyncio.sleep(retry_delay)
            if chunk:
                all_candles.extend(chunk)
            else:
                logger.warning(
                    f"ALPHAEDGE skipping chunk after {max_retries} attempts: "
                    f"{pair} {timeframe} ending {current_end.date()}"
                )

            current_end -= timedelta(days=days)

        # Sort by datetime and deduplicate on timestamp
        seen: set[int] = set()
        unique: list[dict[str, Any]] = []
        for bar in sorted(all_candles, key=lambda b: b["timestamp"]):
            ts = bar["timestamp"]
            if ts not in seen:
                seen.add(ts)
                unique.append(bar)

        logger.info(
            f"ALPHAEDGE chunked fetch: {pair} {timeframe} "
            f"{len(unique)} bars from {start_dt.date()} to {end_dt.date()}"
        )
        return unique

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
        self._aggregator = M1BarAggregator()

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
        """Handle incoming 5s bar updates and aggregate into M1."""
        if not has_new or not bars:
            return

        bar_5s = _bar_to_dict(bars[-1])
        m1_candle = self._aggregator.process(pair, bar_5s)
        if m1_candle is not None:
            for callback in self._bar_callbacks:
                callback(pair, m1_candle)

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
        self._aggregator.reset()

    async def get_live_spread(self, pair: str) -> float | None:
        """
        Get the current bid/ask spread for a pair.

        Parameters
        ----------
        pair : str
            Currency pair.

        Returns
        -------
        float | None
            Current spread in price (not pips), or None if unavailable.
        """
        self._broker._ensure_connected()
        await self._broker._throttler.acquire()

        try:
            contract = build_forex_contract(pair)
            self._broker.ib.reqMktData(contract)
            await asyncio.sleep(1.0)  # Allow data to arrive

            ticker = self._broker.ib.ticker(contract)
            if ticker and ticker.bid > 0 and ticker.ask > 0:
                return float(ticker.ask - ticker.bid)
            return None
        except Exception:
            logger.exception(f"ALPHAEDGE get_live_spread failed: {pair}")
            return None

    async def get_mid_price(self, pair: str) -> float | None:
        """
        Get the current mid price for a pair.

        Parameters
        ----------
        pair : str
            Currency pair.

        Returns
        -------
        float | None
            Mid price ((bid + ask) / 2), or None if unavailable.
        """
        self._broker._ensure_connected()
        await self._broker._throttler.acquire()

        try:
            contract = build_forex_contract(pair)
            self._broker.ib.reqMktData(contract)
            await asyncio.sleep(1.0)

            ticker = self._broker.ib.ticker(contract)
            if ticker and ticker.bid > 0 and ticker.ask > 0:
                return float((ticker.bid + ticker.ask) / 2.0)
            return None
        except Exception:
            logger.exception(f"ALPHAEDGE get_mid_price failed: {pair}")
            return None


if __name__ == "__main__":
    print("ALPHAEDGE — Data Feed module loaded (standalone test)")
    print("  Requires IB Gateway running for full test.")
    print("  Supported timeframes: M1, M5")
    print("  Data type: MIDPOINT (Forex)")
