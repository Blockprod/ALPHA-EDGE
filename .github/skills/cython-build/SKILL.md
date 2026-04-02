---
name: cython-build
description: "Use when: editing any .pyx file in alphaedge/core/, rebuilding Cython extensions, troubleshooting missing .pyd/.so modules, or running the full build+QA pipeline after a Cython change."
---

# Cython Build Workflow — ALPHAEDGE

## When to invoke this skill
Invoke this skill when editing any file matching `alphaedge/core/*.pyx` or when troubleshooting Cython compilation issues.

## ⛔ Hard Stop
**Never run `make build` unless a `.pyx` file was intentionally modified.**
It triggers a full recompilation — slow and irreversible mid-session.

## Modules — `.pyx` ↔ stub mapping

| Module | `.pyx` source | Python stub |
|--------|--------------|-------------|
| legacy range detection | `core/momentum_detector.pyx` | `core/_stubs/momentum_detector.py` |
| Gap / ATR filter | `core/gap_detector.pyx` | `core/_stubs/gap_detector.py` |
| Engulfing signal | `core/engulfing_detector.pyx` | `core/_stubs/engulfing_detector.py` |
| Position sizing | `core/risk_manager.pyx` | `core/_stubs/risk_manager.py` |
| Bracket order | `core/order_manager.pyx` | `core/_stubs/order_manager.py` |

> ⚠ All `.pyx` modules use **module-level functions + `cdef struct`**, not `cdef class`.
> Never introduce a `cdef class` without explicit instruction.

## Prerequisites
- Visual Studio Build Tools (Windows) with C++ development tools
- Python virtual environment activated
- Make utility available

## Steps

### 1. Edit the `.pyx` source
- Only change what was explicitly requested
- Read the corresponding stub in `alphaedge/core/_stubs/<module>.py` first to understand the interface
- Maintain backward compatibility when possible

### 2. Mirror the change in the Python stub
- Update `alphaedge/core/_stubs/<module>.py` to match any signature change
- This keeps Pylance, Mypy, and tests aligned with the compiled module
- Ensure type hints are accurate

### 3. Build the extension
```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Compile all Cython extensions
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

## Quick Reference — Types Cython ↔ Python

| Python 3.11 | Cython `cdef` | Notes |
|-------------|--------------|-------|
| `int` | `cdef int` | 32-bit signed |
| `float` | `cdef double` | 64-bit float |
| `bool` | `cdef bint` | 0/1 integer under the hood |
| `str` | `object` | Python object — no `cdef` type |
| `list[float]` | `cdef double[:]` | Typed memoryview |
| `dict` | `object` | Python object |

## Example — Add a field to a `cdef struct`

The real modules use `cdef struct`, not `cdef class`. Example: add a `candle_count` field to `legacy rangeResult` in `momentum_detector.pyx`.

**Step 1 — `.pyx`:**
```cython
# alphaedge/core/momentum_detector.pyx
cdef struct legacy rangeResult:
    bint detected
    double range_high
    double range_low
    double range_size
    long candle_timestamp
    int candle_count       # ← new field
```

**Step 2 — stub** (`core/_stubs/momentum_detector.py`): add `"candle_count": int` to the returned `dict` in `detect_momentum()`.

**Step 3:**
```powershell
make build
make qa
```

## Gotchas (from tasks/lessons.md)

- Après tout edit `.pyx`, vérifier `_stubs/<module>.py` — une divergence de signature (nom de paramètre, ordre, clé du dict retourné) est silencieuse au chargement du `.pyd` et produit des bugs runtime subtils (2026-03-22)
- `make build` ne doit JAMAIS être lancé sans modification `.pyx` intentionnelle — lent et irréversible mid-session
- Nommer le commit `cython: <description>` après chaque edit `.pyx` réussi
