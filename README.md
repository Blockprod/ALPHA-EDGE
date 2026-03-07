# ⚡ ALPHAEDGE — FCR Forex Trading Bot

**Production-ready hybrid Python/Cython automated trading bot implementing the Failed Candle Range (FCR) multi-timeframe strategy for Forex via Interactive Brokers.**

> **⚠️ WARNING: This bot places REAL orders. Always start with PAPER TRADING (IB port 4002). Live trading carries significant risk of financial loss. Use at your own discretion.**

---

## Table of Contents

1. [Strategy Overview](#strategy-overview)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Installation](#installation)
5. [IB Gateway Setup](#ib-gateway-setup)
6. [VSCode Setup](#vscode-setup)
7. [Configuration](#configuration)
8. [Cython Compilation](#cython-compilation)
9. [QA Toolchain](#qa-toolchain)
10. [Running Backtest](#running-backtest)
11. [Running Live / Paper](#running-live--paper)
12. [Project Structure](#project-structure)
13. [License](#license)

---

## Strategy Overview

ALPHAEDGE implements the **FCR (Failed Candle Range) multi-timeframe strategy** adapted for Forex:

| Component | Details |
|-----------|---------|
| **Structure timeframe** | M5 (5-minute candles) |
| **Entry timeframe** | M1 (1-minute candles) |
| **Session** | NYSE Open only: 9:30–10:30 AM EST |
| **Pairs** | EUR/USD, GBP/USD, USD/JPY |
| **Risk per trade** | 1% of account equity |
| **Risk-Reward** | 3:1 minimum |
| **Max trades/session** | 2 |
| **Daily loss limit** | -3% auto-shutdown |

### Signal Flow

```
1. Pre-session (9:25-9:30 EST)  → Detect M5 FCR range
2. Session open (9:30 EST)      → Detect ATR spike (gap equivalent)
3. M1 monitoring (9:30-10:30)   → Detect engulfing pattern at FCR level
4. Entry trigger                → Bracket order: Entry + SL + TP (3:1 RR)
5. Risk check                   → Position size (1%), daily limit (-3%)
```

### Forex Adaptations

- **No true gap at 9:30 EST** — uses ATR spike ratio as volatility expansion proxy
- **Tick count as volume proxy** — Forex has no centralized volume
- **Pip precision** — 4 decimals standard, 2 for JPY pairs (0.0001 / 0.01 pip size)

---

## Architecture

```
alphaedge/
├── core/           ← Cython (.pyx) — low-latency signal + execution
│   ├── fcr_detector.pyx
│   ├── gap_detector.pyx
│   ├── engulfing_detector.pyx
│   ├── order_manager.pyx
│   └── risk_manager.pyx
├── engine/         ← Python — orchestration + I/O
│   ├── broker.py
│   ├── data_feed.py
│   ├── strategy.py
│   ├── backtest.py
│   └── dashboard.py
├── config/         ← Configuration loading
├── utils/          ← Timezone + logging
├── logs/           ← Runtime log files
└── tests/          ← Pytest unit tests
```

**Dependency flow is strictly top-down:** `engine/ → core/`, `engine/ → config/`, `engine/ → utils/`. No circular imports.

---

## Prerequisites

### Python Version

**Python 3.11.9** is strictly required. Verify:

```powershell
python --version
# Expected: Python 3.11.9
```

> Do **not** use Python 3.12+. Some dependencies (vectorbt, ib_insync) are not yet compatible.

### System Requirements

- **OS**: Windows 10/11, macOS 12+, or Linux (Ubuntu 22.04+)
- **C compiler**: Required for Cython compilation
  - Windows: [Microsoft Visual C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
  - macOS: `xcode-select --install`
  - Linux: `sudo apt install build-essential`
- **Interactive Brokers Gateway** or **TWS** (Trader Workstation)

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

### 3. Activate the Virtual Environment

```powershell
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# Windows (cmd)
.\.venv\Scripts\activate.bat

# macOS / Linux
source .venv/bin/activate
```

### 4. Verify Python Version Inside venv

```powershell
python --version
# Must output: Python 3.11.9
```

### 5. Install Dependencies

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

### 6. Compile Cython Modules

```powershell
python setup.py build_ext --inplace
```

See [Cython Compilation](#cython-compilation) for troubleshooting.

---

## IB Gateway Setup

### 1. Install IB Gateway

Download from [Interactive Brokers](https://www.interactivebrokers.com/en/trading/ibgateway-stable.php).

### 2. Configure API Settings

In IB Gateway → Configure → Settings → API:

- ✅ Enable ActiveX and Socket Clients
- ✅ Allow connections from localhost only
- Socket port: **4001** (live) or **4002** (paper)
- Master API client ID: **1** (or match your `.env`)

### 3. Paper Trading (Recommended First)

1. Log into IB Gateway with your **paper trading** credentials
2. Verify port **4002** is active
3. Set `IB_PAPER_MODE=true` in your `.env` file

### 4. Connection Verification

```python
from ib_insync import IB
ib = IB()
ib.connect("127.0.0.1", 4002, clientId=1)
print(ib.isConnected())  # Should print True
ib.disconnect()
```

---

## VSCode Setup

### 1. Install Recommended Extensions

Open the project in VSCode. You'll be prompted to install recommended extensions. Accept all, or manually install:

- **ms-python.python** — Python language support
- **ms-python.vscode-pylance** — Pylance type checker
- **charliermarsh.ruff** — Ruff linter
- **ms-python.black-formatter** — Black formatter
- **matangover.mypy** — Mypy type checking
- **littlefoxteam.vscode-python-test-adapter** — Test explorer

### 2. Select Python Interpreter

1. `Ctrl+Shift+P` → "Python: Select Interpreter"
2. Choose the `.venv` interpreter (Python 3.11.9)

### 3. Debug Configurations

Pre-configured launch configs (`.vscode/launch.json`):

| Config | Description |
|--------|-------------|
| `ALPHAEDGE — Paper Trading` | Run strategy on IB paper account |
| `ALPHAEDGE — Backtest` | Run historical backtest |
| `ALPHAEDGE — Unit Tests` | Run all tests with coverage |
| `ALPHAEDGE — Mypy Check` | Run Mypy type checking |
| `ALPHAEDGE — Ruff Check` | Run Ruff linting |
| `ALPHAEDGE — Dashboard Only` | Preview Rich dashboard |

---

## Configuration

### Environment Variables (`.env`)

Copy the example and fill in your credentials:

```powershell
copy .env.example .env
```

Edit `.env`:

```ini
IB_ACCOUNT=DU1234567        # Your IB account ID
IB_HOST=127.0.0.1           # IB Gateway host
IB_PORT=4002                # 4002 = paper, 4001 = live
IB_CLIENT_ID=1              # API client ID
IB_PAPER_MODE=true          # ALWAYS start with true
```

### Trading Parameters (`config.yaml`)

All strategy parameters are in `config.yaml`. Key sections:

```yaml
trading:
  pairs: ["EURUSD", "GBPUSD", "USDJPY"]
  risk_per_trade_pct: 1.0
  rr_ratio: 3.0
  max_trades_per_session: 2
  max_daily_loss_pct: 3.0
  max_spread_pips: 2.0
```

---

## Cython Compilation

### Build

```powershell
python setup.py build_ext --inplace
# or
make build
```

This compiles all `.pyx` files in `alphaedge/core/` into C extensions.

### Verify Build

```powershell
python -c "from alphaedge.core import fcr_detector; print('OK')"
```

### Clean Build

```powershell
make clean
python setup.py build_ext --inplace
```

### Troubleshooting

| Issue | Solution |
|-------|----------|
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

This runs: Black (format check) → Ruff (lint) → Pylint → Mypy → Pytest.

### Individual Tools

| Tool | Command | Purpose |
|------|---------|---------|
| **Black** | `make format` | Auto-format code (line length 88) |
| **Ruff** | `ruff check alphaedge/` | Fast linting (E, F, W, I, N, UP rules) |
| **Pylint** | `pylint alphaedge/` | Deep analysis (target ≥ 8.5/10) |
| **Mypy** | `mypy alphaedge/` | Static type checking (strict mode) |
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

Each Cython module has 3 dedicated test files (15 total).

---

## Running Backtest

```powershell
python -m alphaedge.engine.backtest
```

**Outputs:**
- `ALPHAEDGE_backtest_results.csv` — Trade-by-trade results
- `ALPHAEDGE_equity_curve.png` — Equity curve plot
- Console summary with win rate, profit factor, max drawdown, Sharpe ratio

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
│   ├── settings.json           # Formatter, linter, test settings
│   ├── extensions.json         # Recommended extensions
│   └── launch.json             # Debug configurations
├── alphaedge/                  # Main package
│   ├── __init__.py
│   ├── core/                   # Cython modules (low-latency)
│   │   ├── __init__.py
│   │   ├── fcr_detector.pyx    # M5 FCR range detection
│   │   ├── gap_detector.pyx    # ATR spike detection
│   │   ├── engulfing_detector.pyx  # M1 engulfing patterns
│   │   ├── order_manager.pyx   # Bracket order creation
│   │   └── risk_manager.pyx    # Position sizing + risk limits
│   ├── engine/                 # Python orchestration
│   │   ├── __init__.py
│   │   ├── broker.py           # IB Gateway connection + execution
│   │   ├── data_feed.py        # Historical + real-time data
│   │   ├── strategy.py         # Main FCR strategy loop
│   │   ├── backtest.py         # Historical backtest engine
│   │   └── dashboard.py        # Rich terminal dashboard
│   ├── config/                 # Configuration
│   │   ├── __init__.py
│   │   ├── constants.py        # Project-wide constants
│   │   └── loader.py           # YAML + env config loader
│   ├── utils/                  # Utilities
│   │   ├── __init__.py
│   │   ├── timezone.py         # DST-aware timezone handling
│   │   └── logger.py           # Loguru dual-time logging
│   ├── logs/                   # Runtime log files
│   │   └── __init__.py
│   └── tests/                  # Pytest tests (15 files)
│       ├── __init__.py
│       ├── conftest.py         # Shared fixtures
│       ├── test_fcr_detector_*.py
│       ├── test_gap_detector_*.py
│       ├── test_engulfing_detector_*.py
│       ├── test_order_manager_*.py
│       └── test_risk_manager_*.py
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
