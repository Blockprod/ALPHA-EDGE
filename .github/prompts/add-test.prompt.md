---
agent: agent
description: Add a pytest stub for a given ALPHAEDGE module
---

# Add Test — ALPHAEDGE

Add a pytest test file for the module specified by the user.

## Rules
- File name: `test_<module>_<scenario>.py` in `alphaedge/tests/`
- One scenario per file. Use `pytest.mark.parametrize` for data variants.
- Import from `alphaedge.core._stubs.<module>` — never from `.pyx` directly.
- Do NOT mock internal Cython logic — test via the public stub interface only.
- Every test must be runnable with `make test` (no IB Gateway required).

## Template
```python
"""ALPHAEDGE — Test: <module> / <scenario>."""
import pytest
from alphaedge.core._stubs.<module> import <function>


@pytest.mark.parametrize("input,expected", [
    # (input_dict, expected_output),
])
def test_<module>_<scenario>(input, expected):
    result = <function>(**input)
    assert result == expected
```

## Checklist after creation
- [ ] `make test` passes
- [ ] Coverage for this module increases in `ALPHAEDGE_coverage_report/`
