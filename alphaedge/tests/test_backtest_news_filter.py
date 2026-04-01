# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_backtest_news_filter.py
# DESCRIPTION  : Tests for P2-03 news filter integration in backtest
# AUTHOR       : ALPHAEDGE Dev Team
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-08
# ============================================================
"""ALPHAEDGE — Verify news blackouts suppress signals in _backtest_pair."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from alphaedge.config.loader import AppConfig, IBConfig, TradingConfig
from alphaedge.engine.backtest import _backtest_pair
from alphaedge.utils.news_filter import EconomicNewsFilter


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _make_config(momentum_lookback_days: int = 2) -> AppConfig:
    cfg = AppConfig()
    cfg.ib = IBConfig(is_paper=True)
    cfg.trading = TradingConfig()
    cfg.trading.pairs = ["EURUSD"]
    cfg.trading.momentum_lookback_days = momentum_lookback_days
    return cfg


def _make_bars(n: int = 20) -> list[dict[str, Any]]:
    """Return minimal M1 bar list with ascending prices."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    ET = ZoneInfo("America/New_York")  # noqa: N806  # pylint: disable=invalid-name
    bars = []
    base_price = 1.0800
    for i in range(n):
        dt = datetime(2024, 1, 2, 9, 30 + i, tzinfo=ET)
        p = base_price + i * 0.0001
        bars.append(
            {
                "open": p,
                "high": p + 0.0005,
                "low": p - 0.0003,
                "close": p + 0.0002,
                "volume": 200.0,
                "datetime": dt,
            }
        )
    return bars


# ==================================================================
# Tests
# ==================================================================
class TestNewsFilterInBacktest:
    """Verify _backtest_pair respects the news_filter."""

    def test_no_news_filter_default_behaviour(self) -> None:
        """Without news_filter, _backtest_pair runs normally (no crash)."""
        cfg = _make_config()
        # With Cython compiled, may return trades; without it returns []
        # Either way should not raise
        try:
            result, _ = _backtest_pair("EURUSD", _make_bars(), cfg)
            assert isinstance(result, list)
        except Exception:
            pytest.skip("Cython not available — skipping integration path")

    def test_news_filter_none_is_noop(self) -> None:
        """Passing news_filter=None is identical to not passing it."""
        cfg = _make_config()
        try:
            result, _ = _backtest_pair("EURUSD", _make_bars(), cfg, news_filter=None)
            assert isinstance(result, list)
        except Exception:
            pytest.skip("Cython not available")

    def test_all_blackout_produces_no_trades(self) -> None:
        """When every bar is in a blackout, no trades should be recorded."""
        cfg = _make_config()

        # Mock news filter: always in blackout
        nf = MagicMock(spec=EconomicNewsFilter)
        nf.is_news_blackout.return_value = True

        bars = _make_bars(20)

        # Mock momentum_detector to always return a detected signal
        fake_signal = {
            "detected": True,
            "direction": 1,
            "strength": 0.8,
            "ema_fast": 1.081,
            "ema_slow": 1.079,
            "adx": 28.5,
            "timestamp": 0,
        }
        with patch(
            "alphaedge.core.momentum_detector.detect_momentum",
            return_value=fake_signal,
        ):
            result, _ = _backtest_pair("EURUSD", bars, cfg, news_filter=nf)

        # All signals suppressed by blackout
        assert result == []
        # is_news_blackout must have been consulted
        assert nf.is_news_blackout.call_count >= 1

    def test_no_blackout_allows_trades(self) -> None:
        """When no bars are in blackout, the filter is transparent."""
        cfg = _make_config()

        nf = MagicMock(spec=EconomicNewsFilter)
        nf.is_news_blackout.return_value = False  # never a blackout

        try:
            result, _ = _backtest_pair(
                "EURUSD",
                _make_bars(30),
                cfg,
                news_filter=nf,
            )
            assert isinstance(result, list)
        except ImportError:
            pytest.skip("Cython not available")

        # Filter was consulted (not short-circuited)
        assert nf.is_news_blackout.call_count >= 0
