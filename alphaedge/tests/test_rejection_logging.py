"""Test suite for signal rejection logging (C-ST-07).

Validates per-trade rejection logging for filter diagnostics.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from alphaedge.engine.backtest_types import RejectionLog


class TestRejectionLogging:
    """Test per-trade rejection logging for filter cascade diagnostics."""

    def test_rejection_log_dataclass_creation(self):
        """Test RejectionLog dataclass instantiation."""
        dt = datetime(2025, 2, 15, 10, 30, 0, tzinfo=ZoneInfo("UTC"))
        log = RejectionLog(
            date=dt,
            pair="EURUSD",
            direction=1,
            rejection_reason="adx_below_threshold",
            rejection_value=18.2,
            primary_filter="adx_gate",
            signal_strength=18.2,
        )

        assert log.date == dt
        assert log.pair == "EURUSD"
        assert log.direction == 1
        assert log.rejection_reason == "adx_below_threshold"
        assert log.rejection_value == 18.2
        assert log.primary_filter == "adx_gate"
        assert log.signal_strength == 18.2

    def test_rejection_log_with_alternative_carries(self):
        """Test RejectionLog with alternative carries tracking."""
        dt = datetime(2025, 2, 15, 10, 30, 0, tzinfo=ZoneInfo("UTC"))
        log = RejectionLog(
            date=dt,
            pair="EURUSD",
            direction=1,
            rejection_reason="carry_conflict",
            rejection_value=0.35,
            primary_filter="carry_filter",
            alternative_carries=["EUR/JPY", "GBP/JPY"],
            signal_strength=25.5,
        )

        assert log.rejection_reason == "carry_conflict"
        assert len(log.alternative_carries) == 2
        assert "EUR/JPY" in log.alternative_carries

    def test_rejection_log_carry_rejection_structure(self):
        """Test rejection log structure for carry conflicts."""
        dt = datetime(2025, 3, 1, 14, 0, 0, tzinfo=ZoneInfo("UTC"))
        log = RejectionLog(
            date=dt,
            pair="GBPUSD",
            direction=-1,  # SHORT
            rejection_reason="carry_conflict",
            rejection_value=0.42,
            primary_filter="carry_filter",
            signal_strength=32.1,
        )

        assert log.pair == "GBPUSD"
        assert log.direction == -1
        assert log.rejection_value == 0.42  # carry differential pct

    def test_rejection_log_adx_rejection_structure(self):
        """Test rejection log structure for ADX threshold breaches."""
        dt = datetime(2025, 2, 20, 9, 0, 0, tzinfo=ZoneInfo("UTC"))
        log = RejectionLog(
            date=dt,
            pair="USDJPY",
            direction=0,  # Signal not detected, direction unknown
            rejection_reason="adx_below_threshold",
            rejection_value=22.5,
            primary_filter="adx_gate",
            signal_strength=22.5,
        )

        assert log.rejection_reason == "adx_below_threshold"
        assert log.primary_filter == "adx_gate"
        assert log.direction == 0  # no direction yet

    def test_rejection_log_regime_rejection(self):
        """Test rejection log for regime-based filtering."""
        dt = datetime(2025, 2, 25, 13, 30, 0, tzinfo=ZoneInfo("UTC"))
        log = RejectionLog(
            date=dt,
            pair="EURUSD",
            direction=1,
            rejection_reason="regime_gate_blocked",
            rejection_value=0.0,  # regime is categorical
            primary_filter="regime_gate",
            signal_strength=28.0,
        )

        assert log.rejection_reason == "regime_gate_blocked"
        assert log.primary_filter == "regime_gate"
        assert log.rejection_value == 0.0

    def test_rejection_log_ml_filter_rejection(self):
        """Test rejection log for ML filter blocks."""
        dt = datetime(2025, 3, 5, 11, 15, 0, tzinfo=ZoneInfo("UTC"))
        log = RejectionLog(
            date=dt,
            pair="GBPUSD",
            direction=-1,
            rejection_reason="ml_filter_blocked",
            rejection_value=0.45,  # model score
            primary_filter="ml_filter",
            signal_strength=30.2,
        )

        assert log.rejection_reason == "ml_filter_blocked"
        assert log.primary_filter == "ml_filter"
        assert log.rejection_value == 0.45

    def test_rejection_log_fields_are_correct_types(self):
        """Validate field types in RejectionLog."""
        dt = datetime(2025, 2, 15, 10, 30, 0, tzinfo=ZoneInfo("UTC"))
        log = RejectionLog(
            date=dt,
            pair="EURUSD",
            direction=1,
            rejection_reason="adx_below_threshold",
            rejection_value=18.2,
            primary_filter="adx_gate",
            alternative_carries=["EUR/JPY"],
            signal_strength=18.2,
        )

        assert isinstance(log.date, datetime)
        assert isinstance(log.pair, str)
        assert isinstance(log.direction, int)
        assert isinstance(log.rejection_reason, str)
        assert isinstance(log.rejection_value, float)
        assert isinstance(log.primary_filter, str)
        assert isinstance(log.alternative_carries, list)
        assert isinstance(log.signal_strength, float)

    def test_multiple_rejections_different_reasons(self):
        """Test tracking multiple rejections with different reasons."""
        dt_1 = datetime(2025, 2, 15, 10, 30, 0, tzinfo=ZoneInfo("UTC"))
        dt_2 = datetime(2025, 2, 15, 11, 45, 0, tzinfo=ZoneInfo("UTC"))

        logs = [
            RejectionLog(
                date=dt_1,
                pair="EURUSD",
                direction=1,
                rejection_reason="adx_below_threshold",
                rejection_value=18.0,
                primary_filter="adx_gate",
            ),
            RejectionLog(
                date=dt_2,
                pair="EURUSD",
                direction=-1,
                rejection_reason="carry_conflict",
                rejection_value=0.40,
                primary_filter="carry_filter",
            ),
        ]

        assert len(logs) == 2
        assert logs[0].rejection_reason == "adx_below_threshold"
        assert logs[1].rejection_reason == "carry_conflict"

    def test_rejection_log_with_zero_values(self):
        """Test RejectionLog handles zero values appropriately."""
        dt = datetime(2025, 2, 15, 10, 30, 0, tzinfo=ZoneInfo("UTC"))
        log = RejectionLog(
            date=dt,
            pair="EURUSD",
            direction=0,
            rejection_reason="signal_not_detected",
            rejection_value=0.0,
            primary_filter="signal_detection",
            signal_strength=0.0,
        )

        assert log.direction == 0
        assert log.rejection_value == 0.0
        assert log.signal_strength == 0.0
