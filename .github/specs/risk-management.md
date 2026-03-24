# Spec — Risk Management

> Comportement attendu de `calculate_position_size()` et `check_daily_limit()`.
> Source : `alphaedge/core/risk_manager.pyx` + `alphaedge/core/_stubs/risk_manager.py`
> Interfaces complètes : `docs/ALPHAEDGE_INTERFACES.md`

---

## calculate_position_size

### Inputs

| Paramètre | Type | Contrainte |
|-----------|------|-----------|
| `account_equity` | `float` | > 0 |
| `risk_pct` | `float` | 0 < risk_pct ≤ 1.0 · depuis `constants.py` |
| `sl_pips` | `float` | > 0 |
| `pair` | `str` | ex: `"EURUSD"`, `"GBPUSD"`, `"USDJPY"` |
| `pip_size` | `float` | > 0 (0.0001 ou 0.01) |
| `lot_type` | `str` | `"standard"` | `"mini"` | `"micro"` |
| `min_lots` | `float` | > 0 · depuis `constants.py` |
| `max_lots` | `float` | ≥ `min_lots` · depuis `constants.py` |
| `exchange_rate` | `float` | 0.0 = auto-détecté (pair USD-based) |

### Output succès

```python
{
    "lot_size": float,     # taille de position calculée, clampée [min_lots, max_lots]
    "risk_amount": float,  # montant risqué en devise du compte
    "pip_value": float,    # valeur pip pour la taille calculée
    "sl_pips": float,      # echo du paramètre d'entrée
    "is_valid": True,
}
```

### Output échec → STOP pipeline

```python
{
    "lot_size": 0.0,
    "risk_amount": 0.0,
    "pip_value": 0.0,
    "sl_pips": sl_pips,
    "is_valid": False,
    "rejection_reason": str,  # description de l'échec
}
```

### Edge Cases

| Scénario | Comportement |
|----------|-------------|
| `account_equity <= 0` | `is_valid: False` |
| `sl_pips <= 0` | `is_valid: False` |
| Lot calculé < `min_lots` | clamp à `min_lots`, `is_valid: True` |
| Lot calculé > `max_lots` | clamp à `max_lots`, `is_valid: True` |
| `risk_pct > 1.0` | `is_valid: False` |

---

## check_daily_limit

### Inputs

| Paramètre | Type | Contrainte |
|-----------|------|-----------|
| `starting_equity` | `float` | > 0 — equity au début de la session |
| `current_equity` | `float` | > 0 — equity actuelle |
| `max_daily_loss_pct` | `float` | 0 < pct ≤ 1.0 · depuis `constants.py` |
| `trades_today` | `int` | ≥ 0 |
| `max_trades` | `int` | ≥ 1 · depuis `constants.py` |

### Output

```python
{
    "daily_pnl": float,         # current_equity - starting_equity
    "daily_pnl_pct": float,     # daily_pnl / starting_equity
    "limit_breached": bool,     # True si perte > max_daily_loss_pct
    "trades_today": int,        # echo du paramètre
    "max_trades": int,          # echo du paramètre
    "can_trade": bool,          # False si limit_breached OU trades >= max_trades
}
```

### Agent Behavior Contract

```python
limit = check_daily_limit(starting_equity, current_equity,
                          max_daily_loss_pct, trades_today, max_trades)
if limit["halt_trading"] or not limit["can_trade"]:
    # STOP ALL — log CRITICAL — ne plus passer d'ordre ce jour
    logger.critical("Daily limit reached — trading halted")
    return
```

> ⚠️ `check_daily_limit` doit être appelé **à chaque cycle** de la boucle principale,
> pas seulement avant de placer un ordre.
