# ⚡ ALPHAEDGE — MASTER AUDIT

> **Date**: 2026-03-07
> **Reviewer**: Senior Quant Developer / Risk Architect
> **Scope**: Full System + Strategic & Statistical Audit
> **Target**: Live Forex deployment via IBKR IB Gateway
> **Repository**: ALPHAEDGE — FCR Forex Trading Bot

---

## TABLE OF CONTENTS

| Part | Section | Title |
|------|---------|-------|
| I | 1 | Architectural Integrity |
| I | 2 | Code Quality & Engineering Standards |
| I | 3 | Risk & Portfolio Architecture |
| I | 4 | Backtesting Infrastructure |
| I | 5 | Monitoring & Alerting |
| II | 6 | Nature of the Strategy |
| II | 7 | Statistical Validity |
| II | 8 | Signal Construction & Entry Logic |
| II | 9 | Entry / Exit Logic |
| II | 10 | Real-World Stress Scenarios |
| II | 11 | Strategy–Risk Engine Interaction |
| III | 12 | Critical Issues (Ranked) |
| III | 13 | Priority Action Plan |
| III | 14 | Scoring & Final Verdict |

---

# PART I — SYSTEM & ARCHITECTURE AUDIT

---

## 1. Architectural Integrity

### 1.1 Modularity & Separation of Concerns

| Layer | Role | Modules | Assessment |
|-------|------|---------|------------|
| **Cython Core** | Low-latency signal engine | `fcr_detector.pyx`, `gap_detector.pyx`, `engulfing_detector.pyx`, `order_manager.pyx`, `risk_manager.pyx` | ✅ Clean separation — all 5 modules are self-contained with no inter-module imports |
| **Python Engine** | Orchestration & I/O | `strategy.py`, `broker.py`, `data_feed.py`, `backtest.py`, `dashboard.py` | ✅ Clear responsibility boundaries |
| **Config** | Constants & YAML loading | `constants.py`, `loader.py` | ✅ Centralized, validated |
| **Utils** | Cross-cutting concerns | `logger.py`, `timezone.py` | ✅ Minimal, focused |

**Architecture Pattern**: The project follows a **signal pipeline architecture**:

```
IB Gateway → data_feed.py → [M5 bars] → fcr_detector.pyx → FCR range
                           → [M1 bars] → gap_detector.pyx → ATR spike
                                        → engulfing_detector.pyx → Signal
                                        → risk_manager.pyx → Position sizing
                                        → order_manager.pyx → Bracket order
                                        → broker.py → IB Gateway
```

**Strengths**:
- Clean Cython ↔ Python boundary: Cython modules expose pure `def` functions returning Python `dict`, no leaked C types
- No circular imports — dependency graph is strictly top-down
- Each Cython module uses `cdef struct` for internal computation and serializes to `dict` at the boundary
- Strategy orchestrator (`FCRStrategy`) cleanly coordinates all modules through a single entry point

**Weaknesses Identified**:

- 🟠 **Tight coupling in `strategy.py`**: The `FCRStrategy` class directly instantiates `BrokerConnection`, `OrderExecutor`, `HistoricalDataFeed`, and `RealtimeDataFeed` — no dependency injection. This makes unit testing the strategy orchestrator impossible without IB Gateway
- 🟡 **Module index access**: `self._modules[0]`, `self._modules[1]`, etc. in `strategy.py` is fragile — a tuple rename or reorder silently breaks all signal flow
- 🟡 **Missing interface contracts**: No ABC or Protocol classes defining what detectors/risk modules must implement — extensibility relies on convention only
- 🟡 **No pure-Python fallback stubs**: Tests for Cython modules fail entirely if not compiled (15/19 test files fail on import). The `_import_core_modules()` function raises `ImportError` instead of providing test-safe stubs

### 1.2 Data Flow Clarity

| Step | Data | Source → Destination | Status |
|------|------|---------------------|--------|
| 1 | M5 OHLCV | `data_feed.fetch_m5_pre_session()` → `fcr_detector.detect_fcr()` | ✅ Correct |
| 2 | FCR range | `fcr_detector` → `engulfing_detector` (via `state.fcr_result`) | ✅ Correct |
| 3 | M1 OHLCV | `RealtimeDataFeed._on_bar_update()` → `_on_new_m1_bar()` → `_detect_engulfing()` | ⚠️ 5s bars aggregated as M1 — see Section 8 |
| 4 | Gap detection | `gap_detector.detect_gap()` | ⚠️ Called in `_detect_gap()` but **never invoked** in the live flow — see below |
| 5 | Risk check | `risk_manager.check_daily_limit()` → equity via IB | ✅ Correct |
| 6 | Order | `order_manager.create_bracket_order()` → `broker.place_bracket_order()` | ✅ Correct |

**Critical Finding**: 🔴 **Gap detection is wired but NOT called in the live session flow**. The `_detect_gap()` method exists in `FCRStrategy` but is never invoked in `run_session()` or `_on_new_m1_bar()`. The strategy trades engulfing signals without requiring an ATR spike confirmation, contradicting the stated FCR+Gap+Engulfing pipeline.

### 1.3 Scalability

- **Multi-pair handling**: ✅ The system iterates `config.trading.pairs` (default: `EURUSD`, `GBPUSD`, `USDJPY`) with per-pair `StrategyState` instances
- **Per-pair risk cap**: ✅ `check_pair_limit(max_open_pairs=1)` enforced in `_on_new_m1_bar()`
- **Extensibility**: 🟡 Adding new pairs requires only updating `config.yaml` and `PIP_SIZES` dict — acceptable
- **Multi-strategy**: 🟡 Not supported — single strategy class with no pluggability

### 1.4 CI/CD Readiness

| Makefile Target | Command | Status |
|-----------------|---------|--------|
| `make format` | `black alphaedge/` | ✅ Works — 35 files unchanged |
| `make lint` | `ruff check` + `pylint` | ✅ Ruff: all checks passed. Pylint: 9.32/10 |
| `make typecheck` | `mypy --strict` | ❌ 13 errors (see Section 2) |
| `make test` | `pytest --cov --cov-fail-under=80` | ❌ 15/19 test files fail to import without Cython compilation |
| `make build` | `setup.py build_ext --inplace` | ⚠️ Requires C compiler + Python 3.11.9 exactly |
| `make qa` | format → lint → typecheck → test | ❌ Pipeline fails |
| `make all` | qa → build | ❌ Pipeline fails |

