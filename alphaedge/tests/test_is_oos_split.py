# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_is_oos_split.py
# DESCRIPTION  : Tests for IS/OOS split, report, and CSV export
# ============================================================
"""ALPHAEDGE — T3.1: In-Sample / Out-of-Sample split tests."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from alphaedge.engine.backtest import (
    BacktestReport,
    BacktestStats,
    TradeRecord,
    compute_split_report,
    compute_stats,
    export_results_csv,
    split_trades_is_oos,
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _make_trade(
    idx: int,
    pnl: float = 10.0,
    pair: str = "EURUSD",
) -> TradeRecord:
    """Create a minimal TradeRecord with unique entry_time."""
    return TradeRecord(
        pair=pair,
        direction=1,
        entry_price=1.08500,
        stop_loss=1.08400,
        take_profit=1.08600,
        entry_time=datetime(2024, 1, 1) + timedelta(hours=idx),
        exit_price=1.08600 if pnl > 0 else 1.08400,
        exit_time=datetime(2024, 1, 1) + timedelta(hours=idx, minutes=30),
        pnl_pips=pnl,
        pnl_usd=pnl * 10.0,
        outcome="win" if pnl > 0 else "loss",
    )


def _make_trades(n: int = 10) -> list[TradeRecord]:
    """Create n trades with alternating wins/losses."""
    trades = []
    for i in range(n):
        pnl = 15.0 if i % 2 == 0 else -10.0
        trades.append(_make_trade(i, pnl))
    return trades


# ------------------------------------------------------------------
# split_trades_is_oos
# ------------------------------------------------------------------
class TestSplitTradesIsOos:
    def test_70_30_split_counts(self) -> None:
        trades = _make_trades(10)
        is_trades, oos_trades = split_trades_is_oos(trades, 0.7)
        assert len(is_trades) == 7
        assert len(oos_trades) == 3

    def test_sample_type_tagging(self) -> None:
        trades = _make_trades(10)
        is_trades, oos_trades = split_trades_is_oos(trades, 0.7)
        assert all(t.sample_type == "IS" for t in is_trades)
        assert all(t.sample_type == "OOS" for t in oos_trades)

    def test_chronological_order(self) -> None:
        """IS trades should precede OOS trades chronologically."""
        trades = _make_trades(10)
        is_trades, oos_trades = split_trades_is_oos(trades, 0.7)
        assert is_trades[-1].entry_time < oos_trades[0].entry_time

    def test_custom_ratio(self) -> None:
        trades = _make_trades(20)
        is_trades, oos_trades = split_trades_is_oos(trades, 0.5)
        assert len(is_trades) == 10
        assert len(oos_trades) == 10

    def test_empty_list(self) -> None:
        is_trades, oos_trades = split_trades_is_oos([], 0.7)
        assert is_trades == []
        assert oos_trades == []

    def test_single_trade(self) -> None:
        trades = [_make_trade(0)]
        is_trades, oos_trades = split_trades_is_oos(trades, 0.7)
        # int(1 * 0.7) = 0 → all go to OOS
        assert len(is_trades) == 0
        assert len(oos_trades) == 1

    def test_unsorted_input_still_splits_correctly(self) -> None:
        """Trades given out of order should be sorted before splitting."""
        trades = _make_trades(10)
        # Reverse to make them unsorted
        trades.reverse()
        is_trades, oos_trades = split_trades_is_oos(trades, 0.7)
        assert len(is_trades) == 7
        assert is_trades[-1].entry_time < oos_trades[0].entry_time


# ------------------------------------------------------------------
# compute_split_report
# ------------------------------------------------------------------
class TestComputeSplitReport:
    def test_report_structure(self) -> None:
        trades = _make_trades(10)
        report = compute_split_report(trades)
        assert isinstance(report, BacktestReport)
        assert isinstance(report.in_sample, BacktestStats)
        assert isinstance(report.out_of_sample, BacktestStats)
        assert isinstance(report.degradation, dict)

    def test_is_oos_trade_counts(self) -> None:
        trades = _make_trades(10)
        report = compute_split_report(trades)
        assert report.in_sample.total_trades == 7
        assert report.out_of_sample.total_trades == 3

    def test_degradation_keys(self) -> None:
        trades = _make_trades(10)
        report = compute_split_report(trades)
        assert "winrate" in report.degradation
        assert "profit_factor" in report.degradation
        assert "sharpe_ratio" in report.degradation

    def test_no_degradation_identical_distribution(self) -> None:
        """All-win trades → degradation should be ~0%."""
        trades = [_make_trade(i, pnl=10.0) for i in range(20)]
        report = compute_split_report(trades)
        # Win rate: 100% IS, 100% OOS → 0% degradation
        assert report.degradation["winrate"] == pytest.approx(0.0, abs=0.1)

    def test_degradation_calculation(self) -> None:
        """Verify degradation = (IS - OOS) / |IS| * 100."""
        trades = _make_trades(10)
        report = compute_split_report(trades)
        is_wr = report.in_sample.winrate
        oos_wr = report.out_of_sample.winrate
        if is_wr != 0.0:
            expected = ((is_wr - oos_wr) / abs(is_wr)) * 100.0
            assert report.degradation["winrate"] == pytest.approx(expected, abs=0.01)

    def test_empty_trades(self) -> None:
        report = compute_split_report([])
        assert report.in_sample.total_trades == 0
        assert report.out_of_sample.total_trades == 0


# ------------------------------------------------------------------
# CSV export includes sample_type
# ------------------------------------------------------------------
class TestCsvSampleTypeColumn:
    def test_csv_contains_sample_type(self, tmp_path: object) -> None:
        """Exported CSV should have a sample_type column."""
        import csv
        import os
        from pathlib import Path

        trades = _make_trades(10)
        # Tag them via split
        split_trades_is_oos(trades, 0.7)
        stats = compute_stats(trades)

        csv_file = str(Path(str(tmp_path)) / "test_results.csv")
        export_results_csv(trades, stats, output_path=csv_file)

        # Verify CSV exists and has sample_type column
        assert os.path.exists(csv_file)
        with open(csv_file, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 10
        assert "sample_type" in rows[0]
        # First 7 sorted by time should be IS, last 3 OOS
        is_count = sum(1 for r in rows if r["sample_type"] == "IS")
        oos_count = sum(1 for r in rows if r["sample_type"] == "OOS")
        assert is_count == 7
        assert oos_count == 3
