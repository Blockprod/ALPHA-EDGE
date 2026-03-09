# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_backtest_export.py
# DESCRIPTION  : Tests for backtest_export module (P3-02 SRP extraction)
# AUTHOR       : ALPHAEDGE Dev Team
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-08
# ============================================================
"""Tests for export_results_csv and plot_equity_curve."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from alphaedge.engine.backtest_export import export_results_csv, plot_equity_curve
from alphaedge.engine.backtest_types import BacktestStats, TradeRecord


# ------------------------------------------------------------------
# Helper
# ------------------------------------------------------------------
def _make_trade(pnl_pips: float = 10.0, direction: int = 1) -> TradeRecord:
    return TradeRecord(
        pair="EURUSD",
        direction=direction,
        entry_price=1.10000,
        stop_loss=1.09900,
        take_profit=1.10300,
        entry_time=datetime(2025, 1, 2, 9, 0),
        exit_price=1.10300 if pnl_pips > 0 else 1.09900,
        exit_time=datetime(2025, 1, 2, 10, 0),
        pnl_pips=pnl_pips,
        pnl_usd=pnl_pips * 10.0,
        outcome="win" if pnl_pips > 0 else "loss",
        sample_type="IS",
    )


# ==================================================================
# Tests — export_results_csv
# ==================================================================
class TestExportResultsCsv:
    """Verify CSV export of trade records."""

    def test_creates_file(self, tmp_path: Path) -> None:
        out = str(tmp_path / "results.csv")
        export_results_csv([_make_trade()], BacktestStats(), output_path=out)
        assert Path(out).exists()

    def test_csv_has_required_columns(self, tmp_path: Path) -> None:
        import pandas as pd

        out = str(tmp_path / "results.csv")
        export_results_csv(
            [_make_trade(), _make_trade(-5.0)], BacktestStats(), output_path=out
        )
        df = pd.read_csv(out)
        for col in (
            "pair",
            "direction",
            "pnl_pips",
            "pnl_usd",
            "outcome",
            "sample_type",
        ):
            assert col in df.columns, f"Missing column: {col}"

    def test_csv_trade_count(self, tmp_path: Path) -> None:
        import pandas as pd

        out = str(tmp_path / "results.csv")
        trades = [_make_trade(10.0), _make_trade(-5.0), _make_trade(8.0)]
        export_results_csv(trades, BacktestStats(), output_path=out)
        df = pd.read_csv(out)
        assert len(df) == 3

    def test_empty_trades_creates_empty_csv(self, tmp_path: Path) -> None:
        out = str(tmp_path / "empty.csv")
        export_results_csv([], BacktestStats(), output_path=out)
        assert Path(out).exists()
        # Empty trades → empty DataFrame → empty CSV (no rows, possibly no columns)
        content = Path(out).read_text(encoding="utf-8").strip()
        assert content == ""

    def test_direction_label(self, tmp_path: Path) -> None:
        import pandas as pd

        out = str(tmp_path / "dir.csv")
        export_results_csv(
            [_make_trade(10.0, direction=1), _make_trade(-5.0, direction=-1)],
            BacktestStats(),
            output_path=out,
        )
        df = pd.read_csv(out)
        assert df.loc[0, "direction"] == "LONG"
        assert df.loc[1, "direction"] == "SHORT"


# ==================================================================
# Tests — plot_equity_curve
# ==================================================================
class TestPlotEquityCurve:
    """Verify equity curve PNG generation."""

    def test_creates_png(self, tmp_path: Path) -> None:
        out = str(tmp_path / "curve.png")
        plot_equity_curve([_make_trade(10.0), _make_trade(-5.0)], output_path=out)
        assert Path(out).exists()
        assert Path(out).stat().st_size > 0

    def test_empty_trades_creates_file(self, tmp_path: Path) -> None:
        out = str(tmp_path / "empty_curve.png")
        plot_equity_curve([], output_path=out)
        assert Path(out).exists()
