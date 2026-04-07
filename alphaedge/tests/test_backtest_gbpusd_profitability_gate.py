from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, cast
from unittest.mock import patch
from zoneinfo import ZoneInfo

from alphaedge.config.loader import AppConfig, TradingConfig
from alphaedge.core.types import MomentumSignal
from alphaedge.engine.backtest import (
    _backtest_pair,
    _get_pair_profitability_gate_rejection,
)


def _make_config() -> AppConfig:
    cfg = AppConfig()
    cfg.trading = TradingConfig()
    cfg.trading.pairs = ["GBPUSD"]
    cfg.trading.momentum_lookback_days = 2
    cfg.trading.gbpusd_long_adx_min = 32.0
    cfg.trading.carry_enabled = False
    return cfg


def _make_bars(n: int = 6) -> list[dict[str, Any]]:
    tz = ZoneInfo("UTC")
    start = datetime(2024, 1, 1, tzinfo=tz)
    bars: list[dict[str, Any]] = []
    for index in range(n):
        price = 1.2500 + index * 0.0010
        bars.append(
            {
                "open": price,
                "high": price + 0.0008,
                "low": price - 0.0008,
                "close": price + 0.0002,
                "volume": 1000.0,
                "datetime": start + timedelta(days=index),
            }
        )
    return bars


class TestGbpusdProfitabilityGate:
    def test_returns_rejection_for_gbpusd_long_below_threshold(self) -> None:
        cfg = _make_config()

        rejection = _get_pair_profitability_gate_rejection(
            "GBPUSD",
            cast(MomentumSignal, {"direction": 1, "adx": 29.5}),
            cfg,
        )

        assert rejection is not None
        assert rejection.rejection_reason == "gbpusd_long_below_profitability_gate"
        assert rejection.primary_filter == "pair_profitability_gate"
        assert rejection.rejection_value == 29.5

    def test_backtest_pair_skips_gbpusd_long_below_threshold(self) -> None:
        cfg = _make_config()
        signal = {"detected": True, "direction": 1, "adx": 29.0}

        with (
            patch(
                "alphaedge.core.momentum_detector.detect_momentum",
                return_value=signal,
            ),
            patch(
                "alphaedge.engine.backtest._collect_daily_trades",
                side_effect=AssertionError("gate should block before trade creation"),
            ),
        ):
            trades, _rejections, rejection_logs = _backtest_pair(
                "GBPUSD",
                _make_bars(),
                cfg,
            )

        assert trades == []
        assert len(rejection_logs) == 4
        assert {log.rejection_reason for log in rejection_logs} == {
            "gbpusd_long_below_profitability_gate"
        }

    def test_backtest_pair_allows_gbpusd_long_above_threshold(self) -> None:
        cfg = _make_config()
        signal = {"detected": True, "direction": 1, "adx": 34.0}

        with (
            patch(
                "alphaedge.core.momentum_detector.detect_momentum",
                return_value=signal,
            ),
            patch(
                "alphaedge.engine.backtest._collect_daily_trades",
                return_value=[],
            ) as collect_daily_trades,
        ):
            trades, _rejections, rejection_logs = _backtest_pair(
                "GBPUSD",
                _make_bars(),
                cfg,
            )

        assert trades == []
        assert rejection_logs == []
        assert collect_daily_trades.call_count == 4
