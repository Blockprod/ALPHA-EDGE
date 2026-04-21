"""Tests — RealtimeDataFeed.on_bar idempotency.

Scenario: calling on_bar multiple times with the same callback must
register it only once (prevents double-fire after session restart).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from alphaedge.engine.data_feed import RealtimeDataFeed

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def feed() -> RealtimeDataFeed:
    """Return a RealtimeDataFeed wired to a mock broker."""
    broker = MagicMock()
    return RealtimeDataFeed(broker)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_on_bar_registers_once(feed: RealtimeDataFeed) -> None:
    """Calling on_bar twice with the same callback registers it only once."""
    cb = MagicMock()
    feed.on_bar(cb)
    feed.on_bar(cb)
    assert feed._bar_callbacks.count(cb) == 1


def test_on_bar_multiple_calls_same_callback_no_duplicate(
    feed: RealtimeDataFeed,
) -> None:
    """N calls with the same callback → exactly 1 entry in _bar_callbacks."""
    cb = MagicMock()
    for _ in range(5):
        feed.on_bar(cb)
    assert len(feed._bar_callbacks) == 1


def test_on_bar_different_callbacks_registered(feed: RealtimeDataFeed) -> None:
    """Two distinct callbacks are both registered."""
    cb1 = MagicMock()
    cb2 = MagicMock()
    feed.on_bar(cb1)
    feed.on_bar(cb2)
    assert len(feed._bar_callbacks) == 2
    assert cb1 in feed._bar_callbacks
    assert cb2 in feed._bar_callbacks


def test_on_bar_fires_once_per_candle(feed: RealtimeDataFeed) -> None:
    """Registering the same callback 3× fires it only once per M1 candle."""
    cb = MagicMock()
    feed.on_bar(cb)
    feed.on_bar(cb)
    feed.on_bar(cb)

    candle = {
        "open": 1.1,
        "high": 1.2,
        "low": 1.0,
        "close": 1.15,
        "volume": 100,
        "timestamp": 0,
        "datetime": None,
    }

    # Simulate internal dispatch (as _on_bar_update does)
    for callback in feed._bar_callbacks:
        callback("EURUSD", candle)

    cb.assert_called_once_with("EURUSD", candle)
