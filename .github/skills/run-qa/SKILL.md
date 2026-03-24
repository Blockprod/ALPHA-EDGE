---
name: run-qa
description: >
  Use when: running make qa, diagnosing lint/mypy/pytest errors, checking
  coverage threshold after any change to alphaedge/ files, or validating
  that a correction did not break the baseline.
---

# Skill — run-qa

## When to invoke this skill

- After editing any `.py` file in `alphaedge/`
- After a failed `make qa` run to diagnose and fix errors
- Before marking any task as complete
- When coverage drops below 80% on `config/`, `utils/`, or `core/`

## Steps

```powershell
# 1. Activate environment (Windows)
.\.venv\Scripts\Activate.ps1

# 2. Run full QA pipeline
make qa
# Runs: ruff check → mypy → pytest --cov

# 3. Read output in order:
#    - Ruff: lint errors (fix first)
#    - Mypy: type errors (fix second)
#    - Pytest: failing tests (fix third)
#    - Coverage: must be ≥80% on config/, utils/, core/
```

## Coverage Thresholds

| Folder | Threshold | Notes |
|--------|-----------|-------|
| `alphaedge/config/` | ≥ 80% | Required |
| `alphaedge/utils/` | ≥ 80% | Required |
| `alphaedge/core/` (stubs) | ≥ 80% | Required |
| `alphaedge/engine/` | Excluded | Requires IB Gateway |

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Missing return type annotation` | mypy strict | Add return type to function signature |
| `Module not found` | venv not active | `.\.venv\Scripts\Activate.ps1` first |
| `Coverage below threshold` | New code without tests | Add test in `tests/test_<module>_<scenario>.py` |
| `Ruff E501 line too long` | Line > 100 chars | Break line or use continuation |
| `assert used in production code` | Ruff S101 | Replace with explicit `if … raise` |
| `Any` annotation | mypy error | Find correct type — never use `Any` |
| `# type: ignore` | forbidden | Fix root cause, create stub if needed |

## Test Naming Convention

```
test_<module>_<scenario>.py    # one scenario per file
```
Examples: `test_fcr_detector_detect.py`, `test_risk_manager_daily.py`

## Baseline

> 504 tests · 100% pass · Coverage ≥80% sur config/, utils/, core/
