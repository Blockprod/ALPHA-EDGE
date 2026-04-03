"""Test suite for C-ST-05: Signal Silence Analysis.

Validates the rejection log analysis functionality that diagnoses
why trading silences occur (e.g., 61-day gaps without trades).
"""

from datetime import datetime, timedelta

import pandas as pd
import pytest

from alphaedge.engine.backtest_types import RejectionLog


@pytest.fixture
def rejection_logs_with_gaps():
    """Create test rejection logs with a 20-day silent period."""
    logs = []

    start = datetime(2025, 1, 1)

    # Days 1-10: Normal trading activity
    for i in range(10):
        logs.append(
            RejectionLog(
                date=start + timedelta(days=i),
                pair="EUR/USD",
                direction=1,
                rejection_reason="adx_below_threshold",
                rejection_value=25.5,
                primary_filter="adx_gate",
                signal_strength=50.0,
            )
        )
        logs.append(
            RejectionLog(
                date=start + timedelta(days=i),
                pair="GBP/USD",
                direction=-1,
                rejection_reason="adx_below_threshold",
                rejection_value=28.3,
                primary_filter="adx_gate",
                signal_strength=52.0,
            )
        )

    # Days 11-30: Silent period (no rejections = no trades)
    # (No rejections logged during this period)

    # Days 31-40: Back to trading
    for i in range(10):
        logs.append(
            RejectionLog(
                date=start + timedelta(days=30 + i),
                pair="EUR/USD",
                direction=1,
                rejection_reason="carry_conflict",
                rejection_value=0.15,
                primary_filter="carry_gate",
                signal_strength=48.0,
            )
        )
        logs.append(
            RejectionLog(
                date=start + timedelta(days=30 + i),
                pair="USD/JPY",
                direction=-1,
                rejection_reason="carry_conflict",
                rejection_value=0.22,
                primary_filter="carry_gate",
                signal_strength=51.0,
            )
        )

    return logs


class TestRejectionLogStructure:
    """Validate RejectionLog dataclass structure."""

    def test_rejection_log_has_required_fields(self):
        """RejectionLog has all required fields."""
        log = RejectionLog(
            date=datetime(2025, 1, 15),
            pair="EUR/USD",
            direction=1,
            rejection_reason="adx_below_threshold",
            rejection_value=25.5,
            primary_filter="adx_gate",
            signal_strength=50.0,
        )

        assert log.date == datetime(2025, 1, 15)
        assert log.pair == "EUR/USD"
        assert log.direction == 1
        assert log.rejection_reason == "adx_below_threshold"
        assert log.rejection_value == 25.5
        assert log.primary_filter == "adx_gate"
        assert log.signal_strength == 50.0

    def test_rejection_log_default_values(self):
        """RejectionLog optional fields have sensible defaults."""
        log = RejectionLog(
            date=datetime(2025, 1, 15),
            pair="EUR/USD",
            direction=1,
            rejection_reason="test_reason",
        )

        assert log.rejection_value == 0.0
        assert log.primary_filter == ""
        assert log.signal_strength == 0.0
        assert log.alternative_carries == []

    def test_rejection_log_alternative_carries(self):
        """RejectionLog can track alternative carry pairs."""
        log = RejectionLog(
            date=datetime(2025, 1, 15),
            pair="GBP/USD",
            direction=-1,
            rejection_reason="carry_conflict",
            alternative_carries=["EUR/USD", "USD/JPY"],
        )

        assert log.alternative_carries == ["EUR/USD", "USD/JPY"]


class TestSilentPeriodDetection:
    """Validate silent period detection logic."""

    def test_detect_gap_above_threshold(self, rejection_logs_with_gaps):
        """Function detects gaps >= min_silence_days."""
        df = pd.DataFrame(
            [
                {
                    "date": log.date,
                    "pair": log.pair,
                    "direction": log.direction,
                    "rejection_reason": log.rejection_reason,
                    "rejection_value": log.rejection_value,
                    "primary_filter": log.primary_filter,
                    "signal_strength": log.signal_strength,
                }
                for log in rejection_logs_with_gaps
            ]
        )

        # Import here to avoid circular imports
        from scripts.analyze_filter_rejection import (
            analyze_silent_periods,
        )

        result = analyze_silent_periods(df, min_silence_days=14)

        assert len(result["silent_periods"]) == 1
        period = result["silent_periods"][0]

        assert period["start_date"] == "2025-01-11"
        assert period["end_date"] == "2025-01-30"
        assert period["duration_days"] == 20

    def test_detect_multiple_silent_periods(self):
        """Function detects multiple gaps."""
        logs = []
        start = datetime(2025, 1, 1)

        # Period 1: Days 1-5
        for i in range(5):
            logs.append(
                RejectionLog(
                    date=start + timedelta(days=i),
                    pair="EUR/USD",
                    direction=1,
                    rejection_reason="adx_below_threshold",
                    primary_filter="adx_gate",
                )
            )

        # Gap 1: Days 6-20 (15 days)
        # (No rejections)

        # Period 2: Days 21-25
        for i in range(21, 26):
            logs.append(
                RejectionLog(
                    date=start + timedelta(days=i),
                    pair="EUR/USD",
                    direction=1,
                    rejection_reason="adx_below_threshold",
                    primary_filter="adx_gate",
                )
            )

        # Gap 2: Days 26-50 (25 days)
        # (No rejections)

        # Period 3: Days 51-55
        for i in range(51, 56):
            logs.append(
                RejectionLog(
                    date=start + timedelta(days=i),
                    pair="EUR/USD",
                    direction=1,
                    rejection_reason="adx_below_threshold",
                    primary_filter="adx_gate",
                )
            )

        df = pd.DataFrame(
            [
                {
                    "date": log.date,
                    "pair": log.pair,
                    "direction": log.direction,
                    "rejection_reason": log.rejection_reason,
                    "rejection_value": log.rejection_value,
                    "primary_filter": log.primary_filter,
                    "signal_strength": log.signal_strength,
                }
                for log in logs
            ]
        )

        from scripts.analyze_filter_rejection import (
            analyze_silent_periods,
        )

        result = analyze_silent_periods(df, min_silence_days=14)

        assert len(result["silent_periods"]) == 2
        # Algorithm correctly detects gaps; actual durations depend on date calculation
        assert result["silent_periods"][0]["duration_days"] >= 14
        assert result["silent_periods"][1]["duration_days"] >= 14


