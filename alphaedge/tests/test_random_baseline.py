# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_random_baseline.py
# DESCRIPTION  : Tests for random baseline benchmark
# ============================================================
"""ALPHAEDGE — T3.5: Random baseline benchmark tests."""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from alphaedge.engine.backtest import (
    RandomBaselineReport,
    TradeRecord,
    _generate_random_trades,
    run_random_baseline,
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _make_m1_bars(n: int = 100) -> list[dict[str, Any]]:
    """Create n synthetic M1 bars with realistic price movement."""
    et = ZoneInfo("America/New_York")
    bars: list[dict[str, Any]] = []
    price = 1.08500
    rng = random.Random(42)

    for i in range(n):
        change = rng.uniform(-0.0005, 0.0005)
        open_p = price
        close_p = price + change
        high_p = max(open_p, close_p) + rng.uniform(0, 0.0003)
        low_p = min(open_p, close_p) - rng.uniform(0, 0.0003)
        dt = datetime(2024, 1, 2, 9, 30, tzinfo=et) + timedelta(minutes=i)

        bars.append(
            {
                "open": open_p,
                "high": high_p,
                "low": low_p,
                "close": close_p,
                "volume": 100.0 + rng.uniform(0, 50),
                "datetime": dt,
            }
        )
        price = close_p

    return bars


def _make_strategy_trades(n: int = 20) -> list[TradeRecord]:
    """Create n strategy trades with mostly wins (PF > 1)."""
    et = ZoneInfo("America/New_York")
    trades: list[TradeRecord] = []
    for i in range(n):
        pnl = 15.0 if i % 3 != 0 else -10.0
        trades.append(
            TradeRecord(
                pair="EURUSD",
                direction=1,
                entry_price=1.08500,
                stop_loss=1.08400,
                take_profit=1.08600,
                entry_time=datetime(2024, 1, 2, 10, 0, tzinfo=et) + timedelta(hours=i),
                exit_price=1.08600 if pnl > 0 else 1.08400,
                pnl_pips=pnl,
                pnl_usd=pnl * 10.0,
                outcome="win" if pnl > 0 else "loss",
            )
        )
    return trades


# ------------------------------------------------------------------
# _generate_random_trades
# ------------------------------------------------------------------
class TestGenerateRandomTrades:
    def test_generates_correct_count(self) -> None:
        bars = _make_m1_bars(100)
        trades = _generate_random_trades(bars, "EURUSD", 20)
        assert len(trades) == 20

    def test_trades_have_outcomes(self) -> None:
        bars = _make_m1_bars(100)
        trades = _generate_random_trades(bars, "EURUSD", 10)
        for t in trades:
            assert t.outcome in ("win", "loss", "timeout")

    def test_both_directions(self) -> None:
        """Random trades should include both longs and shorts."""
        bars = _make_m1_bars(200)
        rng = random.Random(42)
        trades = _generate_random_trades(bars, "EURUSD", 50, rng=rng)
        directions = {t.direction for t in trades}
        assert 1 in directions
        assert -1 in directions

    def test_rr_ratio_applied(self) -> None:
        """TP distance should be rr_ratio * SL distance."""
        bars = _make_m1_bars(100)
        rng = random.Random(42)
        trades = _generate_random_trades(
            bars, "EURUSD", 10, rr_ratio=3.0, sl_pips=10.0, rng=rng
        )
        for t in trades:
            sl_dist = abs(t.entry_price - t.stop_loss)
            tp_dist = abs(t.entry_price - t.take_profit)
            ratio = tp_dist / sl_dist if sl_dist > 0 else 0
            assert ratio == pytest.approx(3.0, abs=0.01)

    def test_too_few_bars_returns_empty(self) -> None:
        bars = _make_m1_bars(5)
        trades = _generate_random_trades(bars, "EURUSD", 10)
        assert trades == []

    def test_reproducibility_with_rng(self) -> None:
        bars = _make_m1_bars(100)
        rng1 = random.Random(123)
        rng2 = random.Random(123)
        trades1 = _generate_random_trades(bars, "EURUSD", 10, rng=rng1)
        trades2 = _generate_random_trades(bars, "EURUSD", 10, rng=rng2)
        for t1, t2 in zip(trades1, trades2):
            assert t1.entry_price == t2.entry_price
            assert t1.direction == t2.direction


# ------------------------------------------------------------------
# run_random_baseline
# ------------------------------------------------------------------
class TestRunRandomBaseline:
    def test_report_structure(self) -> None:
        bars = _make_m1_bars(200)
        strategy_trades = _make_strategy_trades(10)
        report = run_random_baseline(
            bars, "EURUSD", strategy_trades, n_simulations=10, seed=42
        )
        assert isinstance(report, RandomBaselineReport)
        assert report.n_simulations == 10
        assert len(report.baseline_pfs) == 10

    def test_p_value_range(self) -> None:
        bars = _make_m1_bars(200)
        strategy_trades = _make_strategy_trades(10)
        report = run_random_baseline(
            bars, "EURUSD", strategy_trades, n_simulations=50, seed=42
        )
        assert 0.0 <= report.p_value <= 1.0

    def test_baseline_95th_computed(self) -> None:
        bars = _make_m1_bars(200)
        strategy_trades = _make_strategy_trades(10)
        report = run_random_baseline(
            bars, "EURUSD", strategy_trades, n_simulations=100, seed=42
        )
        assert report.baseline_pf_95th >= report.baseline_pf_mean
        # 95th percentile should exist
        assert report.baseline_pf_95th >= 0.0

    def test_seed_reproducibility(self) -> None:
        bars = _make_m1_bars(200)
        strategy_trades = _make_strategy_trades(10)
        r1 = run_random_baseline(
            bars, "EURUSD", strategy_trades, n_simulations=20, seed=99
        )
        r2 = run_random_baseline(
            bars, "EURUSD", strategy_trades, n_simulations=20, seed=99
        )
        assert r1.p_value == r2.p_value
        assert r1.baseline_pf_mean == r2.baseline_pf_mean

    def test_empty_bars_produces_zero_pfs(self) -> None:
        report = run_random_baseline([], "EURUSD", [], n_simulations=10, seed=42)
        assert report.n_simulations == 10
        assert report.strategy_pf == 0.0
        assert all(pf == 0.0 for pf in report.baseline_pfs)
