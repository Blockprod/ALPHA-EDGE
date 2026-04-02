"""ALPHAEDGE — Offline Bayesian optimization script.

Runs walk-forward Bayesian parameter search on the Momentum+Carry strategy
and proposes updated config.yaml values when OOS Sharpe improves baseline.

PREREQUISITES
-------------
1. A valid Momentum+Carry backtest must exist (post-migration Audit #13).
2. ``walk_forward_enabled: false`` must remain in config.yaml during live
   paper trading — run this script offline only.
3. Activate the virtual environment before running:
       .venv\\Scripts\\Activate.ps1

USAGE
-----
    python scripts/run_bayesian_optimization.py \\
        --pair EURUSD \\
        --n-trials 150 \\
        --train-months 6 \\
        --test-months 2

OUTPUT
------
    reports/bayesian_opt_result_YYYY-MM-DD.json

GATE: New parameters are proposed only when OOS Sharpe improves
      over the current baseline by at least 5%.

PARAMETERS OPTIMISED (Momentum+Carry)
--------------------------------------
    adx_threshold       : 20 – 35
    momentum_fast_period: 8  – 20  (EMA fast)
    momentum_slow_period: 20 – 50  (EMA slow)
    rr_ratio            : 1.5 – 3.0
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

# Resolve workspace root so the script works from any cwd
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from alphaedge.config.loader import load_config  # noqa: E402
from alphaedge.engine.bayesian_optimizer import optuna_search_best  # noqa: E402
from alphaedge.engine.walk_forward import run_walk_forward  # noqa: E402
from alphaedge.utils.logger import get_logger  # noqa: E402

logger = get_logger()

# Gate: only propose new params when OOS Sharpe improves by at least this ratio
_MIN_SHARPE_IMPROVEMENT: float = 1.05

# Baseline Sharpe to beat — UPDATE after first Momentum+Carry backtest
# (3.37 is the legacy baseline; Momentum+Carry OOS target is Sharpe >= 0.8)
_baseline_sharpe: float = 3.37


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Offline Bayesian parameter optimisation for ALPHAEDGE."
    )
    parser.add_argument("--pair", default="EURUSD", help="Currency pair.")
    parser.add_argument(
        "--n-trials", type=int, default=150, help="Number of Optuna trials."
    )
    parser.add_argument(
        "--train-months",
        type=int,
        default=6,
        help="Walk-forward training window (months).",
    )
    parser.add_argument(
        "--test-months",
        type=int,
        default=2,
        help="Walk-forward test window (months).",
    )
    parser.add_argument(
        "--metric",
        default="sharpe",
        choices=["sharpe", "pf"],
        help="Optimisation metric.",
    )
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    cfg = load_config(args.config)

    logger.info(
        "ALPHAEDGE BayesOpt: pair=%s trials=%d metric=%s",
        args.pair,
        args.n_trials,
        args.metric,
    )

    wf_report = run_walk_forward(
        daily_bars=[],  # Caller must supply bars — replace with data-fetch call
        pair=args.pair,
        config=cfg,
        optimize_fn=lambda bars, pair_, cfg_: optuna_search_best(
            bars, pair_, cfg_, n_trials=args.n_trials, metric=args.metric
        ),
        train_months=args.train_months,
        test_months=args.test_months,
    )

    oos_sharpe = wf_report.aggregated_oos_optimized.sharpe_ratio

    logger.info(
        "ALPHAEDGE BayesOpt: OOS optimised Sharpe=%.4f windows=%d",
        oos_sharpe,
        len(wf_report.windows),
    )

    # Gate: propose params only when improvement is meaningful
    output: dict[str, object] = {
        "generated": date.today().isoformat(),
        "pair": args.pair,
        "metric": args.metric,
        "n_trials": args.n_trials,
        "n_windows": len(wf_report.windows),
        "oos_optimised_sharpe": oos_sharpe,
        "best_params_per_window": [w.best_params for w in wf_report.windows],
        "proposal": None,
        "gate_passed": False,
    }

    if wf_report.windows:
        # Majority-vote on best params across OOS windows
        proposal: dict[str, float] = {}
        first_params = wf_report.windows[0].best_params or {}
        for param_name in first_params.keys():
            values = [
                w.best_params[param_name] for w in wf_report.windows if w.best_params
            ]
            counts: Counter[float] = Counter(round(v, 4) for v in values)
            proposal[param_name] = counts.most_common(1)[0][0]

        gate_passed = oos_sharpe >= _baseline_sharpe * _MIN_SHARPE_IMPROVEMENT
        output["proposal"] = proposal
        output["gate_passed"] = gate_passed

        if gate_passed:
            logger.info(
                "ALPHAEDGE BayesOpt: GATE PASSED — proposed params: %s", proposal
            )
            logger.info(
                "ALPHAEDGE BayesOpt: Update config.yaml manually after "
                "paper-trading validation."
            )
        else:
            logger.info(
                "ALPHAEDGE BayesOpt: GATE NOT PASSED — OOS Sharpe %.4f < "
                "baseline × %.2f = %.4f. Current params retained.",
                oos_sharpe,
                _MIN_SHARPE_IMPROVEMENT,
                _baseline_sharpe * _MIN_SHARPE_IMPROVEMENT,
            )

    # Write results
    reports_dir = _ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)
    out_path = reports_dir / f"bayesian_opt_result_{date.today().isoformat()}.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2)

    logger.info("ALPHAEDGE BayesOpt: results saved to %s", out_path)


if __name__ == "__main__":
    main()