**Critical Finding**: 🔴 **CI/CD pipeline (`make qa`) is broken**. It cannot pass on any system without a C compiler + Python 3.11.9 + Cython pre-compilation. No GitHub Actions / CI config file exists.

### 1.5 Production Readiness vs Paper Trading

- ✅ **Paper trading enforced by default**: `config.yaml` defaults to port 4002 (paper), `is_paper: True`
- ✅ **Live mode requires explicit confirmation**: `strategy.py` CLI requires typing "YES" for live mode
- ✅ **Port override**: Paper mode forces port 4002 in CLI handler
- 🟡 **No account ID validation**: The system accepts any account ID without verifying it matches the IB Gateway session

---

## 2. Code Quality & Engineering Standards

### 2.1 File Engineering Compliance

| Check | Result |
|-------|--------|
| Header blocks in every `.py` file | ✅ All 16 Python files + 5 `.pyx` files have standardized headers |
| Header blocks in config files | ✅ `pyproject.toml`, `mypy.ini`, `.pylintrc`, `Makefile`, `setup.py`, `config.yaml`, `requirements.txt` |
| Consistent header format | ✅ PROJECT / FILE / DESCRIPTION / AUTHOR / WORKFLOW / PYTHON / LAST UPDATED |

### 2.2 Python Version Compliance

| Check | Result |
|-------|--------|
| Target version | 3.11.9 strict |
| `setup.py` enforcement | ✅ `sys.version_info[:2] != (3, 11)` → exit |
| `pyproject.toml` | ✅ `requires-python = ">=3.11,<3.12"` |
| 3.12+ features used | ❌ **`datetime | None` union syntax used in type hints** — this is 3.10+ syntax, acceptable due to `from __future__ import annotations` |
| Actual dev environment | ⚠️ **Python 3.13.1 detected** on developer machine — violates project's own strict 3.11.9 requirement |

### 2.3 Formatting & Linting Results

| Tool | Configuration | Result |
|------|--------------|--------|
| **Black** | line-length 88, target py311 | ✅ **0 violations** — 35 files unchanged |
| **Ruff** | E, F, W, I, N, UP rules | ✅ **0 warnings** — all checks passed |
| **Mypy** | strict mode | ❌ **13 errors** in 4 files (`broker.py`, `data_feed.py`, `backtest.py`, `logger.py`) |
| **Pylint** | fail-under 8.5 | ✅ **9.32/10** — passes threshold |

### 2.4 Mypy Errors (13 total)

| File | Error | Type |
|------|-------|------|
| `logger.py:83,92` | Unused `type: ignore` comments | `unused-ignore` |
| `broker.py:87,135,269` | Unused `type: ignore` comments | `unused-ignore` |
| `broker.py:94` | Returning `Any` from `bool` function | `no-any-return` |
| `broker.py:286` | Returning `Any` from `list[Any]` function | `no-any-return` |
| `data_feed.py:47,48,49` | Unused `type: ignore` comments | `unused-ignore` |
| `data_feed.py:314,344` | Returning `Any` from `float` function | `no-any-return` |
| `backtest.py:589` | Unused `type: ignore` comment | `unused-ignore` |

**Root cause**: `type: ignore` comments were written for Python 3.11.9 type stubs but are stale under 3.13. The `no-any-return` errors arise from `ib_insync` returning untyped objects.

### 2.5 Test Coverage

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Total test files | — | 21 | — |
| Test files requiring Cython | — | 15 | ❌ All fail without compilation |
| Test files runnable (pure Python) | — | 4 | ✅ All 19 tests pass |
| Coverage (testable modules: config/, utils/) | ≥ 80% | ~92% (config + utils) | ✅ Meets target for covered scope |
| Coverage (engine/) | — | 0% | ❌ Excluded from coverage via `pyproject.toml` |
| Coverage (core/) | — | 0% | ❌ Cython modules untestable without compilation |

**Critical Finding**: 🟠 **Effective test coverage is ~20% of total codebase**. The `[tool.coverage.run] omit = ["alphaedge/engine/*"]` directive excludes the entire engine layer from coverage measurement, masking the true gap.

### 2.6 Function Length Compliance

All functions reviewed are under 50 lines. The longest functions:
- `run_session()` in `strategy.py`: ~45 lines — borderline but compliant
- `_backtest_pair()` in `backtest.py`: ~25 lines — compliant

### 2.7 Additional Quality Checks

| Check | Result |
|-------|--------|
| `if __name__ == "__main__"` blocks | ✅ Present in all applicable modules (13 files) |
| Circular imports | ✅ None detected — top-down dependency graph |
| Docstrings on all functions | ✅ All public and private functions documented |
| Type hints on all functions | ✅ Full annotation coverage on Python layer |
| Inline comments | ✅ Section separators and rationale comments throughout |

---

## 3. Risk & Portfolio Architecture

### 3.1 Risk Module Separation

| Component | Location | Independence |
|-----------|----------|-------------|
| Position sizing | `risk_manager.pyx` → `calculate_position_size()` | ✅ Independent of strategy |
| Daily loss limit | `risk_manager.pyx` → `check_daily_limit()` | ✅ Independent of strategy |
| Per-pair cap | `risk_manager.pyx` → `check_pair_limit()` | ✅ Independent of strategy |
| Slippage buffer | `risk_manager.pyx` → `apply_slippage_buffer()` | ✅ Independent of strategy |
| Spread filter | `order_manager.pyx` → `_validate_spread()` | ✅ At order level |
| Bracket order validation | `order_manager.pyx` → `create_bracket_order()` | ✅ Multi-gate validation |

### 3.2 Kill-Switch Analysis

```
check_daily_limit():
    daily_pnl_pct = (current_equity - starting_equity) / starting_equity * 100
    if daily_pnl_pct <= -max_daily_loss_pct:
        limit_breached = True
    if trades_today >= max_trades:
        limit_breached = True
```

| Feature | Implementation | Assessment |
|---------|---------------|------------|
| Daily -3% loss trigger | ✅ `daily_pnl_pct <= -3.0` → `limit_breached` | Correctly implemented |
| Auto-shutdown on breach | ✅ `_check_daily_loss_shutdown()` → sets `_shutdown_requested = True` → `cancel_all_orders()` | Correctly implemented |
| Check frequency | Every 30 seconds in session loop | ⚠️ 30-second gap could allow additional losses during fast moves |
| Max 2 trades/session | ✅ `trades_today >= max_trades` → `limit_breached` | Correctly implemented |

**Weakness**: 🟠 The daily loss check polls equity every 30 seconds. In a flash crash, a position could breach well beyond -3% between checks. No event-driven loss monitoring exists.

