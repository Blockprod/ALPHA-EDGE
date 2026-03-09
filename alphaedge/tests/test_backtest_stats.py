# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_backtest_stats.py
# DESCRIPTION  : Tests for backtest_stats module (P3-02 SRP extraction)
# AUTHOR       : ALPHAEDGE Dev Team
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-08
# ============================================================
"""Tests for compute_stats, split_trades_is_oos, and compute_split_report."""

from __future__ import annotations

import math
from datetime import datetime

import pytest

from alphaedge.engine.backtest_stats import (
    _compute_max_drawdown,
    _compute_profit_factor,
    _compute_sharpe,
    _compute_winrate,
    compute_split_report,
    compute_stats,
    split_trades_is_oos,
)
from alphaedge.engine.backtest_types import TradeRecord


# ------------------------------------------------------------------
# Helper
# ------------------------------------------------------------------
def _make_trade(
    pnl_pips: float,
    pnl_usd: float | None = None,
    entry_offset: int = 0,
) -> TradeRecord:
    """Build a minimal TradeRecord for testing."""
    if pnl_usd is None:
        pnl_usd = pnl_pips * 10.0  # rough approximation

    entry_dt = datetime(2025, 1, 1, 12, entry_offset % 60)
    return TradeRecord(
        pair="EURUSD",
        direction=1,
        entry_price=1.10000,
        stop_loss=1.09900,
        take_profit=1.10300,
        entry_time=entry_dt,
        pnl_pips=pnl_pips,
        pnl_usd=pnl_usd,
        outcome="win" if pnl_pips > 0 else "loss",
    )


# ==================================================================
# Tests — compute_stats
# ==================================================================
class TestComputeStats:
    """Verify aggregate stats from a list of TradeRecords."""

    def test_empty_list_returns_zeroed_stats(self) -> None:
        stats = compute_stats([])
        assert stats.total_trades == 0
        assert stats.wins == 0
        assert stats.losses == 0
        assert stats.winrate == 0.0
        assert stats.profit_factor == 0.0
        assert stats.total_pnl_pips == 0.0

    def test_all_wins(self) -> None:
        trades = [_make_trade(10.0, entry_offset=i) for i in range(5)]
        stats = compute_stats(trades)
        assert stats.total_trades == 5
        assert stats.wins == 5
        assert stats.losses == 0
        assert stats.winrate == pytest.approx(100.0)
        assert stats.total_pnl_pips == pytest.approx(50.0)

    def test_mixed_win_loss(self) -> None:
        trades = [
            _make_trade(30.0, entry_offset=0),  # win
            _make_trade(-10.0, entry_offset=1),  # loss
            _make_trade(30.0, entry_offset=2),  # win
            _make_trade(-10.0, entry_offset=3),  # loss
        ]
        stats = compute_stats(trades)
        assert stats.total_trades == 4
        assert stats.wins == 2
        assert stats.losses == 2
        assert stats.winrate == pytest.approx(50.0)
        assert stats.profit_factor == pytest.approx(3.0)  # 60 / 20

    def test_max_drawdown_computed(self) -> None:
        trades = [
            _make_trade(-100.0, pnl_usd=-100.0, entry_offset=0),
            _make_trade(-100.0, pnl_usd=-100.0, entry_offset=1),
            _make_trade(50.0, pnl_usd=50.0, entry_offset=2),
        ]
        stats = compute_stats(trades)
        assert stats.max_drawdown_pct > 0.0

    def test_single_trade(self) -> None:
        stats = compute_stats([_make_trade(20.0)])
        assert stats.total_trades == 1
        assert stats.sharpe_ratio == 0.0  # < 2 trades → Sharpe returns 0


# ==================================================================
# Tests — _compute_winrate
# ==================================================================
class TestComputeWinrate:
    """Edge cases for win-rate calculation."""

    def test_zero_total_returns_zero(self) -> None:
        assert _compute_winrate(0, 0) == 0.0

    def test_all_wins(self) -> None:
        assert _compute_winrate(10, 10) == pytest.approx(100.0)

    def test_half_wins(self) -> None:
        assert _compute_winrate(5, 10) == pytest.approx(50.0)


