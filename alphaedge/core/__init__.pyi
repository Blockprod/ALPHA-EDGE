"""Type stubs for alphaedge.core — Pylance / Pyright resolution."""

# NOTE: Pyright resolves all core imports to _stubs/ (compiled .pyd are not
# statically analysable). Interface drift between .pyx and stubs is only
# detected at runtime or via integration tests. Run `make qa` after any
# .pyx change to ensure stub compatibility.
from types import ModuleType

from alphaedge.core._stubs import momentum_detector as momentum_detector
from alphaedge.core._stubs import order_manager as order_manager
from alphaedge.core._stubs import risk_manager as risk_manager

def get_backend_name() -> str: ...
def get_fallback_modules() -> tuple[str, ...]: ...
def reset_backend_tracking() -> None: ...
def load_core_module(name: str) -> ModuleType: ...
