# ⚡ ALPHAEDGE — AI Agent Entry Point

> **Read this file first.** It contains everything an AI agent needs to work
> safely and correctly on this codebase. Do NOT skip it.
> **Review `tasks/lessons.md` at the start of EVERY session — no exceptions.**

---

## Session Startup Checklist

Before touching any file, execute in this exact order:

1. Read `tasks/lessons.md` — internalize past mistakes before writing a single line
2. Read `docs/ALPHAEDGE_STRUCTURAL_ACTION_PLAN.md` — know what is open and in progress
3. Run `make qa` — confirm the baseline is green before any change
4. Check `.env.example` — confirm `ALPHAEDGE_PAPER=true` is intact
5. Identify the minimal set of files impacted by the task — touch nothing else

---

## ⛔ Hard Stops — Never Do These

Violating any of these is grounds for immediate task abort and re-plan.

- **Never** set `ALPHAEDGE_PAPER=false` in any file, ever
- **Never** modify `core/*.pyx` without an explicit instruction from the user
- **Never** commit `.env`, `*.log`, or any proprietary action plan files
- **Never** run `make build` unless a `.pyx` file was intentionally modified
- **Never** use `# type: ignore` or `# pyright: ignore` as a fix — find and fix the root cause
- **Never** use `Any` as a type annotation shortcut — it is a rustine, not a solution
- **Never** hardcode pip values, RR ratios, session times, or risk parameters outside `alphaedge/config/constants.py`
- **Never** touch `alphaedge/utils/timezone.py` or `session_manager.py` without re-running DST edge case tests
- **Never** mark a task complete without running `make qa` and confirming all 504 tests pass
- **Never** push a `.pyx` edit without running `make build` followed by `make qa`

---

## Workflow Orchestration

### 1. Plan Mode Default

- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately — don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

### 2. Subagent Strategy

- Use the `Explore` subagent to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One task per subagent for focused execution

### 3. Self-Improvement Loop

- After ANY correction from the user: update `tasks/lessons.md` with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- **Review `tasks/lessons.md` at the start of every session — non-negotiable**

### 4. Verification Before Done

- Never mark a task complete without proving it works
- Run `make qa` — all 504 tests must pass
- Ask yourself: "Would a staff engineer approve this?"
- Check logs, demonstrate correctness

### 5. Demand Elegance (Balanced)

- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this for simple, obvious fixes — don't over-engineer
- Challenge your own work before presenting it

### 6. Autonomous Bug Fixing

- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests — then resolve them
- Zero context switching required from the user
- Go fix failing `make qa` tests without being told how

---

## Task Management

1. **Plan First**: Use the Copilot todo list tool with checkable items
2. **Verify Plan**: Check in before starting implementation
3. **Track Progress**: Mark items complete as you go
4. **Explain Changes**: High-level summary at each step
5. **Capture Lessons**: Update `tasks/lessons.md` after any correction

---

## Core Principles

- **Simplicity First**: Make every change as simple as possible. Impact minimal code.
- **No Laziness**: Find root causes. No temporary fixes. Senior developer standards.
- **Minimal Impact**: Changes should only touch what's necessary. Avoid introducing bugs.
- **Audit Before Modify**: For any non-trivial change, read before writing. Cite file + line before proposing a modification.

---

## Project Identity

| Field | Value |
|-------|-------|
| Name | ALPHAEDGE — FCR Forex Trading Bot |
| Python | **3.11.9 strictly** — never use 3.12+ syntax |
| Stack | Python / Cython 3.0 / ib_insync / loguru / Rich / vectorbt |
| Broker | Interactive Brokers via IB Gateway |
| Market | Forex — EUR/USD, GBP/USD, USD/JPY (configurable) |
| Session | NYSE open 9:30–10:30 EST (15:30–16:30 CET / 14:30–15:30 CEST) |
| Mode | Paper trading default (`ALPHAEDGE_PAPER=true`) |
| Developer TZ | Europe/Paris — DST-aware via `zoneinfo` exclusively |

---

## Architecture — Signal Pipeline

```
IB Gateway
  └─► data_feed.py           [Python]  — M5 + M1 bar feed (reqHistoricalData)
        └─► fcr_detector.pyx  [Cython]  — FCR range detection (M5)
        └─► gap_detector.pyx  [Cython]  — ATR spike / volatility filter (M1)
        └─► engulfing_detector.pyx [Cython] — Entry signal (M1 engulfing)
              └─► risk_manager.pyx  [Cython]  — Position sizing, daily loss limit
              └─► order_manager.pyx [Cython]  — Bracket order construction
                    └─► broker.py    [Python]  — IB Gateway order submission
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

## Cython Edit Workflow (Mandatory)

Any modification to a `.pyx` file requires this exact sequence — no shortcuts:

```powershell
# Step 1 — Edit the .pyx source file

# Step 2 — Recompile Cython extensions
make build

# Step 3 — Validate no regression
make qa

