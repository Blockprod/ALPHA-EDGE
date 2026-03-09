# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/engine/ml_filter.py
# DESCRIPTION  : ML-based signal filter (logistic regression)
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-08
# ============================================================
"""ALPHAEDGE — T4.3: ML signal filter (logistic regression).

Trains a logistic regression model on trade features (ATR ratio,
FCR range, volume ratio, spread, day of week) to predict win
probability.  Uses walk-forward training to prevent look-ahead bias.
Only passes signals where P(win) exceeds a calibrated threshold.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from alphaedge.utils.logger import get_logger

logger = get_logger()

# Feature names (order matters — must match extract_features)
FEATURE_NAMES: list[str] = [
    "atr_ratio",
    "fcr_range",
    "volume_ratio",
    "spread",
    "day_of_week",
]

DEFAULT_WIN_THRESHOLD: float = 0.55


# ------------------------------------------------------------------
# Data structures
# ------------------------------------------------------------------
@dataclass
class SignalFeatures:
    """Feature vector for a single trade signal."""

    atr_ratio: float = 0.0
    fcr_range: float = 0.0
    volume_ratio: float = 0.0
    spread: float = 0.0
    day_of_week: int = 0  # 0=Monday … 4=Friday

    def to_array(self) -> list[float]:
        """Convert to flat feature list."""
        return [
            self.atr_ratio,
            self.fcr_range,
            self.volume_ratio,
            self.spread,
            float(self.day_of_week),
        ]


@dataclass
class MLFilterResult:
    """Result of an ML filter prediction."""

    win_probability: float = 0.0
    threshold: float = DEFAULT_WIN_THRESHOLD
    passed: bool = False
    model_trained: bool = False


@dataclass
class WalkForwardMLReport:
    """Results of walk-forward ML evaluation."""

    n_windows: int = 0
    accuracy_per_window: list[float] = field(default_factory=list)
    mean_accuracy: float = 0.0
    predictions_total: int = 0
    predictions_correct: int = 0
    threshold_used: float = DEFAULT_WIN_THRESHOLD


# ------------------------------------------------------------------
# Feature extraction
# ------------------------------------------------------------------
def extract_features(signal: dict[str, Any]) -> SignalFeatures:
    """
    Extract ML features from a signal dictionary.

    Parameters
    ----------
    signal : dict
        Signal data with keys: atr_ratio, fcr_range, volume_ratio,
        spread, entry_time (datetime with weekday info).

    Returns
    -------
    SignalFeatures
        Extracted feature vector.
    """
    entry_time = signal.get("entry_time")
    dow = 0
    if entry_time is not None:
        dow = entry_time.weekday()

    return SignalFeatures(
        atr_ratio=float(signal.get("atr_ratio", 0.0)),
        fcr_range=float(signal.get("fcr_range", 0.0)),
        volume_ratio=float(signal.get("volume_ratio", 0.0)),
        spread=float(signal.get("spread", 0.0)),
        day_of_week=dow,
    )


# ------------------------------------------------------------------
# ML Signal Filter
# ------------------------------------------------------------------
class MLSignalFilter:
    """
    Logistic regression filter for trade signals.

    Predicts P(win) from signal features and gates entry
    to signals above a calibrated threshold.
    """

    def __init__(self, threshold: float = DEFAULT_WIN_THRESHOLD) -> None:
        self._threshold = threshold
        self._model: LogisticRegression | None = None
        self._scaler: StandardScaler = StandardScaler()
        self._trained = False

    @property
    def is_trained(self) -> bool:
        """Whether the model has been trained."""
        return self._trained

    @property
    def threshold(self) -> float:
        """Current win probability threshold."""
        return self._threshold

    def train(
        self,
        features: list[list[float]],
        labels: list[int],
    ) -> None:
        """
        Train the logistic regression model.

        Parameters
        ----------
        features : list[list[float]]
            Feature matrix (n_samples × n_features).
        labels : list[int]
            Binary labels (1=win, 0=loss).
        """
        if len(features) < 10:
            logger.warning(
                f"ALPHAEDGE ML: Insufficient training data ({len(features)} samples, "
                f"need ≥10). Model NOT trained."
            )
            return

        x = np.array(features, dtype=np.float64)
        y = np.array(labels, dtype=np.int32)

        # Check we have both classes
        unique_labels = set(y.tolist())
        if len(unique_labels) < 2:
            logger.warning(
                "ALPHAEDGE ML: Only one class in training data. Model NOT trained."
            )
            return

        self._scaler = StandardScaler()
        x_scaled: np.ndarray[Any, Any] = self._scaler.fit_transform(x)

        self._model = LogisticRegression(
            max_iter=1000,
            solver="lbfgs",
            random_state=42,
        )
        self._model.fit(x_scaled, y)
        self._trained = True

        train_acc = float(self._model.score(x_scaled, y))
        logger.info(
            f"ALPHAEDGE ML: Model trained — {len(features)} samples, "
            f"train accuracy: {train_acc:.2%}"
        )

    def predict(self, features: list[float]) -> MLFilterResult:
        """
        Predict win probability for a signal.

        Parameters
        ----------
        features : list[float]
            Feature vector for a single signal.

        Returns
        -------
        MLFilterResult
            Prediction result with win probability and pass/fail.
        """
        if not self._trained or self._model is None:
            return MLFilterResult(
                threshold=self._threshold,
                model_trained=False,
            )

        x = np.array([features], dtype=np.float64)
        x_scaled: np.ndarray[Any, Any] = self._scaler.transform(x)
        proba: np.ndarray[Any, Any] = self._model.predict_proba(x_scaled)
        win_prob = float(proba[0, 1])

        result = MLFilterResult(
            win_probability=win_prob,
            threshold=self._threshold,
            passed=win_prob >= self._threshold,
            model_trained=True,
        )

        if not result.passed:
            logger.info(
                f"ALPHAEDGE ML: Signal REJECTED — P(win)={win_prob:.2%} "
                f"< threshold {self._threshold:.2%}"
            )

        return result


# ------------------------------------------------------------------
# Walk-forward evaluation
# ------------------------------------------------------------------
def walk_forward_ml(
    features: list[list[float]],
    labels: list[int],
    n_windows: int = 5,
    threshold: float = DEFAULT_WIN_THRESHOLD,
) -> WalkForwardMLReport:
    """
    Walk-forward evaluation of the ML filter.

    Splits data chronologically into n_windows folds. For each fold,
    trains on all prior data and evaluates on the current fold.

    Parameters
    ----------
    features : list[list[float]]
        Feature matrix (chronologically ordered).
    labels : list[int]
        Binary labels (1=win, 0=loss).
    n_windows : int
        Number of walk-forward windows.
    threshold : float
        Win probability threshold.

    Returns
    -------
    WalkForwardMLReport
        Walk-forward evaluation results.
    """
    n = len(features)
    if n < 20 or n_windows < 2:
        logger.warning(
            f"ALPHAEDGE ML WF: Insufficient data for walk-forward "
            f"({n} samples, {n_windows} windows). Need ≥20 samples."
        )
        return WalkForwardMLReport(threshold_used=threshold)

    window_size = n // n_windows
    accuracy_per_window: list[float] = []
    total_correct = 0
    total_predictions = 0

    for w in range(1, n_windows):
        train_end = w * window_size
        test_end = min((w + 1) * window_size, n)

        train_x = features[:train_end]
        train_y = labels[:train_end]
        test_x = features[train_end:test_end]
        test_y = labels[train_end:test_end]

        if not test_x:
            continue

        model = MLSignalFilter(threshold=threshold)
        model.train(train_x, train_y)

        if not model.is_trained:
            continue

        correct = 0
        for fx, actual in zip(test_x, test_y):
            result = model.predict(fx)
            predicted = 1 if result.passed else 0
            if predicted == actual:
                correct += 1

        acc = correct / len(test_y) if test_y else 0.0
        accuracy_per_window.append(acc)
        total_correct += correct
        total_predictions += len(test_y)

    mean_acc = float(np.mean(accuracy_per_window)) if accuracy_per_window else 0.0

    report = WalkForwardMLReport(
        n_windows=len(accuracy_per_window),
        accuracy_per_window=accuracy_per_window,
        mean_accuracy=mean_acc,
        predictions_total=total_predictions,
        predictions_correct=total_correct,
        threshold_used=threshold,
    )

    logger.info(
        f"ALPHAEDGE ML WF: {report.n_windows} windows, "
        f"mean accuracy: {report.mean_accuracy:.2%}, "
        f"total: {report.predictions_correct}/{report.predictions_total}"
    )

    return report
