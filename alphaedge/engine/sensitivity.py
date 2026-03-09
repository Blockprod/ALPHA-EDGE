# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/engine/sensitivity.py
# DESCRIPTION  : Parameter sensitivity analysis with grid search
# ============================================================
"""ALPHAEDGE — Parameter sensitivity analysis and heatmap generation."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from alphaedge.config.constants import PROJECT_TITLE
from alphaedge.config.loader import AppConfig
from alphaedge.engine.backtest import (  # pylint: disable=cyclic-import
    BacktestStats,
    _backtest_pair,
    compute_stats,
)
from alphaedge.utils.logger import get_logger

matplotlib.use("Agg")

logger = get_logger()


# ------------------------------------------------------------------
# Parameter definition
# ------------------------------------------------------------------
@dataclass
class SensitivityParam:
    """Defines a parameter to sweep in sensitivity analysis."""

    name: str
    display_name: str
    min_val: float
    max_val: float
    step: float
    # Where the param lives: 'config' (TradingConfig) or 'constant' (module-level)
    source: str  # 'config' or 'constant'
    # Attribute name on TradingConfig (if source='config')
    # or constant name in backtest module (if source='constant')
    attr_name: str

    def values(self) -> list[float]:
        """Generate the sweep values for this parameter."""
        vals: list[float] = []
        v = self.min_val
        while v <= self.max_val + self.step * 0.01:
            vals.append(round(v, 4))
            v += self.step
        return vals


# ------------------------------------------------------------------
# Pre-defined parameter grid per spec
# ------------------------------------------------------------------
SENSITIVITY_PARAMS: dict[str, SensitivityParam] = {
    "min_atr_ratio": SensitivityParam(
        name="min_atr_ratio",
        display_name="ATR Ratio Threshold",
        min_val=1.0,
        max_val=2.5,
        step=0.1,
        source="constant",
        attr_name="DEFAULT_MIN_ATR_RATIO",
    ),
    "min_volume_ratio": SensitivityParam(
        name="min_volume_ratio",
        display_name="Volume Ratio",
        min_val=1.0,
        max_val=2.0,
        step=0.1,
        source="constant",
        attr_name="DEFAULT_MIN_VOLUME_RATIO",
    ),
    "min_range_pips": SensitivityParam(
        name="min_range_pips",
        display_name="Min FCR Range (pips)",
        min_val=3.0,
        max_val=15.0,
        step=1.0,
        source="constant",
        attr_name="DEFAULT_MIN_RANGE_PIPS",
    ),
    "rr_ratio": SensitivityParam(
        name="rr_ratio",
        display_name="RR Ratio",
        min_val=2.0,
        max_val=4.0,
        step=0.5,
        source="config",
        attr_name="rr_ratio",
    ),
    "min_body_ratio": SensitivityParam(
        name="min_body_ratio",
        display_name="Engulfing Min Body Ratio",
        min_val=0.1,
        max_val=0.5,
        step=0.1,
        source="config",
        attr_name="min_body_ratio",
    ),
}


# ------------------------------------------------------------------
# Sensitivity results
# ------------------------------------------------------------------
@dataclass
class Sensitivity2DResult:
    """Results of a 2D parameter sweep."""

    param_x: SensitivityParam
    param_y: SensitivityParam
    x_values: list[float] = field(default_factory=list)
    y_values: list[float] = field(default_factory=list)
    sharpe_grid: list[list[float]] = field(default_factory=list)
    pf_grid: list[list[float]] = field(default_factory=list)
    trade_count_grid: list[list[int]] = field(default_factory=list)


@dataclass
class RobustnessPlateau:
    """A region of parameter space with stable performance."""

    param_x_name: str
    param_y_name: str
    x_range: tuple[float, float]
    y_range: tuple[float, float]
    avg_sharpe: float
    avg_pf: float
    stability_score: float  # lower = more stable


# ------------------------------------------------------------------
# Apply parameter overrides
# ------------------------------------------------------------------
def _apply_param(
    config: AppConfig,
    param: SensitivityParam,
    value: float,
) -> AppConfig:
    """Apply a parameter value, returning a modified config copy."""
    import alphaedge.engine.backtest as bt_mod

    if param.source == "config":
        cfg = copy.deepcopy(config)
        setattr(cfg.trading, param.attr_name, value)
        return cfg
    # constant — patch the module-level constant
    setattr(bt_mod, param.attr_name, value)
    return config


def _restore_constant(param: SensitivityParam, original: float) -> None:
    """Restore a module-level constant to its original value."""
    if param.source == "constant":
        import alphaedge.engine.backtest as bt_mod

        setattr(bt_mod, param.attr_name, original)


def _get_original_constant(param: SensitivityParam) -> float:
    """Get the current value of a module-level constant."""
    import alphaedge.engine.backtest as bt_mod

    return float(getattr(bt_mod, param.attr_name))


# ------------------------------------------------------------------
# Run backtest with specific parameter values
# ------------------------------------------------------------------
def _run_with_params(
    m1_bars: list[dict[str, Any]],
    m5_bars: list[dict[str, Any]],
    pair: str,
    config: AppConfig,
    overrides: dict[str, float],
) -> BacktestStats:
    """
    Run a single backtest with parameter overrides.

    Parameters
    ----------
    m1_bars : list[dict]
        M1 bar data.
    m5_bars : list[dict]
        M5 bar data.
    pair : str
        Currency pair.
    config : AppConfig
        Base configuration.
    overrides : dict[str, float]
        Parameter name → value overrides.

    Returns
    -------
    BacktestStats
        Backtest stats for this parameter combination.
    """
    cfg = copy.deepcopy(config)
    originals: dict[str, float] = {}

    try:
        for name, value in overrides.items():
            param = SENSITIVITY_PARAMS[name]
            if param.source == "constant":
                originals[name] = _get_original_constant(param)
            cfg = _apply_param(cfg, param, value)

        trades = _backtest_pair(pair, m1_bars, m5_bars, cfg)
        return compute_stats(trades)
    finally:
        # Always restore patched constants
        for name, orig_val in originals.items():
            _restore_constant(SENSITIVITY_PARAMS[name], orig_val)


def _run_with_params_trades(
    m1_bars: list[dict[str, Any]],
    m5_bars: list[dict[str, Any]],
    pair: str,
    config: AppConfig,
    overrides: dict[str, float],
) -> list[Any]:
    """Like _run_with_params but returns raw trade records instead of stats."""
    cfg = copy.deepcopy(config)
    originals: dict[str, float] = {}

    try:
        for name, value in overrides.items():
            param = SENSITIVITY_PARAMS[name]
            if param.source == "constant":
                originals[name] = _get_original_constant(param)
            cfg = _apply_param(cfg, param, value)

        return _backtest_pair(pair, m1_bars, m5_bars, cfg)
    finally:
        for name, orig_val in originals.items():
            _restore_constant(SENSITIVITY_PARAMS[name], orig_val)


def grid_search_best(
    m1_bars: list[dict[str, Any]],
    m5_bars: list[dict[str, Any]],
    pair: str,
    config: AppConfig,
    param_names: list[str] | None = None,
    metric: str = "sharpe",
) -> dict[str, float]:
    """
    Find parameter overrides that maximise *metric* on IS bars.

    Runs ``_run_with_params`` for every combination in the Cartesian
    product of the specified parameters' sweep ranges and returns the
    combination that produced the highest metric value.

    Parameters
    ----------
    m1_bars : list[dict]
        In-sample M1 bars.
    m5_bars : list[dict]
        In-sample M5 bars.
    pair : str
        Currency pair.
    config : AppConfig
        Base configuration.
    param_names : list[str] | None
        Keys from SENSITIVITY_PARAMS to sweep.  Defaults to
        ``["min_atr_ratio", "min_volume_ratio", "rr_ratio"]``.
    metric : str
        ``"sharpe"`` (Sharpe ratio) or ``"pf"`` (profit factor).

    Returns
    -------
    dict[str, float]
        Best ``{param_name: value}`` overrides.
    """
    import itertools

    if param_names is None:
        param_names = ["min_atr_ratio", "min_volume_ratio", "rr_ratio"]

    param_objs = [SENSITIVITY_PARAMS[n] for n in param_names]
    value_lists = [p.values() for p in param_objs]

    best_score = float("-inf")
    best_overrides: dict[str, float] = {
        n: param_objs[i].min_val for i, n in enumerate(param_names)
    }

    for combo in itertools.product(*value_lists):
        overrides = dict(zip(param_names, combo))
        stats = _run_with_params(m1_bars, m5_bars, pair, config, overrides)
        score = stats.sharpe_ratio if metric == "sharpe" else stats.profit_factor

        if score > best_score:
            best_score = score
            best_overrides = overrides

    return best_overrides


# ------------------------------------------------------------------
# 2D parameter sweep
# ------------------------------------------------------------------
def run_sensitivity_2d(
    m1_bars: list[dict[str, Any]],
    m5_bars: list[dict[str, Any]],
    pair: str,
    config: AppConfig,
    param_x_name: str,
    param_y_name: str,
) -> Sensitivity2DResult:
    """
    Run a 2D grid search over two parameters.

    Parameters
    ----------
    m1_bars : list[dict]
        M1 bar data.
    m5_bars : list[dict]
        M5 bar data.
    pair : str
        Currency pair.
    config : AppConfig
        Base configuration.
    param_x_name : str
        Name of the X-axis parameter (key in SENSITIVITY_PARAMS).
    param_y_name : str
        Name of the Y-axis parameter.

    Returns
    -------
    Sensitivity2DResult
        Grid of Sharpe, PF, and trade counts.
    """
    param_x = SENSITIVITY_PARAMS[param_x_name]
    param_y = SENSITIVITY_PARAMS[param_y_name]
    x_vals = param_x.values()
    y_vals = param_y.values()

    result = Sensitivity2DResult(
        param_x=param_x,
        param_y=param_y,
        x_values=x_vals,
        y_values=y_vals,
    )

    for y_val in y_vals:
        sharpe_row: list[float] = []
        pf_row: list[float] = []
        count_row: list[int] = []

        for x_val in x_vals:
            stats = _run_with_params(
                m1_bars,
                m5_bars,
                pair,
                config,
                {param_x_name: x_val, param_y_name: y_val},
            )
            sharpe_row.append(stats.sharpe_ratio)
            pf_row.append(stats.profit_factor)
            count_row.append(stats.total_trades)

        result.sharpe_grid.append(sharpe_row)
        result.pf_grid.append(pf_row)
        result.trade_count_grid.append(count_row)

    return result


# ------------------------------------------------------------------
# Heatmap generation
# ------------------------------------------------------------------
def generate_heatmap(
    result: Sensitivity2DResult,
    metric: str = "sharpe",
    output_path: str | None = None,
) -> str:
    """
    Generate a heatmap for a 2D sensitivity sweep.

    Parameters
    ----------
    result : Sensitivity2DResult
        The grid search results.
    metric : str
        'sharpe' or 'pf' (profit factor).
    output_path : str | None
        Output file path. Auto-generated if None.

    Returns
    -------
    str
        Path to the saved heatmap PNG.
    """
    if metric == "sharpe":
        grid = np.array(result.sharpe_grid)
        title_metric = "Sharpe Ratio"
    else:
        grid = np.array(result.pf_grid)
        title_metric = "Profit Factor"

    if output_path is None:
        output_path = (
            f"ALPHAEDGE_heatmap_{result.param_x.name}_vs_"
            f"{result.param_y.name}_{metric}.png"
        )

    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(grid, aspect="auto", cmap="RdYlGn", origin="lower")

    ax.set_xticks(range(len(result.x_values)))
    ax.set_xticklabels([f"{v:.1f}" for v in result.x_values], rotation=45)
    ax.set_yticks(range(len(result.y_values)))
    ax.set_yticklabels([f"{v:.1f}" for v in result.y_values])

    ax.set_xlabel(result.param_x.display_name)
    ax.set_ylabel(result.param_y.display_name)
    ax.set_title(
        f"{PROJECT_TITLE} — {title_metric}: "
        f"{result.param_x.display_name} vs {result.param_y.display_name}"
    )

    fig.colorbar(im, ax=ax, label=title_metric)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    logger.info(f"ALPHAEDGE heatmap saved to {output_path}")
    return output_path


# ------------------------------------------------------------------
# Robustness plateau detection
# ------------------------------------------------------------------
def find_robustness_plateau(
    result: Sensitivity2DResult,
    min_sharpe: float = 0.0,
    min_pf: float = 1.0,
    min_trades: int = 5,
) -> RobustnessPlateau | None:
    """
    Identify the largest contiguous region of stable performance.

    A cell qualifies if Sharpe >= min_sharpe, PF >= min_pf,
    and trade count >= min_trades. The plateau is the bounding box
    of qualifying cells with the lowest coefficient of variation
    in Sharpe across the region.

    Parameters
    ----------
    result : Sensitivity2DResult
        2D sweep results.
    min_sharpe : float
        Minimum Sharpe to qualify.
    min_pf : float
        Minimum profit factor to qualify.
    min_trades : int
        Minimum trade count to qualify.

    Returns
    -------
    RobustnessPlateau | None
        The identified plateau, or None if no qualifying region found.
    """
    sharpe_arr = np.array(result.sharpe_grid)
    pf_arr = np.array(result.pf_grid)
    count_arr = np.array(result.trade_count_grid)

    # Mask of qualifying cells
    mask = (sharpe_arr >= min_sharpe) & (pf_arr >= min_pf) & (count_arr >= min_trades)

    qualifying_cells = list(zip(*np.where(mask)))
    if not qualifying_cells:
        return None

    # Bounding box of qualifying cells
    y_indices = [c[0] for c in qualifying_cells]
    x_indices = [c[1] for c in qualifying_cells]

    y_min_idx, y_max_idx = min(y_indices), max(y_indices)
    x_min_idx, x_max_idx = min(x_indices), max(x_indices)

    # Extract the region
    region_sharpe = sharpe_arr[y_min_idx : y_max_idx + 1, x_min_idx : x_max_idx + 1]
    region_pf = pf_arr[y_min_idx : y_max_idx + 1, x_min_idx : x_max_idx + 1]

    avg_sharpe = float(np.mean(region_sharpe))
    avg_pf = float(np.mean(region_pf))

    # Stability score: coefficient of variation of Sharpe in the region
    std_sharpe = float(np.std(region_sharpe))
    stability = std_sharpe / abs(avg_sharpe) if avg_sharpe != 0 else float("inf")

    return RobustnessPlateau(
        param_x_name=result.param_x.name,
        param_y_name=result.param_y.name,
        x_range=(result.x_values[x_min_idx], result.x_values[x_max_idx]),
        y_range=(result.y_values[y_min_idx], result.y_values[y_max_idx]),
        avg_sharpe=avg_sharpe,
        avg_pf=avg_pf,
        stability_score=stability,
    )


# ------------------------------------------------------------------
# Full sensitivity analysis
# ------------------------------------------------------------------
def run_full_sensitivity(
    m1_bars: list[dict[str, Any]],
    m5_bars: list[dict[str, Any]],
    pair: str,
    config: AppConfig,
    output_dir: str = ".",
) -> list[RobustnessPlateau]:
    """
    Run all 2D parameter combinations and generate heatmaps.

    Parameters
    ----------
    m1_bars : list[dict]
        M1 bar data.
    m5_bars : list[dict]
        M5 bar data.
    pair : str
        Currency pair.
    config : AppConfig
        Base configuration.
    output_dir : str
        Directory for output heatmap files.

    Returns
    -------
    list[RobustnessPlateau]
        Plateaus found for each parameter pair.
    """
    import os

    param_names = list(SENSITIVITY_PARAMS.keys())
    plateaus: list[RobustnessPlateau] = []

    for i, px in enumerate(param_names):
        for py in param_names[i + 1 :]:
            logger.info(
                f"{PROJECT_TITLE} — Sensitivity: "
                f"{SENSITIVITY_PARAMS[px].display_name} vs "
                f"{SENSITIVITY_PARAMS[py].display_name}"
            )

            result = run_sensitivity_2d(m1_bars, m5_bars, pair, config, px, py)

            # Generate heatmaps
            for metric in ("sharpe", "pf"):
                path = os.path.join(
                    output_dir,
                    f"ALPHAEDGE_heatmap_{px}_vs_{py}_{metric}.png",
                )
                generate_heatmap(result, metric=metric, output_path=path)

            # Find plateau
            plateau = find_robustness_plateau(result)
            if plateau:
                plateaus.append(plateau)
                logger.info(
                    f"  Plateau found: "
                    f"{plateau.param_x_name}="
                    f"[{plateau.x_range[0]:.1f}-{plateau.x_range[1]:.1f}], "
                    f"{plateau.param_y_name}="
                    f"[{plateau.y_range[0]:.1f}-{plateau.y_range[1]:.1f}], "
                    f"avg Sharpe={plateau.avg_sharpe:.2f}, "
                    f"stability={plateau.stability_score:.3f}"
                )
            else:
                logger.warning(f"  No robustness plateau found for {px} vs {py}")

    return plateaus
