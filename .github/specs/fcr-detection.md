# Spec — FCR Detection

> Comportement attendu de `detect_fcr()` et `detect_fcr_scan()`.
> Source : `alphaedge/core/fcr_detector.pyx` + `alphaedge/core/_stubs/fcr_detector.py`
> Interfaces complètes : `docs/ALPHAEDGE_INTERFACES.md`

---

## Définition FCR

Un FCR (Fair Competition Range) est une bougie M5 dont le corps (high-low)
dépasse `min_range_pips` × `pip_size`. Il représente une zone de déséquilibre
institutionnel à laquelle le prix peut revenir.

## Inputs

| Paramètre | Type | Contrainte |
|-----------|------|-----------|
| `candles_data` | `list[dict]` | ≥ 1 bougie, ordonnées chronologiquement (index 0 = plus ancien) |
| `min_range_pips` | `float` | > 0 · depuis `constants.py` |
| `pip_size` | `float` | > 0 · 0.0001 pour EUR/USD, 0.01 pour JPY pairs |

Chaque bougie dans `candles_data` doit contenir :
`{ "open": float, "high": float, "low": float, "close": float, "timestamp": str }`

## Outputs

### Cas succès
```python
{
    "detected": True,
    "range_high": float,     # high de la bougie FCR
    "range_low": float,      # low de la bougie FCR
    "range_size": float,     # high - low (en pips)
    "candle_timestamp": str, # ISO 8601 UTC
}
```

### Cas échec (retour falsy → STOP pipeline)
```python
None
```

## Règles comportementales

1. Si `candles_data` est vide → retourner `None`
2. Si aucune bougie ne dépasse `min_range_pips` → retourner `None`
3. `detect_fcr` évalue uniquement la **dernière bougie** de la liste
4. `detect_fcr_scan` évalue les `lookback` dernières bougies et retourne la plus récente valide
5. `range_high` > `range_low` garanti si `detected: True`

## Edge Cases

| Scénario | Comportement attendu |
|----------|---------------------|
| Liste vide `[]` | `None` |
| 1 bougie sous le seuil | `None` |
| 1 bougie exactement au seuil (`=` min_range_pips) | `None` (doit être strictement supérieur) |
| Bougies non triées chronologiquement | Comportement indéfini — l'appelant doit trier |
| `pip_size = 0.0` | Risque division par zéro — l'appelant doit valider |
| `lookback` > len(candles_data) | Scan sur toutes les bougies disponibles |

## Agent Behavior Contract

```python
result = detect_fcr(candles_data, min_range_pips, pip_size)
if result is None:
    # STOP — ne pas appeler detect_gap
    return
# Continuer avec result["range_high"] et result["range_low"]
```