### 3.3 Position Sizing

```
lot_size = risk_amount / (sl_pips * pip_value_per_lot)
risk_amount = account_equity * (risk_pct / 100.0)  # Default: 1%
```

| Feature | Implementation | Assessment |
|---------|---------------|------------|
| % risk calculation | ✅ `account_equity * (risk_pct / 100)` | Correct |
| Pip value for USD-quoted pairs | ✅ `lot_units * pip_size` | Correct ($0.10/pip for micro EUR/USD) |
| JPY pair pip value | ✅ `raw_pip_value / exchange_rate` when `pip_size >= 0.001` | ✅ Correctly converts via live rate |
| Lot bounds | ✅ `min_lots=0.01`, `max_lots=10.0` | Validated |
| Round-down | ✅ `floor(raw_lots * 100) / 100` | Conservative — correct |

### 3.4 JPY Pair Handling

| Feature | Implementation | Status |
|---------|---------------|--------|
| Pip size | `USDJPY: 0.01`, `EURJPY: 0.01`, `GBPJPY: 0.01` in `PIP_SIZES` | ✅ Correct |
| FCR range in pips | `(high - low) / 0.01` | ✅ Correct |
| Pip value conversion | Division by exchange rate when `pip_size >= 0.001` | ✅ Correct |
| Stop loss calculation | Uses same `fabs(entry - stop_loss) / pip_size` formula | ✅ Correct |

### 3.5 Spread Filter

| Feature | Implementation | Status |
|---------|---------------|--------|
| Default max spread | 2.0 pips | ✅ Configurable |
| Check location | `order_manager.create_bracket_order()` — first validation | ✅ Cheapest-first filter |
| Spread adjustment to SL | BUY: `SL - (spread * pip_size)`, SELL: `SL + (spread * pip_size)` | ✅ Correctly widens SL |
| Live spread fetch | `RealtimeDataFeed.get_live_spread()` called before order | ✅ At entry only |

**Weakness**: 🟠 **Spread is checked only at entry time**, not continuously. A spread spike after entry does not trigger any re-evaluation or position closure.

### 3.6 IB Gateway Disconnection Protection

| Feature | Implementation | Status |
|---------|---------------|--------|
| Auto-reconnect | ✅ `broker.reconnect(max_retries=3)` with exponential backoff | Present but **never called** |
| Connection check | ✅ `_ensure_connected()` raises `ConnectionError` | Present |
| Mid-trade disconnection | ❌ **No position recovery logic** | 🔴 CRITICAL |
| Open position detection on reconnect | ❌ Not implemented | 🔴 CRITICAL |

**Critical Finding**: 🔴 If IB Gateway disconnects while a bracket order is partially filled (entry filled, SL/TP pending), there is **no mechanism to detect and re-submit the protective orders**. The position would be unprotected.

---

## 4. Backtesting Infrastructure

### 4.1 Architecture Overview

| Component | Implementation | Status |
|-----------|---------------|--------|
| Data source | `ib_insync.reqHistoricalData()` | ✅ Real IB data |
| Bar simulation | Walk-forward through M1 bars | ✅ Bar-by-bar |
| Trade simulation | `_simulate_trade_exit()` — forward walk to SL/TP hit | ✅ Correct |
| SL/TP hit detection | Checks bar high/low against SL/TP | ✅ Standard approach |
| Same-bar resolution | `_sl_hit_first()` uses bar direction | ⚠️ Heuristic — see below |
| Spread cost | `DEFAULT_SLIPPAGE_PIPS = 0.5` deducted from P&L | ✅ Included |
| Output CSV | `ALPHAEDGE_backtest_results.csv` | ✅ Correct |
| Equity curve | `ALPHAEDGE_equity_curve.png` | ✅ Correct |
| Metrics | Winrate, profit factor, max drawdown, Sharpe | ✅ All computed |

### 4.2 vectorbt Integration

```python
def _validate_with_vectorbt(trades):
    pnl_series = pd.Series([t.pnl_pips for t in trades])
    vbt_sharpe = pnl_series.vbt.returns.sharpe_ratio()
```

**Finding**: 🟠 **Misuse of vectorbt**: The code calls `.vbt.returns.sharpe_ratio()` on raw pip P&L, not on return percentages. This produces a meaningless Sharpe ratio. vectorbt expects percentage returns, not absolute pip values. The "cross-validation" provides false comfort.

### 4.3 Bias Detection

| Bias Type | Status | Evidence |
|-----------|--------|----------|
| **Look-ahead bias** | 🔴 **PRESENT** | `_detect_signal_at_bar()` uses `m5_equivalent = bars[max(0, index - 10) : index - 2]` — this slices M1 bars as "M5 equivalent" by using raw bar indexes, not timestamp-based session alignment. The FCR range is computed from bars immediately before the evaluation bar, not from pre-9:30 ET bars. In live, FCR is computed once before session; in backtest, it's re-computed at every bar. |
| **Data leakage** | 🟠 **LIKELY** | The backtest uses a single `bars` array of M1 data. M5 candles are simulated by slicing `bars[i-10:i-2]`. There is no actual M5 aggregation or session-boundary enforcement. The M1→M5 mapping is structurally incorrect. |
| **Survivorship bias** | 🟡 **MINOR** | Three pairs hardcoded (EURUSD, GBPUSD, USDJPY) — these are the most liquid and thus least affected by survivorship. But the selection is not justified by systematic screening. |
| **Over-optimization** | 🟠 **RISK** | ATR spike threshold (`1.5x`), volume ratio (`1.2x`), min range (`5 pips`) are set as constants with no documented parameter sensitivity analysis. |
| **In-sample / out-of-sample split** | ❌ **NOT IMPLEMENTED** | All data is used as a single block. No train/test split. |
| **Walk-forward validation** | ❌ **NOT IMPLEMENTED** | No rolling window backtest. |

### 4.4 Slippage & Spread Modeling

| Feature | Implementation | Assessment |
|---------|---------------|------------|
| Fixed slippage | 0.5 pips per trade | 🟡 Too optimistic for live Forex, especially during NYSE open volatility |
| Spread cost | Deducted from P&L at exit | ✅ Correct |
| Variable spread | ❌ Not modeled | 🟠 Real spreads widen significantly at 9:30 ET |
| Market impact | ❌ Not modeled | 🟡 Not material for micro lots |

### 4.5 Output Completeness

