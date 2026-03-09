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

1. **`ALPHAEDGE_PAPER=true` is the default.** Never suggest live trading
   without explicit user confirmation.

2. **After editing any `.pyx` file, run `make build`** to recompile Cython.
   The `.pyx` sources are not the runtime modules — the compiled `.pyd`/`.so`
   files are.

3. **Do not modify `alphaedge/core/` logic** without explicit instruction.
   The FCR strategy is proprietary.

4. **`make qa` must pass before any commit:**
   Ruff lint + Mypy (`pyproject.toml`) + Pytest ≥80% coverage.

5. **Python 3.11.9 only.** No 3.12+ syntax.

6. **Coverage threshold applies to `config/`, `utils/`, `core/` only.**
   `engine/` modules are excluded (require IB Gateway).

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
