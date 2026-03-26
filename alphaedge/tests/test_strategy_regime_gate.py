# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/tests/test_strategy_regime_gate.py
# DESCRIPTION  : Regime gate in _detect_momentum (C-01 — Audit IA/ML)
# ============================================================
"""Tests for the DailyRegimeFilter gate in SwingStrategy._detect_momentum.

Scenarios
---------
1. Gate disabled → regime filter skipped → detect_momentum called.
2. Gate enabled + regime=high_vol → returns None (BLOCK).
3. Gate enabled + regime=low_vol → detect_momentum called (pass-through).
4. Gate enabled + regime=unknown → detect_momentum called (unknown = no block).
5. No regime filter attached → gate logic skipped → detect_momentum called.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from alphaedge.engine.strategy import StrategyState, SwingStrategy


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------
def _make_state(pair: str = "EURUSD") -> StrategyState:
    """Return a minimal StrategyState with 20 daily bars."""
    state = StrategyState(pair=pair)
    state.daily_bars = [
        {"open": 1.08, "high": 1.085, "low": 1.075, "close": 1.080} for _ in range(20)
    ]
    return state


def _make_strategy(
    *,
    regime_gate_enabled: bool,
    regime_block_on: str = "high_vol",
    regime_label: str = "unknown",
    has_regime_filter: bool = True,
) -> tuple[SwingStrategy, MagicMock]:
    """Build a minimal SwingStrategy with mocked dependencies for gate tests.

    Returns
    -------
    tuple[SwingStrategy, MagicMock]
        The strategy and the pipeline mock (for assertions).
    """
    config = MagicMock()
    config.regime_gate_enabled = regime_gate_enabled
    config.regime_block_on = regime_block_on
    config.trading.carry_enabled = (
        False  # P-03: disable carry check in regime-gate tests
    )

    pipeline_mock = MagicMock()
    pipeline_mock.detect_momentum.return_value = {
        "direction": 1,
        "adx": 30.0,
    }

    strat = SwingStrategy.__new__(SwingStrategy)
    strat._config = config
    strat._signal_pipeline = pipeline_mock
    strat._modules = MagicMock()

    # Optionally attach a mock regime filter
    if has_regime_filter:
        regime_filter = MagicMock()
        regime_filter.predict.return_value = regime_label
        strat._regime_filter = regime_filter

    return strat, pipeline_mock


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------
class TestRegimeGate:
    """Unit tests for the regime gate in _detect_momentum."""

    def test_gate_disabled_calls_detect_momentum(self) -> None:
        """Gate disabled → regime label is irrelevant → detect_momentum executes."""
        strat, pipeline_mock = _make_strategy(
            regime_gate_enabled=False,
            regime_label="high_vol",
        )
        state = _make_state()

        result = strat._detect_momentum(state, pip_size=0.0001)

        pipeline_mock.detect_momentum.assert_called_once()
        assert result is not None

    def test_gate_enabled_high_vol_returns_none(self) -> None:
        """Gate enabled + regime=high_vol → pipeline blocked, returns None."""
        strat, pipeline_mock = _make_strategy(
            regime_gate_enabled=True,
            regime_block_on="high_vol",
            regime_label="high_vol",
        )
        state = _make_state()

        result = strat._detect_momentum(state, pip_size=0.0001)

        pipeline_mock.detect_momentum.assert_not_called()
        assert result is None

    def test_gate_enabled_low_vol_calls_detect_momentum(self) -> None:
        """Gate enabled + regime=low_vol → not blocked, detect_momentum executes."""
        strat, pipeline_mock = _make_strategy(
            regime_gate_enabled=True,
            regime_block_on="high_vol",
            regime_label="low_vol",
        )
        state = _make_state()

        result = strat._detect_momentum(state, pip_size=0.0001)

        pipeline_mock.detect_momentum.assert_called_once()
        assert result is not None

    def test_gate_enabled_unknown_regime_calls_detect_momentum(self) -> None:
        """Gate enabled + regime=unknown → not blocked (unknown is not block_on)."""
        strat, pipeline_mock = _make_strategy(
            regime_gate_enabled=True,
            regime_block_on="high_vol",
            regime_label="unknown",
        )
        state = _make_state()

        result = strat._detect_momentum(state, pip_size=0.0001)

        pipeline_mock.detect_momentum.assert_called_once()
        assert result is not None

    def test_no_regime_filter_gate_enabled_calls_detect_momentum(self) -> None:
        """No regime filter attached → regime='unknown' → gate never triggers."""
        strat, pipeline_mock = _make_strategy(
            regime_gate_enabled=True,
            regime_block_on="high_vol",
            has_regime_filter=False,
        )
        state = _make_state()

        result = strat._detect_momentum(state, pip_size=0.0001)

        pipeline_mock.detect_momentum.assert_called_once()
        assert result is not None

    @pytest.mark.parametrize("block_label", ["high_vol", "low_vol"])
    def test_gate_blocks_on_configured_label(self, block_label: str) -> None:
        """Gate blocks whichever label is configured via regime_block_on."""
        strat, pipeline_mock = _make_strategy(
            regime_gate_enabled=True,
            regime_block_on=block_label,
            regime_label=block_label,
        )
        state = _make_state()

        result = strat._detect_momentum(state, pip_size=0.0001)

        pipeline_mock.detect_momentum.assert_not_called()
        assert result is None
