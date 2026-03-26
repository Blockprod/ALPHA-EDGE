# ALPHAEDGE — Trading Constraints

Contraintes de trading FCR extraites du code source.

---

## Stratégie FCR — Fair Competition Range

### Définition

Le signal FCR est une zone de consolidation détectée sur M5 avant l'ouverture de session. Un trade est pris quand le prix revient dans cette zone avec un engulfing M1 confirmé.

### Conditions d'entrée (toutes obligatoires)

1. **FCR détecté** : range ≥ 8 pips (`DEFAULT_MIN_RANGE_PIPS`) sur 6 bougies M5 (`DEFAULT_FCR_LOOKBACK`)
2. **Gap validé** : ATR spike ≥ 2.0× ATR moyen (`DEFAULT_MIN_ATR_RATIO`) sur 14 périodes (`DEFAULT_ATR_PERIOD`)
3. **Engulfing confirmé** : bougie M1 englobante avec body ≥ 30% (`DEFAULT_MIN_BODY_RATIO`), wick ≤ 150% (`DEFAULT_MAX_WICK_RATIO`), volume ≥ 1.0× (`DEFAULT_MIN_VOLUME_RATIO`)
4. **Spread acceptable** : spread live ≤ 2.0 pips (`DEFAULT_MAX_SPREAD_PIPS`)
5. **Limite quotidienne non atteinte** : < 2 trades/session (`DEFAULT_MAX_TRADES_PER_SESSION`)
6. **Daily loss limit non atteinte** : perte < 3.0% equity (`DEFAULT_MAX_DAILY_LOSS_PCT`)

---

## Gestion du Risque

| Paramètre | Valeur | Constante |
|-----------|--------|-----------|
| Risk par trade | 2.0% de l'equity | `DEFAULT_RISK_PCT` |
| RR ratio | 2.5:1 | `DEFAULT_RR_RATIO` |
| Max daily loss | 3.0% de l'equity | `DEFAULT_MAX_DAILY_LOSS_PCT` |
| Max trades/session | 2 | `DEFAULT_MAX_TRADES_PER_SESSION` |
| Max spread | 2.0 pips | `DEFAULT_MAX_SPREAD_PIPS` |

---

## Sizing Position

- Lot type : micro (`DEFAULT_LOT_TYPE = "micro"`)
- Min lots : 0.01 (`MIN_LOTS`)
- Max lots : 10.0 (`MAX_LOTS`)
- Calcul : `risk_amount / (sl_pips × pip_value)` → arrondi au lot micro

Si `calculate_position_size()` retourne `is_valid=False` → **STOP, aucun ordre soumis**.

---

## Sessions de Trading

| Session | Paire principale | Fenêtre UTC (hiver) | Fenêtre UTC (été) |
|---------|-----------------|--------------------|--------------------|
| NYSE Open | USDJPY | 15:30–16:30 | 14:30–15:30 |
| London Open | EURUSD, GBPUSD | 08:00–09:00 | 08:00–09:00 |

**DST** : La semaine de transition EU/US crée un décalage supplémentaire de ±1h sur les sessions NYSE.

---

## Slippage & Spread Modèles

### Slippage variable

| Condition | Slippage |
|-----------|----------|
| Normal | 0.3 pips (`BASE_SLIPPAGE_PIPS`) |
| NYSE open (5 min) | 0.6 pips (`×NYSE_OPEN_SLIPPAGE_MULTIPLIER = 2.0`) |
| Événement news | 1.5 pips (`×NEWS_SLIPPAGE_MULTIPLIER = 5.0`) |

### Spread variable (EUR/USD base)

| Condition | Spread |
|-----------|--------|
| Normal | 0.8 pips (`BASE_SPREAD_PIPS`) |
| NYSE open | 1.5 pips (`NYSE_OPEN_SPREAD_PIPS`) |
| News haute-impact | 3.0 pips (`NEWS_SPREAD_PIPS`) |

---

## Filtres Additionnels

| Filtre | Paramètre | Fichier |
|--------|-----------|---------|
| Corrélation USD | max 0.7 (`DEFAULT_MAX_CORRELATION`) | `pair_correlation.py` |
| Régime volatilité | ATR 20j (`REGIME_ATR_LOOKBACK_DAYS`) | `volatility_regime.py` |
| News haute-impact | Blackout ±15 min (`DEFAULT_BLACKOUT_MINUTES`) | `news_filter.py` |
| Spread spike | 3× spread normal (`DEFAULT_SPREAD_SPIKE_MULTIPLIER`) | `session_lifecycle.py` |

---

## Pip Sizes par Paire

| Paire | Pip size |
|-------|----------|
| EURUSD, GBPUSD, AUDUSD, USDCAD, USDCHF, NZDUSD, EURGBP | 0.0001 |
| USDJPY, EURJPY, GBPJPY | 0.01 |

Source unique : `PIP_SIZES` et `DEFAULT_PIP_SIZE` dans `constants.py`. Ne jamais hardcoder ailleurs.

---

## Kill Switch

`check_daily_limit()` arrête **tout** trading si :
- Perte journalière ≥ `DEFAULT_MAX_DAILY_LOSS_PCT` (3.0%)
- Trades journaliers ≥ `DEFAULT_MAX_TRADES_PER_SESSION` (2)

Retourne `halt_trading=True` → log CRITICAL + arrêt immédiat du pipeline.
