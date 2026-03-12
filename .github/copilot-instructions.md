# ⚡ ALPHAEDGE — GitHub Copilot Instructions

> This file is read automatically by GitHub Copilot in every session.
> It defines the project context, rules, and workflow for AI-assisted development.

---

## Project Identity

| Field | Value |
|-------|-------|
| Name | ALPHAEDGE — FCR Forex Trading Bot |
| Python | **3.11.9 strictly** — never use 3.12+ syntax |
| Stack | Python / Cython 3.0 / ib_insync / loguru / Rich / vectorbt |
| Broker | Interactive Brokers via IB Gateway |
| Mode | Paper trading default (`ALPHAEDGE_PAPER=true`) |

---

## Architecture — Signal Pipeline

```
IB Gateway
  └─► data_feed.py          [Python]  — M5 bar feed
        └─► fcr_detector.pyx [Cython]  — FCR range detection
        └─► gap_detector.pyx [Cython]  — ATR spike filter
        └─► engulfing_detector.pyx [Cython] — M1 entry signal
              └─► risk_manager.pyx [Cython]  — Position sizing
              └─► order_manager.pyx [Cython] — Bracket order
                    └─► broker.py    [Python] — IB order submission
```

**Dependency flow:** `engine/` → `core/` → `config/` → `utils/`

---

## Absolute Rules


1. **`ALPHAEDGE_PAPER=true` is the default.** Never suggest live trading without explicit user confirmation.
2. **After editing any `.pyx` file, run `make build`** to recompile Cython. The `.pyx` sources are not the runtime modules — the compiled `.pyd`/`.so` files are.
3. **Do not modify `alphaedge/core/` logic** without explicit instruction. The FCR strategy is proprietary.
4. **`make qa` must pass before any commit:** Ruff lint + Mypy (`pyproject.toml`) + Pytest ≥80% coverage.
5. **Python 3.11.9 only.** No 3.12+ syntax.
6. **Coverage threshold applies to `config/`, `utils/`, `core/` only.** `engine/` modules are excluded (require IB Gateway).

---

## Hard Stops — Never Do These

- Never set `ALPHAEDGE_PAPER=false` in any file, ever
- Never modify `core/*.pyx` without explicit instruction from the user
- Never commit `.env`, `*.log`, or any proprietary action plan files
- Never run `make build` unless a `.pyx` file was intentionally modified
- Never use `# type: ignore` or `# pyright: ignore` as a fix — find and fix the root cause
- Never use `Any` as a type annotation shortcut — it is a rustine, not a solution
- Never hardcode pip values, RR ratios, session times, or risk parameters outside `alphaedge/config/constants.py`
- Never touch `alphaedge/utils/timezone.py` or `session_manager.py` without re-running DST edge case tests
- Never mark a task complete without running `make qa` and confirm all tests pass
- Never push a `.pyx` edit without running `make build` followed by `make qa`

---

## Workflow Orchestration

- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately — don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity
- Use the `Explore` subagent for research/exploration
- After ANY correction from the user: update `tasks/lessons.md` with the pattern
- Never mark a task complete without proving it works (run `make qa` — all tests must pass)
- Demand elegance: challenge your own work before presenting it
- When given a bug report: just fix it. Don't ask for hand-holding

---

## Task Management

1. Plan First: Use the Copilot todo list tool with checkable items
2. Verify Plan: Check in before starting implementation
3. Track Progress: Mark items complete as you go
4. Explain Changes: High-level summary at each step
5. Capture Lessons: Update `tasks/lessons.md` after any correction

---

## Core Principles

- Simplicity First: Make every change as simple as possible. Impact minimal code.
- No Laziness: Find root causes. No temporary fixes. Senior developer standards.
- Minimal Impact: Changes should only touch what's necessary. Avoid introducing bugs.
- Audit Before Modify: For any non-trivial change, read before writing. Cite file + line before proposing a modification.

---

## Return Value Contracts

| Function | Returns None / falsy | Correct agent behavior |
|----------|----------------------|------------------------|
| `detect_fcr(...)` | No valid FCR found | STOP — do not proceed to gap detection |
| `detect_gap(...)` | `detected: False` | STOP — do not proceed to engulfing detection |
| `detect_engulfing(...)` | `None` | STOP — do not place any order |
| `calculate_position_size(...)` | `is_valid: False` | STOP — do not submit order, log WARNING |
| `check_daily_limit(...)` | `halt_trading: True` | STOP ALL trading immediately — log CRITICAL |
| `create_bracket_order(...)` | `is_valid: False` | STOP — log rejection_reason, skip trade |

**The pipeline is all-or-nothing: one STOP at any stage cancels the entire trade.**

---

## Key Files

| Purpose | File |
|---------|------|
| Trading thresholds | `alphaedge/config/constants.py` |
| Runtime config | `config.yaml` |
| Environment template | `.env.example` |
| Build | `setup.py` |
| QA | `Makefile` + `pyproject.toml` |
| Technical audit | `ALPHAEDGE_MASTER_AUDIT.md` |
| Open tasks | `ALPHAEDGE_STRUCTURAL_ACTION_PLAN.md` |

---

## QA Commands

```powershell
.\.venv\Scripts\Activate.ps1   # activate venv (Windows)
make qa                         # lint + mypy + tests
make build                      # compile Cython after .pyx changes
make clean                      # remove build artifacts
```

---

## Test Naming Convention

All test files must follow: `test_<module>_<scenario>.py`

Examples:
- `test_fcr_detector_detect.py` — happy path FCR detection
- `test_risk_manager_daily.py` — daily loss limit check
- `test_order_manager_validation.py` — bracket order rejection

One scenario per file. Use `pytest.mark.parametrize` for data variants.

---

## Cython `.pyx` Files — Handling Rules

- **Never edit `.pyx` files** without running `make build` immediately after.
- The compiled `.pyd` (Windows) / `.so` (Linux) is the runtime module.
  The `.pyx` source alone does nothing at runtime.
- For quick iteration, use the pure-Python stubs in `alphaedge/core/_stubs/`.
- Workflow after any `.pyx` change: `make build` → `make qa` (both must pass).
- Always flag `.pyx` edits in commit messages: `cython: <description>`.

---

## Gitignored / Proprietary

- `ALPHAEDGE_ACTION_PLAN.md` — proprietary, do not regenerate
- `.env` — IB credentials, never commit
- `alphaedge/logs/*.log` — runtime only
