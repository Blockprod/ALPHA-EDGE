# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_race_condition_multi_pair.py
# DESCRIPTION  : Tests for P0-01 asyncio.Lock race condition fix
# AUTHOR       : ALPHAEDGE Dev Team
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-08
# ============================================================
"""ALPHAEDGE — Verify asyncio.Lock prevents concurrent trade execution."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alphaedge.config.loader import AppConfig, IBConfig, TradingConfig
from alphaedge.engine.strategy import CoreModules, FCRStrategy, StrategyState


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _make_config(pairs: list[str] | None = None) -> AppConfig:
    """Build a minimal AppConfig for tests."""
    return AppConfig(
        ib=IBConfig(is_paper=True),
        trading=TradingConfig(
            pairs=pairs or ["EURUSD", "GBPUSD"],
            max_trades_per_session=5,
        ),
    )


def _build_strategy(config: AppConfig | None = None) -> FCRStrategy:
    """Create FCRStrategy with mocked broker, feeds, and modules."""
    cfg = config or _make_config()
    with (
        patch("alphaedge.engine.strategy.BrokerConnection") as mock_broker_cls,
        patch("alphaedge.engine.strategy.OrderExecutor"),
        patch("alphaedge.engine.strategy.HistoricalDataFeed"),
        patch("alphaedge.engine.strategy.RealtimeDataFeed"),
        patch("alphaedge.engine.strategy._import_core_modules") as mock_modules,
    ):
        mock_ib = MagicMock()
        mock_ib.disconnectedEvent = MagicMock()
        mock_broker_cls.return_value.ib = mock_ib

        risk_mock = MagicMock()

        # check_pair_limit: allow when no open pairs, reject otherwise
        def _check_pair_limit(
            pair: str, open_pairs: list[str], max_open_pairs: int
        ) -> dict[str, Any]:
            return {"allowed": len(open_pairs) < max_open_pairs}

        risk_mock.check_pair_limit.side_effect = _check_pair_limit

        mock_modules.return_value = CoreModules(
            fcr_detector=MagicMock(),
            gap_detector=MagicMock(),
            engulfing_detector=MagicMock(),
            order_manager=MagicMock(),
            risk_manager=risk_mock,
        )
        strategy = FCRStrategy(cfg)
    return strategy


# ==================================================================
# Tests
# ==================================================================
class TestTradeLockExists:
    """Verify _trade_lock attribute is created at init."""

    def test_lock_attribute(self) -> None:
        strategy = _build_strategy()
        assert hasattr(strategy, "_trade_lock")
        assert isinstance(strategy._trade_lock, asyncio.Lock)


class TestAtomicCheckAndExecute:
    """Verify _atomic_check_and_execute re-checks under lock."""

    @pytest.mark.asyncio()
    async def test_rejects_when_pair_already_open(self) -> None:
        """Second signal is rejected because first already opened."""
        strategy = _build_strategy()

        # Init two pair states
        state_eu = strategy._init_pair_state("EURUSD")
        state_gb = strategy._init_pair_state("GBPUSD")

        # Mark EURUSD as already open (simulates first trade filled)
        state_eu.is_position_open = True

        signal = {
            "detected": True,
            "signal": 1,
            "entry_price": 1.2500,
            "stop_loss": 1.2450,
            "take_profit": 1.2600,
            "risk_pips": 50.0,
        }

        # _atomic_check_and_execute should re-check pair limit and reject
        result = await strategy._lifecycle._atomic_check_and_execute(
            state_gb, signal, 0.0001
        )
        assert result is False

    @pytest.mark.asyncio()
    async def test_allows_when_no_pair_open(self) -> None:
        """Signal is allowed when no position is open."""
        strategy = _build_strategy()

        state_eu = strategy._init_pair_state("EURUSD")
        _state_gb = strategy._init_pair_state("GBPUSD")  # must exist in _states

        signal = {
            "detected": True,
            "signal": 1,
            "entry_price": 1.2500,
            "stop_loss": 1.2450,
            "take_profit": 1.2600,
            "risk_pips": 50.0,
        }

        # Mock _check_spread_and_execute to return True
        strategy._lifecycle._check_spread_and_execute = AsyncMock(return_value=True)

        result = await strategy._lifecycle._atomic_check_and_execute(
            state_eu, signal, 0.0001
        )
        assert result is True
        strategy._lifecycle._check_spread_and_execute.assert_awaited_once()


class TestConcurrentSignalsOnlyOneExecutes:
    """Simulate two concurrent signals — only one should execute."""

    @pytest.mark.asyncio()
    async def test_two_simultaneous_signals_one_trade(self) -> None:
        """Two signals fired quasi-simultaneously: only one trade executes."""
        strategy = _build_strategy()
        state_eu = strategy._init_pair_state("EURUSD")
        state_gb = strategy._init_pair_state("GBPUSD")

        execution_count = 0

        async def _mock_spread_and_execute(
            state: StrategyState,
            signal: dict[str, Any],
            pip_size: float,
        ) -> bool:
            nonlocal execution_count
            # Simulate IB network delay
            await asyncio.sleep(0.05)
            state.is_position_open = True
            state.trades_today += 1
            execution_count += 1
            return True

        strategy._lifecycle._check_spread_and_execute = _mock_spread_and_execute

        signal = {
            "detected": True,
            "signal": 1,
            "entry_price": 1.2500,
            "stop_loss": 1.2450,
            "take_profit": 1.2600,
            "risk_pips": 50.0,
        }

        # Launch both concurrently
        results = await asyncio.gather(
            strategy._lifecycle._atomic_check_and_execute(state_eu, signal, 0.0001),
            strategy._lifecycle._atomic_check_and_execute(state_gb, signal, 0.0001),
        )

        # Exactly one should succeed, one should be rejected
        assert sum(results) == 1, (
            f"Expected exactly 1 trade executed, got {sum(results)}"
        )
        assert execution_count == 1


class TestOnTradeClosedUsesLock:
    """Verify _on_trade_closed acquires lock before mutating state."""

    @pytest.mark.asyncio()
    async def test_trade_closed_resets_flag(self) -> None:
        """_on_trade_closed resets is_position_open under lock."""
        strategy = _build_strategy()
        state = strategy._init_pair_state("EURUSD")
        state.is_position_open = True

        # Call _on_trade_closed (schedules coroutine)
        strategy._lifecycle._on_trade_closed("EURUSD")

        # Give the event loop a tick to run the scheduled coroutine
        await asyncio.sleep(0.05)

        assert state.is_position_open is False
