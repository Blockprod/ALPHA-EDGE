# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/tests/test_main_gateway_watchdog.py
# DESCRIPTION  : Gateway watchdog relaunch guards
# PYTHON       : 3.11.9
# ============================================================
"""Regression tests for the CLI gateway watchdog tick helper."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import pytest

import alphaedge.__main__ as main_mod


class _DummyStrategy:
    def __init__(self, *, broker_connected: bool) -> None:
        self._broker = SimpleNamespace(is_connected=broker_connected)
        self.gateway_updates: list[tuple[bool, str]] = []

    def set_gateway_health(
        self,
        *,
        gateway_connected: bool,
        gateway_status: str,
    ) -> None:
        self.gateway_updates.append((gateway_connected, gateway_status))


@pytest.mark.asyncio()
async def test_watchdog_skips_relaunch_when_broker_session_alive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    strategy = _DummyStrategy(broker_connected=True)
    config = SimpleNamespace(ib=object())
    ensure_gateway_ready = AsyncMock(return_value=True)
    check_gateway_health = AsyncMock(return_value=False)

    monkeypatch.setattr(main_mod, "ensure_gateway_ready", ensure_gateway_ready)
    monkeypatch.setattr(main_mod, "check_gateway_health", check_gateway_health)

    await main_mod._run_gateway_watchdog_tick(
        cast(main_mod.SwingStrategy, strategy),
        cast(main_mod.AppConfig, config),
    )

    check_gateway_health.assert_not_awaited()
    ensure_gateway_ready.assert_not_awaited()
    assert strategy.gateway_updates == [(True, "healthy")]


@pytest.mark.asyncio()
async def test_watchdog_reasserts_gateway_when_broker_is_disconnected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    strategy = _DummyStrategy(broker_connected=False)
    config = SimpleNamespace(ib=object())
    ensure_gateway_ready = AsyncMock(return_value=True)
    check_gateway_health = AsyncMock(return_value=False)

    monkeypatch.setattr(main_mod, "ensure_gateway_ready", ensure_gateway_ready)
    monkeypatch.setattr(main_mod, "check_gateway_health", check_gateway_health)

    await main_mod._run_gateway_watchdog_tick(
        cast(main_mod.SwingStrategy, strategy),
        cast(main_mod.AppConfig, config),
    )

    check_gateway_health.assert_awaited_once()
    ensure_gateway_ready.assert_awaited_once()
    assert strategy.gateway_updates == [(False, "down"), (True, "healthy")]