| Metric | Present | Notes |
|--------|---------|-------|
| Total trades | ✅ | — |
| Wins / Losses | ✅ | — |
| Win rate % | ✅ | — |
| Profit factor | ✅ | — |
| Max drawdown % | ✅ | — |
| Sharpe ratio | ✅ | Annualized √252 — correct formula |
| ≥100 trades | ⚠️ | Not enforced — depends on data duration |
| CSV export | ✅ | — |
| PNG equity curve | ✅ | — |

---

## 5. Monitoring & Alerting

### 5.1 Logging

| Feature | Implementation | Status |
|---------|---------------|--------|
| Logger framework | loguru (via `utils/logger.py`) | ✅ |
| Dual timestamp | `UTC | Europe/Paris` on every log line | ✅ Correct |
| Format | `[ALPHAEDGE] UTC_time | Paris_time | LEVEL | location | message` | ✅ Clear |
| Log rotation | `alphaedge_{YYYY-MM-DD}.log` daily rotation | ✅ Correct |
| Log retention | 30 days | ✅ Configured |
| Strategy signals logged | ✅ FCR detection, engulfing signals | Present |
| Risk events logged | ✅ "Daily loss limit breached" | Present |
| Order execution logged | ✅ Bracket order details | Present |
| IB Gateway status | ✅ Connect/disconnect events | Present |

**Verified from actual log output**:
```
[ALPHAEDGE] 2026-03-07 17:49:20 UTC | 2026-03-07 18:49:20 CET | INFO | ...
```

### 5.2 Rich Dashboard

| Panel | Content | Status |
|-------|---------|--------|
| Header | Project title + IB connection status (green/red dot) | ✅ |
| Time | UTC + Europe/Paris + session active/inactive | ✅ |
| Signals | Per-pair: FCR range, gap status, signal direction, spread | ✅ |
| Position & P&L | Open position, direction, P&L pips/USD, trades today, daily P&L | ✅ |
| Trade eligibility | "Blocked — daily limit" / "Max trades reached" / "Eligible (N left)" | ✅ |
| Footer | Ctrl+C instruction + version | ✅ |

### 5.3 DST Auto-Detection

| Feature | Implementation | Status |
|---------|---------------|--------|
| Session window | Uses `zoneinfo.ZoneInfo("America/New_York")` | ✅ Auto-DST via IANA database |
| EU/US DST gap week | zoneinfo handles both independently | ✅ Correct — tested with spring-forward and fall-back fixtures |
| Weekend guard | `weekday() >= 5` → skip | ✅ Correct |

### 5.4 Missing Alerts

| Alert | Status |
|-------|--------|
| Daily loss limit breach | ✅ Logged + shutdown triggered |
| IB disconnection | ✅ Logged at connection layer |
| Spread filter trigger | 🟡 Logged as "Order rejected — spread_too_wide" but no distinct alert |
| Session end | ✅ Logged |
| **Position still open at session end** | ❌ **NOT IMPLEMENTED** — see Section 9 |
| **Partial fill / orphaned order** | ❌ **NOT IMPLEMENTED** |
| **Consecutive losses alert** | ❌ Not implemented |

---

# PART II — STRATEGIC & STATISTICAL AUDIT (FCR FOREX STRATEGY)

---

## 6. Nature of the Strategy

### 6.1 Exact Behavior (Inferred from Code)

1. **Pre-session** (before 9:30 ET): Fetch M5 candles (30 min lookback). Identify the last M5 candle as the FCR (Failed Candle Range) — take its high/low as the range boundaries
2. **Session open** (9:30–10:30 ET): Subscribe to real-time 5-second bars on M1 timeframe
3. **Signal trigger**: On each new bar, check if the last two M1 candles form an engulfing pattern where:
   - Bearish engulfing: current close ≤ FCR low → SHORT
   - Bullish engulfing: current close ≥ FCR high → LONG
4. **Volume confirmation**: Current candle tick volume ≥ 1.2× average of last 20 candles
5. **Entry**: At engulfing candle close price
6. **Stop loss**: At engulfing candle wick (high for bearish, low for bullish)
7. **Take profit**: 3× risk distance from entry
8. **Position management**: Bracket order (entry + SL + TP) sent to IB Gateway

### 6.2 Economic Rationale

**Thesis**: At NYSE open (9:30 ET), equity order flow creates cross-market volatility expansion in Forex. The FCR range (pre-session M5 high/low) acts as a liquidity zone. When price breaks through this zone with a confirmed engulfing pattern and above-average tick volume, it signals a directional momentum burst.

**Classification**: This is a **breakout-of-range + momentum confirmation** strategy. More specifically:
- **Primary**: Volatility expansion breakout (FCR range breach)
- **Secondary**: Candle pattern confirmation (engulfing)
- **Tertiary**: Volume confirmation (tick count proxy)

### 6.3 Structural Coherence

| Element | Coherence Assessment |
|---------|---------------------|
| M5 FCR range as reference level | 🟡 Using a single M5 candle's high/low is thin. Institutional support/resistance typically requires multiple touches. A single 5-minute range captures noise more than structure. |
| M1 engulfing as trigger | ✅ Appropriate — M1 provides the resolution needed for the 15:30–16:30 UTC window |
| ATR spike as "gap equivalent" | ⚠️ Conceptually valid for Forex (continuous market, no gaps). Implementation exists but **is not connected** to the live trading flow |
| Tick volume as Forex volume proxy | 🟡 Tick count is a weak volume proxy. It measures broker-specific activity, not actual interbank flow. Validity varies by broker and data source. |

### 6.4 Validity of ATR Spike on 24h Forex

Forex does not gap (except over weekends). Using ATR ratio (session / pre-session) as a "gap equivalent" is a reasonable adaptation. The 1.5x threshold means the opening bars must have 50% wider ranges than the pre-session baseline. This does capture the NYSE volatility injection. However, the threshold is not empirically validated in this codebase.

---

## 7. Statistical Validity

### 7.1 FCR Range Detection Correctness

```python
# Uses the LAST M5 candle before session as FCR candidate
cdef dict last_candle_data = candles_data[len(candles_data) - 1]
```

**Assessment**: 🟠 The FCR is defined as the high/low of a **single M5 candle** (the last one before 9:30 ET). This is an extremely narrow range definition:
- For EUR/USD, a typical M5 candle range pre-session is 5–15 pips
- A 5-pip range (minimum threshold) gives a 5-pip SL — after spread/slippage, this leaves very tight margins
- There is no multi-candle consolidation zone identification (no support/resistance confirmation)

### 7.2 ATR Spike Threshold Justification

```python
DEFAULT_MIN_ATR_RATIO: float = 1.5
```

