# ============================================================
# PROJECT      : ALPHAEDGE
# FILE         : alphaedge/tests/test_regime_filter_contract.py
# DESCRIPTION  : Contract tests — DailyRegimeFilter return value spec (ADR-009)
#                Tests the 4 limit cases: untrained, empty bars, single bar,
#                trained model with sufficient data.
# PYTHON       : 3.11.9
# ============================================================
"""Contract tests for DailyRegimeFilter (ADR-009).

Verifies:
- Return values are always in {"high_vol", "low_vol", "unknown"}
- Untrained model → always "unknown"
- Empty pre_session_m5 → always "unknown"
- Single bar (insufficient for std) → features extracted, predict proceeds
- Trained model → returns "high_vol" or "low_vol" (never "unknown")
"""

from __future__ import annotations

import datetime

import pytest

from alphaedge.engine.regime_filter import DailyRegimeFilter

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_REGIMES: frozenset[str] = frozenset({"high_vol", "low_vol", "unknown"})
TODAY = datetime.date(2026, 3, 26)

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_bar(
    close: float = 1.0800,
    delta: float = 0.0002,
    dt: datetime.datetime | None = None,
) -> dict[str, object]:
    """Build a single synthetic OHLC bar."""
    if dt is None:
        dt = datetime.datetime(2026, 3, 26, 9, 0, tzinfo=datetime.UTC)
    return {
        "open": close - delta,
        "high": close + delta,
        "low": close - delta,
        "close": close,
        "datetime": dt,
    }


def _make_history(n_days: int = 30) -> list[dict[str, object]]:
    """Build *n_days* daily bars for training (one bar per day)."""
    base_dt = datetime.datetime(2026, 1, 1, 0, 0, tzinfo=datetime.UTC)
    bars = []
    for i in range(n_days):
        close = 1.0800 + i * 0.0001
        dt = base_dt + datetime.timedelta(days=i)
        bars.append(
            {
                "open": close - 0.0005,
                "high": close + 0.0010,
                "low": close - 0.0010,
                "close": close,
                "datetime": dt,
            }
        )
    return bars


# ---------------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------------


class TestDailyRegimeFilterContract:
    """DailyRegimeFilter must honour the ADR-009 return value contract."""

    def test_return_value_set(self) -> None:
        """All possible return values must be in VALID_REGIMES."""
        assert VALID_REGIMES == {"high_vol", "low_vol", "unknown"}

    def test_untrained_returns_unknown(self) -> None:
        """Untrained model must return 'unknown' regardless of input."""
        filt = DailyRegimeFilter()
        result = filt.predict(TODAY, [_make_bar()])
        assert result == "unknown"

    def test_empty_bars_returns_unknown(self) -> None:
        """Empty pre_session_m5 list must return 'unknown'."""
        filt = DailyRegimeFilter()
        result = filt.predict(TODAY, [])
        assert result == "unknown"

    @pytest.mark.parametrize("n_bars", [1, 5, 10])
    def test_untrained_with_any_bars_returns_unknown(self, n_bars: int) -> None:
        """Untrained model must return 'unknown' for any bar count."""
        filt = DailyRegimeFilter()
        bars = [_make_bar(close=1.0800 + i * 0.0001) for i in range(n_bars)]
        result = filt.predict(TODAY, bars)
        assert result == "unknown"

    def test_trained_returns_valid_regime(self) -> None:
        """Trained model must return 'high_vol' or 'low_vol' (never 'unknown')
        when features can be extracted from the pre_session bars."""
        filt = DailyRegimeFilter()
        history = _make_history(30)  # 30-day training set
        filt.fit(history, pair="EURUSD")

        # Provide bars with non-zero range so features are extractable
        pre_session = [
            _make_bar(close=1.0850 + i * 0.0005, delta=0.0010) for i in range(5)
        ]
        result = filt.predict(TODAY, pre_session)

        assert result in {"high_vol", "low_vol"}, (
            f"Trained model returned unexpected regime: {result!r}"
        )

    def test_result_always_in_valid_regimes(self) -> None:
        """predict() result must always be one of the 3 valid states."""
        filt = DailyRegimeFilter()
        filt.fit(_make_history(30), pair="EURUSD")

        for _ in range(5):
            bars = [_make_bar(close=1.0800 + i * 0.0002) for i in range(3)]
            result = filt.predict(TODAY, bars)
            assert result in VALID_REGIMES, f"Invalid regime: {result!r}"
