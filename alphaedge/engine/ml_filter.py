# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/engine/ml_filter.py
# DESCRIPTION  : Compatibility shim — code archived to _experimental/
# PYTHON       : 3.11.9
# ============================================================
"""Backward-compatible re-export shim.

All ML filter logic has been moved to
``alphaedge.engine._experimental.ml_filter`` (pending strategic
validation before live-pipeline integration).

Importing from this module continues to work as before.
"""

from alphaedge.engine._experimental.ml_filter import (  # noqa: F401
    DEFAULT_WIN_THRESHOLD,
    FEATURE_NAMES,
    MLFilterResult,
    MLSignalFilter,
    SignalFeatures,
    WalkForwardMLReport,
    extract_features,
    walk_forward_ml,
)

LIVE_PIPELINE_INTEGRATED = False
DEPRECATION_MESSAGE = (
    "alphaedge.engine.ml_filter is a research-only compatibility shim and is not "
    "wired into the live trading pipeline."
)

__all__ = [
    "LIVE_PIPELINE_INTEGRATED",
    "DEPRECATION_MESSAGE",
    "DEFAULT_WIN_THRESHOLD",
    "FEATURE_NAMES",
    "MLFilterResult",
    "MLSignalFilter",
    "SignalFeatures",
    "WalkForwardMLReport",
    "extract_features",
    "walk_forward_ml",
]