**Assessment**: 🔴 **No statistical justification exists** in the codebase for the 1.5x threshold. This is an arbitrary constant. No sensitivity analysis, no distribution analysis of ATR ratios at NYSE open, no regime-dependent adjustment. A 1.5x threshold may:
- Be too loose in high-volatility regimes (NFP weeks) → excessive false positives
- Be too tight in low-volatility regimes → no signals for weeks

### 7.3 Engulfing Pattern Statistical Edge

| Factor | Assessment |
|--------|------------|
| Engulfing pattern base rate | Engulfing patterns occur frequently on M1 — low signal-to-noise ratio without additional filters |
| FCR boundary filter | Adds meaningful constraint (close must breach range) — reduces false positives |
| Tick volume confirmation | 🟡 1.2× average is a weak threshold. Tick count distributions are heavily skewed; the mean is not a robust baseline. Median or percentile would be more appropriate |
| Combined edge | Unknown — **no backtest results presented** to validate the combined filter's predictive power |

### 7.4 Session Filter Validity

Does the NYSE open produce exploitable volatility on Forex?

**Evidence from market microstructure**: Yes — the 9:30 ET window shows statistically significant volatility expansion in EUR/USD, GBP/USD, and USD/JPY due to equity-hedging order flow. This is well-documented in academic literature. The 1-hour window (9:30–10:30 ET) is reasonable.

**Risk**: The exploitable edge has been diminishing as HFT firms arbitrage the pattern. Furthermore, on days with pre-market economic releases (8:30 ET NFP, CPI), the volatility expansion occurs before the session window opens — the strategy would miss or miscount these moves.

### 7.5 RR 3:1 Viability

| Metric | Value |
|--------|-------|
| Required win rate at 3:1 RR for breakeven | 25% |
| Required win rate for profitability after costs | ~30% (accounting for spread + slippage) |
| Typical M1 engulfing breakout win rate on Forex | 25–40% (depending on filter quality) |

**Assessment**: 🟡 The 3:1 RR ratio is aggressive but not unrealistic. The key question is whether the combined FCR+engulfing+volume filter produces a win rate above 30%. **This has not been validated due to the absence of backtest results.**

### 7.6 Missing Statistical Validations

- 🔴 No parameter sensitivity analysis (ATR threshold, volume ratio, min range pips, RR ratio)
- 🔴 No regime analysis (VIX-adjusted performance, news-day performance)
- 🔴 No distribution analysis of trade outcomes (fat tails, skewness)
- 🟠 No Monte Carlo simulation for drawdown estimation
- 🟠 No p-value or confidence interval on win rate
- 🟠 No comparison against a random-entry baseline with same RR/SL

---

## 8. Signal Construction & Entry Logic

### 8.1 FCR High/Low Calculation

```python
result.range_high = candle.high
result.range_low = candle.low
```

✅ Correct — simple extraction from the M5 OHLC bar.

🟠 **Concern**: The `detect_fcr_scan()` function selects the candle with the "widest range" from the lookback window. This biases toward volatile pre-session candles, which may not represent meaningful support/resistance levels.

### 8.2 Gap/ATR Spike Detection

```python
baseline_atr = avg(high - low) for pre-session M1 candles
current_atr = avg(high - low) for first session M1 candles
ratio = current / baseline
detected = ratio >= 1.5
```

✅ Correct formula. Uses high-low as true range proxy (appropriate for continuous Forex).

🔴 **Critical**: This detection is **wired but never called in live mode**. The `_detect_gap()` method in `FCRStrategy` is defined but `run_session()` and `_on_new_m1_bar()` never invoke it. Signals are generated without gap/ATR confirmation.

### 8.3 Engulfing Candle Validation

| Check | Implementation | Assessment |
|-------|---------------|------------|
| Previous candle direction | ✅ Bullish→bearish or bearish→bullish required | Correct |
| Body engulfment | ✅ Current body must engulf previous body (open/close comparison) | Correct |
| Body size ratio | ❌ **Not checked** | Missing — a 1-pip body can "engulf" a 0.5-pip body, which has no conviction |
| Wick tolerance | ❌ **Not checked** | Missing — long wicks on the engulfing candle indicate rejection, weakening the signal |
| Close position relative to range | ✅ Must close beyond FCR boundary | Correct |

### 8.4 Tick-Count Volume Proxy

```python
threshold = avg_volume * min_volume_ratio  # 1.2x
confirmation = curr_candle.volume >= threshold
```

| Issue | Detail |
|-------|--------|
| Zero-volume bypass | ✅ If `avg_volume <= 0`, filter is skipped — prevents division-by-zero |
| Threshold definition | `1.2× mean` — weak; should be percentile-based |
| Volume source | IB tick count — broker-specific, not interbank |

### 8.5 Entry Timing

```python
# In _on_new_m1_bar():
signal = self._detect_engulfing(state, pip_size)
```

**Assessment**: 🟠 Entry timing is ambiguous. The real-time feed subscribes to **5-second bars** (`reqRealTimeBars(barSize=5)`), not M1 bars. Each 5-second bar triggers `_on_new_m1_bar()` — which means the engulfing check runs on every 5-second bar, not on M1 candle close. This fundamentally changes the signal meaning:
- An engulfing pattern on 5-second bars is noise, not M1 structure
- The candle list grows with 5-second bars, not M1 bars
- The `volume_period=20` baseline covers 20 × 5 seconds = 100 seconds, not 20 minutes

**This is a structural design flaw in the live trading path.**

### 8.6 Signal Deduplication

| Check | Status |
|-------|--------|
| `state.is_position_open` guard | ✅ Prevents signal while in a trade |
| `check_pair_limit(max_open_pairs=1)` | ✅ Prevents multiple pairs simultaneously |
| Two signals on same bar for same pair | ✅ Code checks bearish first, then bullish — only one can fire |
| Same pair fires after close/re-enter | ✅ `trades_today` counter prevents exceeding max |

---

## 9. Entry / Exit Logic

### 9.1 Stop Loss Placement

| Direction | SL Placement | Implementation | Assessment |
|-----------|-------------|----------------|------------|
| SHORT (bearish engulfing) | Above engulfing candle high | `candle["high"]` | ✅ Correct |
| LONG (bullish engulfing) | Below engulfing candle low | `candle["low"]` | ✅ Correct |
| Spread buffer | SL widened by `spread_pips * pip_size` | ✅ Correct direction |
| Slippage buffer | `apply_slippage_buffer()` available | ⚠️ Available but **not called in live flow** |

