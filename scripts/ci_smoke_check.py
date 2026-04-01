"""CI smoke check — verifies all Cython core modules loaded from compiled .so.

Run via: python scripts/ci_smoke_check.py
Required env: ALPHAEDGE_CORE_BACKEND=compiled
"""

import sys
from pathlib import Path

# Ensure repo root is on sys.path when script is invoked directly
# (Python adds the script's directory, not cwd, to sys.path[0])
sys.path.insert(0, str(Path(__file__).parent.parent))

from alphaedge.core import (
    get_backend_name,
    get_fallback_modules,
    momentum_detector,  # noqa: F401 — import verifies .so presence
    order_manager,  # noqa: F401
    risk_manager,  # noqa: F401
)

backend = get_backend_name()
fallback = get_fallback_modules()

print(f"Backend: {backend}")

if fallback:
    print(f"Fallbacks: {fallback}")
    sys.exit("Compiled modules expected — got stubs")

print("All Cython core modules loaded from compiled .so")
