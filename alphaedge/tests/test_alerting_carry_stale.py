# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/tests/test_alerting_carry_stale.py
# DESCRIPTION  : Tests for alert_carry_rates_stale
# ============================================================
"""Tests — alert_carry_rates_stale builder (AlertEvent.CARRY_RATES_STALE)."""

from __future__ import annotations

from alphaedge.utils.alerting import (
    AlertEvent,
    AlertLevel,
    alert_carry_rates_stale,
)


class TestAlertCarryRatesStale:
    def test_warning_level_when_moderate_days(self) -> None:
        alert = alert_carry_rates_stale(days_old=45, last_updated="2026-04-01")
        assert alert.event == AlertEvent.CARRY_RATES_STALE
        assert alert.level == AlertLevel.WARNING
        assert "45" in alert.message
        assert "2026-04-01" in alert.message

    def test_critical_level_when_very_stale(self) -> None:
        alert = alert_carry_rates_stale(days_old=65, last_updated="2026-03-01")
        assert alert.level == AlertLevel.CRITICAL
        assert "65" in alert.message

    def test_warning_level_boundary_at_60(self) -> None:
        # 60 days is still WARNING, >60 becomes CRITICAL
        alert = alert_carry_rates_stale(days_old=60, last_updated="2026-03-27")
        assert alert.level == AlertLevel.WARNING

    def test_critical_level_boundary_at_61(self) -> None:
        alert = alert_carry_rates_stale(days_old=61, last_updated="2026-03-26")
        assert alert.level == AlertLevel.CRITICAL

    def test_unknown_last_updated(self) -> None:
        alert = alert_carry_rates_stale(days_old=90, last_updated="")
        assert "unknown" in alert.message

    def test_title_contains_days(self) -> None:
        alert = alert_carry_rates_stale(days_old=50, last_updated="2026-04-07")
        assert "50" in alert.title
