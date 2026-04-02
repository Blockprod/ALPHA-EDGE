---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: PLAN_ACTION_audit_ia_ml_alphaedge_2026-03-25.md
derniere_revision: 2026-03-25
creation: 2026-03-25 à 19:30
---

# PLAN D'ACTION — ALPHAEDGE — 2026-03-25
Sources : `tasks/audits/resultats/audit_ia_ml_alphaedge.md`
Total : 🔴 0 · 🟠 1 · 🟡 3 · Effort estimé : ~1 jour

---

## PHASE 1 — CRITIQUES 🔴

*Aucune correction critique identifiée dans cet audit.*

---

## PHASE 2 — MAJEURES 🟠

### [C-01] Activer le flag de configuration `regime_filter_gate_enabled`

Fichier : `alphaedge/engine/strategy.py:203–217` · `config.yaml` · `alphaedge/config/constants.py`
Problème : `DailyRegimeFilter` est instancié et produit un label `high_vol / low_vol`, mais ne bloque **jamais** un trade (`[observation only]`). Le gate est absent depuis l'implémentation initiale. Les sessions haute volatilité non-directionnelle ne sont pas filtrées.
Correction :
  1. Ajouter dans `config.yaml` (section `momentum` ou `filters`) :
     ```yaml
     regime_filter:
       enabled: false          # activer après 30 sessions paper en observation
       block_on: "high_vol"   # bloquer si K-Means prédit haute volatilité
     ```
  2. Ajouter dans `alphaedge/config/constants.py` :
     ```python
     DEFAULT_REGIME_GATE_ENABLED: bool = False
     DEFAULT_REGIME_BLOCK_ON: str = "high_vol"
     ```
  3. Dans `alphaedge/config/loader.py` : exposer `regime_gate_enabled` et `regime_block_on` dans `AppConfig`.
  4. Dans `alphaedge/engine/strategy.py:203–217` : remplacer le log `[observation only]` par un gate conditionnel :
     ```python
     if self._cfg.regime_gate_enabled and regime == self._cfg.regime_block_on:
         logger.info("ALPHAEDGE: regime gate BLOCK pair=%s regime=%s", pair, regime)
         return None  # STOP pipeline
     logger.info("ALPHAEDGE: regime=%s pair=%s", regime, pair)
     ```
  5. Ajouter tests unitaires `tests/test_strategy_regime_gate.py` couvrant :
     - gate disabled → trade non bloqué (comportement actuel préservé)
     - gate enabled + regime=high_vol → retourne `None`
     - gate enabled + regime=low_vol → trade non bloqué
     - gate enabled + regime=unknown → trade non bloqué (unknown = pas de signal K-Means)
Validation :
  ```
  make qa
  # Attendu : tous tests passent · 0 ruff · 0 pyright
  # Aucun fichier .pyx modifié — make build NON requis
  ```
Dépend de : Aucune
Statut : ✅ 2026-03-25 — make qa vert (581 tests · 0 ruff · 0 pyright)

> ⚠️ Précondition opérationnelle (hors code) : laisser tourner 30 sessions NYSE paper trading en observation (`regime_filter_gate_enabled: false`) avant de passer à `true`. La bascule se fait manuellement dans `config.yaml` après validation observation.

---

## PHASE 3 — MINEURES 🟡

### [C-02] Mettre à jour les features de `_experimental/ml_filter.py` pour Momentum+Carry

Fichier : `alphaedge/engine/_experimental/ml_filter.py:37` (features list)
Problème : Les features actuelles `["atr_ratio", "fcr_range", "volume_ratio", "spread", "day_of_week"]` référencent des champs FCR (`fcr_range`, `volume_ratio`) inexistants dans le dict signal Momentum+Carry. Si le `MLSignalFilter` est jamais activé, le feature extraction lèvera un `KeyError` en production.
Correction :
  1. Mettre à jour `DEFAULT_FEATURE_NAMES` dans `_experimental/ml_filter.py` :
     ```python
     DEFAULT_FEATURE_NAMES: list[str] = [
         "adx",             # ADX value at signal time
         "ema_delta_pct",   # (fast_ema - slow_ema) / slow_ema
         "carry_diff",      # carry differential (absolute value)
         "atr_ratio",       # ATR daily / ATR 20-day avg
         "day_of_week",     # 0=Mon … 4=Fri
     ]
     ```
  2. Mettre à jour le docstring de `MLSignalFilter` pour indiquer ces features Momentum+Carry.
  3. Ajouter un commentaire `# STATUS: features updated for Momentum+Carry — NOT connected to live pipeline`.
  4. Aucune modification des classes publiques — `LIVE_PIPELINE_INTEGRATED = False` reste inchangé.
Validation :
  ```
  make qa
  # Attendu : tous tests passent · 0 ruff · 0 pyright
  # Aucun fichier .pyx modifié — make build NON requis
  ```
Dépend de : Aucune
Statut : ✅ 2026-03-25 — make qa vert (581 tests · 0 ruff · 0 pyright)

---

### [C-03] Documenter le workflow mensuel Bayesian optimization dans `scripts/`

