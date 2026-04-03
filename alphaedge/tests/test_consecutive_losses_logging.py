"""Tests for C-ST-04 consecutive loss streak warning threshold logic."""

from alphaedge.engine.session_lifecycle import _should_log_loss_streak_warning


class TestConsecutiveLossesLogging:
    """Validate warning trigger for long loss streaks."""

    def test_warns_on_streak_gt_7(self) -> None:
        """Warning triggers when streak > 7 and streak PnL breaches 50% limit."""
        result = _should_log_loss_streak_warning(
            consecutive_losses=8,
            loss_streak_pnl_usd=-150.0,
            daily_loss_limit_usd=200.0,
        )
        assert result is True

    def test_does_not_warn_when_streak_too_short(self) -> None:
        """No warning when consecutive losses are <= 7."""
        result = _should_log_loss_streak_warning(
            consecutive_losses=7,
            loss_streak_pnl_usd=-150.0,
            daily_loss_limit_usd=200.0,
        )
        assert result is False

    def test_does_not_warn_when_pnl_above_threshold(self) -> None:
        """No warning when streak PnL has not breached the 50% threshold."""
        result = _should_log_loss_streak_warning(
            consecutive_losses=9,
            loss_streak_pnl_usd=-90.0,
            daily_loss_limit_usd=200.0,
        )
        assert result is False

    def test_does_not_warn_with_non_positive_daily_limit(self) -> None:
        """No warning when daily loss limit is invalid."""
        result = _should_log_loss_streak_warning(
            consecutive_losses=9,
            loss_streak_pnl_usd=-200.0,
            daily_loss_limit_usd=0.0,
        )
        assert result is False
