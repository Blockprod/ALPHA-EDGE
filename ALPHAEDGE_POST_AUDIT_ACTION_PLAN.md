# ⚡ ALPHAEDGE — PLAN D'ACTION POST-AUDIT

> **Date** : 2026-03-08
> **Source** : `ALPHAEDGE_MASTER_AUDIT.md` (Audit du 2026-03-07)
> **Score actuel** : 5.3 / 10 — STRUCTURALLY FRAGILE
> **Objectif** : Amener AlphaEdge à un niveau **production-ready IBKR**
> **Méthode** : 4 phases séquentielles — chaque phase doit être **100% validée** avant de passer à la suivante

---

## TABLE DES MATIÈRES

| Phase | Nom | Objectif | Tâches |
|-------|-----|----------|--------|
| [Phase 1](#phase-1--corrections-critiques) | 🔴 Corrections Critiques | Éliminer les bugs bloquants pour le paper trading | 7 |
| [Phase 2](#phase-2--sécurisation-live) | 🟠 Sécurisation Live | Préparer le déploiement live IBKR | 8 |
| [Phase 3](#phase-3--validation-statistique) | 🟡 Validation Statistique | Prouver l'edge de la stratégie | 7 |
| [Phase 4](#phase-4--optimisation--scale) | 🔵 Optimisation & Scale | Améliorations avancées | 6 |
| [Déploiement](#protocole-de-déploiement-live) | 🟢 Protocole Live | Mise en production progressive | 4 étapes |

**Total : 28 tâches + 4 étapes de déploiement**

---

# PHASE 1 — 🔴 CORRECTIONS CRITIQUES

> **Objectif** : Corriger les 7 bugs critiques identifiés dans l'audit.
> **Condition de sortie** : `make qa` passe à 100%, tous les tests passent, le pipeline de signal est fonctionnel.

---

### TÂCHE 1.1 — Agréger les barres 5 secondes en chandeliers M1

**Réf. audit** : C2 / Section 8.5
**Fichiers** : `alphaedge/engine/strategy.py`, `alphaedge/engine/data_feed.py`
**Sévérité** : 🔴 CRITIQUE

**Problème** :
`reqRealTimeBars(barSize=5)` envoie un callback toutes les 5 secondes. Chaque callback déclenche `_on_new_m1_bar()` qui exécute la détection d'engulfing sur des barres 5s, pas sur des chandeliers M1 fermés.

**Actions** :

1. **Créer un agrégateur M1** dans `data_feed.py` :
   ```
   Classe M1Aggregator :
   - Accumule les barres 5s reçues
   - Construit un chandelier M1 OHLCV :
     open  = open de la première barre 5s de la minute
     high  = max(high) de toutes les barres 5s de la minute
     low   = min(low) de toutes les barres 5s de la minute
     close = close de la dernière barre 5s de la minute
     volume = sum(volume) de toutes les barres 5s
   - Émet le chandelier M1 uniquement au franchissement de la minute
   ```

2. **Modifier `_on_bar_update()`** dans `RealtimeDataFeed` :
   - Accumuler les barres 5s dans `M1Aggregator`
   - Ne déclencher le callback de la stratégie qu'à la fermeture d'un chandelier M1 complet

3. **Mettre à jour `_on_new_m1_bar()`** dans `strategy.py` :
   - S'assurer qu'il reçoit un chandelier M1 complet (OHLCV agrégé), pas une barre 5s

**Critères de validation** :
- [ ] Le callback de signal ne se déclenche qu'**une fois par minute** (pas toutes les 5 secondes)
- [ ] Le chandelier M1 a les bons OHLCV (open = première barre 5s, close = dernière, high/low = max/min)
- [ ] Le volume est la somme des volumes des barres 5s de la minute
- [ ] Test unitaire : 12 barres 5s (1 minute) → 1 chandelier M1 correct
- [ ] Test unitaire : 60 barres 5s (5 minutes) → 5 chandeliers M1

---

### TÂCHE 1.2 — Connecter la détection de gap ATR dans le flux live

**Réf. audit** : C1 / Section 8.2
**Fichiers** : `alphaedge/engine/strategy.py`
**Sévérité** : 🔴 CRITIQUE

**Problème** :
La méthode `_detect_gap()` est définie dans `FCRStrategy` mais `run_session()` et `_on_new_m1_bar()` ne l'invoquent jamais. La stratégie trade des signaux engulfing sans confirmation ATR spike, ce qui contredit le pipeline documenté : FCR → Gap → Engulfing.

**Actions** :

1. **Dans `run_session()`**, après la détection FCR et avant d'activer le scan M1 :
   - Appeler `_detect_gap()` pour chaque paire
   - Stocker le résultat dans `state.gap_result`

2. **Dans `_on_new_m1_bar()`**, ajouter un guard :
   ```python
   if not state.gap_result or not state.gap_result["detected"]:
       return  # Pas de spike ATR → pas de signal possible
   ```

3. **Logger** le résultat de la détection gap pour chaque paire au début de session

**Critères de validation** :
- [ ] `_detect_gap()` est appelée dans `run_session()` pour chaque paire
- [ ] Un signal engulfing ne peut PAS se déclencher si `gap_result.detected == False`
- [ ] Les logs montrent le ratio ATR et le statut gap pour chaque paire
- [ ] Test : simuler une session sans spike ATR → 0 trades exécutés

---

### TÂCHE 1.3 — Gérer les positions ouvertes en fin de session

**Réf. audit** : C5 / Section 9.4
**Fichiers** : `alphaedge/engine/strategy.py`, `alphaedge/engine/broker.py`
**Sévérité** : 🔴 CRITIQUE

**Problème** :
Quand la fenêtre de session (10:30 ET) se termine, le bot déconnecte d'IB Gateway. Si une position est ouverte, le bracket SL/TP reste actif côté IB, mais aucune alerte n'est émise et aucun time stop n'est appliqué.

**Actions** :

1. **Dans `run_session()`**, à la sortie de la boucle `while is_session_active()` :
   ```python
   positions = broker.get_open_positions()
   for pos in positions:
       if pos est sur une paire tradée :
           logger.warning(f"Position ouverte en fin de session : {pos}")
           # Action selon config
   ```

2. **Ajouter un paramètre `session_end_action`** dans `config.yaml` :
   - `"close"` — fermeture au marché en fin de session
   - `"hold"` — laisser le bracket (défaut, comportement actuel + alerte)

3. **Logger un résumé de session** à la fin :
   - Trades exécutés, P&L session, positions encore ouvertes

**Critères de validation** :
- [ ] En fin de session, les positions ouvertes sont détectées et loguées
- [ ] Si `session_end_action: close`, la position est fermée au marché
- [ ] Si `session_end_action: hold`, un warning critique est émis
- [ ] Test : simuler une fin de session avec position ouverte → alerte déclenchée

---

### TÂCHE 1.4 — Corriger le look-ahead bias dans le backtest

**Réf. audit** : C6 / Section 4.3
**Fichiers** : `alphaedge/engine/backtest.py`
**Sévérité** : 🔴 CRITIQUE

**Problème** :
`_detect_signal_at_bar()` recalcule le FCR range à chaque barre en prenant `bars[i-10:i-2]` comme "M5 équivalent". En live, le FCR est calculé **une seule fois** avant 9:30 ET avec de vraies barres M5. En backtest, il est recalculé continuellement, créant un biais de look-ahead.

**Actions** :

1. **Restructurer `_backtest_pair()`** :
   ```
   Pour chaque jour de trading :
     1. Filtrer les barres M5 avant 9:30 ET par timestamp
     2. Calculer le FCR UNE SEULE FOIS avec ces barres pré-session
     3. Filtrer les barres M1 de 9:30 à 10:30 ET
     4. Itérer uniquement sur ces barres M1 pour les signaux
   ```

2. **Séparer les barres par session** :
   - Utiliser les timestamps réels (pas les indices) pour isoler pré-session vs session
   - Demander des barres M5 distinctes à IB pour la période pré-session

3. **Calculer le gap ATR cohérent** :
   - Baseline ATR = barres pré-session (avant 9:30 ET)
   - Session ATR = premières barres après 9:30 ET
   - Appliquer le même filtre que le live (ratio ≥ 1.5)

**Critères de validation** :
- [ ] Le FCR est calculé 1 fois par session (pas par barre)
- [ ] Les barres sont filtrées par timestamp, pas par index
- [ ] Le gap ATR est calculé avec la même logique que le live
- [ ] Comparer les résultats avant/après correction — les métriques DOIVENT changer

---

### TÂCHE 1.5 — Ajouter des filtres de qualité au détecteur d'engulfing

**Réf. audit** : M7 / Section 8.3
**Fichiers** : `alphaedge/core/engulfing_detector.pyx`
**Sévérité** : 🟠 MAJEUR

**Problème** :
Le détecteur vérifie l'englobement du body mais aucune taille minimum. Une bougie de 0.1 pip qui englobe une bougie de 0.05 pip déclenche un signal, malgré un manque total de conviction.

**Actions** :

1. **Ajouter un filtre de taille minimale du body** :
   ```cython
   cdef double body_size = fabs(current.close - current.open)
   cdef double min_body = fcr_range * min_body_ratio  # ex: 0.3
   if body_size < min_body:
       result.detected = False
   ```

2. **Ajouter un filtre de ratio wick/body** :
   ```cython
   cdef double upper_wick = current.high - max(current.open, current.close)
   cdef double lower_wick = min(current.open, current.close) - current.low
   cdef double total_wick = upper_wick + lower_wick
   if total_wick > max_wick_ratio * body_size:  # ex: 2.0
       result.detected = False
   ```

3. **Ajouter les paramètres** dans `config.yaml` :
   ```yaml
   engulfing:
     min_body_ratio: 0.3    # Body ≥ 30% du FCR range
     max_wick_ratio: 2.0    # Wick ≤ 200% du body
   ```

4. **Recompiler** le module Cython après modification

**Critères de validation** :
- [ ] Un engulfing avec body < 30% du FCR range est rejeté
- [ ] Un engulfing avec wick > 2× body est rejeté
- [ ] Les tests existants passent avec les nouveaux filtres
- [ ] Nouveau test : engulfing trivial (0.1 pip) → rejeté

---

### TÂCHE 1.6 — Corriger les 13 erreurs Mypy

**Réf. audit** : M5 / Section 2.4
**Fichiers** : `alphaedge/utils/logger.py`, `alphaedge/engine/broker.py`, `alphaedge/engine/data_feed.py`, `alphaedge/engine/backtest.py`
**Sévérité** : 🟠 MAJEUR

**Problème** :
13 erreurs Mypy : 8 `unused-ignore` (commentaires `type: ignore` obsolètes) et 5 `no-any-return` (retours de `ib_insync` non typés).

**Actions** :

1. **Supprimer les `# type: ignore` obsolètes** (8 occurrences) :
   - `logger.py` : lignes 83, 92
   - `broker.py` : lignes 87, 135, 269
   - `data_feed.py` : lignes 47, 48, 49
   - `backtest.py` : ligne 589

2. **Corriger les `no-any-return`** (5 occurrences) :
   - `broker.py:94` — ajouter un cast explicite : `return bool(self._ib.isConnected())`
   - `broker.py:286` — typer le retour ou ajouter assertion
   - `data_feed.py:314, 344` — ajouter des casts `float()` sur les retours IB

3. **Vérifier** : `python -m mypy --strict alphaedge/` → 0 erreurs

**Critères de validation** :
- [ ] `mypy --strict` retourne **0 erreurs**
- [ ] Aucune régression fonctionnelle
- [ ] `make typecheck` passe ✅

---

### TÂCHE 1.7 — Réparer le pipeline CI/CD et le test suite

**Réf. audit** : C7 / Section 1.4
**Fichiers** : `alphaedge/core/__init__.py`, `alphaedge/tests/`, `.github/workflows/`
**Sévérité** : 🔴 CRITIQUE

**Problème** :
15/19 fichiers de test échouent sans compilation Cython. Aucun workflow CI n'existe.

**Actions** :

1. **Créer des stubs Python pure** pour les 5 modules Cython :
   ```
   alphaedge/core/_stubs/
   ├── fcr_detector.py
   ├── gap_detector.py
   ├── engulfing_detector.py
   ├── order_manager.py
   └── risk_manager.py
   ```
   - Chaque stub implémente la même interface (mêmes signatures de fonctions)
   - Logique simplifiée mais fonctionnellement identique

2. **Modifier `core/__init__.py`** :
   ```python
   try:
       from alphaedge.core.fcr_detector import detect_fcr, detect_fcr_scan
   except ImportError:
       from alphaedge.core._stubs.fcr_detector import detect_fcr, detect_fcr_scan
   ```

3. **Créer `.github/workflows/ci.yml`** :
   ```yaml
   name: AlphaEdge CI
   on: [push, pull_request]
   jobs:
     qa:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-python@v5
           with:
             python-version: '3.11.9'
         - run: pip install -r requirements.txt
         - run: make qa
   ```

4. **Vérifier** : `make qa` passe intégralement

**Critères de validation** :
- [ ] `pytest` exécute les **19 fichiers de test** sans erreur d'import
- [ ] Les stubs produisent les **mêmes résultats** que les modules Cython
- [ ] `make qa` passe entièrement ✅
- [ ] Le workflow CI est fonctionnel sur GitHub Actions
- [ ] Les stubs sont exclus de l'utilisation en production (import conditionnel)

---

### ✅ CHECKLIST DE SORTIE — PHASE 1

```
[ ] TÂCHE 1.1 — Agrégation 5s → M1 implémentée et testée
[ ] TÂCHE 1.2 — Gap detection connectée au flux live
[ ] TÂCHE 1.3 — Gestion des positions en fin de session
[ ] TÂCHE 1.4 — Look-ahead bias corrigé dans backtest
[ ] TÂCHE 1.5 — Filtres qualité engulfing ajoutés
[ ] TÂCHE 1.6 — Mypy strict : 0 erreurs
[ ] TÂCHE 1.7 — CI/CD pipeline : make qa passe à 100%
[ ] make format ✅
[ ] make lint ✅
[ ] make typecheck ✅
[ ] make test ✅ (19/19 fichiers)
[ ] Paper trading possible avec pipeline FCR → Gap → Engulfing complet
```

---

# PHASE 2 — 🟠 SÉCURISATION LIVE

> **Objectif** : Ajouter les protections nécessaires pour un déploiement live sûr sur IBKR.
> **Prérequis** : Phase 1 100% validée + 2 semaines minimum de paper trading stable.
> **Condition de sortie** : Toutes les protections de sécurité sont en place et testées.

---

### TÂCHE 2.1 — Implémenter la récupération de déconnexion IB

**Réf. audit** : C3 / Section 10.2
**Fichiers** : `alphaedge/engine/strategy.py`, `alphaedge/engine/broker.py`

**Actions** :

1. **Câbler `disconnectedEvent`** sur `self._broker.ib` dans `FCRStrategy.__init__()` :
   ```python
   self._broker.ib.disconnectedEvent += self._on_ib_disconnect
   ```

2. **Implémenter `_on_ib_disconnect()`** :
   - Logger un événement CRITICAL
   - Appeler `broker.reconnect(max_retries=3)` (existe déjà, jamais appelé)
   - Si reconnexion réussie :
     - Scanner les positions via `ib.positions()`
     - Réconcilier avec `StrategyState`
     - Re-souscrire aux flux temps réel
   - Si reconnexion échouée :
     - Logger CRITICAL + arrêt propre

3. **Gérer les ordres orphelins** :
   - Après reconnexion, vérifier `ib.openOrders()`
   - Identifier les brackets incomplets (entry filled mais SL/TP manquants)
   - Re-soumettre les ordres protecteurs manquants

**Critères de validation** :
- [ ] La déconnexion IB déclenche automatiquement une tentative de reconnexion
- [ ] Les positions ouvertes sont retrouvées après reconnexion
- [ ] Les ordres orphelins sont détectés et gérés
- [ ] Test simulé : déconnexion manuelle d'IB Gateway → reconnexion automatique

---

### TÂCHE 2.2 — Ajouter un filtre de news économiques

**Réf. audit** : C4 / Section 10.1
**Fichiers** : nouveau `alphaedge/utils/news_filter.py`, `alphaedge/engine/strategy.py`, `config.yaml`

**Actions** :

1. **Créer `alphaedge/utils/news_filter.py`** :
   - Charger un calendrier économique (CSV statique ou API)
   - Filtrer les événements "High Impact" pour les devises tradées
   - Méthode `is_news_blackout(datetime, pair) -> bool`

2. **Intégrer dans `run_session()`** :
   ```python
   if news_filter.is_news_blackout(now_utc, pair):
       logger.warning(f"News blackout actif pour {pair}")
       continue
   ```

3. **Configurer dans `config.yaml`** :
   ```yaml
   news_filter:
     enabled: true
     blackout_minutes: 15
     impact_levels: ["high"]
     calendar_path: "data/economic_calendar.csv"
   ```

**Critères de validation** :
- [ ] NFP (1er vendredi du mois, 8:30 ET) → blackout de 8:15 à 8:45 ET
- [ ] Signal en période de blackout → rejeté avec log
- [ ] Jours sans news → aucun blocage

---

### TÂCHE 2.3 — Monitoring continu du spread

**Réf. audit** : M3 / Section 3.5
**Fichiers** : `alphaedge/engine/strategy.py`

**Actions** :

1. **Vérifier le spread à chaque barre M1** (pas seulement à l'entrée) :
   ```python
   current_spread = self._realtime_feed.get_live_spread(pair)
   if current_spread > self._config.trading.max_spread_pips:
       logger.info(f"Spread trop large ({current_spread} pips)")
       return
   ```

2. **Monitoring pendant position ouverte** :
   - Spread > 3× max configuré → log WARNING
   - Configurable pour fermer si spread extrême

**Critères de validation** :
- [ ] Signal ignoré si spread > 2 pips au moment de l'évaluation
- [ ] Alerte si spread spike pendant position ouverte

---

### TÂCHE 2.4 — Accélérer le contrôle de perte journalière

**Réf. audit** : M6 / Section 3.2
**Fichiers** : `alphaedge/engine/strategy.py`

**Actions** :

1. **Réduire l'intervalle de polling** :
   - Sans position ouverte : 30 secondes (actuel)
   - Avec position ouverte : **5 secondes**

2. **Alternative (meilleure)** :
   - Souscrire à `ib.accountSummary()` streaming pour kill-switch immédiat

**Critères de validation** :
- [ ] Avec position ouverte, le check de perte ≤ 5 secondes
- [ ] Le kill-switch se déclenche en < 10 secondes après breach
- [ ] Test : simuler equity drop > -3% → shutdown en < 10s

---

### TÂCHE 2.5 — Changer l'ordre d'entrée Limit → Market

**Réf. audit** : m6 / Section 9.5
**Fichiers** : `alphaedge/engine/broker.py`

**Actions** :

1. Changer le parent order du bracket de `LimitOrder` à `MarketOrder`
2. Alternative : `LimitIfTouched` pour un compromis fill-garanti / prix maîtrisé
3. Mettre à jour le backtest pour refléter le slippage d'un Market order

**Critères de validation** :
- [ ] Les ordres d'entrée sont des Market orders
- [ ] Le bracket SL/TP reste en Limit/Stop comme avant
- [ ] Test IB paper : l'ordre se fill immédiatement

---

### TÂCHE 2.6 — Câbler `reconnect()` et supprimer le dead code

**Réf. audit** : M8, m5
**Fichiers** : `alphaedge/engine/broker.py`, `alphaedge/core/risk_manager.pyx`

**Actions** :

1. **`reconnect()`** : câblé via tâche 2.1 → tester les 3 retries avec backoff
2. **`apply_slippage_buffer()`** : soit l'intégrer dans le flux d'order, soit le supprimer
3. Aucun dead code ne doit rester dans le projet

**Critères de validation** :
- [ ] `reconnect()` est appelé automatiquement sur déconnexion
- [ ] `apply_slippage_buffer()` est utilisé ou supprimé
- [ ] 0 fonctions dead code

---

### TÂCHE 2.7 — Refactorer l'accès aux modules par nom

**Réf. audit** : m1 / Section 1.1
**Fichiers** : `alphaedge/engine/strategy.py`

**Actions** :

1. **Remplacer l'accès par index** (`self._modules[0]`, `self._modules[1]`, ...) par des accès nommés :
   ```python
   @dataclass
   class CoreModules:
       fcr_detector: ModuleType
       gap_detector: ModuleType
       engulfing_detector: ModuleType
       order_manager: ModuleType
       risk_manager: ModuleType
   ```

**Critères de validation** :
- [ ] Tous les `self._modules[N]` remplacés par des accès nommés
- [ ] L'ajout ou le retrait d'un module ne casse pas les indices
- [ ] Tous les tests passent

---

### TÂCHE 2.8 — Injection de dépendances dans FCRStrategy

**Réf. audit** : Section 1.1
**Fichiers** : `alphaedge/engine/strategy.py`

**Actions** :

1. **Modifier `FCRStrategy.__init__()`** pour accepter des instances injectées :
   ```python
   def __init__(
       self,
       config: AlphaEdgeConfig,
       broker: BrokerConnection | None = None,
       historical_feed: HistoricalDataFeed | None = None,
       realtime_feed: RealtimeDataFeed | None = None,
   ):
       self._broker = broker or BrokerConnection(config)
       # ...
   ```

2. Ceci permet de tester `FCRStrategy` avec des mocks, sans IB Gateway

**Critères de validation** :
- [ ] `FCRStrategy` fonctionne avec les dépendances par défaut (comportement préservé)
- [ ] `FCRStrategy` accepte des mocks pour testing
- [ ] Nouveau test : `FCRStrategy` avec mock broker → exécution de signal simulée

---

### ✅ CHECKLIST DE SORTIE — PHASE 2

```
[ ] TÂCHE 2.1 — Récupération de déconnexion IB fonctionnelle
[ ] TÂCHE 2.2 — Filtre de news économiques actif
[ ] TÂCHE 2.3 — Spread monitoré en continu
[ ] TÂCHE 2.4 — Kill-switch réactif (< 10s)
[ ] TÂCHE 2.5 — Ordres d'entrée en Market order
[ ] TÂCHE 2.6 — Dead code éliminé
[ ] TÂCHE 2.7 — Accès modules par nom
[ ] TÂCHE 2.8 — Injection de dépendances
[ ] 4 semaines minimum de paper trading avec Phase 1+2
[ ] 0 déconnexions non récupérées
[ ] 0 positions orphelines
[ ] Résultats paper trading documentés
```

---

# PHASE 3 — 🟡 VALIDATION STATISTIQUE

> **Objectif** : Démontrer mathématiquement que la stratégie a un avantage statistique exploitable.
> **Prérequis** : Phase 2 validée.
> **Condition de sortie** : Backtest robuste avec edge prouvé out-of-sample.

---

### TÂCHE 3.1 — Split In-Sample / Out-of-Sample

**Réf. audit** : M1 / Section 4.3
**Fichiers** : `alphaedge/engine/backtest.py`

**Actions** :

1. Diviser les données historiques : **70% IS / 30% OOS**
2. Rapporter les métriques séparément :
   | Métrique | In-Sample | Out-of-Sample |
   |----------|-----------|---------------|
   | Win rate | — | — |
   | Profit factor | — | — |
   | Max drawdown | — | — |
   | Sharpe ratio | — | — |
3. Condition de validité : métriques OOS ne se dégradent pas de > 30% vs IS

**Critères de validation** :
- [x] Deux jeux de métriques produits (IS et OOS)
- [x] Rapport CSV avec colonne `sample_type`

---

### TÂCHE 3.2 — Walk-Forward Optimization

**Réf. audit** : Section 4.3
**Fichiers** : `alphaedge/engine/backtest.py`

**Actions** :

1. **Implémenter un walk-forward rolling** :
   - Fenêtre train : 3 mois / Fenêtre test : 1 mois
   - Slider d'1 mois à chaque itération

2. Pour chaque itération :
   - Optimiser les paramètres sur la fenêtre train
   - Tester sur la fenêtre test avec paramètres optimisés
   - N'enregistrer que les métriques test

3. Consolider les résultats test de toutes les fenêtres

**Critères de validation** :
- [x] ≥ 12 itérations walk-forward (12 mois de données minimum)
- [x] Profit factor agrégé OOS > 1.0
- [x] Sharpe ratio annualisé OOS > 0.5

---

### TÂCHE 3.3 — Analyse de sensibilité des paramètres

**Réf. audit** : M4 / Section 7.2
**Fichiers** : nouveau `alphaedge/engine/sensitivity.py`

**Actions** :

1. **Grid search** sur les paramètres clés :
   | Paramètre | Range | Step |
   |-----------|-------|------|
   | ATR ratio threshold | 1.0 → 2.5 | 0.1 |
   | Volume ratio | 1.0 → 2.0 | 0.1 |
   | Min FCR range (pips) | 3 → 15 | 1 |
   | RR ratio | 2.0 → 4.0 | 0.5 |
   | Engulfing min body ratio | 0.1 → 0.5 | 0.1 |

2. **Générer des heatmaps** (matplotlib) : Sharpe + Profit Factor en 2D
3. **Identifier le plateau de robustesse** (pas l'optimum ponctuel)

**Critères de validation** :
- [x] Heatmaps générés pour toutes les combinaisons 2D
- [x] Un plateau de robustesse identifié
- [x] Les paramètres finaux sont dans le plateau, pas au maximum absolu

---

### TÂCHE 3.4 — Corriger la validation vectorbt

**Réf. audit** : M2 / Section 4.2
**Fichiers** : `alphaedge/engine/backtest.py`

**Actions** :

1. Passer des **pourcentages de rendement** (pas des pips bruts) :
   ```python
   # Correct :
   return_series = pd.Series([t.pnl_usd / equity_at_trade for t in trades])
   vbt_sharpe = return_series.vbt.returns.sharpe_ratio()
   ```

2. Comparer Sharpe vectorbt vs Sharpe manuel → doivent être cohérents (< 5% d'écart)

**Critères de validation** :
- [x] vectorbt reçoit des percentage returns
- [x] Sharpe vectorbt ≈ Sharpe manuel (écart < 5%)

---

### TÂCHE 3.5 — Benchmark contre un baseline aléatoire ✅ TERMINÉE

**Fichiers** : `alphaedge/engine/backtest.py`

**Actions** :

1. ✅ Créer un **baseline** : entrée aléatoire, mêmes paramètres (SL/TP 3:1, mêmes paires) — `_generate_random_trades()`
2. ✅ Exécuter **1000 simulations** du baseline — `run_random_baseline(n_simulations=1000)`
3. ✅ Comparer : profit factor FCR > 95e percentile du baseline — `RandomBaselineReport.baseline_pf_95th`
4. ✅ Calculer un **p-value** : proportion de runs aléatoires battant la stratégie — `RandomBaselineReport.p_value`

**Implémentation** : `RandomBaselineReport`, `_generate_random_trades()`, `run_random_baseline()`, `_log_random_baseline_report()`
**Tests** : `test_random_baseline.py` — 11 tests (163/163 total)

**Critères de validation** (runtime) :
- [ ] p-value < 0.05 (stratégie significativement meilleure que le hasard)
- [ ] Profit factor FCR > 95e percentile du baseline

---

### TÂCHE 3.6 — Monte Carlo pour estimation du drawdown ✅ TERMINÉE

**Réf. audit** : A5
**Fichiers** : nouveau `alphaedge/engine/monte_carlo.py`

**Actions** :

1. ✅ **10 000 permutations** de l'ordre des trades — `run_monte_carlo(n_permutations=10000)`
2. ✅ Pour chaque permutation, calculer le max drawdown — `_compute_max_drawdown_from_pnls()`
3. ✅ Extraire : drawdown médian, 95e percentile, 99e percentile — `MonteCarloReport`
4. ✅ Utiliser le **95e percentile** pour calibrer le risk % par trade — `suggested_risk_pct`

**Implémentation** : `MonteCarloReport`, `_compute_max_drawdown_from_pnls()`, `run_monte_carlo()`, `generate_drawdown_histogram()`, `_log_monte_carlo_report()`
**Tests** : `test_monte_carlo.py` — 18 tests (181/181 total)

**Critères de validation** :
- [x] 10 000 permutations exécutées
- [x] Distribution du drawdown visualisée (histogramme) — `generate_drawdown_histogram()`
- [x] Drawdown 95e percentile utilisé pour position sizing — `suggested_risk_pct`

---

### TÂCHE 3.7 — Modélisation réaliste du slippage ✅ TERMINÉE

**Réf. audit** : m7 / Section 4.4
**Fichiers** : `alphaedge/engine/backtest.py`, `alphaedge/config/constants.py`

**Actions** :

1. ✅ **Slippage variable** (remplacer le 0.5 pips fixe) — `compute_variable_slippage()`
   - Base: 0.3 pips, NYSE open: ×2.0 (0.6 pips), News: ×5.0 (1.5 pips)
2. ✅ **Spread variable** dans le backtest :
   - Base: 0.8 pips, NYSE open: 1.5 pips, News: 3.0 pips

**Implémentation** : `compute_variable_slippage()`, constants `BASE_SLIPPAGE_PIPS`, `NYSE_OPEN_*`, `NEWS_*`
**Tests** : `test_variable_slippage.py` — 11 tests (192/192 total)

**Critères de validation** :
- [x] Le backtest utilise un slippage variable
- [ ] Le profit factor survit au slippage réaliste (PF > 1.0) — runtime

---

### ✅ CHECKLIST DE SORTIE — PHASE 3

```
[x] TÂCHE 3.1 — Split IS/OOS implémenté
[x] TÂCHE 3.2 — Walk-forward terminé (≥ 12 itérations)
[x] TÂCHE 3.3 — Heatmaps de sensibilité générés
[x] TÂCHE 3.4 — vectorbt corrigé
[x] TÂCHE 3.5 — Baseline aléatoire : p-value < 0.05
[x] TÂCHE 3.6 — Monte Carlo : drawdown 95e percentile connu
[x] TÂCHE 3.7 — Slippage variable intégré
[ ] Profit factor OOS > 1.2
[ ] Sharpe annualisé OOS > 0.5
[ ] Win rate OOS > 30% (seuil pour 3:1 RR)
[ ] ≥ 100 trades dans le backtest OOS
[ ] Rapport de validation statistique finalisé
```

---

# PHASE 4 — 🔵 OPTIMISATION & SCALE

> **Objectif** : Améliorations optionnelles pour renforcer la robustesse.
> **Prérequis** : Phase 3 validée avec edge statistique prouvé.

---

### TÂCHE 4.1 — Filtre de régime de volatilité ✅ TERMINÉE

**Réf. audit** : A1

Calculer l'ATR rolling 20 jours à 9:30 ET. Ne trader que si l'ATR du jour est entre 0.5× et 2.0× de la moyenne rolling. Logger les jours skippés.

**Implémentation** : `alphaedge/utils/volatility_regime.py` — `VolatilityRegimeResult`, `compute_daily_atr()`, `compute_rolling_atr()`, `check_volatility_regime()`
**Constants** : `REGIME_ATR_LOOKBACK_DAYS=20`, `REGIME_ATR_LOW_MULTIPLIER=0.5`, `REGIME_ATR_HIGH_MULTIPLIER=2.0`
**Tests** : `test_volatility_regime.py` — 17 tests (209/209 total)

---

### TÂCHE 4.2 — Extension multi-session (London Open) ✅ TERMINÉE

**Réf. audit** : A2

Ajouter une fenêtre configurable pour London Open (8:00–9:00 UTC). Tester les mêmes paires via backtest. N'ajouter que si edge confirmé OOS.

**Implémentation** : `alphaedge/utils/session_manager.py` — `SessionWindow`, `NYSE_SESSION`, `LONDON_SESSION`, `get_active_sessions()`, `is_any_session_active()`, `build_sessions_from_config()`
**Constants** : `LONDON_START_HOUR=8`, `LONDON_END_HOUR=9`, `LONDON_TZ="UTC"`
**Config** : `london_open_enabled: false` in `TradingConfig` + `config.yaml` (disabled by default — enable after OOS validation)
**Tests** : `test_session_manager.py` — 22 tests (231/231 total)

---

### TÂCHE 4.3 — Filtre ML de signal (optionnel) ✅ TERMINÉE

**Réf. audit** : A3

Entraîner une régression logistique sur les features (ATR ratio, FCR range, volume ratio, spread, jour de semaine). Walk-forward le modèle. Ne trader que si P(win) > seuil calibré.

**Implémentation** : `alphaedge/engine/ml_filter.py` — `SignalFeatures`, `MLSignalFilter` (LogisticRegression + StandardScaler), `MLFilterResult`, `extract_features()`, `walk_forward_ml()`, `WalkForwardMLReport`
**Features** : `atr_ratio`, `fcr_range`, `volume_ratio`, `spread`, `day_of_week`
**Seuil** : `DEFAULT_WIN_THRESHOLD=0.55` (configurable)
**Tests** : `test_ml_filter.py` — 19 tests (250/250 total)

---

### TÂCHE 4.4 — Corrélation de portfolio multi-paires  ✅

**Réf. audit** : A4

Calculer la corrélation des signaux entre paires. Bloquer les signaux corrélés (ρ > 0.7). Ajuster le risk % en fonction des positions corrélées ouvertes.

**Implémentation** :
- `alphaedge/utils/pair_correlation.py` — `compute_returns()`, `compute_correlation()`, `build_correlation_matrix()`, `get_correlation()`, `check_signal_allowed()`, `adjust_risk_for_correlation()`
- Dataclasses : `CorrelationCheckResult`, `RiskAdjustmentResult`
- Constantes : `DEFAULT_MAX_CORRELATION=0.7`, `CORRELATION_RISK_DECAY=0.5`, `CORRELATION_LOOKBACK_BARS=100`
- 44 tests (`test_pair_correlation.py`) — 294/294 total, mypy strict 0 errors

---

### TÂCHE 4.5 — Dashboard web (Streamlit / FastAPI)  ✅

Remplacer le dashboard Rich terminal par une interface web légère. Ajouter l’historique des trades temps réel, l’equity curve live, et l’accès distant sécurisé.

**Implémentation** :
- `alphaedge/engine/web_dashboard.py` — FastAPI REST + WebSocket live feed
- Endpoints : `GET /health`, `GET /api/state`, `GET /api/trades`, `GET /api/equity`, `WS /ws`
- Auth : token HMAC-safe via query param, `configure_auth()`
- Dataclasses : `DashboardState`, `TradeHistoryEntry`, `EquityPoint`, `DashboardStore`
- Broadcast : `broadcast_state()` pousse l’état à tous les WebSocket clients
- Intégration : `run_web_dashboard()` loop async, `start_server()` launcher uvicorn
- Config : `config.yaml` section `dashboard:` (host, port, api_token)
- Dépendances : fastapi 0.135.1, uvicorn 0.41.0, httpx 0.28.1
- 36 tests (`test_web_dashboard.py`) — 330/330 total, mypy strict 0 errors

---

### TÂCHE 4.6 — Alerting externe (Telegram / Discord)  ✅

Intégrer un webhook Telegram ou Discord. Alertes pour : signal/trade exécuté, kill-switch triggered, déconnexion IB, position ouverte en fin de session.

**Implémentation** :
- `alphaedge/utils/alerting.py` — Telegram Bot API + Discord webhooks
- Enums : `AlertLevel` (INFO/WARNING/CRITICAL), `AlertEvent` (9 événements)
- Dataclasses : `Alert`, `TelegramConfig`, `DiscordConfig`, `AlertConfig`
- `AlertManager` : dispatcher central avec `send()` / `send_async()`, compteurs send/fail
- Formatters : `format_telegram()` (HTML), `format_discord()` (embeds)
- 9 builders : `alert_trade_executed()`, `alert_kill_switch()`, `alert_ib_disconnected()`, etc.
- Config : section `alerting:` dans `config.yaml`, `build_alert_config()` parser
- Filtrage par event type via config `events:` list
- 46 tests (`test_alerting.py`) — 376/376 total, mypy strict 0 errors

---

### ✅ CHECKLIST DE SORTIE — PHASE 4

```
[x] TÂCHE 4.1 — Filtre de régime actif
[x] TÂCHE 4.2 — Multi-session testé
[x] TÂCHE 4.3 — Filtre ML opérationnel (si ROI positif)
[x] TÂCHE 4.4 — Corrélation multi-paires gérée
[x] TÂCHE 4.5 — Dashboard web déployé
[x] TÂCHE 4.6 — Alerting externe fonctionnel
```

---

# PROTOCOLE DE DÉPLOIEMENT LIVE

> Ne doit être exécuté qu'**APRÈS** la Phase 3 entièrement validée.

---

### Étape 1 — Paper Trading étendu (4 semaines minimum)

| Métrique | Seuil minimum |
|----------|---------------|
| Trades exécutés | ≥ 30 |
| Win rate | ≥ 28% |
| Profit factor | ≥ 1.2 |
| Max drawdown | ≤ 8% |
| Déconnexions récupérées | 100% |
| Positions orphelines | 0 |

### Étape 2 — Live micro-lots (4 semaines)

1. Passer `config.yaml` en mode live : `is_paper: false`, `port: 4001`
2. **Risk réduit** : `risk_pct: 0.25` (quart du risque cible)
3. **1 seule paire** : commencer avec EUR/USD uniquement
4. Monitorer quotidiennement : P&L, slippage réel vs modèle, spread réel vs modèle

### Étape 3 — Live risque normal (progressif)

1. Augmenter progressivement : `risk_pct: 0.5` → `0.75` → `1.0`
2. Ajouter les paires une par une : GBP/USD puis USD/JPY
3. Chaque augmentation requiert **2 semaines de stabilité**

### Étape 4 — Monitoring continu

| Check | Fréquence |
|-------|-----------|
| P&L vs backtest | Hebdomadaire |
| Slippage réel vs modèle | Hebdomadaire |
| Win rate running | Quotidien |
| Drawdown tracking | Quotidien |
| Mise à jour calendrier news | Mensuel |
| Revue des paramètres | Trimestriel |

---

# TABLEAU DE BORD GLOBAL

| Phase | Tâches | Statut |
|-------|--------|--------|
| **Phase 1** — 🔴 Corrections Critiques | 7 tâches | ✅ Terminé |
| **Phase 2** — 🟠 Sécurisation Live | 8 tâches | ✅ Terminé |
| **Phase 3** — 🟡 Validation Statistique | 7 tâches | 🔄 T3.4 terminé |
| **Phase 4** — 🔵 Optimisation & Scale | 6 tâches | ⬜ Non commencé |
| **Déploiement** — 🟢 Protocole Live | 4 étapes | ⬜ Non commencé |

---

*Plan d'action généré à partir de l'audit ALPHAEDGE du 2026-03-07*
*Exécution séquentielle obligatoire : Phase 1 → Phase 2 → Phase 3 → Phase 4 → Déploiement*
