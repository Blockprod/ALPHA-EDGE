# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_strategy_p2_04.py
# DESCRIPTION  : P2-04 — volatility_regime + pair_correlation integration
# ============================================================
"""Tests for P2-04: regime gate in run_session, correlation check in _on_new_m1_bar."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alphaedge.engine.position_manager import PositionManager
from alphaedge.engine.session_lifecycle import SessionLifecycle
from alphaedge.engine.signal_pipeline import SignalPipeline
from alphaedge.engine.strategy import FCRStrategy, StrategyState
from alphaedge.utils.pair_correlation import CorrelationCheckResult
from alphaedge.utils.volatility_regime import VolatilityRegimeResult


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _make_m5_candles(n: int = 5, base: float = 1.0850) -> list[dict[str, Any]]:
    return [
        {
            "open": base,
            "high": base + 0.0010,
            "low": base - 0.0010,
            "close": base + 0.0001,
        }
        for _ in range(n)
    ]


def _make_daily_bars(n: int = 25) -> list[dict[str, Any]]:
    price = 1.0800
    bars = []
    for _ in range(n):
        bars.append(
            {"open": price, "high": price + 0.005, "low": price - 0.005, "close": price}
        )
        price += 0.0001
    return bars


def _make_strategy(pairs: list[str] | None = None) -> FCRStrategy:
    """Build an FCRStrategy with fully mocked dependencies."""
    if pairs is None:
        pairs = ["EURUSD"]
    config = MagicMock()
    config.trading.pairs = pairs
    config.trading.max_trades_per_session = 2
    config.trading.max_spread_pips = 3.0
    config.trading.spread_spike_multiplier = 2.0
    config.trading.rr_ratio = 2.0
    config.trading.min_body_ratio = 0.5
    config.trading.max_wick_ratio = 0.5
    config.trading.risk_pct = 1.0
    config.trading.lot_type = "micro"
    config.trading.max_daily_loss_pct = 2.0
    config.trading.session_end_action = "keep"
    config.news_filter_raw = {}
    config.ib = MagicMock()

    broker = MagicMock()
    broker.ib.disconnectedEvent = MagicMock()
    broker.ib.disconnectedEvent.__iadd__ = MagicMock(return_value=None)

    strat = FCRStrategy.__new__(FCRStrategy)
    strat._config = config
    strat._broker = broker
    strat._executor = MagicMock()
    strat._hist_feed = MagicMock()
    strat._rt_feed = MagicMock()
    strat._states = {}
    strat._modules = MagicMock()
    strat._shutdown_requested = False
    strat._reconnecting = False
    strat._news_filter = MagicMock()
    strat._news_filter.is_news_blackout.return_value = False
    strat._trade_lock = __import__("asyncio").Lock()
    strat._global_trades_today = 0
    strat._correlation_matrix = {}
    strat._signal_pipeline = SignalPipeline()
    strat._position_manager = PositionManager()
    strat._lifecycle = SessionLifecycle(strat)
    return strat


# ------------------------------------------------------------------
# Volatility regime gate in run_session (unit tests for new logic)
# ------------------------------------------------------------------
class TestVolatilityRegimeGate:
    """Test that run_session skips pairs whose regime check is False."""

    @pytest.mark.asyncio
    async def test_pair_skipped_when_regime_not_allowed(self) -> None:
        """When regime.allowed=False, the pair is not added to active_pairs."""
        strat = _make_strategy(["EURUSD"])

        m5 = _make_m5_candles()
        daily = _make_daily_bars()

        strat._hist_feed.fetch_bars = AsyncMock(return_value=daily)
        strat._hist_feed.fetch_m5_pre_session = AsyncMock(return_value=m5)

        blocked_result = VolatilityRegimeResult(
            allowed=False,
            reason="too_quiet",
            current_atr=0.001,
            rolling_mean_atr=0.005,
            low_threshold=0.0025,
            high_threshold=0.010,
        )

        strat._executor.get_account_equity = AsyncMock(return_value=10_000.0)
        strat._broker.connect = AsyncMock(return_value=True)
        strat._rt_feed.on_bar = MagicMock()
        strat._rt_feed.subscribe = AsyncMock()
        strat._rt_feed.unsubscribe_all = AsyncMock()
        strat._rt_feed.get_live_spread = AsyncMock(return_value=None)
        strat._broker.disconnect = AsyncMock()
        strat._executor.get_open_positions = AsyncMock(return_value=[])

        with (
            patch(
                "alphaedge.engine.session_lifecycle.load_daily_state", return_value=None
            ),
            patch(
                "alphaedge.engine.session_lifecycle.get_session_window_utc",
                return_value=(MagicMock(), MagicMock()),
            ),
            patch(
                "alphaedge.engine.session_lifecycle.check_volatility_regime",
                return_value=blocked_result,
            ),
            patch(
                "alphaedge.engine.session_lifecycle.is_session_active",
                return_value=False,
            ),
        ):
            await strat.run_session()

        # Pair was skipped — no state created, no subscribe call
        assert "EURUSD" not in strat._states
        strat._rt_feed.subscribe.assert_not_called()

    @pytest.mark.asyncio
    async def test_pair_active_when_regime_allowed(self) -> None:
        """When regime.allowed=True, the pair is subscribed normally."""
        strat = _make_strategy(["EURUSD"])

        m5 = _make_m5_candles()
        daily = _make_daily_bars()

        strat._hist_feed.fetch_bars = AsyncMock(return_value=daily)
        strat._hist_feed.fetch_m5_pre_session = AsyncMock(return_value=m5)

        allowed_result = VolatilityRegimeResult(allowed=True, reason="")

        strat._executor.get_account_equity = AsyncMock(return_value=10_000.0)
        strat._broker.connect = AsyncMock(return_value=True)
        strat._rt_feed.on_bar = MagicMock()
        strat._rt_feed.subscribe = AsyncMock()
        strat._rt_feed.unsubscribe_all = AsyncMock()
        strat._broker.disconnect = AsyncMock()
        strat._executor.get_open_positions = AsyncMock(return_value=[])
        strat._modules.fcr_detector.detect_fcr.return_value = None

        with (
            patch(
                "alphaedge.engine.session_lifecycle.load_daily_state", return_value=None
            ),
            patch(
                "alphaedge.engine.session_lifecycle.get_session_window_utc",
                return_value=(MagicMock(), MagicMock()),
            ),
            patch(
                "alphaedge.engine.session_lifecycle.check_volatility_regime",
                return_value=allowed_result,
            ),
            patch(
                "alphaedge.engine.session_lifecycle.is_session_active",
                return_value=False,
            ),
        ):
            await strat.run_session()

        # State created and subscribe called
        assert "EURUSD" in strat._states
        strat._rt_feed.subscribe.assert_called_once_with("EURUSD")

    @pytest.mark.asyncio
    async def test_regime_skipped_when_no_daily_bars(self) -> None:
        """No daily bars → regime not called → pair allowed by default."""
        strat = _make_strategy(["EURUSD"])

        m5 = _make_m5_candles()

        strat._hist_feed.fetch_bars = AsyncMock(return_value=[])  # empty daily bars
        strat._hist_feed.fetch_m5_pre_session = AsyncMock(return_value=m5)

        strat._executor.get_account_equity = AsyncMock(return_value=10_000.0)
        strat._broker.connect = AsyncMock(return_value=True)
        strat._rt_feed.on_bar = MagicMock()
        strat._rt_feed.subscribe = AsyncMock()
        strat._rt_feed.unsubscribe_all = AsyncMock()
        strat._broker.disconnect = AsyncMock()
        strat._executor.get_open_positions = AsyncMock(return_value=[])
        strat._modules.fcr_detector.detect_fcr.return_value = None

        check_called: list[int] = []

        def _track_vol_regime_call(*a: Any, **k: Any) -> VolatilityRegimeResult:
            check_called.append(1)
            return VolatilityRegimeResult(allowed=True)

        with (
            patch(
                "alphaedge.engine.session_lifecycle.load_daily_state", return_value=None
            ),
            patch(
                "alphaedge.engine.session_lifecycle.get_session_window_utc",
                return_value=(MagicMock(), MagicMock()),
            ),
            patch(
                "alphaedge.engine.session_lifecycle.check_volatility_regime",
                side_effect=_track_vol_regime_call,
            ),
            patch(
                "alphaedge.engine.session_lifecycle.is_session_active",
                return_value=False,
            ),
        ):
            await strat.run_session()

        # check_volatility_regime must NOT have been called (empty daily_bars guard)
        assert check_called == []
        # Pair proceeds normally
        assert "EURUSD" in strat._states


# ------------------------------------------------------------------
# Pair correlation check in _on_new_m1_bar
# ------------------------------------------------------------------
class TestCorrelationCheckInBar:
    """Test that _on_new_m1_bar blocks correlated signals."""

    def _make_strat_with_state(self, pair: str = "EURUSD") -> FCRStrategy:
        strat = _make_strategy([pair])
        state = StrategyState(pair=pair)
        state.trades_today = 0
        state.is_position_open = False
        state.m5_candles = _make_m5_candles()
        state.m1_candles = []
        state.gap_result = {"detected": True}
        state.fcr_result = {"range_high": 1.0860, "range_low": 1.0840}
        strat._states[pair] = state
        strat._modules.engulfing_detector.detect_engulfing.return_value = None
        return strat

    def test_correlation_not_checked_when_matrix_empty(self) -> None:
        """Empty correlation matrix → check_signal_allowed never called."""
        strat = self._make_strat_with_state("EURUSD")
        strat._correlation_matrix = {}

        with patch(
            "alphaedge.engine.session_lifecycle.check_signal_allowed"
        ) as mock_check:
            strat._lifecycle._on_new_m1_bar(
                "EURUSD", {"open": 1.085, "high": 1.086, "low": 1.084, "close": 1.0855}
            )
            mock_check.assert_not_called()

    def test_correlated_signal_blocked(self) -> None:
        """correlation_matrix set + check False → bar handler returns early."""
        strat = self._make_strat_with_state("GBPUSD")

        # Simulate EURUSD open (correlated with GBPUSD)
        eur_state = StrategyState(pair="EURUSD")
        eur_state.is_position_open = True
        strat._states["EURUSD"] = eur_state

        strat._correlation_matrix = {
            ("EURUSD", "GBPUSD"): 0.85,
            ("GBPUSD", "EURUSD"): 0.85,
        }

        block_result = CorrelationCheckResult(
            allowed=False,
            reason="correlation_too_high (GBPUSD/EURUSD ρ=0.850)",
            max_rho=0.85,
            blocking_pair="EURUSD",
        )

        with patch(
            "alphaedge.engine.session_lifecycle.check_signal_allowed",
            return_value=block_result,
        ):
            # engulfing should never be called if correlation blocks early
            strat._modules.engulfing_detector.detect_engulfing.reset_mock()
            strat._lifecycle._on_new_m1_bar(
                "GBPUSD",
                {"open": 1.265, "high": 1.266, "low": 1.264, "close": 1.2655},
            )

        strat._modules.engulfing_detector.detect_engulfing.assert_not_called()

    def test_uncorrelated_signal_allowed(self) -> None:
        """When check_signal_allowed returns True, execution proceeds normally."""
        strat = self._make_strat_with_state("USDJPY")
        strat._correlation_matrix = {
            ("EURUSD", "USDJPY"): 0.1,
            ("USDJPY", "EURUSD"): 0.1,
        }

        allow_result = CorrelationCheckResult(
            allowed=True,
            reason="correlation_acceptable",
            max_rho=0.1,
            blocking_pair="",
        )

        with patch(
            "alphaedge.engine.session_lifecycle.check_signal_allowed",
            return_value=allow_result,
        ):
            # engulfing IS called (returns None → no exec_task)
            strat._lifecycle._on_new_m1_bar(
                "USDJPY",
                {"open": 151.50, "high": 151.60, "low": 151.40, "close": 151.55},
            )

        strat._modules.engulfing_detector.detect_engulfing.assert_called_once()

    def test_correlation_check_passes_open_pairs(self) -> None:
        """check_signal_allowed receives open_pairs with all open positions."""
        strat = self._make_strat_with_state("AUDUSD")

        # Open a second pair
        gbp_state = StrategyState(pair="GBPUSD")
        gbp_state.is_position_open = True
        strat._states["GBPUSD"] = gbp_state

        strat._correlation_matrix = {
            ("AUDUSD", "GBPUSD"): 0.5,
            ("GBPUSD", "AUDUSD"): 0.5,
        }

        captured: list[list[str]] = []

        def _capture_check(
            pair: str, open_pairs: list[str], *args: Any, **kwargs: Any
        ) -> CorrelationCheckResult:
            captured.append(list(open_pairs))
            return CorrelationCheckResult(
                allowed=True, reason="ok", max_rho=0.5, blocking_pair=""
            )

        with patch(
            "alphaedge.engine.session_lifecycle.check_signal_allowed",
            side_effect=_capture_check,
        ):
            strat._lifecycle._on_new_m1_bar(
                "AUDUSD",
                {"open": 0.655, "high": 0.656, "low": 0.654, "close": 0.6555},
            )

        assert len(captured) == 1
        assert "GBPUSD" in captured[0]