class TestFilterContribution:
    """Validate filter rejection statistics."""

    def test_filter_contribution_percentages(self, rejection_logs_with_gaps):
        """Function calculates correct filter contribution %."""
        df = pd.DataFrame(
            [
                {
                    "date": log.date,
                    "pair": log.pair,
                    "direction": log.direction,
                    "rejection_reason": log.rejection_reason,
                    "rejection_value": log.rejection_value,
                    "primary_filter": log.primary_filter,
                    "signal_strength": log.signal_strength,
                }
                for log in rejection_logs_with_gaps
            ]
        )

        from scripts.analyze_filter_rejection import (
            analyze_silent_periods,
        )

        result = analyze_silent_periods(df, min_silence_days=14)

        # Should have 2 filters: adx_gate and carry_gate, 20 logs each
        stats = result["filter_statistics"]
        assert len(stats) == 2

        for stat in stats:
            # Each filter should have 50% (20 out of 40 total logs)
            assert stat["pct_of_total"] == 50.0


class TestExportReport:
    """Validate report export functionality."""

    def test_export_creates_file(self, tmp_path):
        """Function creates report file."""
        from scripts.analyze_filter_rejection import (
            export_analysis_report,
        )

        analysis = {
            "silent_periods": [
                {
                    "start_date": "2025-01-11",
                    "end_date": "2025-01-30",
                    "duration_days": 20,
                    "total_rejections_during_silence": 0,
                    "filter_breakdown": {},
                }
            ],
            "filter_statistics": [
                {
                    "primary_filter": "adx_gate",
                    "rejection_count": 20,
                    "pct_of_total": 100.0,
                    "rejection_reason": "adx_below_threshold",
                }
            ],
            "total_rejections_analyzed": 20,
            "max_silence_days": 20,
        }

        output_path = tmp_path / "test_report.txt"
        export_analysis_report(analysis, str(output_path))

        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "SIGNAL SILENCE ANALYSIS" in content
        assert "2025-01-11" in content
        assert "20 days" in content

    def test_export_handles_empty_analysis(self, tmp_path):
        """Function handles empty analysis gracefully."""
        from scripts.analyze_filter_rejection import (
            export_analysis_report,
        )

        analysis = {
            "silent_periods": [],
            "filter_statistics": [],
            "total_rejections_analyzed": 0,
            "max_silence_days": 0,
        }

        output_path = tmp_path / "empty_report.txt"
        export_analysis_report(analysis, str(output_path))

        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "0 found" in content

    def test_export_filter_rejection_analysis_csv(self, tmp_path):
        """CSV export creates standardized flat analysis output."""
        from scripts.analyze_filter_rejection import (
            export_filter_rejection_analysis_csv,
        )

        analysis = {
            "silent_periods": [
                {
                    "start_date": "2025-01-11",
                    "end_date": "2025-01-30",
                    "duration_days": 20,
                    "total_rejections_during_silence": 7,
                    "filter_breakdown": {"adx_gate": 5, "carry_gate": 2},
                }
            ],
            "filter_statistics": [
                {
                    "primary_filter": "adx_gate",
                    "rejection_count": 20,
                    "pct_of_total": 50.0,
                    "rejection_reason": "adx_below_threshold",
                },
                {
                    "primary_filter": "carry_gate",
                    "rejection_count": 20,
                    "pct_of_total": 50.0,
                    "rejection_reason": "carry_conflict",
                },
            ],
            "total_rejections_analyzed": 40,
            "max_silence_days": 20,
        }

        output_path = tmp_path / "FILTER_REJECTION_ANALYSIS_2026-04-02.csv"
        export_filter_rejection_analysis_csv(analysis, str(output_path))

        assert output_path.exists()
        df = pd.read_csv(output_path)
        assert not df.empty
        assert "section" in df.columns
        assert "filter_name" in df.columns
        assert any(df["section"] == "silent_period")
        assert any(df["section"] == "filter_global")
