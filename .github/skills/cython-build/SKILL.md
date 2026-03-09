---
name: cython-build
description: "Use when: editing any .pyx file in alphaedge/core/, rebuilding Cython extensions, troubleshooting missing .pyd/.so modules, or running the full build+QA pipeline after a Cython change."
---

# Cython Build Workflow — ALPHAEDGE

## When to invoke this skill
Any edit to a file matching `alphaedge/core/*.pyx`.

## Steps

### 1. Edit the `.pyx` source
Only change what was explicitly requested. Read the corresponding stub
in `alphaedge/core/_stubs/<module>.py` first to understand the interface.

### 2. Mirror the change in the Python stub
Update `alphaedge/core/_stubs/<module>.py` to match any signature change.
This keeps Pylance, Mypy, and tests aligned with the compiled module.

### 3. Build
```powershell
.\.venv\Scripts\Activate.ps1
make build
```
Compiles all `.pyx` files via `setup.py`. Produces `.pyd` (Windows) or `.so` (Linux).

### 4. QA
```powershell
make qa
```
Runs: Ruff lint → Mypy strict → Pytest (≥80% coverage on `config/`, `utils/`, `core/`).

## Common Errors

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ModuleNotFoundError: alphaedge.core.X` | `.pyx` not compiled | Run `make build` |
| `cannot import name 'X'` | Stub/`.pyx` signature mismatch | Sync `_stubs/<module>.py` |
| `fatal error C1083` on Windows | MSVC not in PATH | Open terminal from VS Developer Shell |
| Coverage < 80% | New code path not covered | Add parametrized test in `alphaedge/tests/` |
| `make build` hangs | Stale `.c` file | Run `make clean` then `make build` |

## Commit convention
```
cython: <description of change>
```
