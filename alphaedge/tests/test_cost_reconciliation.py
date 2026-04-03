"""Tests for C-ST-08 cost reconciliation helpers."""

from pathlib import Path

import pandas as pd

from alphaedge.engine.backtest_export import (
    cost_divergence_within_tolerance,
    export_cost_comparison,
)


class TestCostReconciliation:
    """Validate backtest/live transaction cost reconciliation."""

    def test_export_cost_comparison_creates_csv(self, tmp_path: Path) -> None:
        backtest_df = pd.DataFrame(
            [
                {
                    "pair": "EURUSD",
                    "direction": "LONG",
                    "entry_time": "2026-03-24T15:30:00+00:00",
                    "spread_cost_pips": 0.5,
                    "slippage_pips": 0.2,
                },
                {
                    "pair": "GBPUSD",
                    "direction": "SHORT",
                    "entry_time": "2026-03-24T15:45:00+00:00",
                    "spread_cost_pips": 1.0,
                    "slippage_pips": 0.3,
                },
            ]
        )
        live_df = pd.DataFrame(
            [
                {
                    "pair": "EURUSD",
                    "direction": "LONG",
                    "entry_time": "2026-03-24T15:30:10+00:00",
                    "spread_pips": 0.6,
                    "slippage_pips": 0.25,
                },
                {
                    "pair": "GBPUSD",
                    "direction": "SHORT",
                    "entry_time": "2026-03-24T15:45:10+00:00",
                    "spread_pips": 1.1,
                    "slippage_pips": 0.35,
                },
            ]
        )

        output_path = tmp_path / "cost_comparison.csv"
        result = export_cost_comparison(backtest_df, live_df, str(output_path))

        assert output_path.exists()
        assert not result.empty
        assert "diff_pips" in result.columns
        assert "diff_pct" in result.columns
        assert len(result) == 2

    def test_cost_divergence_within_tolerance_percent(self) -> None:
        comparison_df = pd.DataFrame(
            [
                {"diff_pct": 10.0},
                {"diff_pct": -12.5},
                {"diff_pct": 14.9},
            ]
        )
        assert cost_divergence_within_tolerance(comparison_df, tolerance_pct=15.0)

        breached_df = pd.DataFrame(
            [
                {"diff_pct": 10.0},
                {"diff_pct": 16.0},
            ]
        )
        assert not cost_divergence_within_tolerance(breached_df, tolerance_pct=15.0)
