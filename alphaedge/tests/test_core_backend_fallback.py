# ============================================================
# PROJECT      : ALPHAEDGE — Swing Trading Bot
# FILE         : alphaedge/tests/test_core_backend_fallback.py
# DESCRIPTION  : Cover _load_core_module() cascade: ImportError→fallback
#                and production raise when compiled module is missing.
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-25
# ============================================================
"""ALPHAEDGE — Verify _load_core_module() fallback and production-raise behaviour."""

from __future__ import annotations

import importlib
from types import ModuleType
from unittest.mock import patch

import pytest

import alphaedge.core as core_pkg

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
_MODULE_NAME = "momentum_detector"
_COMPILED_PATH = f"alphaedge.core.{_MODULE_NAME}"
_STUB_PATH = f"alphaedge.core._stubs.{_MODULE_NAME}"

_orig_import = importlib.import_module


def _import_side_effect(name: str, package: str | None = None) -> ModuleType:
    """Raise ImportError for the compiled path; delegate everything else."""
    if name == _COMPILED_PATH:
        raise ImportError(f"mocked: compiled module '{name}' not found")
    return _orig_import(name, package=package)


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------
class TestCoreBackendFallback:
    """Verify _load_core_module() ImportError→fallback cascade."""

    def test_backend_fallback_on_import_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        When compiled .pyd is absent (ImportError), auto mode must:
        - silently return the stub module
        - register the module in get_fallback_modules()
        """
        monkeypatch.setenv("ALPHAEDGE_CORE_BACKEND", "auto")
        monkeypatch.delenv("ALPHAEDGE_ENV", raising=False)

        core_pkg.reset_backend_tracking()

        with patch(
            "alphaedge.core.importlib.import_module", side_effect=_import_side_effect
        ):
            module = core_pkg.load_core_module(_MODULE_NAME)

        # Should have fallen back to the stub
        assert module is not None
        assert hasattr(module, "detect_momentum"), (
            "Fallback stub must expose detect_momentum()"
        )
        assert _MODULE_NAME in core_pkg.get_fallback_modules(), (
            f"get_fallback_modules() must include '{_MODULE_NAME}' after fallback"
        )

    def test_backend_production_raises_on_missing_compiled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        In ALPHAEDGE_ENV=production, a missing compiled module must raise
        ImportError — never fall back silently.
        """
        monkeypatch.setenv("ALPHAEDGE_CORE_BACKEND", "auto")
        monkeypatch.setenv("ALPHAEDGE_ENV", "production")

        core_pkg.reset_backend_tracking()

        with (
            patch(
                "alphaedge.core.importlib.import_module",
                side_effect=_import_side_effect,
            ),
            pytest.raises(ImportError, match="required in production"),
        ):
            core_pkg.load_core_module(_MODULE_NAME)

            core_pkg.load_core_module(_MODULE_NAME)