**Finding**: 🟡 The `apply_slippage_buffer()` function exists in `risk_manager.pyx` but is **never called** in the strategy or order flow. Only `_adjust_sl_for_spread()` in `order_manager.pyx` is used (via `adjust_for_spread=True`).

### 9.2 Take Profit Calculation

```python
# For SHORT:
tp = entry - (fabs(entry - stop_loss) * 3.0)
# For LONG:
tp = entry + (fabs(entry - stop_loss) * 3.0)
```

| Pair | Assessment |
|------|------------|
| EUR/USD | ✅ Correct in pip terms (0.0001 base) |
| GBP/USD | ✅ Correct in pip terms (0.0001 base) |
| USD/JPY | ✅ Correct in pip terms (0.01 base) — tested in `test_fcr_detector_jpy.py` |

### 9.3 Max 2 Trades / Session

```python
if state.trades_today >= self._config.trading.max_trades_per_session:
    return  # Skip signal
```

- ✅ Counter incremented on trade execution: `state.trades_today += 1`
- ✅ Counter checked before signal evaluation in `_on_new_m1_bar()`
- 🟠 **Counter is NOT explicitly reset at session end** — it relies on a new `StrategyState` being created per session via `_init_pair_state()`. If `run_session()` is called twice without restarting the process, the counter persists.

### 9.4 Time Stop / Session End

**Critical Finding**: 🔴 **No time stop exists**. When the session window (10:30 ET) closes:
1. The strategy stops monitoring (`while is_session_active()` loop exits)
2. Real-time data is unsubscribed
3. Broker is disconnected

But if a **position is still open** at session end:
- The bracket order (SL/TP) remains active on IB Gateway (which is correct)
- **However**, the bot disconnects from IB Gateway, losing the ability to monitor the position
- If the SL/TP bracket is a linked order via IB, it will execute server-side — this is safe
- But there is **no explicit session-end position closure**, no alerting that a position was left open, and no reconciliation on the next session

### 9.5 Bracket Order Correctness

```python
bracket = self._broker.ib.bracketOrder(
    action=action,
    quantity=quantity,
    limitPrice=entry_price,
    takeProfitPrice=take_profit,
    stopLossPrice=stop_loss,
)
for order in bracket:
    trade = self._broker.ib.placeOrder(contract, order)
```

✅ **Correct**: IB `bracketOrder()` creates three linked orders (parent + 2 children). IB Gateway handles SL/TP execution server-side. This is the proper approach — no manual monitoring needed.

🟡 **Concern**: The parent order uses a **Limit order** at `entry_price`. For a momentum breakout strategy, a Market order would be more appropriate (at the cost of slippage) to ensure fill. A Limit order at the engulfing close may not fill if price moves away.

---

## 10. Real-World Stress Scenarios

### 10.1 High-Impact News Events (NFP, FOMC)

| Feature | Status |
|---------|--------|
| Economic calendar filter | ❌ **NOT IMPLEMENTED** |
| News blackout window | ❌ **NOT IMPLEMENTED** |
| Behavior during news | The bot trades blindly — FCR range and engulfing signals will fire on news-driven volatility |

**Risk**: 🔴 NFP (first Friday of month, 8:30 ET) occurs 1 hour before session window. The pre-session M5 candles will capture the news spike as the FCR range. The engulfing signals at 9:30 may fire on the aftershock, with widened spreads and extreme slippage. The 0.5-pip slippage assumption is dangerously optimistic during NFP.

### 10.2 IB Gateway Disconnection Mid-Trade

| Feature | Status |
|---------|--------|
| Reconnect logic | ✅ `reconnect(max_retries=3)` exists |
| Reconnect invocation | ❌ **Never called** — no disconnection handler in strategy loop |
| Position recovery | ❌ Not implemented |
| Orphaned bracket detection | ❌ Not implemented |

**Risk**: 🔴 If IB Gateway disconnects and reconnects, the strategy has no way to:
1. Detect existing open positions from the previous session
2. Re-attach monitoring to active bracket orders
3. Prevent duplicate orders on the same pair

### 10.3 Spread Spike > 2 pips Mid-Session

| Feature | Status |
|---------|--------|
| Spread check at entry | ✅ `_validate_spread(spread_pips, max_spread_pips)` |
| Continuous spread monitoring | ❌ Not implemented |
| Spread-triggered exit | ❌ Not implemented |

**Risk**: 🟠 Spread widens during the exact window the bot trades (NYSE open). The check is a snapshot at order creation time. If spread widens between signal detection and order execution, the order may fill at a worse price than modeled.

### 10.4 Flash Crash / Extreme Wick

| Feature | Status |
|---------|--------|
| Gap-through SL protection | ❌ **NOT IMPLEMENTED** — IB stop orders become market orders; gap-through means fill at market, potentially far below SL |
| Guaranteed stop loss | ❌ IB does not offer guaranteed stops — this is a broker limitation, not a code issue |
| Maximum loss per trade cap | ❌ No absolute max-loss-per-trade parameter |

**Risk**: 🟠 During a flash crash (e.g., Jan 2019 JPY flash crash), a 30-pip SL on USD/JPY could result in a 200+ pip loss. Position sizing assumes the SL is the maximum loss — it is not.

### 10.5 IB Pacing Violations

```python
class RequestThrottler:
    max_requests = 50  # per 10 seconds
```

✅ **Correctly implemented**: The `RequestThrottler` tracks request timestamps and waits when the limit is approached. Applied to `data_feed` and `broker` operations.

🟡 `get_live_spread()` uses `await asyncio.sleep(1.0)` to wait for data — this is fragile. IB's data delivery timing is not guaranteed.

### 10.6 DST Transition Week

✅ **Correctly handled**: Uses `zoneinfo.ZoneInfo("America/New_York")` which automatically handles DST transitions. Tested with fixtures for spring-forward (March) and fall-back (November) scenarios. EU/US DST gap week (typically 1 week in March and November) is implicitly handled because the system uses NY timezone for session boundaries.

---

## 11. Strategy–Risk Engine Interaction

### 11.1 Does the FCR Strategy Stand Alone Without Risk Overlay?

**No.** Without the risk overlay:
- No position sizing → undefined lot sizes
- No daily loss limit → unlimited drawdowns
- No spread filter → trades on widened spreads
- No per-pair cap → multiple simultaneous exposures

The strategy **requires** the risk framework to be viable. This is correct architecture — the signal engine should not embed risk logic.

### 11.2 Is Risk Masking Statistical Fragility?

