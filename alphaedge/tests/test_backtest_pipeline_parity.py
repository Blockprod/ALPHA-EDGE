# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/tests/test_backtest_pipeline_parity.py
# DESCRIPTION  : P2-02/03 — verify backtest routes through SignalPipeline
#                and PositionManager (no direct module calls in _backtest_pair)
# PYTHON       : 3.11.9
# ============================================================
"""Non-regression tests confirming that _backtest_pair routes momentum
detection through SignalPipeline and sizing through PositionManager."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from alphaedge.config.loader import AppConfig, TradingConfig
from alphaedge.engine.backtest import _backtest_pair

# ------------------------------------------------------------------
# Shared helpers
# ------------------------------------------------------------------


def _make_config() -> AppConfig:
    """Minimal AppConfig sufficient for _backtest_pair without IB."""
    cfg = AppConfig()
    cfg.trading = TradingConfig()
    cfg.trading.pairs = ["EURUSD"]
    cfg.trading.momentum_lookback_days = 2
    cfg.trading.carry_enabled = False
    cfg.trading.carry_rates = {}
    cfg.trading.ml_filter_enabled = False
    cfg.trading.direction_filter = "ALL"
    cfg.trading.session_end_action = "hold"
    cfg.trading.excluded_days = []
    cfg.trading.max_trades_per_day = 3
    cfg.trading.max_daily_loss_pct = 5.0
    cfg.trading.gbpusd_long_adx_min = 0.0
    return cfg


def _make_bars(n: int = 8) -> list[dict[str, Any]]:
    """Rising daily bars with datetime stamps."""
    tz = ZoneInfo("UTC")
    start = datetime(2024, 3, 1, tzinfo=tz)
    bars: list[dict[str, Any]] = []
    price = 1.0800
    for i in range(n):
        bars.append(
            {
                "open": price,
                "high": price + 0.0012,
                "low": price - 0.0006,
                "close": price + 0.0006,
                "volume": 1000.0,
                "datetime": start + timedelta(days=i),
            }
        )
        price += 0.0008
    return bars


# Valid EURUSD signal used across several tests
_VALID_SIGNAL = {
    "detected": True,
    "direction": 1,
    "adx": 30.0,
    "ema_fast": 1.0820,
    "ema_slow": 1.0800,
}


class TestSignalPipelineRouting:
    """Verify detect_momentum is routed through SignalPipeline, not called
    directly on momentum_detector from within _backtest_pair."""

    def test_no_trade_when_signal_pipeline_returns_none(self) -> None:
        """Patch SignalPipeline.detect_momentum to return None → zero trades.

        If _backtest_pair still called momentum_detector.detect_momentum
        directly, this patch would have no effect and trades could be produced.
        """
        cfg = _make_config()
        with patch(
            "alphaedge.engine.signal_pipeline.SignalPipeline.detect_momentum",
            return_value=None,
        ):
            trades, rejections, _ = _backtest_pair("EURUSD", _make_bars(8), cfg)

        assert trades == []
        assert rejections.get("adx_gate", 0) > 0

    def test_signal_pipeline_detect_momentum_is_called(self) -> None:
        """detect_momentum on SignalPipeline must be invoked per bar in the loop."""
        cfg = _make_config()
        mock_detect = MagicMock(return_value=None)
        with patch(
            "alphaedge.engine.signal_pipeline.SignalPipeline.detect_momentum",
            mock_detect,
        ):
            _backtest_pair("EURUSD", _make_bars(8), cfg)

        # lookback=2 → 6 iterations (indices 2..7)
        assert mock_detect.call_count == 6


class TestPositionManagerRouting:
    """Verify sizing is routed through PositionManager, not directly to
    risk_manager.calculate_position_size inside _backtest_pair."""

    def test_no_trade_when_position_manager_rejects(self) -> None:
        """PositionManager.size_position returning None must block trade creation."""
        cfg = _make_config()
        with (
            patch(
                "alphaedge.core.momentum_detector.detect_momentum",
                return_value=_VALID_SIGNAL,
            ),
            patch(
                "alphaedge.engine.position_manager.PositionManager.size_position",
                return_value=None,
            ),
        ):
            trades, _, _ = _backtest_pair("EURUSD", _make_bars(8), cfg)

        assert trades == []

    def test_no_trade_when_build_validated_order_rejects(self) -> None:
        """PositionManager.build_validated_order returning None must block trade."""
        cfg = _make_config()
        with (
            patch(
                "alphaedge.core.momentum_detector.detect_momentum",
                return_value=_VALID_SIGNAL,
            ),
            patch(
                "alphaedge.engine.position_manager.PositionManager.size_position",
                return_value={"lot_size": 0.10},
            ),
            patch(
                "alphaedge.engine.position_manager.PositionManager.build_validated_order",
                return_value=None,
            ),
        ):
            trades, _, _ = _backtest_pair("EURUSD", _make_bars(8), cfg)

        assert trades == []


class TestCarryConflictRouting:
    """Verify carry conflict filtering is routed through SignalPipeline."""

    def test_carry_conflict_via_pipeline_blocks_trade(self) -> None:
        """is_carry_conflict returning True must suppress the trade."""
        cfg = _make_config()
        cfg.trading.carry_enabled = True
        cfg.trading.carry_rates = {"EUR": 3.0, "USD": 5.0}

        fake_carry = MagicMock()
        fake_carry.is_valid = True
        fake_carry.direction = "SHORT"
        fake_carry.differential_pct = 2.0

        with (
            patch(
                "alphaedge.core.momentum_detector.detect_momentum",
                return_value=_VALID_SIGNAL,
            ),
            patch(
                "alphaedge.engine.signal_pipeline.SignalPipeline.get_carry",
                return_value=fake_carry,
            ),
            patch(
                "alphaedge.engine.signal_pipeline.SignalPipeline.is_carry_conflict",
                return_value=True,
            ),
        ):
            trades, rejections, _ = _backtest_pair("EURUSD", _make_bars(8), cfg)

        assert trades == []
        assert rejections.get("carry_conflict", 0) > 0


class TestFullPipelineEndToEnd:
    """End-to-end non-regression: full pipeline produces trades from stubs."""

    def test_full_pipeline_produces_trade_with_valid_signal(self) -> None:
        """With a valid momentum signal and real stubs, at least one trade is made."""
        cfg = _make_config()

        # Return a complete valid bracket from order_manager stub
        bracket_result = {
            "is_valid": True,
            "stop_loss": 1.0780,
            "take_profit": 1.0860,
            "risk_pips": 20.0,
            "reward_pips": 40.0,
            "rejection_reason": None,
        }
        size_result = {"is_valid": True, "lot_size": 0.10}

        with (
            patch(
                "alphaedge.core.momentum_detector.detect_momentum",
                return_value=_VALID_SIGNAL,
            ),
            patch(
                "alphaedge.core.risk_manager.calculate_position_size",
                return_value=size_result,
            ),
            patch(
                "alphaedge.core.order_manager.create_bracket_order",
                return_value=bracket_result,
            ),
        ):
            trades, _, _ = _backtest_pair("EURUSD", _make_bars(8), cfg)

        assert len(trades) > 0
        assert trades[0].pair == "EURUSD"
        assert trades[0].direction == 1
