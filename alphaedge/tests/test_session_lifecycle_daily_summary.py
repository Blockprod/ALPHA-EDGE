# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/tests/test_session_lifecycle_daily_summary.py
# DESCRIPTION  : Regression tests — daily summary real value aggregation
# AUTHOR       : ALPHAEDGE Dev Team
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-27
# ============================================================
"""Verify StrategyState accumulates wins/losses/pnl_usd and that
the aggregation across pairs matches expected totals."""

from __future__ import annotations

from alphaedge.engine.strategy import StrategyState


class TestStrategyStateDailySummaryFields:
    """StrategyState must initialise and accumulate session counters."""

    def test_initial_values_are_zero(self) -> None:
        state = StrategyState(pair="EURUSD")

        assert state.wins_today == 0
        assert state.losses_today == 0
        assert state.pnl_usd_today == 0.0

    def test_win_increments_wins_today(self) -> None:
        state = StrategyState(pair="EURUSD")
        state.wins_today += 1

        assert state.wins_today == 1
        assert state.losses_today == 0

    def test_loss_increments_losses_today(self) -> None:
        state = StrategyState(pair="EURUSD")
        state.losses_today += 1

        assert state.losses_today == 1
        assert state.wins_today == 0

    def test_pnl_usd_today_accumulates(self) -> None:
        state = StrategyState(pair="EURUSD")
        state.pnl_usd_today += 25.50
        state.pnl_usd_today += -10.00

        assert round(state.pnl_usd_today, 2) == 15.50


class TestDailySummaryAggregation:
    """Aggregation across multiple states mirrors _handle_session_end."""

    def _make_states(self) -> dict[str, StrategyState]:
        eurusd = StrategyState(pair="EURUSD")
        eurusd.wins_today = 2
        eurusd.losses_today = 1
        eurusd.pnl_usd_today = 40.0

        gbpusd = StrategyState(pair="GBPUSD")
        gbpusd.wins_today = 1
        gbpusd.losses_today = 3
        gbpusd.pnl_usd_today = -30.0

        return {"EURUSD": eurusd, "GBPUSD": gbpusd}

    def test_aggregate_wins(self) -> None:
        states = self._make_states()
        total_wins = sum(s.wins_today for s in states.values())
        assert total_wins == 3

    def test_aggregate_losses(self) -> None:
        states = self._make_states()
        total_losses = sum(s.losses_today for s in states.values())
        assert total_losses == 4

    def test_aggregate_pnl_usd(self) -> None:
        states = self._make_states()
        total_pnl = sum(s.pnl_usd_today for s in states.values())
        assert round(total_pnl, 2) == 10.0
