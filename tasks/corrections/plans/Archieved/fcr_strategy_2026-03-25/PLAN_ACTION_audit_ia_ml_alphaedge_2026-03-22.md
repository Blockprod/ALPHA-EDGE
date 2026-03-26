# PLAN D'ACTION — ALPHAEDGE — IA / ML — 2026-03-22
**Créé le :** 2026-03-22 à 16:56
**Sources :** `tasks/audits/audit_ia_ml_alphaedge.md`
**Total :** 🔴 0 · 🟠 1 · 🟡 1 · **Effort estimé : 3–4 jours**

> Contexte : audit IA/ML conclu que 8/10 opportunités sont NON PERTINENTES.
> Seules C (régime de marché K-Means) et D (Optuna walk-forward) sont retenues.
> Aucune modification de `core/*.pyx` requise. Pas de `make build`.

---

## PHASE 1 — CRITIQUES 🔴

*Aucun élément critique identifié dans cet audit.*

---

## PHASE 2 — MAJEURES 🟠

### [C-01] Implémenter `regime_filter.py` — Détection de régime de marché (K-Means)

**Fichier :** `alphaedge/engine/regime_filter.py` *(à créer)*
**Problème :** Le pipeline ne distingue pas les jours de marché "choppy" / basse volatilité des jours favorables au FCR. Le `gap_detector` filtre la volatilité intraday (spike ATR), mais ne classe pas le régime de la journée en amont. Sur des jours de range flat ou de fort trend directionnel sans spike, des signaux FCR valides peuvent être pris sur un contexte journalier défavorable, dégradant le Max DD.
**Correction :**

1. Créer `alphaedge/engine/regime_filter.py` avec :
   - Classe `DailyRegimeFilter` avec méthode `fit(m5_bars_history: list[dict]) -> None`
   - Méthode `predict(session_date: date, pre_session_m5: list[dict]) -> str` retournant `"high_vol"` | `"low_vol"` | `"unknown"`
   - Features journalières : ATR daily (std des ranges M5 J-1), range intraday M5 J-1, spread moyen M1 pré-session (si disponible), momentum (close J-1 vs close J-2)
   - `sklearn.cluster.KMeans(n_clusters=2, random_state=42)` sur features normalisées (`StandardScaler`)
   - Identification automatique du cluster "high_vol" = cluster avec ATR daily moyen le plus élevé
   - Re-calibration mensuelle : méthode `needs_recalibration(last_fit_date: date) -> bool` (True si > 30 jours)
   - Sérialisation du modèle via `joblib` dans `alphaedge/cache/regime_model_{pair}.pkl`

2. **Mode observation uniquement (NIVEAU 1) :** Le filtre logue le régime détecté mais ne bloque aucun trade. Intégration dans `strategy.py` :
   - Import de `DailyRegimeFilter`
   - Instanciation dans `FCRStrategy.__init__()` : `self._regime_filter: DailyRegimeFilter = DailyRegimeFilter()`
   - Appel dans `_detect_fcr()` avant la détection : `regime = self._regime_filter.predict(...)` + log INFO uniquement
   - Aucune condition `if regime == "low_vol": return` — le filtre est passif

