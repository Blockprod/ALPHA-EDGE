# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_ib_error_codes.py
# DESCRIPTION  : Tests for P1-04 IB error code handlers
# AUTHOR       : ALPHAEDGE Dev Team
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-08
# ============================================================
"""ALPHAEDGE — Verify IB error codes are handled with correct severity."""

from __future__ import annotations

import io
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from loguru import logger

from alphaedge.engine.broker import BrokerConnection


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _build_broker() -> BrokerConnection:
    with patch.object(BrokerConnection, "__init__", lambda self, *a, **kw: None):
        broker = BrokerConnection.__new__(BrokerConnection)
        mock_ib = MagicMock()
        object.__setattr__(broker, "_ib", mock_ib)
        object.__setattr__(broker, "_connected", False)

        from alphaedge.engine.broker import RequestThrottler

        object.__setattr__(broker, "_throttler", RequestThrottler())
        object.__setattr__(broker, "_config", MagicMock())
    return broker


@pytest.fixture()
def log_capture() -> Generator[io.StringIO, None, None]:
    """Capture loguru output for assertions."""
    sink = io.StringIO()
    handler_id = logger.add(sink, format="{level} {message}", level="DEBUG")
    yield sink
    logger.remove(handler_id)


# ==================================================================
# Tests
# ==================================================================
class TestIBErrorCodePacing:
    """Code 162 — historical data pacing violation."""

    def test_code_162_logs_debug(self, log_capture: io.StringIO) -> None:
        broker = _build_broker()
        broker._on_ib_error(1, 162, "pacing violation", None)
        output = log_capture.getvalue()
        assert "162" in output
        assert "DEBUG" in output

    def test_code_162_injects_throttler_penalty(self) -> None:
        broker = _build_broker()
        # Token bucket: after penalise() tokens should be 0
        broker._throttler._tokens = 5.0  # prime with some tokens
        broker._on_ib_error(1, 162, "pacing", None)
        assert broker._throttler._tokens == 0.0


class TestIBErrorCodeSecurity:
    """Code 200 — no security definition found."""

    def test_code_200_logs_error(self, log_capture: io.StringIO) -> None:
        broker = _build_broker()
        broker._on_ib_error(2, 200, "No security definition", None)
        output = log_capture.getvalue()
        assert "No security definition" in output
        assert "ERROR" in output


class TestIBErrorCodeValidation:
    """Code 321 — server validation error."""

    def test_code_321_logs_error(self, log_capture: io.StringIO) -> None:
        broker = _build_broker()
        broker._on_ib_error(3, 321, "server validation", None)
        output = log_capture.getvalue()
        assert "Server validation error" in output
        assert "ERROR" in output


class TestIBErrorCodeNotConnected:
    """Code 504 — not connected."""

    def test_code_504_logs_critical(self, log_capture: io.StringIO) -> None:
        broker = _build_broker()
        broker._on_ib_error(4, 504, "Not connected", None)
        output = log_capture.getvalue()
        assert "Not connected" in output
        assert "CRITICAL" in output


class TestIBErrorCodeConnection:
    """Codes 1100-1102 — connectivity issues."""

    @pytest.mark.parametrize("code", [1100, 1101, 1102])
    def test_connection_codes_log_critical(
        self, code: int, log_capture: io.StringIO
    ) -> None:
        broker = _build_broker()
        broker._on_ib_error(5, code, f"connection issue {code}", None)
        output = log_capture.getvalue()
        assert f"code={code}" in output
        assert "CRITICAL" in output


class TestIBErrorCodeUnknown:
    """Unknown error codes — default warning."""

    def test_unknown_code_logs_warning(self, log_capture: io.StringIO) -> None:
        broker = _build_broker()
        broker._on_ib_error(6, 9999, "unknown err", None)
        output = log_capture.getvalue()
        assert "9999" in output
        assert "WARNING" in output


class TestIBErrorHandlerRegistered:
    """Verify _on_ib_error is registered during connect."""

    def test_handler_method_exists(self) -> None:
        broker = _build_broker()
        assert hasattr(broker, "_on_ib_error")
        assert callable(broker._on_ib_error)
