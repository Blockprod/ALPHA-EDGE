"""Tests — RealtimeDataFeed.get_live_spread diagnostic warnings.

Scenario: verify that get_live_spread returns None and emits distinct WARNING
log messages when the ticker is None or when bid/ask quotes are zero.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest
from loguru import logger

from alphaedge.engine.data_feed import RealtimeDataFeed

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def feed() -> RealtimeDataFeed:
    broker = MagicMock()
    broker._ensure_connected = MagicMock(return_value=None)
    f = RealtimeDataFeed(broker)
    # Simulate a recent tick so staleness check passes
    f._last_tick_ts["USDJPY"] = time.monotonic()
    return f


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_live_spread_ticker_none_returns_none(
    feed: RealtimeDataFeed,
) -> None:
    """ticker is None → returns None."""
    feed._broker.ib.ticker = MagicMock(return_value=None)
    result = await feed.get_live_spread("USDJPY")
    assert result is None


@pytest.mark.asyncio
async def test_get_live_spread_ticker_none_emits_warning(
    feed: RealtimeDataFeed,
) -> None:
    """ticker is None → WARNING mentioning 'No ticker object'."""
    feed._broker.ib.ticker = MagicMock(return_value=None)

    captured: list[str] = []
    handler_id = logger.add(
        lambda msg: captured.append(msg.record["message"]),
        level="WARNING",
        format="{message}",
    )
    try:
        await feed.get_live_spread("USDJPY")
    finally:
        logger.remove(handler_id)

    assert any("No ticker object" in m for m in captured)


@pytest.mark.asyncio
async def test_get_live_spread_bid_zero_returns_none(
    feed: RealtimeDataFeed,
) -> None:
    """bid == 0 → returns None."""
    ticker = MagicMock()
    ticker.bid = 0.0
    ticker.ask = 149.5
    feed._broker.ib.ticker = MagicMock(return_value=ticker)
    result = await feed.get_live_spread("USDJPY")
    assert result is None


@pytest.mark.asyncio
async def test_get_live_spread_bid_zero_emits_warning(
    feed: RealtimeDataFeed,
) -> None:
    """bid == 0 → WARNING mentioning 'quotes not yet delivered'."""
    ticker = MagicMock()
    ticker.bid = 0.0
    ticker.ask = 149.5
    feed._broker.ib.ticker = MagicMock(return_value=ticker)

    captured: list[str] = []
    handler_id = logger.add(
        lambda msg: captured.append(msg.record["message"]),
        level="WARNING",
        format="{message}",
    )
    try:
        await feed.get_live_spread("USDJPY")
    finally:
        logger.remove(handler_id)

    assert any("quotes not yet delivered" in m for m in captured)


@pytest.mark.asyncio
async def test_get_live_spread_ask_zero_returns_none(
    feed: RealtimeDataFeed,
) -> None:
    """ask == 0 → returns None."""
    ticker = MagicMock()
    ticker.bid = 149.2
    ticker.ask = 0.0
    feed._broker.ib.ticker = MagicMock(return_value=ticker)
    result = await feed.get_live_spread("USDJPY")
    assert result is None


@pytest.mark.asyncio
async def test_get_live_spread_valid_quotes_returns_spread(
    feed: RealtimeDataFeed,
) -> None:
    """Valid bid/ask → returns ask - bid."""
    ticker = MagicMock()
    ticker.bid = 149.20
    ticker.ask = 149.23
    feed._broker.ib.ticker = MagicMock(return_value=ticker)

    result = await feed.get_live_spread("USDJPY")

    assert result == pytest.approx(0.03, abs=1e-6)
