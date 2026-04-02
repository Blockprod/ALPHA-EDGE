# ALPHAEDGE — Public Core Interfaces & Return Value Contracts

> Implementation is [PROPRIETARY]. These are call signatures and behavioral
> contracts only. Do not infer, reverse-engineer, or reconstruct strategy logic.
> Source of truth for Copilot / AI agents acting on pipeline return values.

---

## Return Value Contracts

> **Pipeline rule: all-or-nothing.**
> One STOP at any stage cancels the entire trade for that cycle.

| Function | Returns None / falsy | Correct agent behavior |
|----------|----------------------|------------------------|
| `detect_fcr(...)` | No valid FCR found | STOP — do not proceed to gap detection |
| `detect_gap(...)` | `detected: False` | STOP — do not proceed to engulfing detection |
| `detect_engulfing(...)` | `None` | STOP — do not place any order |
| `calculate_position_size(...)` | `is_valid: False` | STOP — do not submit order, log WARNING |
| `check_daily_limit(...)` | `halt_trading: True` | STOP ALL trading immediately — log CRITICAL |
| `create_bracket_order(...)` | `is_valid: False` | STOP — log rejection_reason, skip trade |

---

## fcr_detector

```python
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
```

## gap_detector

```python
detect_gap(
    pre_session_m1, session_m1,
    pre_close, session_open,
    atr_period, min_atr_ratio
) -> dict
# Returns: {detected, gap_high, gap_low, gap_size, atr_ratio, direction}

is_in_gap_zone(
    price: float,
    gap_high: float,
    gap_low: float,
    tolerance_pips: float,
    pip_size: float
) -> bool
```

## engulfing_detector

```python
detect_engulfing(
    candles_data,
    fcr_high, fcr_low,
    rr_ratio, pip_size,
    volume_period, min_volume_ratio,
    min_body_ratio=0.3,
    max_wick_ratio=2.0
) -> dict | None
# Returns: {detected, signal, entry_price, stop_loss, take_profit,
#           risk_pips, reward_pips} | None
```

## risk_manager

```python
calculate_position_size(
    account_equity, risk_pct,
    sl_pips, pair,
    pip_size, lot_type,
    min_lots, max_lots,
    exchange_rate=0.0
) -> dict
# Returns: {lot_size, risk_amount, pip_value, sl_pips, is_valid}

check_daily_limit(
    starting_equity, current_equity,
    max_daily_loss_pct,
    trades_today, max_trades
) -> dict
# Returns: {daily_pnl, daily_pnl_pct, limit_breached, trades_today,
#           max_trades, can_trade}
```

## order_manager

```python
create_bracket_order(
    direction, entry_price,
    stop_loss, take_profit,
    lot_size, pip_size,
    spread_pips, ...
) -> dict
# Returns: {is_valid, rejection_reason?, direction, entry, sl, tp,
#           lot_size, rr_ratio}
```

---

*Mis à jour : 2026-03-24. Source canonique pour agents AI et revues de code.*
