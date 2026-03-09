# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : setup.py
# DESCRIPTION  : Cython compilation setup for core modules
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: Cython build configuration."""

from __future__ import annotations

import os
import sys

from Cython.Build import cythonize
from setuptools import Extension, setup

# Verify Python version
_REQUIRED = (3, 11)
if sys.version_info[:2] != _REQUIRED:
    sys.exit(
        f"ALPHAEDGE requires Python {_REQUIRED[0]}.{_REQUIRED[1]}.x — "
        f"detected {sys.version}"
    )

# Cython extension modules
_CORE_DIR = os.path.join("alphaedge", "core")

extensions: list[Extension] = [
    Extension(
        name="alphaedge.core.fcr_detector",
        sources=[os.path.join(_CORE_DIR, "fcr_detector.pyx")],
    ),
    Extension(
        name="alphaedge.core.gap_detector",
        sources=[os.path.join(_CORE_DIR, "gap_detector.pyx")],
    ),
    Extension(
        name="alphaedge.core.engulfing_detector",
        sources=[os.path.join(_CORE_DIR, "engulfing_detector.pyx")],
    ),
    Extension(
        name="alphaedge.core.order_manager",
        sources=[os.path.join(_CORE_DIR, "order_manager.pyx")],
    ),
    Extension(
        name="alphaedge.core.risk_manager",
        sources=[os.path.join(_CORE_DIR, "risk_manager.pyx")],
    ),
]

setup(
    # Project metadata is in pyproject.toml ([project] section).
    # This setup() call exists solely to compile Cython extensions via
    # `python setup.py build_ext --inplace` (i.e. `make build`).
    # setuptools PEP 517 does not yet support `build_ext --inplace` natively,
    # so setup.py is intentionally kept for that single purpose.
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            "language_level": "3",
            "boundscheck": False,
            "wraparound": False,
            "cdivision": True,
        },
    ),
)


if __name__ == "__main__":
    print("ALPHAEDGE — Run: python setup.py build_ext --inplace")
