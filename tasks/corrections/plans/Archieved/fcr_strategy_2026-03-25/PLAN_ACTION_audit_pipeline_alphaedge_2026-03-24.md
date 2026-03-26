---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: PLAN_ACTION_audit_pipeline_alphaedge_2026-03-24.md
derniere_revision: 2026-03-24
creation: 2026-03-24 à 16:30
---

# PLAN D'ACTION — ALPHAEDGE — 2026-03-24
Sources : `tasks/audits/resultats/audit_pipeline_alphaedge.md`
Total : 🔴 0 · 🟠 3 · 🟡 0 · Effort estimé : 0.5 jour

---

## PHASE 1 — CRITIQUES 🔴

*Aucune anomalie critique identifiée dans cet audit.*

---

## PHASE 2 — MAJEURES 🟠

### [C-01] Remplacer DEFAULT_VOLUME_PERIOD par config.trading.volume_period en backtest

Fichier : `alphaedge/engine/backtest.py:294`
Problème : La fonction `_detect_signal_at_bar()` passe la constante `DEFAULT_VOLUME_PERIOD` à `eng_mod.detect_engulfing()` au lieu de lire `config.trading.volume_period`. La valeur actuelle est identique (20), mais cette dérive est silencieuse — toute recalibration dans `config.yaml` sera ignorée par le backtest sans avertissement d'aucune sorte.
Correction :
```python
# AVANT (backtest.py:294)
volume_period=DEFAULT_VOLUME_PERIOD,

# APRÈS
volume_period=config.trading.volume_period,
```
S'assurer que `config` est accessible dans la portée de `_detect_signal_at_bar()` (signature actuelle inclut `config: AppConfig`).
Validation :
```
make qa
# Attendu : 100% pass — aucun test ne devrait changer (valeur identique)
# Vérifier : grep "DEFAULT_VOLUME_PERIOD" backtest.py → 0 occurrence (hors imports)
```
Dépend de : Aucune
Statut : ✅

---

### [C-02] Remplacer DEFAULT_ATR_PERIOD par config.trading.atr_period en backtest

Fichier : `alphaedge/engine/backtest.py:437`
Problème : La fonction `_detect_session_gap()` passe la constante `DEFAULT_ATR_PERIOD` à `gap_mod.detect_gap()` au lieu de lire `config.trading.atr_period`. La valeur actuelle est identique (14), mais toute recalibration dans `config.yaml` sera ignorée par le backtest.
Correction :
```python
# AVANT (backtest.py:437)
atr_period=DEFAULT_ATR_PERIOD,

# APRÈS
atr_period=config.trading.atr_period,
```
S'assurer que `config` est accessible dans la portée de `_detect_session_gap()`. Si elle n'est pas dans la signature, l'ajouter en paramètre.
Validation :
```
make qa
# Attendu : 100% pass — valeur identique, comportement inchangé
# Vérifier : grep "DEFAULT_ATR_PERIOD" backtest.py → 0 occurrence (hors imports)
```
Dépend de : Aucune
Statut : ✅

---

### [C-03] Documenter explicitement la divergence du modèle coûts backtest vs live

Fichier : `alphaedge/engine/backtest_simulation.py:41`
Problème : Le modèle de coûts utilisé en backtest (`compute_variable_slippage()` — spread par paire fixe + slippage variable contexte NYSE/news) diverge du modèle live (`get_live_spread()` réel + buffer fixe `DEFAULT_MARKET_SLIPPAGE_PIPS`). Cette divergence est une hypothèse de modélisation implicite, jamais documentée.
Impact : La comparaison backtest/live est biaisée. La dégradation IS→OOS observée (PF 1.63 IS → 0.71 OOS) peut partiellement refléter cette divergence plutôt que la dégradation réelle de l'edge.
Correction (option minimale — documentation) :
Ajouter dans `backtest_simulation.py`, en tête de `compute_variable_slippage()` :
```python
# HYPOTHÈSE DE MODÉLISATION — Approuvée 2026-03-24
# Le backtest utilise des spreads par paire calibrés (BASE_SPREAD_BY_PAIR)
# avec des multiplicateurs contextuels (NYSE open, news).
# Le live utilise le spread réel IB + un buffer fixe (DEFAULT_MARKET_SLIPPAGE_PIPS).
# Ces deux méthodes sont des approximations non équivalentes.
# Conséquence : toute comparaison PnL backtest ↔ live requiert +0.5 pip de
# coût additionnel côté backtest pour corriger le biais de modélisation.
# Référence : audit_pipeline_alphaedge.md — BLOC 4 — P-03
```
Correction (option complète — alignement) : À étudier séparément — nécessite de connaître l'écart réel IB spread sur EURUSD/USDJPY en production. Non planifié dans ce cycle.
Validation :
```
make qa
# Attendu : 100% pass — ajout de commentaire uniquement, aucun changement
# comportemental
```
Dépend de : Aucune (option minimale) · C-01, C-02 doivent être terminés d'abord si option complète
Statut : ✅

---

## PHASE 3 — MINEURES 🟡

*Aucune anomalie mineure identifiée dans cet audit.*

---

## SÉQUENCE D'EXÉCUTION

```
1. C-01  — backtest.py:294  — 1 ligne, risque zéro
2. C-02  — backtest.py:437  — 1 ligne, risque zéro
   → make qa après C-01 + C-02 (un seul passage suffit)
3. C-03  — backtest_simulation.py — commentaire uniquement, aucun risque
   → make qa après C-03
```

> Aucune modification `.pyx` dans ce plan → `make build` non requis.
> C-01 et C-02 peuvent être appliqués en une seule passe (même fichier).

---

## CRITÈRES PASSAGE EN PRODUCTION

- [ ] Zéro 🔴 ouvert
- [ ] `make qa` : 100% pass (lint + mypy + pytest ≥80%)
- [ ] Zéro credential dans les logs loguru
- [ ] `ALPHAEDGE_PAPER=true` intact dans `.env.example`
- [ ] Bracket order `is_valid` vérifié avant envoi IB
- [ ] `check_daily_limit()` appelé chaque cycle
- [ ] Paper trading validé 5 sessions NYSE minimum

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier | Effort | Statut | Date |
|----|-------|----------|---------|--------|--------|------|
| C-01 | Remplacer DEFAULT_VOLUME_PERIOD par config | 🟠 Majeur | `backtest.py:294` | 15 min | ✅ | 2026-03-24 |
| C-02 | Remplacer DEFAULT_ATR_PERIOD par config | 🟠 Majeur | `backtest.py:437` | 15 min | ✅ | 2026-03-24 |
| C-03 | Documenter divergence modèle coûts | 🟠 Majeur | `backtest_simulation.py:41` | 30 min | ✅ | 2026-03-24 |
