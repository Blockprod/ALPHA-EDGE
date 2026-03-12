# ALPHAEDGE — AI Lessons Learned

> Updated after every user correction. Review at session start.
> Format: `[date] [file/module] — mistake → correct pattern`

---

## Cython

- Always run `make build` after **any** `.pyx` edit. The `.pyd`/`.so` is the runtime — the `.pyx` alone does nothing.

## Config / YAML

- `excluded_days`, `usd_correlation_filter`, `fcr_range_cv_max` were tested and ELIMINATED. Do not re-suggest them.
- Baseline locked: EURUSD+USDJPY, RR=2.0, risk_pct=3.0, Sharpe=3.37.

## File Organisation

- Outputs (csv, png, coverage) → `reports/`
- Documentation (.md audits, roadmap) → `docs/`
- Launcher scripts (.bat, .ps1) → `scripts/`
- Temporary sweep files → `scripts/` (not root)

## Windows Task Scheduler

- Use `.bat` + `schtasks /create /xml` pattern (not PowerShell `Register-ScheduledTask` — fails silently with UAC).
- Auto-elevate with `net session >nul 2>&1` check.
- Cleanup `%TEMP%\*.xml` after `schtasks /create`.

## Architecture

- AlphaEdge is event-driven (IB push via `reqRealTimeBars`). No polling/scheduling needed. Do not suggest `schedule.every(...)`.
- `asyncio.sleep(1.0)` in `get_live_spread` / `get_mid_price` is intentional (IB data arrival wait). Not a latency bug for M1 strategy.
- `max_lot_size` in config is unused in backtest (kept for call-site compatibility). Changing it has no effect on backtest results.
