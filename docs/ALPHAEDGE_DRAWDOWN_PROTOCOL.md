# ALPHAEDGE Drawdown Protocol

Purpose: define operator behavior under losing streak pressure and remove ad-hoc manual intervention.

## Context

- Strategic audit finding C-ST-04: max consecutive losses can reach 9 trades.
- Risk objective: keep execution discipline intact during statistically normal drawdown periods.

## Core Rule

- Do not pause trading manually only because of a loss streak.
- The hard stop remains the daily loss limit enforced by risk controls.
- If the warning condition below triggers, continue trading and follow the recovery checklist.

## Warning Condition (Live)

A warning is logged when both conditions are met:

1. `consecutive_losses_count > 7`
2. `loss_streak_pnl_usd < -(daily_loss_limit_usd * 0.5)`

Where:

- `daily_loss_limit_usd = equity_base * max_daily_loss_pct / 100`
- `equity_base = current_equity if available, else starting_equity`

## Recovery Checklist (When Warning Triggers)

1. Confirm no daily hard-stop breach has occurred.
2. Keep system running; do not disable entries manually.
3. Verify data/feed health and broker connectivity.
4. Review spread/slippage behavior for anomaly detection.
5. Record event timestamp and pair context in session notes.

## Historical Reference

- Current audit reference: longest streak observed = 9 losses.
- Data source for detailed extraction: reports/ALPHAEDGE_backtest_results.csv.

Extracted 7+ loss streak windows (from trade-level backtest CSV):

| Streak Length | Start (UTC) | End (UTC) | Streak PnL (USD) |
|---:|---|---|---:|
| 7 | 2024-04-16 | 2024-04-18 | -490.83 |
| 7 | 2024-08-02 | 2024-08-12 | -414.07 |
| 9 | 2024-09-26 | 2024-10-07 | -582.20 |
| 7 | 2024-11-29 | 2024-12-04 | -814.89 |
| 7 | 2025-10-13 | 2025-10-15 | -1071.16 |
| 7 | 2025-11-04 | 2025-11-07 | -1013.12 |

Summary:

- Longest streak: 9 losses (2024-09-26 to 2024-10-07), PnL = -582.20 USD
- Worst 7+ streak by capital impact: -1071.16 USD (2025-10-13 to 2025-10-15)

## Implementation Notes

- Live tracking fields are maintained in strategy state:
  - `consecutive_losses_count`
  - `loss_streak_pnl_usd`
- Warning logic is implemented in session lifecycle close handling.
- Unit tests validate threshold behavior:
  - `alphaedge/tests/test_consecutive_losses_logging.py`
