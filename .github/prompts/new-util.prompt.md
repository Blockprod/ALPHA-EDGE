---
agent: agent
description: Add a utility function with type hints and tests to alphaedge/utils/
---

# Add Utility Function — ALPHAEDGE

Add a new utility function to `alphaedge/utils/`.

## Rules
- Place the function in the most relevant existing file under `alphaedge/utils/`
  (check `logger.py`, `timezone.py`, `session_manager.py` before creating a new file).
- Type hints are mandatory — all parameters and return types must be annotated.
- Do NOT use `print()` — use `from loguru import logger` if logging is needed.
- No circular imports: `utils/` must not import from `engine/` or `core/`.

## Template
```python
def <name>(<param>: <type>, ...) -> <return_type>:
    """One-line description of what the function does."""
    # implementation
```

## Test file to create alongside
`alphaedge/tests/test_<util_module>_<scenario>.py`

```python
"""ALPHAEDGE — Test: utils/<module> / <scenario>."""
import pytest
from alphaedge.utils.<module> import <name>


def test_<util_module>_<scenario>():
    result = <name>(<args>)
    assert result == <expected>
```

## Checklist after creation
- [ ] `make qa` passes (Ruff + Mypy + Pytest)
- [ ] No new import added to `engine/` or `core/`