3. Ajouter `scikit-learn>=1.4.0` et `joblib>=1.3.0` dans `requirements.txt` (sklearn est souvent déjà présent comme dépendance indirecte via vectorbt — vérifier avant d'ajouter)

4. Créer `alphaedge/tests/test_regime_filter_kmeans.py` :
   - Test `test_fit_does_not_raise` : fit sur 30 jours de données synthétiques M5
   - Test `test_predict_returns_valid_label` : predict retourne une des 3 valeurs attendues
   - Test `test_needs_recalibration_after_30d` : vérifie la logique de recalibration
   - Test `test_unknown_on_no_data` : predict avec liste vide retourne `"unknown"` sans exception

**Validation :**
```powershell
python -m pytest alphaedge/tests/test_regime_filter_kmeans.py -v
python -m ruff check alphaedge/engine/regime_filter.py alphaedge/tests/test_regime_filter_kmeans.py
python -m pyright alphaedge/engine/regime_filter.py
python -m pytest alphaedge/tests/ -q
# Attendu : 508+ passed (504 existants + 4 nouveaux), 0 ruff, 0 pyright
```

> ⚠️ Aucun `core/*.pyx` modifié — `make build` non requis.
> ⚠️ Mode observation obligatoire : le filtre ne bloque AUCUN trade lors de la première intégration.
> ⚠️ Vérifier que sklearn est disponible : `python -c "import sklearn; print(sklearn.__version__)"` avant implémentation.

**Dépend de :** Aucune
**Statut :** ✅ 2026-03-22

---

## PHASE 3 — MINEURES 🟡

### [C-02] Implémenter `bayesian_optimizer.py` — Remplacement du grid search par Optuna

**Fichier :** `alphaedge/engine/bayesian_optimizer.py` *(à créer)*
**Problème :** `sensitivity.grid_search_best()` ([sensitivity.py:189–231](../../alphaedge/engine/sensitivity.py)) effectue un produit Cartésien sur 5 paramètres × 5–15 valeurs = jusqu'à 3 125 backtests par fenêtre walk-forward. Cela rend l'optimisation IS/OOS prohibitivement lente sur de grands espaces de paramètres. Optuna (TPE sampler) explore l'espace de façon intelligente et atteint des résultats équivalents en 100–200 trials (facteur 10–15× moins de temps de calcul).
**Correction :**

1. Créer `alphaedge/engine/bayesian_optimizer.py` avec :
   - Fonction publique : `optuna_search_best(m1_bars: list[dict], m5_bars: list[dict], pair: str, config: AppConfig, n_trials: int = 150, metric: str = "sharpe") -> dict[str, float]`
   - Signature identique à `sensitivity.grid_search_best()` pour compatibilité directe avec `optimize_fn` de `run_walk_forward()`
   - Espace de recherche (identique à `SENSITIVITY_PARAMS` dans sensitivity.py) :
     - `min_atr_ratio` : FloatDistribution(1.0, 2.5)
     - `min_volume_ratio` : FloatDistribution(1.0, 2.0)
     - `min_range_pips` : FloatDistribution(3.0, 15.0)
     - `rr_ratio` : FloatDistribution(2.0, 4.0)
     - `min_body_ratio` : FloatDistribution(0.1, 0.5)
   - Sampler : `optuna.samplers.TPESampler(seed=42)` pour reproductibilité
   - Direction : `"maximize"`
   - Suppression des logs Optuna verbeux : `optuna.logging.set_verbosity(optuna.logging.WARNING)`
   - Pruning : `MedianPruner` (abort les trials clairement inférieurs à la médiane après 20 trials)
   - Retourne le meilleur `dict[str, float]` de paramètres (même format que `grid_search_best`)

2. Ajouter `optuna>=3.6.0` dans `requirements.txt`

3. **Ne pas modifier `walk_forward.py` ni `sensitivity.py`** — `optuna_search_best` est passé comme `optimize_fn` optionnelle, l'API est compatible sans changement.

4. Créer `alphaedge/tests/test_bayesian_optimizer_search.py` :
   - Test `test_returns_valid_param_dict` : vérifie que le retour est un dict avec les clés attendues
   - Test `test_param_values_in_range` : vérifie que chaque valeur retournée est dans son intervalle
   - Test `test_n_trials_respected` : vérifie que l'optimisation ne dépasse pas `n_trials`
   - Test `test_metric_sharpe_vs_pf` : vérifie que l'argument `metric="pf"` change le critère d'optimisation
   - Utiliser des données synthétiques M1/M5 minimales (10–20 barres) pour rendre les tests rapides (<2s)

**Validation :**
```powershell
python -m pytest alphaedge/tests/test_bayesian_optimizer_search.py -v
python -m ruff check alphaedge/engine/bayesian_optimizer.py alphaedge/tests/test_bayesian_optimizer_search.py
python -m pyright alphaedge/engine/bayesian_optimizer.py
python -m pytest alphaedge/tests/ -q
# Attendu : 512+ passed (508 existants + 4 nouveaux), 0 ruff, 0 pyright
```

> ⚠️ Aucun `core/*.pyx` modifié — `make build` non requis.
> ⚠️ `optuna` doit être installé dans le venv AVANT les tests : `pip install optuna>=3.6.0`.
> ⚠️ Ne pas remplacer `grid_search_best` comme optimize_fn par défaut — laisser le choix à l'utilisateur via un paramètre explicite.

**Dépend de :** Aucune (C-01 et C-02 sont indépendants)
**Statut :** ✅ 2026-03-22

---

## SÉQUENCE D'EXÉCUTION

```
C-01 (🟠) — regime_filter.py
    └─ Vérifier sklearn disponible
    └─ Créer alphaedge/engine/regime_filter.py
    └─ Intégrer dans strategy.py (mode observation)
    └─ Créer test_regime_filter_kmeans.py
    └─ python -m pytest alphaedge/tests/ -q → 508+ passed

C-02 (🟡) — bayesian_optimizer.py
    └─ pip install optuna>=3.6.0
    └─ Créer alphaedge/engine/bayesian_optimizer.py
    └─ Créer test_bayesian_optimizer_search.py
    └─ python -m pytest alphaedge/tests/ -q → 512+ passed
```

> C-01 et C-02 sont indépendants — peuvent être exécutés dans n'importe quel ordre.
> Aucun `make build` requis dans cette séquence.
> Valider `python -m ruff check alphaedge/` + `python -m pyright alphaedge/` à chaque étape.

---

## CRITÈRES PASSAGE EN PRODUCTION

- [ ] Zéro 🔴 ouvert
- [ ] `python -m pytest alphaedge/tests/ -q` : 100% pass (lint + mypy + pytest ≥80%)
- [ ] Zéro credential dans les logs loguru
- [ ] `ALPHAEDGE_PAPER=true` intact dans `.env.example`
- [ ] Bracket order `is_valid` vérifié avant envoi IB
- [ ] `check_daily_limit()` appelé chaque cycle
- [ ] `DailyRegimeFilter` en mode observation (log seulement, aucun blocage trade) pendant 30 sessions NYSE minimum avant activation
- [ ] Paper trading validé 5 sessions NYSE minimum après intégration C-01

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier | Effort | Statut | Date |
|----|-------|----------|---------|--------|--------|------|
| C-01 | Régime de marché K-Means (mode observation) | 🟠 | `engine/regime_filter.py` (nouveau) | 1.5 jours | ✅ | 2026-03-22 |
| C-02 | Optuna walk-forward optimizer | 🟡 | `engine/bayesian_optimizer.py` (nouveau) | 1 jour | ✅ | 2026-03-22 |

---

## OPPORTUNITÉS EXPLICITEMENT EXCLUES

Ces 8 opportunités identifiées dans l'audit sont définitivement fermées.
Ne pas les rouvrir sans nouvelle analyse de données (>1000 trades OOS).

| ID | Opportunité | Raison d'exclusion |
|----|-------------|-------------------|
| A | Filtre ML qualité FCR (RF/XGBoost) | <400 samples/an → surapprentissage garanti. `fcr_range_cv_max` couvre le besoin. |
| B | Filtre ML signal engulfing | <200 samples/an → surapprentissage garanti. `min_body_ratio` configurable suffit. |
| E | Sizing dynamique risk_pct | Casse fixed-fraction model (`backtest_stats._apply_equity_sizing`). Amplifie les DD. |
| F | Sélection paires ML | `max_trades_per_session` + `pair_sessions` couvrent déjà. Données 1h/session insuffisantes. |
| G | Stop-loss dynamique ML | Requiert modification `order_manager.pyx` (make build + régression). Casse R:R validation. |
| H | LLM sentiment macro | Latence 1–10s incompatible event-driven M1. `news_filter.py` couvre le besoin. |
| I | SHAP values paramètres FCR | `sensitivity.find_robustness_plateau()` équivalent, déterministe. Couche ML inutile. |
| J | Walk-forward adaptatif fenêtres | 3–4 cycles = bruit pur. Paramètres `train_months`/`test_months` déjà configurables. |
