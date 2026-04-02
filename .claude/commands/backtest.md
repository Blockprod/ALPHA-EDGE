# /backtest — Lance et interprète le backtest AlphaEdge

Lire le skill complet avant de commencer :
`.github/skills/run-backtest/SKILL.md`

## Lancement
```powershell
.\.venv\Scripts\Activate.ps1
python -m alphaedge.engine.backtest
```

## Affichage des résultats
Après exécution, affiche :

```
📈 Backtest AlphaEdge
─────────────────────────────────
Période     : <start> → <end>
Trades      : <n> total · <w> wins · <l> losses
Win rate    : <x>%
Profit factor : <x>
Max drawdown : <x>%
Sharpe      : <x>
─────────────────────────────────
Fichier     : reports/ALPHAEDGE_backtest_results.csv
```

## Diagnostics automatiques
- Si win rate < 40% → vérifier les filtres de régime
- Si max drawdown > 20% → vérifier les paramètres de risque dans `constants.py`
- Si 0 trades → vérifier les dates et la session NYSE (15:30–16:30 CET / 14:30–15:30 CEST)
- DST gap EU/US (~1 semaine/an) → consulter `alphaedge/utils/timezone.py`

## Règles
- Ne jamais modifier `core/*.pyx` pour ajuster les résultats sans instruction explicite
- Tout ajustement de paramètre → modifier `alphaedge/config/constants.py` uniquement
