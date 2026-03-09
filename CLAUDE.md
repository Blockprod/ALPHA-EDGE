# ⚡ ALPHAEDGE — AI Agent Entry Point

> **Read this file first.** It contains everything an AI agent needs to work
> safely and correctly on this codebase. Do NOT skip it.

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
  └─► data_feed.py          [Python]  — M5 bar feed (reqHistoricalData)
        └─► fcr_detector.pyx [Cython]  — FCR range detection
        └─► gap_detector.pyx [Cython]  — ATR spike / volatility filter
        └─► engulfing_detector.pyx [Cython] — Entry signal (M1 engulfing)
              └─► risk_manager.pyx [Cython]  — Position sizing, daily loss limit
              └─► order_manager.pyx [Cython] — Bracket order construction
                    └─► broker.py    [Python] — IB Gateway order submission
```

**Dependency flow is strictly top-down:**
`engine/` → `core/` → `config/` → `utils/`
No circular imports (pylint verified).

---

## Module Responsibilities

| Module | Language | Role |
|--------|----------|------|
| `alphaedge/core/*.pyx` | Cython | Low-latency signal detection + execution logic |
| `alphaedge/engine/strategy.py` | Python | Main async loop, orchestration |
| `alphaedge/engine/broker.py` | Python | IB Gateway connectivity (ib_insync) |
| `alphaedge/engine/data_feed.py` | Python | Real-time bar subscription |
| `alphaedge/engine/backtest.py` | Python | Historical simulation engine |
| `alphaedge/engine/dashboard.py` | Python | Rich terminal UI |
| `alphaedge/config/constants.py` | Python | All magic numbers / thresholds |
| `alphaedge/config/loader.py` | Python | YAML config → typed AppConfig |
| `alphaedge/utils/logger.py` | Python | Loguru setup (UTC + Paris dual-time) |
| `alphaedge/utils/timezone.py` | Python | DST-aware session time helpers |
| `alphaedge/utils/session_manager.py` | Python | NYSE/London session windows |

---

## Absolute Rules — Never Violate These

1. **`ALPHAEDGE_PAPER=true` is the default.** Never change `.env.example` to
   `false`. Never suggest live trading without explicit user confirmation.

2. **After editing any `.pyx` file, `make build` MUST be run** to recompile
   Cython extensions. The `.pyd`/`.so` files in `core/` are the runtime
   modules — the `.pyx` sources alone do nothing at runtime.

3. **Do not modify `alphaedge/core/` logic** without explicit instruction.
   The FCR strategy is proprietary. Treat `core/*.pyx` as read-only unless
   explicitly asked to change them.

4. **`make qa` must pass before any commit:**
   ```powershell
   make qa   # Ruff lint + Mypy type check + Pytest (≥80% coverage)
   ```

5. **Python 3.11.9 only.** No walrus operator misuse, no `match` statements
   if they break 3.11 compat, no `tomllib` without backport.

6. **`engine/` tests require IB Gateway** — they are excluded from coverage.
   The ≥80% threshold applies to `config/`, `utils/`, and `core/` (stubs).

---

## Key Files to Read Before Editing

| Purpose | File |
|---------|------|
| All trading thresholds | `alphaedge/config/constants.py` |
| Runtime configuration | `config.yaml` |
| Environment variables | `.env.example` |
| Cython build | `setup.py` |
| QA pipeline | `Makefile` + `pyproject.toml` |
| Full technical audit | `ALPHAEDGE_MASTER_AUDIT.md` |
| Open tasks / roadmap | `ALPHAEDGE_STRUCTURAL_ACTION_PLAN.md` |

---

## QA Workflow

```powershell
# Activate environment (Windows)
.\.venv\Scripts\Activate.ps1

# Standard QA (lint + mypy + tests)
make qa

# With Pylint
make qa-strict

# Build Cython core after .pyx changes
make build

# Full rebuild + QA
make all

# Clean build artifacts
make clean
```

---

## Public Core Interfaces

> Implementation is [PROPRIETARY]. These are call signatures only — do not infer strategy logic.

```python
# fcr_detector
detect_fcr(candles_data: list[dict], min_range_pips: float, pip_size: float) -> dict | None
detect_fcr_scan(candles_data: list[dict], min_range_pips: float, pip_size: float, lookback: int) -> dict | None
# → {detected, range_high, range_low, range_size, candle_timestamp}

# gap_detector
detect_gap(pre_session_m1, session_m1, pre_close, session_open, atr_period, min_atr_ratio) -> dict
is_in_gap_zone(price: float, gap_high: float, gap_low: float) -> bool
# → {detected, gap_high, gap_low, gap_size, atr_ratio, direction}

# engulfing_detector
detect_engulfing(candles_data, fcr_high, fcr_low, rr_ratio, pip_size, volume_period, min_volume_ratio) -> dict | None
# → {direction, entry, stop_loss, take_profit, rr_ratio} | None

# risk_manager
calculate_position_size(account_equity, risk_pct, sl_pips, pair, pip_size, lot_type, min_lots, max_lots) -> dict
check_daily_limit(starting_equity, current_equity, max_daily_loss_pct, trades_today, max_trades) -> dict
# → {lot_size, risk_amount, pip_value, sl_pips, is_valid}

# order_manager
create_bracket_order(direction, entry_price, stop_loss, take_profit, lot_size, pip_size, spread_pips, ...) -> dict
# → {is_valid, rejection_reason?, direction, entry, sl, tp, lot_size, rr_ratio}
```

---

## Gitignored / Proprietary Files

The following files exist locally but are **intentionally not committed**:

- `ALPHAEDGE_ACTION_PLAN.md` — proprietary strategy implementation details
- `.env` — IB credentials (use `.env.example` as template)
- `alphaedge/logs/*.log` — runtime logs

Do **not** regenerate or re-commit these files.

---

## Current Audit State (2026-03-09)

| Dimension | Score | Status |
|-----------|-------|--------|
| Root hygiene | 4→8/10 | 🟡 In progress |
| AI-readiness | 3→8/10 | 🟢 This file created |
| VSCode workspace | 7→9/10 | 🟢 Fixed |
| QA pipeline | 5→8/10 | 🟡 In progress |
| Documentation | 5→8/10 | 🟡 In progress |
| Security | 7→9/10 | 🟢 Verified clean |

Open tasks tracked in: `ALPHAEDGE_STRUCTURAL_ACTION_PLAN.md`
