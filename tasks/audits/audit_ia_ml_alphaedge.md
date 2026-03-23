# AUDIT IA / ML — ALPHAEDGE FCR Trading Bot
**Date :** 2026-03-22
**Auditeur :** Senior Quantitative Engineer
**Baseline QA :** 504 tests · 0 ruff · 0 pyright
**Sharpe baseline :** 3.37 (IS, 1 an EUR/USD, compte $10 000, risk_pct=3%)

---

## PHASE 1 — DIAGNOSTIC DE L'EXISTANT

### 1.1 Signal FCR et pipeline actuel

#### Détecteurs Cython actifs

Le pipeline live est **100 % déterministe**. Aucun ML n'est présent dans la chaîne d'exécution.

| Module | Fichier | Rôle |
|--------|---------|------|
| `fcr_detector.pyx` | `alphaedge/core/fcr_detector.pyx` | Détection de range FCR sur barres M5 |
| `gap_detector.pyx` | `alphaedge/core/gap_detector.pyx` | Filtre de spike ATR / volatilité |
| `engulfing_detector.pyx` | `alphaedge/core/engulfing_detector.pyx` | Signal d'entrée M1 (engulfing 2 bougies) |
| `risk_manager.pyx` | `alphaedge/core/risk_manager.pyx` | Sizing et daily loss limit |
| `order_manager.pyx` | `alphaedge/core/order_manager.pyx` | Validation bracket order |

Orchestration : `strategy.py` → `signal_pipeline.py` → Cython detectors.
Référence : [signal_pipeline.py](../../alphaedge/engine/signal_pipeline.py) lignes 29–107.

#### Génération du signal d'entrée M1

La méthode `detect_engulfing()` ([signal_pipeline.py:69–107](../../alphaedge/engine/signal_pipeline.py)) itère sur les barres M1 de la session. Pour chaque barre :

