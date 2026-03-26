# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_bayesian_optimizer_search.py
# DESCRIPTION  : Unit tests for Optuna-based parameter search
# SCENARIO     : Return shape · ranges · trial count · metric switch
# PYTHON       : 3.11.9
# ============================================================
"""Tests for alphaedge.engine.bayesian_optimizer.optuna_search_best."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from alphaedge.config.loader import load_config
from alphaedge.engine.bayesian_optimizer import optuna_search_best
from alphaedge.engine.sensitivity import SENSITIVITY_PARAMS


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _make_bar(
    dt: datetime,
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: float = 1000.0,
) -> dict[str, Any]:
    return {
        "datetime": dt,
        "timestamp": int(dt.timestamp()),
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


def _make_synthetic_bars() -> list[dict[str, Any]]:
    """Build a minimal but valid daily synthetic dataset for optimization."""
    start = datetime(2025, 1, 2, 0, 0, tzinfo=UTC)

    daily_bars: list[dict[str, Any]] = []
    for i in range(60):
        base = 1.1000 + i * 0.0002
        daily_bars.append(
            _make_bar(
                start + timedelta(days=i),
                open_=base,
                high=base + 0.0050,
                low=base - 0.0040,
                close=base + 0.0020,
            )
        )

    return daily_bars


@pytest.fixture()
def app_config():
    """Load the real project config for optimizer tests."""
    return load_config("config.yaml")


class TestOptunaSearchBest:
    """C-02 — Optuna Bayesian search tests."""

    def test_returns_valid_param_dict(self, app_config) -> None:
        """The optimizer must return a dict with the requested keys."""
        daily_bars = _make_synthetic_bars()
        result = optuna_search_best(
            daily_bars,
            "EURUSD",
            app_config,
            n_trials=2,
        )
        assert isinstance(result, dict)
        assert set(result) == {
            "adx_threshold",
            "momentum_fast_period",
            "momentum_slow_period",
            "rr_ratio",
        }

    def test_param_values_in_range(self, app_config) -> None:
        """Every returned value must stay inside the configured bounds."""
        daily_bars = _make_synthetic_bars()
        result = optuna_search_best(
            daily_bars,
            "EURUSD",
            app_config,
            n_trials=2,
        )
        for name, value in result.items():
            param = SENSITIVITY_PARAMS[name]
            assert param.min_val <= value <= param.max_val

    def test_n_trials_respected(
        self,
        app_config,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The optimizer must pass the requested n_trials to Optuna."""
        import optuna

        captured: dict[str, int] = {}
        real_optimize = optuna.study.Study.optimize

        def wrapped_optimize(self, func, n_trials=None, *o_args, **o_kwargs):
            captured["n_trials"] = int(n_trials or 0)
            return real_optimize(self, func, n_trials=n_trials, *o_args, **o_kwargs)

        monkeypatch.setattr(optuna.study.Study, "optimize", wrapped_optimize)

        daily_bars = _make_synthetic_bars()
        optuna_search_best(
            daily_bars,
            "EURUSD",
            app_config,
            n_trials=3,
        )
        assert captured["n_trials"] == 3

    def test_metric_sharpe_vs_pf(self, app_config) -> None:
        """Both supported metrics must execute without raising."""
        daily_bars = _make_synthetic_bars()

        sharpe_result = optuna_search_best(
            daily_bars,
            "EURUSD",
            app_config,
            n_trials=2,
            metric="sharpe",
        )
        pf_result = optuna_search_best(
            daily_bars,
            "EURUSD",
            app_config,
            n_trials=2,
            metric="pf",
        )

        assert set(sharpe_result) == set(pf_result)

    def test_invalid_metric_raises(self, app_config) -> None:
        """An invalid metric must raise ValueError."""
        daily_bars = _make_synthetic_bars()
        with pytest.raises(ValueError, match="metric must be 'sharpe' or 'pf'"):
            optuna_search_best(
                daily_bars,
                "EURUSD",
                app_config,
                n_trials=1,
                metric="invalid",
            )
