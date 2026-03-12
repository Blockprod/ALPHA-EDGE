# ⚡ ALPHAEDGE
# ALPHAEDGE

This repository contains proprietary trading software.


Minimal README. No documentation provided.

## Running Backtest

```powershell
python -m alphaedge.engine.backtest
# ALPHAEDGE

This repository contains proprietary trading software.

**No public documentation is provided.**

For inquiries, contact the project owner.
| `error: Microsoft Visual C++ 14.0 is required` | Install [VS Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) |
| `fatal error: Python.h: No such file` | Install `python3.11-dev` (Linux) |
| `ImportError: cannot import` after build | Re-run `python setup.py build_ext --inplace` |

> **Note**: If Cython modules are not compiled, the strategy engine falls back to a warning mode. Compile before running.

---

## QA Toolchain

### Run All QA Checks

```powershell
make qa
```

This runs: Ruff (lint) → Pyright / Pylance (type checking) → Pytest.

> **Coverage scope** : The ≥80% threshold applies to `config/`, `utils/`, and `core/` (via stubs) only.
> `engine/` modules require a live IB Gateway connection and are excluded from automated coverage.

### Individual Tools

| Tool | Command | Purpose |
|------|---------|---------|
| **Ruff** | `make lint` | Fast linting (E, F, W, I, N, UP rules) |
| **Pyright** | `make typecheck` | Static type checking (Pylance engine) |
| **Pylint** | `make pylint` | Deep analysis — included in `make qa-strict` |
| **Pytest** | `make test` | Unit tests + coverage report |

### Pytest

```powershell
# Run all tests with coverage
pytest --cov=alphaedge --cov-report=term-missing -v

# Run specific module tests
pytest alphaedge/tests/test_fcr_detector_detect.py -v

# Run with output
pytest -v -s
```

**Coverage target: ≥ 80%**

### Test Naming Convention

```
test_<module>_<function_or_scenario>.py
```

---

## Running Backtest

```powershell
python -m alphaedge.engine.backtest
```

**Outputs:**
- Trade results CSV
- Equity curve plot
- Console summary with key performance metrics

> Backtest requires IB Gateway connection for historical data retrieval.

---

## Running Live / Paper

### Paper Trading (Recommended)

```powershell
python -m alphaedge.engine.strategy --mode paper
```

### Live Trading

```powershell
python -m alphaedge.engine.strategy --mode live
```

> **⚠️ Live mode requires explicit confirmation prompt.** Set `IB_PAPER_MODE=false` in `.env` and use port **4001**.

### Dashboard Preview

```powershell
python -m alphaedge.engine.dashboard
```

Displays the Rich terminal dashboard with mock data for layout testing.

---

## License

This project is proprietary. All rights reserved.

---

**Built with:** Python 3.11.9 · Cython 3.0 · Interactive Brokers · loguru · Rich · vectorbt
