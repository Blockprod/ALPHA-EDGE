---
agent: agent
description: Full Cython edit → build → QA workflow for ALPHAEDGE
---

# Cython Edit Workflow — ALPHAEDGE

Guide the user through a safe edit of a `.pyx` file in `alphaedge/core/`.

## Pre-edit checklist
- [ ] Identify the target `.pyx` file (never modify without explicit instruction)
- [ ] Read the corresponding stub in `alphaedge/core/_stubs/` first
- [ ] Confirm the public interface (inputs/outputs) is unchanged

## Workflow

### 1. Edit the `.pyx` source
Only edit what was explicitly requested. Do not refactor surrounding logic.

### 2. Mirror the change in the Python stub
Update `alphaedge/core/_stubs/<module>.py` to match the new signature.

### 3. Build
```powershell
.\.venv\Scripts\Activate.ps1
make build
```
Expected: no compiler errors, `.pyd` file updated in `alphaedge/core/`.

### 4. Run QA
```powershell
make qa
```
Expected: Ruff ✓, Mypy ✓, Pytest ✓ (≥80% coverage)

## Common errors

| Error | Fix |
|-------|-----|
| `ModuleNotFoundError: alphaedge.core.X` | `make build` was not run |
| `cannot import name 'X'` | Stub and `.pyx` signature mismatch |
| `fatal error C1083` (Windows) | MSVC Build Tools not in PATH — reopen VS Code from dev shell |
| Coverage drops below 80% | Add/update stub tests in `alphaedge/tests/` |

## Commit message convention
```
cython: <description of change>
```