# Step 4 — Only then proceed to commit
```

> ⚠️ The `.pyd` / `.so` compiled files in `core/` are the **runtime modules**.
> The `.pyx` sources alone do nothing at runtime.
> A `.pyx` edit without `make build` is silently broken.

---

## Absolute Rules — Never Violate These

1. **`ALPHAEDGE_PAPER=true` is the default.** Never change `.env.example` to
   `false`. Never suggest live trading without explicit user confirmation.
   Live trading on IBKR means real capital at risk.

2. **After editing any `.pyx` file, `make build` MUST be run** to recompile
   Cython extensions. The `.pyd`/`.so` files in `core/` are the runtime
   modules — the `.pyx` sources alone do nothing at runtime.

3. **Do not modify `alphaedge/core/` logic** without explicit instruction.
   The FCR strategy is proprietary. Treat `core/*.pyx` as read-only unless
   explicitly asked to change them.

4. **`make qa` must pass before any commit:**

```powershell
make qa   # Ruff lint + Mypy type check + Pytest (>=80% coverage)
```

5. **Python 3.11.9 only.** No walrus operator misuse, no `match` statements
   if they break 3.11 compat, no `tomllib` without backport.

6. **`engine/` tests require IB Gateway** — they are excluded from coverage.
   The >=80% threshold applies to `config/`, `utils/`, and `core/` (stubs).

7. **All magic numbers live in `constants.py` exclusively.** RR ratio,
   pip values, session times, risk thresholds — never hardcoded elsewhere.

8. **No rustines.** `# type: ignore`, `# pyright: ignore`, and `Any` type
   annotations are forbidden. Fix the root cause, create a stub if needed.

---

## Return Value Contracts

> These are the behavioral contracts for Cython core interfaces.
> An agent MUST respect these before acting on any return value.

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

## Timezone — Critical Note

> This is a live operational risk. One wrong assumption here costs money.

- All session logic lives in `alphaedge/utils/timezone.py`
- All timestamps stored internally in **UTC**
- Dashboard displays **two columns**: UTC and Europe/Paris local time
- NYSE open = 9:30 EST = **15:30 CET (winter) / 14:30 CEST (summer)**
- `zoneinfo` is used **exclusively** — never `pytz`, never hardcoded UTC offsets
- EU and US DST switch on **different dates** — there is a ~1-week gap each year
  where the Paris to NYSE offset shifts by 1 hour
- **Never touch `timezone.py` or `session_manager.py`** without re-running
  the DST edge case tests covering: standard CET, standard CEST,
  EU-switch week, US-switch week

---

## Key Files to Read Before Editing

| Purpose | File |
|---------|------|
| All trading thresholds | `alphaedge/config/constants.py` |
| Runtime configuration | `config.yaml` |
| Environment variables | `.env.example` |
| Cython build | `setup.py` |
| QA pipeline | `Makefile` + `pyproject.toml` |
| Full technical audit | `docs/ALPHAEDGE_MASTER_AUDIT.md` |
| Open tasks / roadmap | `docs/ALPHAEDGE_STRUCTURAL_ACTION_PLAN.md` |
| AI lessons learned | `tasks/lessons.md` |

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

> Implementation is [PROPRIETARY]. These are call signatures only.
> Do not infer, reverse-engineer, or reconstruct strategy logic from these.

```python
# fcr_detector
detect_fcr(
    candles_data: list[dict],
    min_range_pips: float,
    pip_size: float
) -> dict | None
# Returns: {detected, range_high, range_low, range_size, candle_timestamp} | None

detect_fcr_scan(
    candles_data: list[dict],
    min_range_pips: float,
    pip_size: float,
    lookback: int
) -> dict | None

# gap_detector
detect_gap(
    pre_session_m1, session_m1,
    pre_close, session_open,
    atr_period, min_atr_ratio
) -> dict
# Returns: {detected, gap_high, gap_low, gap_size, atr_ratio, direction}

is_in_gap_zone(
    price: float,
    gap_high: float,
    gap_low: float
) -> bool

# engulfing_detector
detect_engulfing(
    candles_data,
    fcr_high, fcr_low,
    rr_ratio, pip_size,
    volume_period, min_volume_ratio
) -> dict | None
# Returns: {direction, entry, stop_loss, take_profit, rr_ratio} | None

# risk_manager
calculate_position_size(
    account_equity, risk_pct,
    sl_pips, pair, pip_size,
    lot_type, min_lots, max_lots
) -> dict
# Returns: {lot_size, risk_amount, pip_value, sl_pips, is_valid}

check_daily_limit(
    starting_equity, current_equity,
    max_daily_loss_pct,
    trades_today, max_trades
) -> dict
# Returns: {halt_trading, daily_pnl_pct, trades_remaining, reason}

# order_manager
create_bracket_order(
    direction, entry_price,
    stop_loss, take_profit,
    lot_size, pip_size,
    spread_pips, ...
) -> dict
# Returns: {is_valid, rejection_reason?, direction, entry, sl, tp, lot_size, rr_ratio}
```

---

## Gitignored / Proprietary Files

The following files exist locally but are **intentionally not committed**.
Do not regenerate, reconstruct, or re-commit them under any circumstances.

| File | Reason |
|------|--------|
| `ALPHAEDGE_ACTION_PLAN.md` | Proprietary strategy implementation details |
| `.env` | IB credentials — use `.env.example` as template only |
| `alphaedge/logs/*.log` | Runtime logs — never committed |

---

## Current Project Health

Live status is tracked in dedicated files — do not rely on static scores here.

| Document | Purpose |
|----------|---------|
| `docs/ALPHAEDGE_STRUCTURAL_ACTION_PLAN.md` | Open tasks, priorities, blockers |
| `docs/ALPHAEDGE_MASTER_AUDIT.md` | Last full technical audit |
| `tasks/lessons.md` | AI agent lessons learned (read every session) |

> Last known `make qa` baseline: **504 tests — 100% pass rate**
> Coverage threshold: **>=80%** on `config/`, `utils/`, `core/` (stubs)