# ==================================================================
# Tests — _compute_profit_factor
# ==================================================================
class TestComputeProfitFactor:
    """Edge cases for profit factor calculation."""

    def test_no_losses_returns_inf(self) -> None:
        wins = [_make_trade(10.0)]
        result = _compute_profit_factor(wins, [])
        assert math.isinf(result)

    def test_no_wins_no_losses_returns_zero(self) -> None:
        result = _compute_profit_factor([], [])
        assert result == 0.0

    def test_correct_ratio(self) -> None:
        wins = [_make_trade(30.0), _make_trade(30.0)]
        losses = [_make_trade(-10.0), _make_trade(-10.0)]
        result = _compute_profit_factor(wins, losses)
        assert result == pytest.approx(3.0)


# ==================================================================
# Tests — _compute_max_drawdown
# ==================================================================
class TestComputeMaxDrawdown:
    """Verify drawdown calculation on equity curve."""

    def test_empty_returns_zero(self) -> None:
        assert _compute_max_drawdown([]) == 0.0

    def test_all_wins_no_drawdown(self) -> None:
        trades = [_make_trade(10.0, pnl_usd=100.0, entry_offset=i) for i in range(3)]
        dd = _compute_max_drawdown(trades)
        assert dd == pytest.approx(0.0)

    def test_drawdown_after_loss(self) -> None:
        trades = [
            _make_trade(0.0, pnl_usd=500.0, entry_offset=0),  # equity → 10500
            _make_trade(0.0, pnl_usd=-1050.0, entry_offset=1),  # equity → 9450 (10% dd)
        ]
        dd = _compute_max_drawdown(trades)
        assert dd == pytest.approx(10.0)


# ==================================================================
# Tests — _compute_sharpe
# ==================================================================
class TestComputeSharpe:
    """Verify Sharpe ratio calculation."""

    def test_less_than_two_trades_returns_zero(self) -> None:
        assert _compute_sharpe([]) == 0.0
        assert _compute_sharpe([_make_trade(10.0)]) == 0.0

    def test_uniform_returns_zero_std(self) -> None:
        trades = [_make_trade(10.0, entry_offset=i) for i in range(5)]
        result = _compute_sharpe(trades)
        assert result == 0.0  # std=0 → returns 0

    def test_positive_return_positive_sharpe(self) -> None:
        trades = [
            _make_trade(20.0, entry_offset=0),
            _make_trade(10.0, entry_offset=1),
            _make_trade(30.0, entry_offset=2),
        ]
        result = _compute_sharpe(trades)
        assert result > 0.0


# ==================================================================
# Tests — split_trades_is_oos
# ==================================================================
class TestSplitTradesIsOos:
    """Verify chronological IS/OOS split and sample_type tagging."""

    def test_default_70_30_split(self) -> None:
        trades = [_make_trade(10.0, entry_offset=i) for i in range(10)]
        is_t, oos_t = split_trades_is_oos(trades)
        assert len(is_t) == 7
        assert len(oos_t) == 3

    def test_sample_type_tags(self) -> None:
        trades = [_make_trade(10.0, entry_offset=i) for i in range(4)]
        is_t, oos_t = split_trades_is_oos(trades)
        assert all(t.sample_type == "IS" for t in is_t)
        assert all(t.sample_type == "OOS" for t in oos_t)

    def test_empty_trades(self) -> None:
        is_t, oos_t = split_trades_is_oos([])
        assert is_t == []
        assert oos_t == []


# ==================================================================
# Tests — compute_split_report
# ==================================================================
class TestComputeSplitReport:
    """Verify IS/OOS report with degradation metrics."""

    def test_report_has_both_stats(self) -> None:
        trades = [_make_trade(10.0, entry_offset=i) for i in range(10)]
        report = compute_split_report(trades)
        assert report.in_sample.total_trades == 7
        assert report.out_of_sample.total_trades == 3

    def test_degradation_keys_present(self) -> None:
        trades = [_make_trade(10.0, entry_offset=i) for i in range(10)]
        report = compute_split_report(trades)
        assert "winrate" in report.degradation
        assert "profit_factor" in report.degradation
        assert "sharpe_ratio" in report.degradation
