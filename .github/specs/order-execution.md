# Spec — Order Execution

> Comportement attendu de `create_bracket_order()` et de `broker.py`.
> Source : `alphaedge/core/order_manager.pyx` + `alphaedge/engine/broker.py`
> Interfaces complètes : `docs/ALPHAEDGE_INTERFACES.md`

---

## create_bracket_order

### Inputs

| Paramètre | Type | Contrainte |
|-----------|------|-----------|
| `direction` | `str` | `"BUY"` ou `"SELL"` |
| `entry_price` | `float` | > 0 |
| `stop_loss` | `float` | > 0 · du bon côté selon direction |
| `take_profit` | `float` | > 0 · du bon côté selon direction |
| `lot_size` | `float` | > 0 · validé par `calculate_position_size` |
| `pip_size` | `float` | > 0 |
| `spread_pips` | `float` | ≥ 0 · depuis `constants.py` ou IB live |

### Output succès

```python
{
    "is_valid": True,
    "direction": str,       # "BUY" | "SELL"
    "entry": float,
    "sl": float,
    "tp": float,
    "lot_size": float,
    "rr_ratio": float,      # (tp - entry) / (entry - sl) pour BUY
}
```

### Output échec → STOP pipeline

```python
{
    "is_valid": False,
    "rejection_reason": str,   # ex: "SL on wrong side of entry"
}
```

### Règles de validation

| Règle | BUY | SELL |
|-------|-----|------|
| SL doit être sous entry | `sl < entry` | `sl > entry` |
| TP doit être au-dessus entry | `tp > entry` | `tp < entry` |
| RR ratio minimum | `rr_ratio >= constants.MIN_RR_RATIO` | idem |
| Spread ajouté à entry | `entry += spread_pips * pip_size` | `entry -= ...` |

### Edge Cases

| Scénario | Comportement |
|----------|-------------|
| SL du mauvais côté | `is_valid: False`, rejection_reason renseigné |
| RR ratio < MIN_RR_RATIO | `is_valid: False` |
| `lot_size <= 0` | `is_valid: False` |
| `entry == sl` | `is_valid: False` (division par zéro RR) |

---

## broker.py — Soumission IB Gateway

### Règles de sécurité

- **Toujours vérifier `is_valid: True`** avant d'appeler `broker.submit_order()`
- **Toujours vérifier `ALPHAEDGE_PAPER`** avant toute soumission réelle
- `broker.py` ne doit jamais être appelé directement sans passer par `order_manager`

### Séquence complète avant soumission

```python
# 1. Vérifier limite journalière
limit = check_daily_limit(...)
if not limit["can_trade"]:
    return  # STOP

# 2. Calculer la taille de position
size = calculate_position_size(...)
if not size["is_valid"]:
    return  # STOP

# 3. Construire l'ordre bracket
order = create_bracket_order(..., lot_size=size["lot_size"])
if not order["is_valid"]:
    logger.warning(f"Order rejected: {order['rejection_reason']}")
    return  # STOP

# 4. Soumettre via broker
await broker.submit_bracket_order(order)
```

### Paper Trading Guard

```python
# Toujours présent dans broker.py
PAPER_MODE = os.getenv("ALPHAEDGE_PAPER", "true").lower() == "true"
# Ne jamais set ALPHAEDGE_PAPER=false dans un fichier commité
```
