# ⚡ ALPHAEDGE
# ALPHAEDGE

This repository contains proprietary trading software.

**No public documentation is provided.**

For inquiries, contact the project owner.
---

## Installation

### 1. Clone the Repository

```powershell
git clone <repository-url> AlphaEdge
cd AlphaEdge
```

### 2. Create Virtual Environment

```powershell
python -m venv .venv
```

### 3. Activate

```powershell
.\.venv\Scripts\Activate.ps1
```

### 4. Install Dependencies

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Compile Cython Modules

```powershell
python setup.py build_ext --inplace
```

---

## IB Gateway Setup

1. Download IB Gateway from [Interactive Brokers](https://www.interactivebrokers.com/en/trading/ibgateway-stable.php)
2. Configure API → Enable ActiveX and Socket Clients
3. Socket port: **4002** (paper) — **4001** (live)
4. Log in with **paper trading** credentials first

---

## VSCode Setup

1. Open project in VSCode — accept recommended extensions
2. `Ctrl+Shift+P` → "Python: Select Interpreter" → choose `.venv` (3.11.9)

---

## Configuration

### Environment Variables (`.env`)

```powershell
copy .env.example .env
```

Edit `.env`:

```ini
IB_ACCOUNT=DU1234567        # Your IB paper account ID
IB_HOST=127.0.0.1
IB_PORT=4002                # 4002 = paper, 4001 = live
IB_CLIENT_ID=1
IB_PAPER_MODE=true          # ALWAYS start with true
```

### Trading Parameters (`config.yaml`)

All risk and execution parameters are in `config.yaml`. Strategy logic is proprietary — do not modify `alphaedge/core/` without authorisation.

---

## Cython Compilation

```powershell
make build
```

Verify:

```powershell
python -c "import alphaedge.core; print('OK')"
```

Troubleshooting:

| Issue | Solution |
|-------|----------|
| `error: Microsoft Visual C++ 14.0 is required` | Install [VS Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) |
| `ImportError: cannot import` after build | Re-run `make build` |

---

## QA Toolchain

```powershell
make qa       # lint + typecheck + tests
make qa-strict  # + pylint
make build    # recompile Cython after .pyx changes
make clean    # remove build artifacts
```

Coverage threshold ≥80% applies to `config/`, `utils/`, `core/` (stubs). `engine/` requires live IB Gateway and is excluded.

---

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

## Project Structure

```
AlphaEdge/
├── .vscode/                    # VSCode workspace config
│   ├── settings.json
│   ├── extensions.json
│   └── launch.json
├── alphaedge/                  # Main package
│   ├── __init__.py
│   ├── core/                   # Cython modules (compiled)
│   ├── engine/                 # Python orchestration
│   ├── config/                 # Configuration loading
│   ├── utils/                  # Timezone + logging
│   ├── logs/                   # Runtime log files
│   └── tests/                  # Pytest tests
├── config.yaml                 # Trading parameters
├── .env.example                # Environment template
├── requirements.txt            # Pinned dependencies
├── pyproject.toml              # Black + Ruff + Pytest config
├── mypy.ini                    # Mypy strict config
├── .pylintrc                   # Pylint config
├── Makefile                    # Build + QA automation
├── setup.py                    # Cython compilation
├── .gitignore                  # Git exclusions
└── README.md                   # This file
```

---

## License

This project is proprietary. All rights reserved.

---

**Built with:** Python 3.11.9 · Cython 3.0 · Interactive Brokers · loguru · Rich · vectorbt
