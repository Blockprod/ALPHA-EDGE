# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/engine/bayesian_optimizer.py
# DESCRIPTION  : Bayesian parameter search with Optuna
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-22
# ============================================================
"""Optuna-powered parameter search for walk-forward optimization.

This module provides a drop-in alternative to
`alphaedge.engine.sensitivity.grid_search_best()` via the same
`optimize_fn` signature expected by `run_walk_forward()`.
"""

from __future__ import annotations

from typing import Any

import optuna

from alphaedge.config.loader import AppConfig
from alphaedge.engine.sensitivity import SENSITIVITY_PARAMS, _run_with_params

_DEFAULT_PARAM_NAMES = [
    "min_atr_ratio",
    "min_volume_ratio",
    "min_range_pips",
    "rr_ratio",
    "min_body_ratio",
]

optuna.logging.set_verbosity(optuna.logging.WARNING)


def _suggest_float(
    trial: optuna.trial.Trial,
    param_name: str,
) -> float:
    """Suggest a float value using the configured sensitivity range."""
    param = SENSITIVITY_PARAMS[param_name]
    return float(
        trial.suggest_float(
            param_name,
            param.min_val,
            param.max_val,
            step=param.step,
        )
    )


def optuna_search_best(
    m1_bars: list[dict[str, Any]],
    m5_bars: list[dict[str, Any]],
    pair: str,
    config: AppConfig,
    n_trials: int = 150,
    metric: str = "sharpe",
    param_names: list[str] | None = None,
) -> dict[str, float]:
    """Find parameter overrides that maximise a metric via Optuna.

    Parameters
    ----------
    m1_bars : list[dict[str, Any]]
        In-sample M1 bars.
    m5_bars : list[dict[str, Any]]
        In-sample M5 bars.
    pair : str
        Currency pair.
    config : AppConfig
        Base configuration.
    n_trials : int
        Number of Optuna trials.
    metric : str
        ``"sharpe"`` or ``"pf"``.
    param_names : list[str] | None
        Parameters to optimize. Defaults to the five main FCR parameters.

    Returns
    -------
    dict[str, float]
        Best ``{param_name: value}`` overrides.
    """
    if metric not in {"sharpe", "pf"}:
        raise ValueError("metric must be 'sharpe' or 'pf'")

    search_names = param_names or list(_DEFAULT_PARAM_NAMES)

    def objective(trial: optuna.trial.Trial) -> float:
        overrides = {name: _suggest_float(trial, name) for name in search_names}
        stats = _run_with_params(m1_bars, m5_bars, pair, config, overrides)
        score = stats.sharpe_ratio if metric == "sharpe" else stats.profit_factor
        trial.set_user_attr("overrides", overrides)
        return float(score)

    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=42),
        pruner=optuna.pruners.MedianPruner(n_startup_trials=20),
    )
    study.optimize(objective, n_trials=n_trials)

    best_params = study.best_params
    return {name: float(best_params[name]) for name in search_names}
