# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_ml_filter.py
# DESCRIPTION  : Tests for ML signal filter
# ============================================================
"""ALPHAEDGE — T4.3: ML signal filter tests."""

from __future__ import annotations

import random
from datetime import datetime
from zoneinfo import ZoneInfo

from alphaedge.engine.ml_filter import (
    DEFAULT_WIN_THRESHOLD,
    FEATURE_NAMES,
    MLFilterResult,
    MLSignalFilter,
    SignalFeatures,
    WalkForwardMLReport,
    extract_features,
    walk_forward_ml,
)

ET = ZoneInfo("America/New_York")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _make_training_data(
    n: int = 100, seed: int = 42
) -> tuple[list[list[float]], list[int]]:
    """Generate synthetic training data with separable classes."""
    rng = random.Random(seed)
    features: list[list[float]] = []
    labels: list[int] = []

    for _ in range(n):
        atr_ratio = rng.uniform(0.5, 3.0)
        fcr_range = rng.uniform(5.0, 30.0)
        volume_ratio = rng.uniform(0.8, 3.0)
        spread = rng.uniform(0.5, 3.0)
        dow = rng.randint(0, 4)

        # Simple rule: wins tend to have higher ATR ratio and volume
        win_score = atr_ratio * 0.4 + volume_ratio * 0.3 - spread * 0.2
        label = 1 if win_score > 1.0 else 0

        features.append([atr_ratio, fcr_range, volume_ratio, spread, float(dow)])
        labels.append(label)

    return features, labels


# ------------------------------------------------------------------
# SignalFeatures
# ------------------------------------------------------------------
class TestSignalFeatures:
    def test_to_array_length(self) -> None:
        sf = SignalFeatures(
            atr_ratio=1.5, fcr_range=10.0, volume_ratio=1.2, spread=0.8, day_of_week=2
        )
        arr = sf.to_array()
        assert len(arr) == len(FEATURE_NAMES)

    def test_to_array_values(self) -> None:
        sf = SignalFeatures(
            atr_ratio=1.5, fcr_range=10.0, volume_ratio=1.2, spread=0.8, day_of_week=3
        )
        arr = sf.to_array()
        assert arr == [1.5, 10.0, 1.2, 0.8, 3.0]

    def test_defaults(self) -> None:
        sf = SignalFeatures()
        assert sf.atr_ratio == 0.0
        assert sf.day_of_week == 0


# ------------------------------------------------------------------
# extract_features
# ------------------------------------------------------------------
class TestExtractFeatures:
    def test_extracts_all_fields(self) -> None:
        signal = {
            "atr_ratio": 1.8,
            "fcr_range": 15.0,
            "volume_ratio": 1.5,
            "spread": 1.0,
            "entry_time": datetime(2024, 1, 3, 10, 0, tzinfo=ET),  # Wednesday
        }
        sf = extract_features(signal)
        assert sf.atr_ratio == 1.8
        assert sf.fcr_range == 15.0
        assert sf.volume_ratio == 1.5
        assert sf.spread == 1.0
        assert sf.day_of_week == 2  # Wednesday = 2

    def test_missing_fields_default_zero(self) -> None:
        sf = extract_features({})
        assert sf.atr_ratio == 0.0
        assert sf.day_of_week == 0

    def test_day_of_week_from_entry_time(self) -> None:
        signal = {"entry_time": datetime(2024, 1, 5, 10, 0, tzinfo=ET)}  # Friday
        sf = extract_features(signal)
        assert sf.day_of_week == 4


# ------------------------------------------------------------------
# MLSignalFilter
# ------------------------------------------------------------------
class TestMLSignalFilter:
    def test_untrained_returns_not_trained(self) -> None:
        filt = MLSignalFilter()
        result = filt.predict([1.5, 10.0, 1.2, 0.8, 2.0])
        assert isinstance(result, MLFilterResult)
        assert result.model_trained is False
        assert result.passed is False

    def test_train_and_predict(self) -> None:
        features, labels = _make_training_data(100)
        filt = MLSignalFilter(threshold=0.5)
        filt.train(features, labels)
        assert filt.is_trained is True

        result = filt.predict([2.0, 15.0, 2.0, 0.5, 2.0])
        assert result.model_trained is True
        assert 0.0 <= result.win_probability <= 1.0

    def test_threshold_respected(self) -> None:
        features, labels = _make_training_data(100)
        filt = MLSignalFilter(threshold=0.99)
        filt.train(features, labels)

        # With a very high threshold, most signals should be rejected
        result = filt.predict([1.5, 10.0, 1.2, 0.8, 2.0])
        assert result.threshold == 0.99

    def test_insufficient_data_not_trained(self) -> None:
        features = [[1.0, 2.0, 3.0, 4.0, 5.0]] * 5
        labels = [1, 0, 1, 0, 1]
        filt = MLSignalFilter()
        filt.train(features, labels)
        assert filt.is_trained is False

    def test_single_class_not_trained(self) -> None:
        features = [[1.0, 2.0, 3.0, 4.0, 5.0]] * 20
        labels = [1] * 20  # All wins — no losses
        filt = MLSignalFilter()
        filt.train(features, labels)
        assert filt.is_trained is False

    def test_default_threshold(self) -> None:
        filt = MLSignalFilter()
        assert filt.threshold == DEFAULT_WIN_THRESHOLD

    def test_custom_threshold(self) -> None:
        filt = MLSignalFilter(threshold=0.7)
        assert filt.threshold == 0.7


# ------------------------------------------------------------------
# walk_forward_ml
# ------------------------------------------------------------------
class TestWalkForwardML:
    def test_report_structure(self) -> None:
        features, labels = _make_training_data(100)
        report = walk_forward_ml(features, labels, n_windows=5)
        assert isinstance(report, WalkForwardMLReport)
        assert report.n_windows > 0
        assert report.predictions_total > 0

    def test_insufficient_data(self) -> None:
        features, labels = _make_training_data(10)
        report = walk_forward_ml(features, labels, n_windows=5)
        assert report.n_windows == 0

    def test_accuracy_range(self) -> None:
        features, labels = _make_training_data(200)
        report = walk_forward_ml(features, labels, n_windows=5)
        assert 0.0 <= report.mean_accuracy <= 1.0
        for acc in report.accuracy_per_window:
            assert 0.0 <= acc <= 1.0

    def test_threshold_preserved(self) -> None:
        features, labels = _make_training_data(100)
        report = walk_forward_ml(features, labels, n_windows=5, threshold=0.6)
        assert report.threshold_used == 0.6

    def test_predictions_sum_correct(self) -> None:
        features, labels = _make_training_data(100)
        report = walk_forward_ml(features, labels, n_windows=5)
        assert report.predictions_correct <= report.predictions_total

    def test_multiple_windows(self) -> None:
        features, labels = _make_training_data(200)
        report = walk_forward_ml(features, labels, n_windows=10)
        assert report.n_windows >= 5  # At least some windows should produce results
