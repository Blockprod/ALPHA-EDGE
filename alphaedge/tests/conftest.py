# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/tests/conftest.py
# DESCRIPTION  : Shared pytest fixtures for all test modules
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — Momentum+Carry Forex Trading Bot: pytest shared fixtures."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

import alphaedge.utils.state_persistence as _state_mod
from alphaedge.utils.state_persistence import clear_daily_state

# Force the pure-Python Cython stubs during unit tests so collection and
# assertions remain reproducible across environments with or without local
# compiled artifacts.
os.environ.setdefault("ALPHAEDGE_CORE_BACKEND", "stubs")


# ------------------------------------------------------------------
# Per-test state file isolation: redirect STATE_FILE to a unique
# tmp_path so concurrent test runners and AV scanners cannot
# interfere with each other through the shared working directory.
# Must be defined BEFORE _global_clear_daily_state so it is set up
# first and torn down last, guaranteeing all clear_daily_state()
# calls inside other fixtures see the patched path.
# ------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _isolate_state_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[None, None, None]:
    """Redirect STATE_FILE to a per-test temp directory."""
    monkeypatch.setattr(
        _state_mod, "STATE_FILE", str(tmp_path / "alphaedge_daily_state.json")
    )
    yield


# ------------------------------------------------------------------
# Global autouse: guarantee a clean state file before every test.
# This prevents tests that write the state file (e.g. via
# _persist_daily_state) from polluting subsequent tests.
# ------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _global_clear_daily_state() -> Generator[None, None, None]:
    """Delete any leftover state file before and after each test."""
    clear_daily_state()
    yield
    clear_daily_state()


# ------------------------------------------------------------------
# Sample OHLCV candle data for backtest/signal tests
# ------------------------------------------------------------------
@pytest.fixture()
def sample_m5_candles() -> list[dict[str, Any]]:
    """Return a list of sample M5 candle dicts for testing."""
    return [
        {
            "open": 1.08500,
            "high": 1.08600,
            "low": 1.08400,
            "close": 1.08550,
            "volume": 150.0,
            "timestamp": 1709200200,
        },
        {
            "open": 1.08550,
            "high": 1.08700,
            "low": 1.08450,
            "close": 1.08650,
            "volume": 200.0,
            "timestamp": 1709200500,
        },
        {
            "open": 1.08650,
            "high": 1.08750,
            "low": 1.08500,
            "close": 1.08600,
            "volume": 180.0,
            "timestamp": 1709200800,
        },
    ]


# ------------------------------------------------------------------
# Sample M1 candle data for engulfing tests
# ------------------------------------------------------------------
@pytest.fixture()
def sample_m1_candles_bearish_engulfing() -> list[dict[str, Any]]:
    """Return M1 candles forming a bearish engulfing pattern."""
    return [
        # Filler candles for volume baseline
        {
            "open": 1.08500,
            "high": 1.08520,
            "low": 1.08490,
            "close": 1.08510,
            "volume": 100.0,
        },
        {
            "open": 1.08510,
            "high": 1.08530,
            "low": 1.08500,
            "close": 1.08520,
            "volume": 110.0,
        },
        # Previous candle: bullish
        {
            "open": 1.08400,
            "high": 1.08500,
            "low": 1.08390,
            "close": 1.08480,
            "volume": 120.0,
        },
        # Current candle: bearish engulfing with high volume
        {
            "open": 1.08500,
            "high": 1.08550,
            "low": 1.08300,
            "close": 1.08350,
            "volume": 250.0,
        },
    ]


# ------------------------------------------------------------------
# Sample M1 candle data for bullish engulfing tests
# ------------------------------------------------------------------
@pytest.fixture()
def sample_m1_candles_bullish_engulfing() -> list[dict[str, Any]]:
    """Return M1 candles forming a bullish engulfing pattern."""
    return [
        {
            "open": 1.08500,
            "high": 1.08520,
            "low": 1.08490,
            "close": 1.08510,
            "volume": 100.0,
        },
        {
            "open": 1.08510,
            "high": 1.08530,
            "low": 1.08500,
            "close": 1.08520,
            "volume": 110.0,
        },
        # Previous candle: bearish
        {
            "open": 1.08700,
            "high": 1.08710,
            "low": 1.08600,
            "close": 1.08620,
            "volume": 120.0,
        },
        # Current candle: bullish engulfing with high volume
        {
            "open": 1.08600,
            "high": 1.08800,
            "low": 1.08590,
            "close": 1.08780,
            "volume": 250.0,
        },
    ]


# ------------------------------------------------------------------
# Default pip size for EUR/USD
# ------------------------------------------------------------------
@pytest.fixture()
def eurusd_pip_size() -> float:
    """Return the EUR/USD pip size."""
    return 0.0001


# ------------------------------------------------------------------
# Default pip size for USD/JPY
# ------------------------------------------------------------------
@pytest.fixture()
def usdjpy_pip_size() -> float:
    """Return the USD/JPY pip size."""
    return 0.01


# ------------------------------------------------------------------
# Pre-session M1 candles for gap detection
# ------------------------------------------------------------------
@pytest.fixture()
def pre_session_m1() -> list[dict[str, Any]]:
    """Return pre-session M1 candles for baseline ATR."""
    return [
        {
            "open": 1.08500,
            "high": 1.08510,
            "low": 1.08495,
            "close": 1.08505,
            "volume": 80.0,
        },
        {
            "open": 1.08505,
            "high": 1.08515,
            "low": 1.08498,
            "close": 1.08508,
            "volume": 85.0,
        },
        {
            "open": 1.08508,
            "high": 1.08518,
            "low": 1.08500,
            "close": 1.08512,
            "volume": 90.0,
        },
        {
            "open": 1.08512,
            "high": 1.08520,
            "low": 1.08505,
            "close": 1.08515,
            "volume": 75.0,
        },
        {
            "open": 1.08515,
            "high": 1.08525,
            "low": 1.08508,
            "close": 1.08518,
            "volume": 82.0,
        },
    ]


# ------------------------------------------------------------------
# Session M1 candles with ATR spike for gap detection
# ------------------------------------------------------------------
@pytest.fixture()
def session_m1_spike() -> list[dict[str, Any]]:
    """Return session M1 candles with a volatility spike."""
    return [
        {
            "open": 1.08520,
            "high": 1.08600,
            "low": 1.08450,
            "close": 1.08580,
            "volume": 300.0,
        },
        {
            "open": 1.08580,
            "high": 1.08650,
            "low": 1.08500,
            "close": 1.08620,
            "volume": 280.0,
        },
        {
            "open": 1.08620,
            "high": 1.08700,
            "low": 1.08550,
            "close": 1.08680,
            "volume": 310.0,
        },
    ]


# ------------------------------------------------------------------
# Session M1 candles without ATR spike
# ------------------------------------------------------------------
@pytest.fixture()
def session_m1_flat() -> list[dict[str, Any]]:
    """Return session M1 candles without a volatility spike."""
    return [
        {
            "open": 1.08520,
            "high": 1.08530,
            "low": 1.08515,
            "close": 1.08525,
            "volume": 90.0,
        },
        {
            "open": 1.08525,
            "high": 1.08535,
            "low": 1.08518,
            "close": 1.08528,
            "volume": 85.0,
        },
        {
            "open": 1.08528,
            "high": 1.08538,
            "low": 1.08520,
            "close": 1.08532,
            "volume": 88.0,
        },
    ]
