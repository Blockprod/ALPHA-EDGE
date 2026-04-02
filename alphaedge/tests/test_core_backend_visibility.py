# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/tests/test_core_backend_visibility.py
# DESCRIPTION  : Tests for core backend visibility and fallback reporting
# AUTHOR       : ALPHAEDGE Dev Team
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-22
# ============================================================
"""ALPHAEDGE — Verify core backend fallback remains visible."""

from __future__ import annotations

import importlib
import io
from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from loguru import logger

import alphaedge.core as core


@pytest.fixture()
def log_capture() -> Generator[io.StringIO, None, None]:
    """Capture loguru output for assertions."""
    sink = io.StringIO()
    handler_id = logger.add(sink, format="{level} {message}", level="DEBUG")
    try:
        yield sink
    finally:
        logger.remove(handler_id)


class TestCoreBackendVisibility:
    """Verify runtime visibility of the selected core backend."""

    def test_auto_backend_logs_fallback_and_tracks_module(
        self,
        monkeypatch: pytest.MonkeyPatch,
        log_capture: io.StringIO,
    ) -> None:
        core.reset_backend_tracking()
        monkeypatch.setenv("ALPHAEDGE_CORE_BACKEND", "auto")

        def _import_module(name: str) -> object:
            if name == "alphaedge.core.risk_manager":
                raise ImportError("compiled missing")
            return SimpleNamespace(__name__=name)

        with patch.object(importlib, "import_module", side_effect=_import_module):
            module = core.load_core_module("risk_manager")

        assert getattr(module, "__name__") == "alphaedge.core._stubs.risk_manager"
        assert "risk_manager" in log_capture.getvalue()
        assert "fallback" in log_capture.getvalue().lower()

    def test_backend_name_reports_forced_stub_mode(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        core.reset_backend_tracking()
        monkeypatch.setenv("ALPHAEDGE_CORE_BACKEND", "stubs")

        with patch.object(
            importlib,
            "import_module",
            return_value=SimpleNamespace(
                __name__="alphaedge.core._stubs.momentum_detector"
            ),
        ):
            core.load_core_module("momentum_detector")
            backend_name = core.get_backend_name()
            fallback_modules = core.get_fallback_modules()

        assert backend_name == "stubs"
        assert fallback_modules == ()
