---
name: run-backtest
description: >
  Use when: launching a backtest, interpreting backtest results, diagnosing
  DST-related bias or warmup issues, adjusting parameters, or exporting
  results to CSV for Bayesian optimization.
---

# Skill — run-backtest

## When to invoke this skill

- Running `python -m alphaedge.engine.backtest`
- Diagnosing unexpected results (DST gap, warmup contamination, look-ahead bias)
- Adjusting `config.yaml` parameters and validating impact
- Exporting results to `reports/` for optimization

## Steps

```powershell
# 1. Activate environment
.\.venv\Scripts\Activate.ps1

# 2. Run backtest
python -m alphaedge.engine.backtest

# 3. Key output files
#    alphaedge/logs/bt_full.txt     — full trade log
#    reports/ALPHAEDGE_backtest_results.csv — summary metrics
#    alphaedge/logs/bt_stderr.txt   — errors / warnings

# 4. Key metrics to check
#    Win rate — target > 50%
#    Profit factor — target > 1.5
#    Max drawdown — must be < max_daily_loss_pct
#    Sharpe ratio — target > 1.0
```

## Configuration

All parameters live in `config.yaml` and `alphaedge/config/constants.py`.
**Never hardcode values** — always use constants.

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| Results differ after EU DST | ~1-week gap where EU/US clocks diverge | Check `timezone.py` DST logic; validate session window |
| Warmup period contamination | Trades in first N bars use incomplete data | Increase `warmup_bars` in config.yaml |
| Look-ahead bias | Signal uses future data | Verify all indicators use `candles[:-1]` slices |
| Empty results | No legacy range detected in date range | Widen `min_range_pips` or extend date range for debug |
| IB connection error | Engine requires IB Gateway for live data | Use `--offline` flag or historical CSV mode |

## Output Files

| File | Purpose |
|------|---------|
| `alphaedge/logs/bt_full.txt` | Complete trade log with timestamps |
| `alphaedge/logs/bt_final.txt` | Summary statistics |
| `reports/ALPHAEDGE_backtest_results.csv` | Exportable metrics for optimization |
| `alphaedge/logs/bt_stderr.txt` | Errors and warnings to investigate |

## DST Critical Dates (Europe/Paris)

- **Winter:** NYSE open = 15:30 CET
- **Summer:** NYSE open = 14:30 CEST
- **EU DST switch:** last Sunday March / last Sunday October
- **US DST switch:** 2nd Sunday March / 1st Sunday November
- **Gap weeks:** ~1 week/year where EU and US offsets diverge

## Gotchas (from tasks/lessons.md)

- EURUSD utilise London Open (08:00–09:00 UTC), PAS NYSE — tout diagnostic basé sur NYSE pour EURUSD produit de faux positifs (2026-03-24)
- `PROJECT_TITLE` contient ⚡ (U+26A1) — ne jamais passer directement à Rich `Text()`/`Panel()` sur Windows cp1252 (crash LegacyWindowsTerm) (2026-03-24)
- Un taux signal ~1-2% sur EURUSD London Open est statistiquement normal (88% sessions rejetées par filtre legacy range) — ne pas modifier les paramètres sans N ≥ 30 trades (2026-03-24)
- `_backtest_pair` directement sans `session_spec` utilise NYSE par défaut — toujours passer `session_spec=config.trading.pair_sessions.get(pair)` (2026-03-24)