🟠 **Partially yes:**
- The max 2 trades/session limit caps exposure to only 2 opportunities per day. If the engulfing signal has a low hit rate (e.g., 30%), limiting to 2 trades masks the poor signal quality because worst-case daily loss is capped at 2 × 1% = 2% of equity
- The 3% daily loss kill-switch prevents catastrophic drawdowns but masks the question of whether the raw signal has positive expectancy
- The spread filter eliminates many signals that would have been losers, inflating the apparent win rate

### 11.3 Would the Raw Strategy Survive Without Protections?

**Almost certainly not.** Without spread filter and daily loss limit:
- Engulfing signals on M1 are high-frequency and low-conviction
- Spread costs during NYSE open would erode edge
- No mechanism to limit consecutive losses
- The raw signal likely has near-random expectancy (untested)

### 11.4 Cython Latency Benefit

| Module | Operations | Data Size | Python Equivalent Time |
|--------|-----------|-----------|----------------------|
| `fcr_detector` | 1 dict comparison + arithmetic | ~6 candles | <1ms in Python |
| `gap_detector` | 2 ATR computations (n=14) | ~20 candles | <1ms in Python |
| `engulfing_detector` | 2 candle comparisons + volume check | ~20 candles | <1ms in Python |
| `order_manager` | 6 comparisons + arithmetic | 1 order | <1ms in Python |
| `risk_manager` | 3 arithmetic operations | 1 check | <1ms in Python |

**Verdict**: 🟡 **Cython provides no meaningful latency benefit for M1 Forex on IB Gateway.** IB Gateway's network round-trip is 1–10ms. IB's 5-second bar granularity means the signal pipeline runs at most once every 5 seconds. Python execution for these operations would be <1ms. Cython adds build complexity (requires C compiler, limits CI/CD, breaks test suite without compilation) for zero practical benefit.

The Cython layer is defensible as a learning exercise or as preparation for future microsecond-critical equity HFT. For this M1 Forex strategy on IB Gateway, it is over-engineering.

---

# PART III — CRITICAL SYNTHESIS

---

## 12. Critical Issues (Ranked)

### 🔴 CRITICAL — Capital Endangerment / Live Trading Risk

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| C1 | **Gap detection not connected to live trading flow** | `strategy.py` — `_detect_gap()` never called | Strategy trades without ATR spike confirmation, contradicting the documented pipeline. False signals on low-volatility opens. |
| C2 | **5-second bars processed as M1 candles** | `data_feed.py` → `strategy.py:_on_new_m1_bar()` | Engulfing patterns detected on 5-second bars, not M1 closes. Fundamentally wrong signal construction in live mode. |
| C3 | **No IB Gateway disconnection recovery** | `strategy.py` — reconnect logic exists but never invoked | Unprotected position if IB drops mid-trade. No orphaned bracket detection. |
| C4 | **No news filter** | Not implemented | Blind trading during NFP/FOMC with 0.5-pip slippage assumption. Catastrophic risk. |
| C5 | **No position closure at session end** | `strategy.py:run_session()` | Open positions left unmonitored after bot disconnects from IB. |
| C6 | **Look-ahead bias in backtest** | `backtest.py:_detect_signal_at_bar()` | FCR range recomputed per-bar, not once pre-session. Backtest results are unreliable. |
| C7 | **CI/CD pipeline broken** | `Makefile:qa` | 15/19 test files fail without Cython compilation. No CI config exists. |

### 🟠 MAJOR — Severe Fragility / Statistical Weakness

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| M1 | **No in-sample / out-of-sample split** | `backtest.py` | Over-optimization risk on ATR threshold, volume ratio, range minimum |
| M2 | **vectorbt cross-validation is broken** | `backtest.py:_validate_with_vectorbt()` | Passes pip P&L as returns — meaningless Sharpe calculation |
| M3 | **Spread checked only at entry, not continuously** | `strategy.py:_execute_signal()` | Spread spike after signal detection not caught |
| M4 | **ATR threshold not empirically validated** | `constants.py` | 1.5x ratio is arbitrary — no sensitivity analysis |
| M5 | **Mypy strict mode fails with 13 errors** | Multiple engine files | Type safety not achieved |
| M6 | **Daily loss check polls every 30 seconds** | `strategy.py:run_session()` | Flash moves can exceed -3% between polls |
| M7 | **No engulfing body-size or wick ratio checks** | `engulfing_detector.pyx` | Trivial 0.1-pip engulfing candles pass detection |
| M8 | **Reconnect logic never invoked** | `broker.py:reconnect()` | Dead code — connection drops unhandled |
| M9 | **Effective test coverage ~20% of codebase** | `pyproject.toml` coverage config | Engine layer explicitly excluded from coverage |
| M10 | **Python 3.13.1 on dev machine vs 3.11.9 requirement** | Dev environment | Potential runtime incompatibilities |

### 🟡 MINOR — Optimization / Engineering / QA

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| m1 | Module access via tuple indices | `strategy.py` — `self._modules[0]` | Fragile, unreadable |
| m2 | No ABC/Protocol for core modules | `core/` | Extensibility relies on convention |
| m3 | Cython provides no measurable latency benefit | `core/*.pyx` | Over-engineering for M1/5s bar frequency |
| m4 | Duplicate test data across test files | `tests/` | Pylint duplicate-code warning |
| m5 | `apply_slippage_buffer()` never called | `risk_manager.pyx` | Dead code |
| m6 | Limit order for momentum entry | `broker.py:_submit_bracket()` | May not fill on breakouts |
| m7 | Fixed 0.5-pip slippage in backtest | `constants.py` | Unrealistic during NYSE open |
| m8 | No `.env.example` file | Project root | Missing for onboarding |
| m9 | No GitHub Actions / CI config | Project root | No automated QA |
| m10 | `filledEvent` callback for position close may not fire for bracket children | `strategy.py` | IB event specifics need broker-side testing |

---

## 13. Priority Action Plan

### 13.1 Top 5 Mandatory Fixes Before Paper Trading

| Priority | Issue | Fix |
|----------|-------|-----|
| **P1** | C2: 5-second bars used as M1 candles | Aggregate 5-second bars into proper M1 OHLCV candles before feeding to signal pipeline. Trigger engulfing detection only on M1 candle close (every 60 seconds). |
| **P2** | C1: Gap detection disconnected | Wire `_detect_gap()` into `run_session()` after FCR detection. Require `gap_result.detected == True` before enabling engulfing scanning for each pair. |
| **P3** | C5: No session-end position closure | At session end, check for open positions via `get_open_positions()`. Log warning if positions remain. Optionally close at market or allow bracket to expire with a configurable time stop. |
| **P4** | C6: Look-ahead bias in backtest | Redesign `_backtest_pair()` to compute FCR once per session using pre-9:30 ET M5 bars only (filter by timestamp). Separate M1 bars by session boundary. |
| **P5** | M7: No engulfing body-size check | Add minimum body-size ratio (e.g., current body ≥ 0.5× FCR range) and maximum wick ratio (e.g., wick ≤ 2× body) to `engulfing_detector.pyx`. |

