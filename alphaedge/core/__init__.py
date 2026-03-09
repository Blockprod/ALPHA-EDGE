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
"""

import importlib
from types import ModuleType


def _load_core_module(name: str) -> ModuleType:
    """Import a compiled Cython module or fall back to the pure-Python stub."""
    try:
        return importlib.import_module(f"alphaedge.core.{name}")
    except ImportError:
        return importlib.import_module(f"alphaedge.core._stubs.{name}")


fcr_detector: ModuleType = _load_core_module("fcr_detector")
gap_detector: ModuleType = _load_core_module("gap_detector")
engulfing_detector: ModuleType = _load_core_module("engulfing_detector")
order_manager: ModuleType = _load_core_module("order_manager")
risk_manager: ModuleType = _load_core_module("risk_manager")
