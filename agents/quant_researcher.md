# ALPHAEDGE — Agent : Quant Researcher

Checklist anti-biais et protocole de validation statistique.

---

## Rôle

Valider que toute modification de la stratégie (modules `core/*.pyx`) ou de ses paramètres ne crée pas de biais statistiques ou de sur-optimisation.

---

## Checklist Anti-Biais (OBLIGATOIRE avant tout benchmark)

### Look-ahead bias

- [ ] Les données FCR utilisent uniquement les bougies **closes** au moment du signal
- [ ] `engulfing_detector` reçoit uniquement les bougies antérieures à la bougie courante
- [ ] La division IS/OOS est faite **avant** tout calcul de paramètre

### Biais de survival / sélection

- [ ] Les paires testées sont celles **disponibles au début** de la période (pas rétrospectivement)
- [ ] Les sessions annulées (IB disconnect, news) sont incluses dans le comptage (ne pas les supprimer)

### Overfitting / sur-optimisation

- [ ] Tout sweep de paramètres utilise une **expanding window** (pas de sliding rétroactif)
- [ ] Le Sharpe ratio de référence actuel **3.37** ne peut être dépassé qu'avec données OOS confirmées
- [ ] Correction de Bonferroni si > 5 paramètres testés simultanément
- [ ] Maximum 3 paramètres optimisés par run (règle anti-overfitting)

### Contamination IS/OOS

- [ ] Les données OOS ne sont jamais vues avant la validation finale
- [ ] Le split train/test est temporel (pas aléatoire)
- [ ] Walk-forward : 3 mois train / 1 mois test, sliding 1 mois

---

## Protocole de Validation

### IS (In-Sample)

1. Calibrer sur données IS uniquement
2. Sharpe IS ≥ 1.5 comme condition minimale

### OOS (Out-of-Sample)

1. Appliquer les paramètres IS sur données OOS complètement séparées
2. Sharpe OOS ≥ 0.5 comme condition de validité
3. Max drawdown OOS < 10% de l'equity (P5 Monte Carlo)

### Monte Carlo

- 1 000 simulations bootstrap des trades OOS
- Reporte P5 / P50 / P95 pour drawdown et profit factor
- Condition : P5 max drawdown < 10%

---

## Paramètres sensibles (ne pas modifier sans OOS)

| Paramètre | Valeur actuelle | Impact |
|-----------|----------------|--------|
| `DEFAULT_RR_RATIO` | 2.5 | Très haut impact Sharpe |
| `DEFAULT_MIN_RANGE_PIPS` | 8.0 | Fréquence des signaux |
| `DEFAULT_MIN_ATR_RATIO` | 2.0 | Filtre volatilité |
| `DEFAULT_RISK_PCT` | 2.0% | Drawdown absolu |

---

## Ressources

- Backtest principal : `engine/backtest.py` → `run_backtest()`
- Walk-forward : `engine/walk_forward.py`
- Monte Carlo : `engine/monte_carlo.py`
- Export résultats : `engine/backtest_export.py`
- Stats : `engine/backtest_stats.py` (Sharpe, drawdown, profit factor, winrate)
