"""Tests for C-ST-09 realized RR ratio analysis."""

import pandas as pd
from scripts.analyze_rr_ratio import analyze_rr_ratio


class TestRRRatioAnalysis:
    """Validate configured vs realized RR computations."""

    def test_realized_rr_computation(self) -> None:
        df = pd.DataFrame(
            [
                {"pair": "EURUSD", "pnl_pips": 20.0},
                {"pair": "EURUSD", "pnl_pips": 30.0},
                {"pair": "EURUSD", "pnl_pips": -10.0},
                {"pair": "EURUSD", "pnl_pips": -10.0},
            ]
        )

        result = analyze_rr_ratio(df, configured_rr=2.0)
        overall = result["overall"]

        assert overall is not None
        assert round(overall.avg_win_pips, 2) == 25.0
        assert round(overall.avg_loss_pips_abs, 2) == 10.0
        assert round(overall.realized_rr, 2) == 2.5
        assert round(overall.rr_gap, 2) == -0.5

    def test_per_pair_breakdown(self) -> None:
        df = pd.DataFrame(
            [
                {"pair": "EURUSD", "pnl_pips": 20.0},
                {"pair": "EURUSD", "pnl_pips": -10.0},
                {"pair": "GBPUSD", "pnl_pips": 15.0},
                {"pair": "GBPUSD", "pnl_pips": -15.0},
            ]
        )

        result = analyze_rr_ratio(df, configured_rr=2.0)
        pairs = result["per_pair"]

        assert len(pairs) == 2
        eur = next(p for p in pairs if p.scope == "EURUSD")
        gbp = next(p for p in pairs if p.scope == "GBPUSD")

        assert round(eur.realized_rr, 2) == 2.0
        assert round(gbp.realized_rr, 2) == 1.0
