# ALPHAEDGE Paper Validation Log

Purpose: record the 5 required paper sessions before full-size deployment.

Reference protocol: docs/ALPHAEDGE_PAPER_VALIDATION_PROTOCOL.md

## Validation Gate

- Required sessions: 5 NYSE sessions
- Decision rule:
  - GO if observed behavior is consistent with backtest tolerance bands
  - NO-GO if repeated divergence is outside tolerance or risk controls fail

## Session Log

| Session | Date | Pairs Traded | Trades Count | Observed WR | Observed PF | Backtest WR Ref | Backtest PF Ref | Spread/Slippage Notes | Risk Controls Check | Verdict |
|---|---|---|---:|---:|---:|---:|---:|---|---|---|
| 1 | 2026-03-24 | EURUSD | 7 | N/A | N/A | 46.11 | 1.454 | spread_pips present, slippage_pips present | No hard-stop seen in file | Data quality block |
| 2 | 2026-03-25 | EURUSD | 31 | N/A | N/A | 46.11 | 1.454 | spread_pips present, slippage_pips present | No hard-stop seen in file | Data quality block |
| 3 | 2026-03-26 | EURUSD | 36 | N/A | N/A | 46.11 | 1.454 | spread_pips present, slippage_pips present | No hard-stop seen in file | Data quality block |
| 4 | 2026-03-27 | EURUSD | 11 | N/A | N/A | 46.11 | 1.454 | spread_pips present, slippage_pips present | No hard-stop seen in file | Data quality block |
| 5 | 2026-03-28 | EURUSD | 1 | N/A | N/A | 46.11 | 1.454 | spread_pips present, slippage_pips present | No hard-stop seen in file | Data quality block |

## Aggregate Summary

- Total sessions completed: 5 / 5
- Total paper trades observed: 86
- Average observed WR: N/A (outcome/pnl_usd non exploitables)
- Average observed PF: N/A (outcome/pnl_usd non exploitables)
- Risk event count (daily limit, bracket rejection, hard stop): 0

## Final Decision

- Status: Blocked by data quality
- Decision date: TBD
- Decision owner: TBD
- Notes:
  - 5 sessions are recorded, but all rows in source files have outcome=unknown and pnl_usd=0.
  - The C-ST-01 gate cannot be validated until the live trade logger records resolved exits and realized PnL.
  - 2026-04-02 remediation applied in alphaedge/engine/session_lifecycle.py:
    close callbacks now ignore non-closing fill events and subscribe to TP/SL children only.
  - Action required: collect a fresh 5-session validation batch after the remediation.