1. `_is_bearish()` / `_is_bullish()` — direction (close vs open)
2. `_has_volume_confirmation()` — volume ≥ avg × `min_volume_ratio`
3. `_passes_quality()` — body ≥ `min_body_ratio` × range FCR, wick ≤ `max_wick_ratio` × body
4. `_build_result()` — calcule entry, SL (bas/haut de l'engulfing), TP = entry ± risk × rr_ratio

#### Paramètres FCR configurables

Tous externalisés dans [constants.py](../../alphaedge/config/constants.py) et surchargés via [config.yaml](../../config.yaml) :

| Paramètre | Valeur live | Fichier:ligne | YAML override |
|-----------|-------------|---------------|---------------|
| `DEFAULT_MIN_RANGE_PIPS` | 8.0 | constants.py:81 | `structure.min_range_pips: 8.0` |
| `DEFAULT_FCR_LOOKBACK` | 6 | constants.py:82 | — |
| `DEFAULT_ATR_PERIOD` | 14 | constants.py:74 | `volatility.atr_period: 14` |
| `DEFAULT_MIN_ATR_RATIO` | 2.0 (constants) / **1.7 (live)** | constants.py:75 | `volatility.min_atr_ratio: 1.7` |
| `DEFAULT_VOLUME_PERIOD` | 20 | constants.py:79 | `pattern.volume_period: 20` |
| `DEFAULT_MIN_VOLUME_RATIO` | 1.0 | constants.py:80 | `pattern.min_volume_ratio: 1.0` |
| `DEFAULT_MIN_BODY_RATIO` | 0.3 | constants.py:85 | `engulfing.min_body_ratio: 0.3` |
| `DEFAULT_MAX_WICK_RATIO` | 1.5 | constants.py:86 | `engulfing.max_wick_ratio: 1.5` |
| `DEFAULT_RR_RATIO` | 2.5 (constants) / **2.0 (live)** | constants.py:52 | `risk.reward_ratio: 2.0` |
| `DEFAULT_RISK_PCT` | 2.0 % | constants.py:53 | `trading.risk_pct: 3.0` (live override) |
| `DEFAULT_MAX_DAILY_LOSS_PCT` | 3.0 % | constants.py:54 | `trading.max_daily_loss_pct: 3.0` |
| `DEFAULT_MAX_TRADES_PER_SESSION` | 2 | constants.py:55 | `trading.max_trades_per_session: 6` |
| `fcr_range_cv_max` | 0.5 | loader.py:87 | `structure.fcr_range_cv_max: 0.5` |

> **Divergence notable :** `min_atr_ratio` dans constants.py vaut 2.0, mais config.yaml override à 1.7. C'est la valeur live. `max_trades_per_session` = 6 dans config.yaml vs 2 dans constants.py.

#### Filtre de régime de marché existant

**Oui, partial.** `gap_detector` joue le rôle de filtre de régime de marché implicite :
- Il calcule un ATR sur les barres M1 pré-session
- Il compare au spike de la première barre M1 d'ouverture de session
- Si `atr_ratio < min_atr_ratio` (1.7 live) → pip STOP, trade annulé

Ce n'est pas un classifieur de régime (trending/ranging/choppy), mais un simple seuil de spike ATR. Il filtre les jours de basse volatilité de façon déterministe.

#### ml_filter.py : statut

**Code orphelin en production — 0 % intégré au pipeline live.**

[`alphaedge/engine/ml_filter.py`](../../alphaedge/engine/ml_filter.py) (37 lignes) est un **shim de ré-export** seulement :

```python
# Lines 8–10 : "All ML filter logic has been moved to _experimental
#               (pending strategic validation before live-pipeline integration)"
from alphaedge.engine._experimental.ml_filter import (
    DEFAULT_WIN_THRESHOLD, FEATURE_NAMES, MLFilterResult,
    MLSignalFilter, SignalFeatures, WalkForwardMLReport,
    extract_features, walk_forward_ml
)
```

`strategy.py` et `signal_pipeline.py` n'importent **pas** `ml_filter`. Aucun appel `predict()`, `fit()`, ou `score()` dans les chemins live.

---

### 1.2 Données disponibles

| Source | Contenu | Granularité | Profondeur |
|--------|---------|-------------|------------|
| IB `reqHistoricalData` | OHLCV barres | M1 + M5 | 7 jours (M1) / 30 jours (M5) par chunk |
| `BarDiskCache` (.pkl) | Cache rolling disque | M1 + M5 | Cumule sur 1 an (`backtest_years=1`) |
| `reports/ALPHAEDGE_backtest_results.csv` | Trade-by-trade export | Par trade | ~1 an de trades simulés |

**Schéma d'un trade (CSV headers) :**
```
pair, direction, entry_price, exit_price, stop_loss, take_profit,
pnl_pips, pnl_usd, pnl_eur, outcome, entry_time, exit_time, sample_type
```

**Volume estimé de trades backtest :** l'échantillon visible montre EURUSD + USDJPY sur Jan 2024 et Jan–Mar 2025. Avec `min_atr_ratio: 1.7` (filtre peu sélectif) et 6 paires × sessions London/NYSE, on estime **200–400 trades/an** en simulation. C'est faible pour entraîner un classifieur ML.

**Colonnes absentes du CSV :** features de marché au moment du signal (ATR, spread, volume_ratio, range_size) — elles ne sont pas exportées. Toute tentative de ML nécessiterait une nouvelle passe de backtest pour exporter ces features.

---

### 1.3 Infrastructure et contraintes techniques

| Dimension | Valeur | Impact ML |
|-----------|--------|-----------|
| Python | 3.11.9, Windows | Compatible sklearn, xgboost, optuna |
| Session trading | 1h/jour/paire (London 08:00–09:00 UTC ou NYSE 09:30–10:30 ET) | Très peu de trades → données rares |
| Event-driven | `reqRealTimeBars` push 5s → M1 agrégation | Latence ML doit être < 1s |
| Reconnexion asyncio | IB Gateway → ib_insync async | Tout modèle ML doit être pre-loaded |
| Cython core | `.pyx` compilés, pas en Python runtime | Injection ML possible uniquement en Python wrapper |
| Backtest IB | Chunked fetch, 3 concurrent max (`IB_MAX_CONCURRENT_HIST_REQUESTS`) | Dataset collection lente |
| News filter | `blackout_minutes=15` autour d'événements H-impact | Filtre existant cover le cas d'usage LLM |

**Contrainte critique :** La fenêtre M1 arrive toutes les 5 secondes (barres temps-réel). Un modèle ML qui s'exécute en <50 ms est nécessaire pour ne pas bloquer la boucle asyncio. Toute inference GPU ou LLM call est hors contrainte.

---

### 1.4 Carte des points de décision — fichier:ligne

| Stage | Paramètre décisionnel | Valeur actuelle | Fichier:ligne | Type |
|-------|----------------------|-----------------|---------------|------|
| **FCR Detection** | `min_range_pips` | 8.0 pips | signal_pipeline.py:36 + constants.py:81 | Seuil fixe |
| **FCR Detection** | `fcr_range_cv_max` | 0.5 | loader.py:87 / signal_pipeline.py:35 | Seuil qualité |
| **FCR Detection** | `fcr_lookback` | 6 barres M5 | signal_pipeline.py:38 | Fixe |
| **Gap Detection** | `min_atr_ratio` | 1.7 (config.yaml) | signal_pipeline.py:55 + constants.py:75 | Seuil filtre volatilité |
| **Gap Detection** | `atr_period` | 14 barres M1 | signal_pipeline.py:54 + constants.py:74 | Fenêtre ATR |
| **Engulfing** | `min_volume_ratio` | 1.0 | signal_pipeline.py:86 + constants.py:80 | Seuil volume |
| **Engulfing** | `min_body_ratio` | 0.3 | signal_pipeline.py:82 + constants.py:85 | Qualité bougie |
| **Engulfing** | `max_wick_ratio` | 1.5 | signal_pipeline.py:83 + constants.py:86 | Qualité mèche |
| **Risk** | `risk_pct` | 3.0 % | loader.py:63 / config.yaml | Sizing fixe |
| **Risk** | `max_daily_loss_pct` | 3.0 % | loader.py:64 + constants.py:54 | Halt trading |
| **Risk** | `max_trades_per_session` | 6 | loader.py:65 + config.yaml | Cap fixe |
| **Order** | `rr_ratio` | 2.0 | loader.py:62 / config.yaml | SL/TP fixe |
| **Order** | `max_spread_pips` | 2.0 | loader.py:66 + constants.py:56 | Filtre spread |
| **Paires** | `pairs` list | 6 paires fixes | loader.py:57–61 | Liste statique |
| **Session** | `pair_sessions` dict | London/NYSE fixe | loader.py:89 | Fenêtre fixe |
| **News** | `blackout_minutes` | 15 min | config.yaml:96–101 | Filtre calendrier |

**Conclusion Phase 1 :** 15 points de décision, tous déterministes, tous configurable via YAML. Aucun point d'adaptation dynamique.

---

## PHASE 2 — ÉVALUATION DES OPPORTUNITÉS IA/ML

---

### A — Filtre ML sur la qualité du range FCR

**Idée :** Classifier (Random Forest, XGBoost) entraîné sur les features du range FCR (taille, position, contexte ATR) pour prédire la probabilité que le range soit respecté.

**Analyse :**

- **Volume de données :** ~200–400 FCR events/an retenus (d'abord filtrés par `min_range_pips`). Les labels sont bruités — la sortie (win/loss) dépend de tout le pipeline, pas du FCR seul.
- **Features exportées :** Le CSV backtest ne contient pas les features FCR (range_size, cv, atr_context). Une passe de ré-export serait nécessaire.
- **Surapprentissage :** Sur 200 trades/an, un Random Forest à 100 arbres va mémoriser. OOS dégradation prévisible.
- **Gain attendu :** Réduire les faux FCR → moins de trades, Sharpe potentiellement supérieur. Mais Sharpe=3.37 baseline est déjà excellent. Le risque de casser cette performance est réel.
- **Compatibilité pipeline :** Injection possible entre `detect_fcr()` et `detect_gap()` dans `signal_pipeline.py` — pas de modification Cython requise.
- **Données suffisantes :** ❌ Non — 200-400 échantillons sur 1 an est insuffisant pour un classifieur robuste en OOS.

| Critère | Évaluation |
|---------|-----------|
| Gain attendu | Faible à moyen (moins de trades, Sharpe ambigu) |
| Complexité | M (export features + entraînement + injection) |
| Risque prod | Élevé (surapprentissage, dégradation Sharpe) |
| Fenêtre 1h/jour | Neutre (exécuté pré-trade, <1ms) |
| Données suffisantes | ❌ Non (200-400 samples/an) |
| Incompatibilité Cython | Non (wrapper Python uniquement) |

**VERDICT : ❌ NON PERTINENT**
Donnée insuffisante pour généralisation OOS. Risque élevé de casser le Sharpe=3.37. Le filtre `fcr_range_cv_max` existant couvre déjà la qualité de range de façon déterministe.

---

### B — Filtre ML sur le signal engulfing

**Idée :** Classifier qui valide/rejette `detect_engulfing()` avec features contextuelles (volume relatif, distance au range, spread).

**Analyse :**

- **Volume de données :** Les signals engulfing retenus en backtest sont encore plus rares que les FCR (pipeline all-or-nothing : FCR → Gap → Engulfing = 3 filtres). Estimation : 100–200 signaux engulfing/an.
- **Labels bruités :** Un signal engulfing "correct" peut échouer à cause du spread, slippage, ou d'un événement macro. Label = outcome du trade ≠ qualité du signal.
- **Features additionnelles :** `min_body_ratio`, `max_wick_ratio`, `min_volume_ratio` couvrent déjà les dimensions de qualité. Ajouter un ML pour les mêmes dimensions = redondance.
- **Compatibilité all-or-nothing :** Rejeter un signal engulfing en ajout ≈ ajouter un filtre rules-based. Un seuil plus strict sur `min_body_ratio` produirait le même effet sans complexité.

| Critère | Évaluation |
|---------|-----------|
| Gain attendu | Très faible (filtres rule-based équivalents) |
| Complexité | M |
| Risque prod | Élevé (surapprentissage sur ~150 samples) |
| Fenêtre 1h/jour | Neutre |
| Données suffisantes | ❌ Non (<200 samples) |
| Incompatibilité Cython | Non |

**VERDICT : ❌ NON PERTINENT**
Les filtres rules-based existants (`min_body_ratio`, `max_wick_ratio`, `min_volume_ratio`) couvrent déjà la qualité du signal engulfing. Un ML sur <200 samples = surapprentissage garanti. Ajuster `min_body_ratio` à 0.4 produit le même effet, sans risque, et teste en 30 secondes.

---

### C — Détection de régime de marché Forex

**Idée :** Clustering (K-Means ou HMM) sur volatilité ATR, momentum M5, pour classifier les journées en régimes high/low volatility. Coupler avec `gap_detector` pour filtrer les journées à basse volatilité ou forte tendance directionnelle.

**Analyse :**

- **Pertinence conceptuelle :** Le `gap_detector` filtre déjà la volatilité intraday (spike ATR). Mais il ne distingue pas les jours de trend fort (EUR/USD en tendance directionnelle sur plusieurs heures) où le FCR range peut être cassé rapidement. Une détection de régime **pré-session** (la veille ou avant l'ouverture) est complémentaire.
- **Données disponibles :** 252 jours de barres M5/an pour EUR/USD. K-Means à 2–3 clusters sur features journalières (ATR daily, range M5 pré-session, volume moyen) = 252 points minimum. Marginal mais fonctionnel.
- **Features simples :** ATR daily (std des hauts-bas M5 sur la journée), spread moyen, momentum (close J-1 vs close J). Calculables depuis le cache disk M5 existant.
- **Latence :** Calcul pré-session unique par jour (<100ms), pas dans la boucle event-driven. Aucun conflit asyncio.
- **Risque prod :** K-Means ne garantit pas de stabilité d'un régime à l'autre. Les frontières de régime peuvent être instables en période de transition (Fed announcement, crise géopolitique). Risque de over-filtering = réduction excessive du nombre de trades.
- **Impact sur Cython :** Zéro modification de `.pyx` requise. Un flag `regime_ok: bool` en Python avant d'appeler `signal_pipeline.detect_fcr()` suffit.
- **Implémentation recommandée :** sklearn `KMeans(n_clusters=2)` sur features journalières normalisées. Cluster "haute volatilité" = trading autorisé. Entraîner sur 1 an, re-calibrer mensuellement (compatible avec walk_forward existant).

| Critère | Évaluation |
|---------|-----------|
| Gain attendu | Moyen — réduit les trades sur jours choppy (impact max DD) |
| Complexité | S (50 lignes Python + sklearn) |
| Risque prod | Moyen (instabilité clustering, over-filtering) |
| Fenêtre 1h/jour | ✅ Calcul pré-session, hors boucle event |
| Données suffisantes | ⚠️ Marginal (252 jours/an, acceptable pour K=2) |
| Incompatibilité Cython | ✅ Aucune — wrapper Python pur |

**VERDICT : ✅ PERTINENT** (NIVEAU 1 — observation uniquement d'abord)
C'est l'opportunité ML la plus réaliste sur ce projet. Features simples, latence nulle, aucune modification Cython. **Condition :** démarrer en mode logging (log le régime détecté mais ne bloque pas les trades) sur 30 sessions NYSE avant activation.

---

### D — Optimisation bayésienne des paramètres FCR (Optuna)

**Idée :** Remplacer le grid search Cartésien de `sensitivity.grid_search_best()` par une optimisation bayésienne (Optuna) pour explorer l'espace de paramètres plus efficacement, dans le framework walk-forward existant.

**Analyse :**

- **Infrastructure existante :** `walk_forward.py` supporte déjà un `optimize_fn` optionnel ([walk_forward.py:117–163](../../alphaedge/engine/walk_forward.py)). `sensitivity.grid_search_best()` est passé comme `optimize_fn`. Il suffit de créer une alternative Optuna.
- **Gain concret :** Le Cartesian product sur 5 paramètres × 5–15 valeurs chacun = 5^5 = 3 125 backtests. Optuna avec 100–200 trials couvre l'espace de façon plus intelligente (TPE sampler), avec 10–15× moins de temps de calcul.
- **Données nécessaires :** Seulement le cache disk M1+M5 (déjà présent). Pas de données ML supplémentaires.
- **Risque prod :** L'optimisation est **hors live** — elle s'exécute sur l'IS window du walk-forward, pas en production. Le risque est uniquement le suroptimisation IS → dégradation OOS, qui est déjà surveillé par le framework walk-forward.
- **Compatibilité :** `optimize_fn(m1_bars, m5_bars, pair, config) -> dict[str, float]` — signature identique à celle attendue par `run_walk_forward()`. Optuna remplace uniquement l'implémentation interne.
- **Implémentation :** `optuna.create_study(direction="maximize")` avec `study.optimize(objective, n_trials=150)`. L'`objective` appelle `_run_with_params()` de `sensitivity.py`. ~80 lignes Python, aucune modification Cython.

| Critère | Évaluation |
|---------|-----------|
| Gain attendu | Élevé (exploration paramétrique plus efficace, moins de temps de calcul) |
| Complexité | S (wrapper Optuna autour de _run_with_params) |
| Risque prod | Faible (exécuté hors live, résultat = dict de paramètres) |
| Fenêtre 1h/jour | ✅ Neutre (calcul offline pré-session ou périodique) |
| Données suffisantes | ✅ Oui (uses existing M1+M5 cache) |
| Incompatibilité Cython | ✅ Aucune |

**VERDICT : ✅ PERTINENT** (NIVEAU 2 — intégration immédiate dans le framework walk_forward)
Remplacer le grid search par Optuna est le changement de meilleur ROI dans le projet actuel. La compatibilité avec l'architecture `optimize_fn` est parfaite. Pas de risque de régression live.

---

### E — Prédiction du sizing optimal (risk_pct dynamique)

**Idée :** Régression ML sur les conditions de marché (ATR, spread, heure dans la session) pour ajuster `risk_pct` dynamiquement par trade.

**Analyse :**

- **Incompatibilité avec le modèle fixed-fraction :** `backtest_stats.py:193–224` implémente un compound fixed-fraction sizing (`_apply_equity_sizing()`). Ce modèle suppose un `risk_pct` constant. Un `risk_pct` variable casse l'invariance de ce calcul et invalide les métriques IS/OOS comparées.
- **Amplification des drawdowns :** Un sizing variable augmente le risque en cas de mauvaise prédiction. Si le modèle augmente `risk_pct` sur un trade qui perd, la perte réelle est amplifiée.
- **Volume de données insuffisant :** Entraîner une régression sur les conditions de marché nécessite des milliers de trades. 200–400 trades/an = régression bruit-dominant.
- **Daily loss limit :** `check_daily_limit()` s'appuie sur `max_daily_loss_pct`. Un `risk_pct` dynamique peut dépasser la limite réelle sans que le check ne le détecte correctement sur la comptabilisation pips.

| Critère | Évaluation |
|---------|-----------|
| Gain attendu | Ambigu (peut amplifier gains ET pertes) |
| Complexité | L (refactor backtest_stats.py + modèle ML) |
| Risque prod | Élevé (casse fixed-fraction invariance, amplifie DD) |
| Fenêtre 1h/jour | Neutre |
| Données suffisantes | ❌ Non |
| Incompatibilité Cython | Non |

**VERDICT : ❌ NON PERTINENT**
Casse le modèle de comptabilisation fixed-fraction. Amplifie le risque sans bénéfice prouvable sur le volume de données disponibles. Risk-adjusted return actuel (Sharpe=3.37) déjà optimal sur le test IS.

---

### F — Agent de sélection de paires Forex

**Idée :** Agent ML qui sélectionne dynamiquement EUR/USD, GBP/USD, USD/JPY selon volatilité et corrélations intraday.

**Analyse :**

- **Opportunité réelle mais pas ML :** La matrice de corrélation entre paires USD (EURUSD/GBPUSD/AUDUSD sont corrélés ~0.8–0.95 intraday) est calculable de façon déterministe. Un seuil rules-based (`if |corr(EURUSD_returns, GBPUSD_returns)| > 0.9 and both_signaled: skip GBPUSD`) suffit.
- **Fenêtre 1h :** 6 paires sur 2 sessions (London + NYSE) = max 12 opportunités/jour. `max_trades_per_session: 6` limite naturellement le sur-trading. L'agent de sélection est redondant.
- **Un cluster K-Means sur corrélations de paires :** données trop bruitées sur 1h de window par session. La corrélation intraday varie fortement selon les événements macro.
- **Risque :** Bloquer des paires "corrélées" peut supprimer des trades profitables si la corrélation est temporaire. Over-filtering à nouveau.

| Critère | Évaluation |
|---------|-----------|
| Gain attendu | Faible (filtres déjà présents, 6 paires only) |
| Complexité | M (si ML) / XS (si règles corrélation) |
| Risque prod | Moyen (over-filtering) |
| Fenêtre 1h/jour | Problème structurel (peu de données intraday) |
| Données suffisantes | ❌ Insuffisant pour ML (1h/session) |
| Incompatibilité Cython | Non |

**VERDICT : ❌ NON PERTINENT** (pour ML)
Le filtrage par corrélation de paires se fait avec 10 lignes de règles Python, sans ML. `max_trades_per_session` et `pair_sessions` (London/NYSE split) couvrent déjà la diversification temporelle. Si le filtre corrélation est souhaité, l'implémenter en rules-based dans `session_lifecycle.py` suffit amplement.

---

### G — Agent de gestion dynamique du stop-loss

**Idée :** Agent ML qui ajuste le niveau SL de `create_bracket_order()` selon la volatilité ATR réalisée de la session.

**Analyse :**

- **Incompatibilité directe avec bracket order IB :** `create_bracket_order()` valide le ratio `(TP - entry) / (entry - SL) ≥ rr_ratio`. Un SL ajusté dynamiquement modifie ce ratio. Si le SL s'élargit, le ratio R:R diminue, et `is_valid` peut retourner `False` → trade annulé.
- **Modification Cython requise :** Le calcul du SL vient de `detect_engulfing()` (bas/haut de la bougie engulfing + buffer). Modifier le SL post-Cython nécessite une logique Python supplémentaire qui peut entrer en conflit avec les checks internes de `order_manager.pyx`. Si on modifie `order_manager.pyx` : **`make build` obligatoire**, risque de régression sur les 504 tests.
- **Fixed-fraction model :** `risk_manager.calculate_position_size()` prend `sl_pips` pour calculer le lot size. Un SL dynamique change le lot size à chaque trade — interaction complexe avec la comptabilisation P&L en backtest.

| Critère | Évaluation |
|---------|-----------|
| Gain attendu | Ambigu (peut réduire fausses sorties mais casse R:R) |
| Complexité | L (interaction broker + Cython) |
| Risque prod | Élevé (is_valid failures, lot size incorrect) |
| Fenêtre 1h/jour | Neutre |
| Données suffisantes | ❌ Non |
| Incompatibilité Cython | ⚠️ Oui — modification order_manager.pyx requise |

**VERDICT : ❌ NON PERTINENT**
Incompatible avec la logique de validation bracket order. Nécessite modification de `core/*.pyx` (coût `make build` + risque régression). Casse le modèle fixed-fraction de comptabilisation.

---

### H — Agent LLM pour le sentiment macro Forex

**Idée :** LLM pour analyser news économiques (NFP, CPI, Fed) et filtrer les signaux FCR les jours de forte volatilité.

**Analyse :**

- **news_filter.py déjà en place :** Le module `EconomicNewsFilter` (importé dans `strategy.py`) applique déjà un blackout de 15 minutes autour des événements H-impact via calendrier économique. Ce use case est **entièrement couvert**.
- **Latence incompatible :** Une API LLM (GPT-4, Claude) prend 1–10 secondes de round-trip. Les barres M1 arrivent toutes les 5 secondes via `reqRealTimeBars`. Une LLM call dans la boucle asyncio bloquerait l'événement suivant.
- **Fiabilité Forex vs crypto :** Forex réagit à des publications macro à horaires fixes (NFP le premier vendredi du mois, CPI, Fed minutes…). Le calendrier économique est plus fiable qu'un LLM pour prédire l'impact.
- **Coût opérationnel :** API LLM = coût variable, rate limits, dépendance externe en live. Risque opérationnel inutile.
- **Hallucinations :** Un LLM peut "inventer" un sentiment baissier sur EUR/USD alors que la publication est neutre. Zéro traçabilité de l'erreur.

| Critère | Évaluation |
|---------|-----------|
| Gain attendu | Nul (news_filter.py couvre déjà le cas) |
| Complexité | L (API LLM, gestion rate limits, prompt engineering) |
| Risque prod | Élevé (latence, hallucinations, coût) |
| Fenêtre 1h/jour | ❌ Incompatible (latence API > période M1) |
| Données suffisantes | N/A |
| Incompatibilité Cython | Non |

**VERDICT : ❌ NON PERTINENT**
`news_filter.py` couvre le cas d'usage. Un LLM ajoute de la latence, du coût et du risque d'hallucination sans bénéfice. Jamais à utiliser dans une boucle event-driven avec contrainte <1s.

---

### I — SHAP values sur les paramètres FCR

**Idée :** Analyse SHAP pour identifier quels paramètres FCR contribuent réellement au Sharpe.

**Analyse :**

- **`sensitivity.py` couvre déjà ce besoin :** `run_sensitivity_2d()` produit des heatmaps 2D (Sharpe grid) pour chaque paire de paramètres. `find_robustness_plateau()` identifie les régions stables. Ces outils donnent une visualisation directe de l'importance des paramètres sans nécessiter de modèle ML intermédiaire.
- **SHAP requiert un modèle :** Il faut d'abord entraîner un XGBoost/RF sur (features, outcome), puis calculer SHAP. Avec 200–400 trades, le modèle intermédiaire sera bruité → les SHAP values hériteront du bruit.
- **Valeur ajoutée nulle vs heatmap :** Une heatmap de sensibilité sur `min_atr_ratio` × `min_range_pips` donne la même information "importance paramètre" de façon directe et déterministe.

| Critère | Évaluation |
|---------|-----------|
| Gain attendu | Nul (sensitivity.py + robustness plateau équivalent) |
| Complexité | M (pipeline SHAP) |
| Risque prod | Faible (analyse offline) |
| Fenêtre 1h/jour | Neutre |
| Données suffisantes | ❌ Non (200–400 trades → modèle bruité) |
| Incompatibilité Cython | Non |

**VERDICT : ❌ NON PERTINENT**
`sensitivity.py:find_robustness_plateau()` répond au même besoin de façon directe et déterministe. SHAP ajoute une couche d'approximation sans gain d'information.

---

### J — Walk-forward adaptatif (fenêtre IS/OOS dynamique)

**Idée :** Ajustement automatique des fenêtres IS/OOS selon la volatilité détectée du marché Forex.

**Analyse :**

- **Données insuffisantes pour calibration :** Avec 1 an de données, `run_walk_forward()` produit 3–4 cycles IS/OOS (train_months=3, step=1). Calibrer la dynamique des fenêtres sur 3–4 cycles = bruit pur.
- **Fenêtres fixes déjà raisonnables :** 3 mois IS / 1 mois OOS est une configuration standard. La fenêtre est déjà paramétrable (`train_months`, `test_months`, `step_months` dans `walk_forward.py:95`).
- **Sur-ingénierie :** L'adaptation des fenêtres ne peut améliorer les résultats que si la stationnarité du marché varie systématiquement avec la volatilité — hypothèse non vérifiable sur 3–4 cycles.
- **Alternative simple :** Tester manuellement fenêtre 2/1 vs 3/1 vs 6/1 via les paramètres existants. Pas besoin de ML.

| Critère | Évaluation |
|---------|-----------|
| Gain attendu | Très faible (non prouvable sur 3-4 cycles) |
| Complexité | M |
| Risque prod | Faible (offline) |
| Fenêtre 1h/jour | Neutre |
| Données suffisantes | ❌ Non (3-4 cycles insuffisant) |
| Incompatibilité Cython | Non |

**VERDICT : ❌ NON PERTINENT**
Sur-ingénierie. Les paramètres `train_months` / `test_months` sont déjà configurables. Tester différentes valeurs fixes est plus rigoureux que d'adapter dynamiquement sur 3–4 cycles.

---

## PHASE 3 — RECOMMANDATION FINALE

### 3.1 Tableau de décision

| ID | Opportunité | Verdict | Gain estimé | Complexité | Risque prod |
|----|-------------|---------|-------------|------------|-------------|
| A | Filtre ML qualité FCR (RF/XGBoost) | ❌ NON PERTINENT | Faible / négatif | M | Élevé |
| B | Filtre ML signal engulfing | ❌ NON PERTINENT | Très faible | M | Élevé |
| C | Détection de régime de marché (K-Means) | ✅ PERTINENT | Moyen (−Max DD) | S | Moyen |
| D | Optimisation bayésienne Optuna (walk-forward) | ✅ PERTINENT | Élevé (efficacité param) | S | Faible |
| E | Sizing dynamique risk_pct (régression) | ❌ NON PERTINENT | Ambigu | L | Élevé |
| F | Sélection paires ML | ❌ NON PERTINENT | Faible | M | Moyen |
| G | Stop-loss dynamique ML | ❌ NON PERTINENT | Ambigu | L | Élevé |
| H | LLM sentiment macro Forex | ❌ NON PERTINENT | Nul | L | Élevé |
| I | SHAP values paramètres FCR | ❌ NON PERTINENT | Nul | M | Faible |
| J | Walk-forward adaptatif fenêtres | ❌ NON PERTINENT | Très faible | M | Faible |

---

### 3.2 Roadmap recommandée

#### NIVEAU 1 — Sans risque pour la production (ALPHAEDGE_PAPER=true obligatoire)

**C — Détection de régime de marché (K-Means)**

Mode observation uniquement : le classifieur détecte le régime mais **ne bloque pas les trades**. On logge uniquement `regime: high_vol | low_vol` par journée. Après 30 sessions NYSE, on analyse la corrélation régime → win_rate avant toute activation.

**Stack :** `sklearn.cluster.KMeans(n_clusters=2)`, `numpy` (déjà présent).
**Features journalières :** ATR daily (std des ranges M5 sur J-1), range intraday J-1, spread moyen M1 pré-session.
**Recalibration :** mensuelle via le cache disk M5 (BarDiskCache).
**Fichier nouveau :** `alphaedge/engine/regime_filter.py` (~80 lignes).
**Intégration :** Dans `strategy.py`, avant l'appel à `signal_pipeline.detect_fcr()` → `if not regime_filter.allows_trading(pair, session_date): log + return`.
**make build :** Non requis (Python pur).
**make qa :** Doit passer à 100% avant activation.

#### NIVEAU 2 — Intégration progressive (paper trading, validation OOS)

**D — Optimisation bayésienne (Optuna) dans walk_forward.py**

Remplacer `sensitivity.grid_search_best()` par une alternative Optuna en tant que `optimize_fn` optionnelle.

**Stack :** `optuna` (à ajouter dans `requirements.txt`).
**Intégration :** Nouvelle fonction `optuna_search_best(m1_bars, m5_bars, pair, config, n_trials=150) -> dict[str, float]` dans un nouveau fichier `alphaedge/engine/bayesian_optimizer.py` (~80 lignes). Compatible avec la signature `optimize_fn` de `run_walk_forward()` sans modification de `walk_forward.py`.
**Validation :** Comparer OOS Sharpe entre grid search et Optuna sur le même dataset IS avant de remplacer définitivement.
**make build :** Non requis.
**make qa :** Doit passer à 100%, y compris nouveaux tests `test_bayesian_optimizer_*.py`.

#### NIVEAU 3 — Remplacement de composants existants

**Conditionnel :** Uniquement si NIVEAU 2 validé sur 30+ sessions NYSE en paper trading pour C, et si les OOS Sharpe via Optuna sont supérieurs ou égaux au grid search sur 3+ fenêtres walk-forward pour D.

---

### 3.3 Ce qu'il ne faut PAS faire

| Intégration | Raison d'exclusion |
|-------------|-------------------|
| **Filtre LLM (H)** | Latence 1–10s incompatible avec boucle asyncio M1 (5s bars). `news_filter.py` couvre le besoin. |
| **Dynamic SL (G)** | Requiert modification `order_manager.pyx` → `make build` + tests de régression. Casse fixed-fraction model. |
| **Dynamic risk_pct (E)** | Invalide le modèle de comptabilisation `backtest_stats._apply_equity_sizing()`. Peut amplifier les drawdowns. |
| **ML sur engulfing (B)** | ~150 samples/an → surapprentissage garanti. `min_body_ratio` configurable couvre le besoin. |
| **ML sur FCR (A)** | Features non exportées, labels bruités, surapprentissage prévisible. `fcr_range_cv_max` couvre le besoin. |
| **SHAP (I)** | `sensitivity.find_robustness_plateau()` répond au même besoin directement. Couche ML inutile. |
| **Tout modèle PyTorch/TF/Keras** | Dépendances lourdes, latence GPU incompatible avec event-driven IB. Hors contexte Forex NYSE 1h. |
| **Walk-forward adaptatif (J)** | 3–4 cycles = bruit pur. Les paramètres `train_months`/`test_months` sont déjà configurables. |

---

### 3.4 Verdict global

**Faut-il intégrer de l'IA/ML sur ALPHAEDGE ?** Marginalement oui, sur deux points précis et à faible risque.

**Par quoi commencer ?** D'abord Optuna (D) — 80 lignes, aucun risque live, gain immédiat en efficacité de recherche de paramètres, compatible avec l'architecture `optimize_fn` existante. Ensuite le régime de marché (C) — mode observation 30 sessions avant toute activation.

**Le risque principal à surveiller :** La diminution du nombre de trades suite à un régime filter trop agressif peut transformer un Sharpe=3.37 en Sharpe non significatif (n< 30 trades/an). Surveiller le trade count avec la même rigueur que le Sharpe.

**Ce qu'il ne faut surtout pas faire :** Importer sklearn, XGBoost, ou tout classifieur supervisé sur les signaux FCR/engulfing. Les données sont trop rares et trop bruitées (200–400 trades/an) pour garantir une généralisation OOS. La robustesse déterministe actuelle (Sharpe=3.37) est plus précieuse que la sophistication apparente d'un ML mal calibré.

---

*Fin d'audit — 2026-03-22*
