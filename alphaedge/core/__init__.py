# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/core/__init__.py
# DESCRIPTION  : Core Cython modules package initializer
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-08
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: Cython core signal and execution modules.

Attempts to import compiled Cython modules first. If compilation is
unavailable (e.g. CI without a C compiler), falls back to pure-Python
stubs that expose identical interfaces.

Set ``ALPHAEDGE_CORE_BACKEND=compiled`` to require compiled extensions,
``ALPHAEDGE_CORE_BACKEND=stubs`` to force the pure-Python fallbacks, or
leave it unset / ``auto`` to prefer compiled modules then fall back.
"""

import importlib
import os
from types import ModuleType

from alphaedge.utils.logger import get_logger

_CORE_BACKEND_ENV_VAR = "ALPHAEDGE_CORE_BACKEND"
_LOADED_BACKENDS: dict[str, str] = {}
_FALLBACK_MODULES: set[str] = set()

logger = get_logger()


def _record_backend(name: str, backend: str) -> None:
    """Store which backend loaded a given core module."""
    _LOADED_BACKENDS[name] = backend


def get_backend_name() -> str:
    """Return the effective core backend currently loaded."""
    backends = set(_LOADED_BACKENDS.values())
    if not backends:
        return "unknown"
    if backends == {"compiled"}:
        return "compiled"
    if backends == {"stubs"}:
        return "stubs"
    return "mixed"


def get_fallback_modules() -> tuple[str, ...]:
    """Return compiled modules that had to fall back to stubs."""
    return tuple(sorted(_FALLBACK_MODULES))


def reset_backend_tracking() -> None:
    """Reset backend bookkeeping. Used by tests and explicit reload flows."""
    _LOADED_BACKENDS.clear()
    _FALLBACK_MODULES.clear()


def load_core_module(name: str) -> ModuleType:
    """Public wrapper around core module loading for tests and diagnostics."""
    return _load_core_module(name)


def _load_core_module(name: str) -> ModuleType:
    """Import a compiled Cython module or fall back to the pure-Python stub."""
    backend = os.getenv(_CORE_BACKEND_ENV_VAR, "auto").strip().lower()

    if backend == "stubs":
        _record_backend(name, "stubs")
        return importlib.import_module(f"alphaedge.core._stubs.{name}")

    if backend == "compiled":
        _record_backend(name, "compiled")
        return importlib.import_module(f"alphaedge.core.{name}")

    try:
        module = importlib.import_module(f"alphaedge.core.{name}")
        _record_backend(name, "compiled")
        return module
    except ImportError:
        _FALLBACK_MODULES.add(name)
        _record_backend(name, "stubs")
        logger.warning(
            "ALPHAEDGE core fallback: compiled module {} unavailable; using stubs",
            name,
        )
        return importlib.import_module(f"alphaedge.core._stubs.{name}")


fcr_detector: ModuleType = _load_core_module("fcr_detector")
gap_detector: ModuleType = _load_core_module("gap_detector")
engulfing_detector: ModuleType = _load_core_module("engulfing_detector")
order_manager: ModuleType = _load_core_module("order_manager")
risk_manager: ModuleType = _load_core_module("risk_manager")
