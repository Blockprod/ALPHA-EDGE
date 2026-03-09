# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_sensitivity.py
# DESCRIPTION  : Tests for parameter sensitivity analysis
# ============================================================
"""ALPHAEDGE — T3.3: Parameter sensitivity analysis tests."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from alphaedge.config.loader import AppConfig
from alphaedge.engine.backtest import BacktestStats, TradeRecord
from alphaedge.engine.sensitivity import (
    SENSITIVITY_PARAMS,
    RobustnessPlateau,
    Sensitivity2DResult,
    SensitivityParam,
    _run_with_params,
    find_robustness_plateau,
    generate_heatmap,
    run_sensitivity_2d,
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _make_trade(pnl: float = 10.0) -> TradeRecord:
    return TradeRecord(
        pair="EURUSD",
        direction=1,
        entry_price=1.08500,
        stop_loss=1.08400,
        take_profit=1.08600,
        entry_time=datetime(2024, 1, 1, 10, 0, tzinfo=ZoneInfo("America/New_York")),
        exit_price=1.08600 if pnl > 0 else 1.08400,
        pnl_pips=pnl,
        pnl_usd=pnl * 10.0,
        outcome="win" if pnl > 0 else "loss",
    )


def _fake_backtest(
    pair: str,
    m1: list[dict[str, Any]],
    m5: list[dict[str, Any]],
    cfg: AppConfig,
) -> list[TradeRecord]:
    """Return trades that vary based on config parameters."""
    rr = cfg.trading.rr_ratio
    # More trades with lower RR, fewer with higher
    n_trades = max(1, int(10 / rr))
    return [_make_trade(pnl=rr * 5.0) for _ in range(n_trades)]


# ------------------------------------------------------------------
# SensitivityParam
# ------------------------------------------------------------------
class TestSensitivityParam:
    def test_values_generation(self) -> None:
        p = SensitivityParam(
            name="test",
            display_name="Test",
            min_val=1.0,
            max_val=2.0,
            step=0.5,
            source="config",
            attr_name="rr_ratio",
        )
        assert p.values() == [1.0, 1.5, 2.0]

    def test_all_params_defined(self) -> None:
        expected = {
            "min_atr_ratio",
            "min_volume_ratio",
            "min_range_pips",
            "rr_ratio",
            "min_body_ratio",
        }
        assert set(SENSITIVITY_PARAMS.keys()) == expected

    def test_param_ranges_match_spec(self) -> None:
        assert SENSITIVITY_PARAMS["min_atr_ratio"].min_val == 1.0
        assert SENSITIVITY_PARAMS["min_atr_ratio"].max_val == 2.5
        assert SENSITIVITY_PARAMS["rr_ratio"].min_val == 2.0
        assert SENSITIVITY_PARAMS["rr_ratio"].max_val == 4.0
        assert SENSITIVITY_PARAMS["min_range_pips"].step == 1.0


# ------------------------------------------------------------------
# _run_with_params
# ------------------------------------------------------------------
class TestRunWithParams:
    def test_config_override_applied(self) -> None:
        """Config-based params should modify the config."""
        with patch(
            "alphaedge.engine.sensitivity._backtest_pair",
            side_effect=_fake_backtest,
        ):
            stats = _run_with_params([], [], "EURUSD", AppConfig(), {"rr_ratio": 3.5})
        assert isinstance(stats, BacktestStats)

    def test_constant_override_restored(self) -> None:
        """Module constants should be restored after run."""
        from alphaedge.engine.sensitivity import _get_original_constant

        param = SENSITIVITY_PARAMS["min_atr_ratio"]
        original = _get_original_constant(param)

        with patch(
            "alphaedge.engine.sensitivity._backtest_pair",
            side_effect=_fake_backtest,
        ):
            _run_with_params([], [], "EURUSD", AppConfig(), {"min_atr_ratio": 99.0})

        assert _get_original_constant(param) == original

    def test_constant_restored_on_error(self) -> None:
        """Constants restored even if backtest raises."""
        from alphaedge.engine.sensitivity import _get_original_constant

        param = SENSITIVITY_PARAMS["min_atr_ratio"]
        original = _get_original_constant(param)

        def raise_error(*args: Any, **kwargs: Any) -> list[TradeRecord]:
            raise RuntimeError("test")

        with (
            patch(
                "alphaedge.engine.sensitivity._backtest_pair",
                side_effect=raise_error,
            ),
            pytest.raises(RuntimeError),
        ):
            _run_with_params([], [], "EURUSD", AppConfig(), {"min_atr_ratio": 99.0})

        assert _get_original_constant(param) == original


# ------------------------------------------------------------------
# run_sensitivity_2d
# ------------------------------------------------------------------
class TestRunSensitivity2D:
    def test_grid_dimensions(self) -> None:
        with patch(
            "alphaedge.engine.sensitivity._backtest_pair",
            side_effect=_fake_backtest,
        ):
            result = run_sensitivity_2d(
                [], [], "EURUSD", AppConfig(), "rr_ratio", "min_body_ratio"
            )

        assert isinstance(result, Sensitivity2DResult)
        n_x = len(SENSITIVITY_PARAMS["rr_ratio"].values())
        n_y = len(SENSITIVITY_PARAMS["min_body_ratio"].values())
        assert len(result.sharpe_grid) == n_y
        assert len(result.sharpe_grid[0]) == n_x
        assert len(result.pf_grid) == n_y
        assert len(result.trade_count_grid) == n_y

    def test_values_populated(self) -> None:
        with patch(
            "alphaedge.engine.sensitivity._backtest_pair",
            side_effect=_fake_backtest,
        ):
            result = run_sensitivity_2d(
                [], [], "EURUSD", AppConfig(), "rr_ratio", "min_body_ratio"
            )

        assert result.x_values == SENSITIVITY_PARAMS["rr_ratio"].values()
        assert result.y_values == SENSITIVITY_PARAMS["min_body_ratio"].values()


# ------------------------------------------------------------------
# generate_heatmap
# ------------------------------------------------------------------
class TestGenerateHeatmap:
    def test_heatmap_file_created(self, tmp_path: Any) -> None:
        result = Sensitivity2DResult(
            param_x=SENSITIVITY_PARAMS["rr_ratio"],
            param_y=SENSITIVITY_PARAMS["min_body_ratio"],
            x_values=[2.0, 2.5, 3.0],
            y_values=[0.1, 0.2, 0.3],
            sharpe_grid=[[0.5, 0.6, 0.7], [0.6, 0.8, 0.9], [0.4, 0.5, 0.6]],
            pf_grid=[[1.2, 1.3, 1.5], [1.4, 1.6, 1.8], [1.1, 1.2, 1.3]],
            trade_count_grid=[[10, 8, 6], [12, 10, 8], [14, 12, 10]],
        )

        path = str(tmp_path / "test_heatmap.png")
        out = generate_heatmap(result, metric="sharpe", output_path=path)
        assert os.path.exists(out)

    def test_pf_heatmap(self, tmp_path: Any) -> None:
        result = Sensitivity2DResult(
            param_x=SENSITIVITY_PARAMS["rr_ratio"],
            param_y=SENSITIVITY_PARAMS["min_body_ratio"],
            x_values=[2.0, 3.0],
            y_values=[0.1, 0.2],
            sharpe_grid=[[0.5, 0.7], [0.6, 0.8]],
            pf_grid=[[1.2, 1.5], [1.4, 1.8]],
            trade_count_grid=[[10, 8], [12, 10]],
        )

        path = str(tmp_path / "test_pf.png")
        out = generate_heatmap(result, metric="pf", output_path=path)
        assert os.path.exists(out)


# ------------------------------------------------------------------
# find_robustness_plateau
# ------------------------------------------------------------------
class TestFindRobustnessPlateau:
    def test_finds_plateau(self) -> None:
        result = Sensitivity2DResult(
            param_x=SENSITIVITY_PARAMS["rr_ratio"],
            param_y=SENSITIVITY_PARAMS["min_body_ratio"],
            x_values=[2.0, 2.5, 3.0, 3.5, 4.0],
            y_values=[0.1, 0.2, 0.3, 0.4, 0.5],
            sharpe_grid=[
                [0.5, 0.6, 0.7, 0.6, 0.5],
                [0.6, 0.8, 0.9, 0.8, 0.6],
                [0.7, 0.9, 1.0, 0.9, 0.7],
                [0.6, 0.8, 0.9, 0.8, 0.6],
                [0.5, 0.6, 0.7, 0.6, 0.5],
            ],
            pf_grid=[
                [1.2, 1.3, 1.5, 1.3, 1.2],
                [1.3, 1.6, 1.8, 1.6, 1.3],
                [1.5, 1.8, 2.0, 1.8, 1.5],
                [1.3, 1.6, 1.8, 1.6, 1.3],
                [1.2, 1.3, 1.5, 1.3, 1.2],
            ],
            trade_count_grid=[
                [10, 10, 10, 10, 10],
                [10, 10, 10, 10, 10],
                [10, 10, 10, 10, 10],
                [10, 10, 10, 10, 10],
                [10, 10, 10, 10, 10],
            ],
        )

        plateau = find_robustness_plateau(result, min_sharpe=0.5, min_pf=1.0)
        assert plateau is not None
        assert isinstance(plateau, RobustnessPlateau)
        assert plateau.avg_sharpe > 0
        assert plateau.avg_pf > 0

    def test_no_plateau_when_all_below_threshold(self) -> None:
        result = Sensitivity2DResult(
            param_x=SENSITIVITY_PARAMS["rr_ratio"],
            param_y=SENSITIVITY_PARAMS["min_body_ratio"],
            x_values=[2.0, 3.0],
            y_values=[0.1, 0.2],
            sharpe_grid=[[-1.0, -0.5], [-0.8, -0.3]],
            pf_grid=[[0.5, 0.6], [0.4, 0.7]],
            trade_count_grid=[[10, 10], [10, 10]],
        )

        plateau = find_robustness_plateau(result, min_sharpe=0.5, min_pf=1.0)
        assert plateau is None

    def test_plateau_stability_score(self) -> None:
        """A perfectly uniform grid should have stability_score=0."""
        result = Sensitivity2DResult(
            param_x=SENSITIVITY_PARAMS["rr_ratio"],
            param_y=SENSITIVITY_PARAMS["min_body_ratio"],
            x_values=[2.0, 3.0],
            y_values=[0.1, 0.2],
            sharpe_grid=[[1.0, 1.0], [1.0, 1.0]],
            pf_grid=[[1.5, 1.5], [1.5, 1.5]],
            trade_count_grid=[[10, 10], [10, 10]],
        )

        plateau = find_robustness_plateau(result, min_sharpe=0.5, min_pf=1.0)
        assert plateau is not None
        assert plateau.stability_score == pytest.approx(0.0, abs=0.001)
