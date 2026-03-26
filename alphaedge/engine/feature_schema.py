# ============================================================
# PROJECT      : ALPHAEDGE
# FILE         : alphaedge/engine/feature_schema.py
# DESCRIPTION  : TypedDict schemas for ML feature pipeline contracts.
#                Defines the expected structure of signal dicts passed
#                to extract_features() and the output of MLSignalFilter.predict().
# PYTHON       : 3.11.9
# ============================================================
"""Schema contracts for the ML signal filter feature pipeline.

These TypedDicts are not enforced at runtime, but they:
- Enable static type checking (Pyright / mypy)
- Document the exact keys / types expected by extract_features()
- Prevent silent regressions when signal dict structure changes

Usage
-----
    from alphaedge.engine.feature_schema import SignalDict, MLFilterResultDict
"""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict


class SignalDict(TypedDict, total=False):
    """Input signal dictionary consumed by ``extract_features()``.

    Keys marked as *optional* (total=False) may be absent — the consumer
    defaults to 0.0 / 0 when they are missing.

    Fields
    ------
    adx : float
        Average Directional Index at signal time (0–100).
    ema_delta_pct : float
        Relative EMA crossover magnitude: (fast – slow) / slow.
    carry_diff : float
        Interest rate carry differential (absolute value).
    atr_ratio : float
        ATR(1d) / ATR(20d avg) — measures volatility expansion.
    entry_time : datetime
        Bar timestamp used to derive day-of-week  (0=Mon … 4=Fri).
        Must be timezone-aware (UTC internally).
    """

    adx: float
    ema_delta_pct: float
    carry_diff: float
    atr_ratio: float
    entry_time: datetime


class MLFilterResultDict(TypedDict):
    """Output of ``MLSignalFilter.predict()`` expressed as a plain dict.

    This mirrors the ``MLFilterResult`` dataclass for callers that prefer
    dict access rather than attribute access.

    Fields
    ------
    win_probability : float
        Predicted P(win) in [0.0, 1.0].
    threshold : float
        Threshold above which the signal is accepted (default 0.55).
    passed : bool
        True when win_probability >= threshold AND model is trained.
    model_trained : bool
        False when the model has not been trained yet — all signals pass through.
    """

    win_probability: float
    threshold: float
    passed: bool
    model_trained: bool


#: Required keys in SignalDict (subset used in regression tests)
SIGNAL_REQUIRED_KEYS: frozenset[str] = frozenset(
    {"adx", "ema_delta_pct", "carry_diff", "atr_ratio"}
)

#: Expected output keys from MLSignalFilter.predict()
ML_RESULT_KEYS: frozenset[str] = frozenset(
    {"win_probability", "threshold", "passed", "model_trained"}
)