### 13.2 Mandatory Fixes Before Live Deployment on IBKR

| Priority | Issue | Fix |
|----------|-------|-----|
| **L1** | C3: IB disconnection recovery | Implement `disconnectedEvent` handler on `self._broker.ib`. On disconnect, log critical alert, attempt `reconnect()`, rescan positions via `ib.positions()`, reconcile with state. |
| **L2** | C4: News filter | Integrate economic calendar (ForexFactory API or static CSV). Disable trading in ±15min window around high-impact events. |
| **L3** | M3: Continuous spread monitoring | Check spread on every bar during signal evaluation. Add spread check before order submission (already done) AND during open position monitoring. |
| **L4** | M6: Faster loss limit checking | Switch from 30-second polling to event-driven equity updates via `ib.accountSummary()` streaming, or reduce interval to 5 seconds during open positions. |
| **L5** | m6: Limit to Market order for entry | Change bracket parent from Limit to Market order (or use LimitIfTouched) for breakout entries to ensure fill. |
| **L6** | C7: Fix CI/CD pipeline | Create pure-Python test stubs for Cython modules so tests run without compilation. Add GitHub Actions workflow with Cython build + test. |

### 13.3 Medium-Term Structural Upgrades

| Priority | Issue | Fix |
|----------|-------|-----|
| **S1** | In-sample / out-of-sample split | Split historical data 70/30. Report metrics on both. Only trust out-of-sample results. |
| **S2** | Walk-forward optimization | Implement rolling 3-month train / 1-month test with anchored or rolling window. |
| **S3** | Parameter sensitivity analysis | Grid-search ATR threshold (1.0–2.5), volume ratio (1.0–2.0), min range (3–10 pips), RR ratio (2.0–4.0). Plot performance heatmaps. |
| **S4** | Fix vectorbt validation | Pass percentage returns (pnl_usd / equity) instead of raw pip values. Compare Sharpe and max drawdown. |
| **S5** | Dependency injection | Refactor `FCRStrategy` to accept broker/feed instances as parameters, enabling unit testing with mocks. |

### 13.4 Advanced Quantitative Improvements

| Priority | Improvement | Description |
|----------|-------------|-------------|
| **A1** | Session volatility regime filter | Compute rolling 20-day ATR at 9:30 ET. Only trade when current ATR is within 0.5–2.0× of the rolling mean. Skip abnormally quiet or violent sessions. |
| **A2** | Multi-session expansion | Test the strategy on London open (3:00 ET) and Asia-London overlap. Different pairs may show edge at different sessions. |
| **A3** | Machine learning signal filter | Train a logistic regression on historical signals to predict win/loss using features: ATR ratio, FCR range size, volume ratio, spread, day of week, consecutive-loss count. |
| **A4** | Portfolio-level correlation filter | If extended to multiple pairs, check correlation between signal directions. Avoid correlated drawdowns (e.g., long EUR/USD + short USD/JPY = doubled USD risk). |
| **A5** | Monte Carlo max drawdown | Run 10,000 permutations of trade outcomes to estimate 95th percentile maximum drawdown. Use this for position sizing instead of historical max drawdown. |

---

## 14. Scoring & Final Verdict

### 14.1 Component Scores

| Category | Score | Rationale |
|----------|-------|-----------|
| **System Architecture** | **7.5 / 10** | Clean modularity and separation of concerns. Pipeline structure is sound. Deductions for disconnected gap detector, 5-second bar processing, lack of DI, and broken CI. |
| **Code Quality & QA Toolchain** | **7.0 / 10** | Black/Ruff clean. Pylint 9.32/10. Good docstrings and type hints. Deductions for 13 mypy errors, broken test suite without Cython, only 20% effective coverage, dead code. |
| **Statistical Robustness** | **3.0 / 10** | No backtest results validated. Look-ahead bias in backtest. No in/out-of-sample split. No parameter sensitivity analysis. ATR threshold unjustified. Engulfing signal edge unproven. |
| **IBKR Integration & Safety** | **5.5 / 10** | Bracket orders correct. Throttler correct. Contract builder correct. Deductions for no disconnection handling, no position recovery, no reconnect invocation, no news filter. |
| **Production Readiness** | **3.5 / 10** | Paper trading default enforcement is good. DST handling correct. Logging comprehensive. Critical deductions for disconnected gap detector, 5-second bar bug, no session-end management, no news filter, broken CI. |

### 14.2 Overall Score

$$\text{Overall} = \frac{7.5 + 7.0 + 3.0 + 5.5 + 3.5}{5} = \textbf{5.3 / 10}$$

### 14.3 Probability of Surviving 12 Months Live on Forex via IBKR

$$P(\text{survival}_{12m}) = \textbf{15\%}$$

**Rationale**: The strategy has reasonable architecture and risk guardrails, but:
- The core signal (M1 engulfing at FCR boundary) has no validated statistical edge
- The live trading path has a fundamental bug (5-second bars as M1)
- Gap detection is disconnected — removing a key filter
- No news protection during the most dangerous events
- No IB disconnection recovery
- Backtest cannot be trusted due to look-ahead bias

### 14.4 Final Verdict

## ⚠️ STRUCTURALLY FRAGILE

The ALPHAEDGE system demonstrates competent software engineering (clean code, proper logging, correct IB bracket orders, DST handling) but suffers from **critical disconnects between design intent and implementation**:

1. The documented pipeline (FCR → Gap → Engulfing) is only partially wired — gap detection is dead code
2. The live trading path processes 5-second bars as M1 candles — invalidating the signal construction
3. The backtest has look-ahead bias — results cannot be trusted
4. No statistical evidence supports the strategy's positive expectancy
5. Critical safety features (disconnect recovery, news filter, session-end management) are missing

**The system MUST NOT be deployed on a live IBKR account in its current state.** Paper trading is acceptable only after fixing P1–P3 (5-second bar aggregation, gap detection wiring, session-end management). Live deployment requires all fixes through L6.

---

*End of ALPHAEDGE Master Audit — 2026-03-07*
