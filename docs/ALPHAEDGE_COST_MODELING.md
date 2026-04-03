# ALPHAEDGE Cost Modeling

## Purpose

Document the structural difference between backtest transaction costs and live execution costs, and define a calibration bridge.

## Model Philosophy

- Backtest costs are deterministic and reproducible.
- Live costs are stochastic and observed at fill time via IBKR.
- The objective is not exact equality trade-by-trade; it is bounded divergence after calibration.

## Backtest Side

Backtest uses regime-aware cost assumptions.

- Spread and slippage are modeled by regime (normal / nyse_open / news).
- Multipliers are configurable in `config.yaml`:
  - `cost_spread_multipliers`
  - `cost_slippage_multipliers`

This provides reproducibility for optimization and regression testing.

## Live Side

Live execution captures observed fills and computes costs from actual fills.

- `spread_pips` and `slippage_pips` are journaled per trade.
- Costs are reactive to current market conditions.

## Reconciliation Bridge

Use `export_cost_comparison(...)` in `alphaedge/engine/backtest_export.py`.

Input:

- backtest trades (CSV/DataFrame/list)
- live trades (CSV/DataFrame/list)

Output CSV columns:

- `pair`
- `direction`
- `entry_time`
- `backtest_slippage_cost`
- `live_slippage_cost`
- `diff_pips`
- `diff_pct`

Note: in this implementation, `backtest_slippage_cost` and `live_slippage_cost` are total transaction costs in pips (spread + slippage) for direct comparability.

## Acceptance Threshold

Default tolerance target:

- `abs(diff_pct) <= 15%`

Helper:

- `cost_divergence_within_tolerance(comparison_df, tolerance_pct=15.0)`

## Operational Procedure

1. Run backtest and export trades.
2. Collect live paper session trades in `reports/live_trades_*.csv`.
3. Generate reconciliation CSV with `export_cost_comparison(...)`.
4. Check tolerance with `cost_divergence_within_tolerance(...)`.
5. If divergence is persistent, recalibrate multipliers in config.

## Current Status

- Framework implemented.
- Reconciliation helper implemented and test-covered.
- Calibration pass should be repeated after each 5-session paper validation batch.
