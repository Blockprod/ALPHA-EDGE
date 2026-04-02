# Spec — Backtest Engine

> Comportement attendu de `alphaedge/engine/backtest.py` et modules associés.
> Source : `alphaedge/engine/backtest.py`, `backtest_simulation.py`, `backtest_stats.py`

---

## Hypothèses du backtest

| Hypothèse | Valeur | Source |
|-----------|--------|--------|
| Spread simulé | `constants.SPREAD_PIPS` | constants.py |
| Commission | 0 (incluse dans spread) | constants.py |
| Slippage | 0 (hypothèse conservatrice) | — |
| Remplissage | Immédiat au prix d'entrée | simulation |
| Capital initial | `config.yaml: initial_equity` | config |
| Taille de position | Via `calculate_position_size()` | risk_manager |

## Biais à éviter

| Biais | Description | Guard |
|-------|-------------|-------|
| Look-ahead | Utiliser close de la bougie courante comme signal | Toujours `candles[:-1]` pour le signal, `candles[-1]` pour l'exécution |
| Warmup | Les N premières bougies ont des indicateurs incomplets | Ignorer trades avant `warmup_bars` configuré |
| DST gap | Semaine de décalage EU/US change l'heure NYSE | Tester avec dates couvrant EU-switch et US-switch |
| Survivorship bias | Tester sur instruments toujours actifs | ALPHAEDGE: paires majeures EUR/USD stable |
| Overfitting | Optimiser sur l'échantillon d'entraînement uniquement | Walk-forward obligatoire (`walk_forward.py`) |

## Pipeline de simulation

```
config.yaml / constants.py
  └─► backtest.py              — orchestration principale
        └─► data_feed.py       — chargement données historiques
        └─► backtest_simulation.py — tick par tick M5/M1
              └─► fcr_detector    — signal
              └─► gap_detector    — filtre
              └─► engulfing_detector — entrée
              └─► risk_manager    — sizing
              └─► order_manager   — bracket
        └─► backtest_stats.py   — métriques (Sharpe, PF, MDD)
        └─► backtest_export.py  — CSV reports/
```

## Métriques de sortie

| Métrique | Cible | Minimum acceptable |
|----------|-------|--------------------|
| Win rate | > 55% | > 45% |
| Profit factor | > 1.5 | > 1.1 |
| Max drawdown | < 10% | < 20% |
| Sharpe ratio | > 1.0 | > 0.5 |
| Nombre de trades | > 30 | > 10 (sinon non statistiquement significatif) |

## Walk-Forward

- Training set : 70% de la période testée
- Test set : 30% final (hors-échantillon)
- Aucun paramètre optimisé sur le test set
- Résultats rapportés sur **le test set uniquement**

## Filtres backtesting

`backtest_filters.py` — filtres applicables :
- `news_filter` : exclure les fenêtres autour des publications macro
- `regime_filter` : exclure les périodes de régime adverse
- `ml_filter` : filtre ML optionnel sur signal FCR

Tous les filtres sont **optionnels** et configurables dans `config.yaml`.

## Commandes

```powershell
# Backtest standard
python -m alphaedge.engine.backtest

# Avec optimisation Bayésienne
python scripts/_opt_run.py

# Walk-forward
python -m alphaedge.engine.walk_forward
```

## Outputs

| Fichier | Contenu |
|---------|---------|
| `alphaedge/logs/bt_full.txt` | Journal complet trade par trade |
| `alphaedge/logs/bt_final.txt` | Résumé statistiques |
| `reports/ALPHAEDGE_backtest_results.csv` | Export métriques pour optimisation |