Fichier : `alphaedge/engine/bayesian_optimizer.py:45` · `config.yaml:54`
Problème : `bayesian_optimizer.py` et `walk_forward.py` sont opérationnels mais désactivés (`walk_forward_enabled: false`). Aucun script ni procédure documentée n'existe pour lancer l'optimisation mensuelle offline. Le paramètre `min_body_ratio` dans `_DEFAULT_PARAM_NAMES` est FCR-specific et générerait des erreurs si l'optimiseur était activé maintenant.
Correction :
  1. Dans `alphaedge/engine/bayesian_optimizer.py`, mettre à jour `_DEFAULT_PARAM_NAMES` :
     ```python
     _DEFAULT_PARAM_NAMES: list[str] = [
         "adx_threshold",        # ADX gate (20–35)
         "momentum_fast_period", # EMA fast (8–20)
         "momentum_slow_period", # EMA slow (20–50)
         "rr_ratio",             # Risk/Reward (1.5–3.0)
     ]
     # "min_body_ratio" retiré — FCR-specific, non applicable à Momentum+Carry
     ```
  2. Créer `scripts/run_bayesian_optimization.py` avec :
     - docstring expliquant les prérequis (backtest Momentum+Carry disponible, `walk_forward_enabled: false` en prod)
     - appel à `run_walk_forward()` + `BayesianOptimizer`
     - sortie : `reports/bayesian_opt_result_YYYY-MM-DD.json`
     - gate : n'applique les nouveaux paramètres au `config.yaml` que si Sharpe OOS ≥ baseline × 1.05
  3. Ajouter commentaire dans `config.yaml:54` :
     ```yaml
     walk_forward_enabled: false  # Activer uniquement offline via scripts/run_bayesian_optimization.py
     ```
Validation :
  ```
  make qa
  # Attendu : tous tests passent · 0 ruff · 0 pyright
  # Aucun fichier .pyx modifié — make build NON requis
  ```
Dépend de : Aucune (exécutable indépendamment de C-01 et C-02)
Statut : ✅ 2026-03-25 — make qa vert (581 tests · 0 ruff · 0 pyright)

---

### [C-04] Créer le script d'analyse SHAP offline

Fichier : `scripts/` (nouveau fichier)
Problème : Aucune analyse de l'importance des paramètres n'est planifiée. Une fois le backtest Momentum+Carry disponible, il sera impossible de savoir quels paramètres (`adx_threshold`, `carry_min_differential`, `rr_ratio`) contribuent réellement au Sharpe sans outillage SHAP.
Correction :
  1. Créer `scripts/shap_analysis.py` avec :
     - lecture du CSV backtest (`reports/ALPHAEDGE_backtest_results.csv` ou path configurable)
     - entraînement d'un `RandomForestClassifier` minimal sur les features disponibles
     - calcul des SHAP values via `shap.TreeExplainer`
     - export `reports/shap_report_YYYY-MM-DD.md` avec tableau importance features
     - guard en tête : `if len(df) < 100: raise ValueError("Insufficient data for SHAP analysis")`
  2. Vérifier que `shap` est dans `requirements.txt` — si absent, l'ajouter.
  3. Le script est **offline uniquement** — aucune intégration dans `engine/` ou `session_lifecycle.py`.
Validation :
  ```
  make qa
  # Attendu : tous tests passent · 0 ruff · 0 pyright
  # Script non importé par le pipeline — aucun risque de régression
  # Aucun fichier .pyx modifié — make build NON requis
  ```
Dépend de : Aucune
Statut : ✅ 2026-03-25 — make qa vert (581 tests · 0 ruff · 0 pyright)

---

## SÉQUENCE D'EXÉCUTION

```
C-03  → Bayesian optimizer param names (correctif isolé, aucune dépendance)
C-02  → Features ml_filter (correctif isolé, aucune dépendance)
C-04  → Script SHAP (création fichier, aucune dépendance)
C-01  → Regime gate (modifie strategy.py + config.yaml + constants.py + loader.py + tests)
        make qa  ← validation finale obligatoire
```

> Aucune correction ne modifie de fichier `.pyx` — `make build` NON requis dans ce plan.

---

## CRITÈRES PASSAGE EN PRODUCTION

- [ ] Zéro 🔴 ouvert
- [ ] `make qa` : 100% pass (lint + mypy + pytest ≥80%)
- [ ] Zéro credential dans les logs loguru
- [ ] `ALPHAEDGE_PAPER=true` intact dans `.env.example`
- [ ] Bracket order `is_valid` vérifié avant envoi IB
- [ ] `check_daily_limit()` appelé chaque cycle
- [ ] Paper trading validé 5 sessions NYSE minimum
- [ ] `regime_filter_gate_enabled: false` en `config.yaml` (défaut — observation only) ← spécifique IA/ML
- [ ] 30 sessions NYSE paper en observation avant activation gate ← spécifique IA/ML

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier | Effort | Statut | Date |
|----|-------|----------|---------|--------|--------|------|
| C-01 | Activer flag `regime_filter_gate_enabled` | 🟠 Majeur | `strategy.py:203` · `config.yaml` · `constants.py` · `loader.py` | ~3h | ✅ | 2026-03-25 |
| C-02 | Mettre à jour features `_experimental/ml_filter.py` | 🟡 Mineur | `_experimental/ml_filter.py:37` | ~30min | ✅ | 2026-03-25 |
| C-03 | Workflow Bayesian optimization mensuel | 🟡 Mineur | `bayesian_optimizer.py:45` · `scripts/` | ~1h | ✅ | 2026-03-25 |
| C-04 | Script SHAP offline | 🟡 Mineur | `scripts/shap_analysis.py` (nouveau) | ~1h | ✅ | 2026-03-25 |
