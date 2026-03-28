# ============================================================
# PROJECT      : ALPHAEDGE
# FILE         : alphaedge/tests/test_ml_filter_schema.py
# DESCRIPTION  : Contract tests — ML feature schema (SignalDict → MLFilterResultDict)
#                Verifies that extract_features() and MLSignalFilter.predict()
#                honour the TypedDict schemas defined in feature_schema.py.
# PYTHON       : 3.11.9
# ============================================================
"""Schema contract tests for the ML signal filter pipeline.

Tests
-----
- extract_features() produces a SignalFeatures with the expected fields
- Missing keys in SignalDict → defaults to 0.0 (no KeyError)
- MLSignalFilter.predict() output matches ML_RESULT_KEYS schema
- feature_schema constants are consistent with SignalFeatures.to_array()
"""

from __future__ import annotations

import datetime

import pytest

from alphaedge.engine._experimental.ml_filter import (
    MLSignalFilter,
    SignalFeatures,
    extract_features,
)
from alphaedge.engine.feature_schema import (
    ML_RESULT_KEYS,
    SIGNAL_REQUIRED_KEYS,
    MLFilterResultDict,
    SignalDict,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _valid_signal() -> SignalDict:
    return {
        "adx": 30.5,
        "ema_delta_pct": 0.0012,
        "carry_diff": 0.015,
        "atr_ratio": 1.2,
        "entry_time": datetime.datetime(2026, 3, 26, 15, 30, tzinfo=datetime.UTC),
    }


# ---------------------------------------------------------------------------
# extract_features() schema contract
# ---------------------------------------------------------------------------


class TestExtractFeaturesSchema:
    """extract_features() must honour the SignalDict contract."""

    def test_full_signal_produces_correct_fields(self) -> None:
        signal: SignalDict = _valid_signal()
        result = extract_features(dict(signal))

        assert isinstance(result, SignalFeatures)
        assert result.adx == pytest.approx(30.5)
        assert result.ema_delta_pct == pytest.approx(0.0012)
        assert result.carry_diff == pytest.approx(0.015)
        assert result.atr_ratio == pytest.approx(1.2)
        assert result.day_of_week == 3  # Thursday 2026-03-26

    def test_missing_optional_keys_default_to_zero(self) -> None:
        """SignalDict is total=False — missing keys must not raise."""
        empty_signal: SignalDict = {}
        result = extract_features(dict(empty_signal))

        assert result.adx == pytest.approx(0.0)
        assert result.ema_delta_pct == pytest.approx(0.0)
        assert result.carry_diff == pytest.approx(0.0)
        assert result.atr_ratio == pytest.approx(0.0)
        assert result.day_of_week == 0

    def test_required_keys_constant_matches_feature_fields(self) -> None:
        """SIGNAL_REQUIRED_KEYS must be a subset of SignalFeatures fields."""
        feature_fields = {
            f.name for f in getattr(SignalFeatures, "__dataclass_fields__").values()
        }
        # day_of_week is derived from entry_time — not a raw key
        expected = {"adx", "ema_delta_pct", "carry_diff", "atr_ratio"}
        assert SIGNAL_REQUIRED_KEYS == expected
        assert SIGNAL_REQUIRED_KEYS <= feature_fields

    def test_to_array_length_matches_feature_names(self) -> None:
        """to_array() must return exactly 5 floats (matches FEATURE_NAMES)."""
        from alphaedge.engine._experimental.ml_filter import FEATURE_NAMES

        result = extract_features(dict(_valid_signal()))
        arr = result.to_array()
        assert len(arr) == len(FEATURE_NAMES)


# ---------------------------------------------------------------------------
# MLSignalFilter.predict() schema contract
# ---------------------------------------------------------------------------


class TestMLFilterResultSchema:
    """MLSignalFilter.predict() output must match MLFilterResultDict keys."""

    def test_untrained_predict_output_keys(self) -> None:
        """Untrained model must return all 4 keys with model_trained=False."""
        filt = MLSignalFilter()
        features = [30.5, 0.0012, 0.015, 1.2, 2.0]
        result = filt.predict(features)

        result_dict: MLFilterResultDict = {
            "win_probability": result.win_probability,
            "threshold": result.threshold,
            "passed": result.passed,
            "model_trained": result.model_trained,
        }

        assert set(result_dict.keys()) == ML_RESULT_KEYS
        assert result_dict["model_trained"] is False
        # Untrained model: passed defaults to False (dataclass default), pass-through
        # handled by the caller — not by predict() itself
        assert result_dict["passed"] is False

    def test_ml_result_keys_constant_complete(self) -> None:
        """ML_RESULT_KEYS must exactly match MLFilterResultDict annotations."""
        schema_keys = set(MLFilterResultDict.__annotations__.keys())
        assert ML_RESULT_KEYS == schema_keys
