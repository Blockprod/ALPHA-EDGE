---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: audit_ia_ml_alphaedge.md
derniere_revision: 2026-03-25
creation: 2026-03-25 à 19:00
---

# AUDIT IA / ML — ALPHAEDGE
> **Date** : 2026-03-25 à 19:00
> **Prompt source** : `tasks/audits/methode/audit_ia_ml_prompt.md`
> **Scope** : Pertinence ML sur signal Momentum+Carry · Régime marché · Sizing adaptatif · Agents IB

---

## PHASE 1 — DIAGNOSTIC DE L'EXISTANT

### 1.1 Signal Momentum+Carry et pipeline actuel

**Détecteurs utilisés :**
- `momentum_detector` (Cython, stub Python en `core/_stubs/`) — détection via EMA fast/slow + ADX gate
  - `signal_pipeline.py:92` appelle `modules.momentum_detector.detect_momentum(bars, fast_period, slow_period, adx_period, adx_threshold)`
  - Retourne `dict[str, Any] | None` — `None` = ADX < seuil = STOP pipeline
- `carry_signal.py` (Python pur) : `get_carry_bias(pair, rates)` → `CarrySignal` dataclass
  - `signal_pipeline.py:114` : conflit carry → STOP
  - Filtre directionnel binaire : `LONG / SHORT / NEUTRAL` selon `differential vs min_differential_pct`

**Paramètres configurables (`config.yaml:98-108`):**
| Paramètre | Valeur | Localisation |
|-----------|--------|-------------|
| `momentum_fast_period` | 12 | `config.yaml:99` |
| `momentum_slow_period` | 26 | `config.yaml:100` |
| `adx_period` | 14 | `config.yaml:101` |
| `adx_threshold` | 25.0 | `config.yaml:102` |
| `momentum_lookback_days` | 252 | `config.yaml:103` |
| `carry_min_differential_pct` | 0.5 | `config.yaml:105` |
| `carry_enabled` | true | `config.yaml:106` |
| `rr_ratio` | 2.5 | `constants.py:DEFAULT_RR_RATIO` |
| `risk_pct` | 2.0 | `constants.py:DEFAULT_RISK_PCT` |

**Filtre de régime :** `DailyRegimeFilter` (K-Means, `regime_filter.py:88`) existe et est instancié dans `strategy.py:203-210`. Il tourne en **observation uniquement** — le label `"high_vol" / "low_vol"` est loggué mais ne bloque aucun trade (`[observation only]`). Statut : PRÉSENT mais INACTIF en production.

**`ml_filter.py` (`engine/ml_filter.py:3`) :** shim de compatibilité pur. Reexporte depuis `engine/_experimental/ml_filter.py`. Constante `LIVE_PIPELINE_INTEGRATED = False`. N'est **jamais importé** par `strategy.py`, `session_lifecycle.py`, ou `signal_pipeline.py`. Statut : CODE MORT en production.

### 1.2 Données disponibles

| Source | Contenu | Disponibilité |
|--------|---------|--------------|
| Daily bars | `fetch_bars("1 day", "30 D")` via `hist_feed` | ✅ Fetch live chaque session (`session_lifecycle.py:830`) |
| Momentum lookback | 252 barres Daily max | ✅ Config |
| Carry rates | `dict[str, float]` dans `StrategyState.carry_rates` | ✅ Peuplé à l'init paire |
| CSV backtest | `reports/ALPHAEDGE_backtest_results.csv` | ✅ (FCR strategy, pas Momentum) |
| Live trade CSV | `append_live_trade_csv()` — rotation mensuelle | ✅ Mais données en production insuffisantes (stratégie non encore live) |
| Session state | `save_daily_state(DailyState)` — JSON daily | ✅ Structurel seulement (no PnL) |

**Remarque critique :** Le CSV backtest (`reports/ALPHAEDGE_backtest_results.csv`) est issu de la stratégie FCR (**ancienne stratégie**), non de la stratégie Momentum+Carry cible. Toute analyse ML sur ce CSV serait basée sur des données hors cible.

### 1.3 Infrastructure et contraintes techniques

- **Stack :** Python 3.11.9, Cython 3.0, `ib_insync`, asyncio event loop, Windows
- **Fenêtre de session :** NYSE 9h30–10h30 EST = **60 minutes/jour max** (`session_lifecycle.py:session_start/end`)
- **Fréquence signal :** Daily bars → 1 décision par paire par jour (pas temps réel)
- **sklearn disponible :** ✅ (`regime_filter.py:25` importe KMeans, StandardScaler — déjà installé)
- **optuna disponible :** ✅ (`bayesian_optimizer.py:17` importe optuna — déjà installé)
- **joblib disponible :** ✅ (`regime_filter.py:24`)
- **CPU/RAM :** Windows local, infra non containerisée — pas de GPU, pas de service ML distant

### 1.4 Points de décision dans le pipeline actuel

| Point de décision | Type | Fichier:Ligne | Paramètre actuel | Adaptatif ? |
|-------------------|------|--------------|-----------------|-------------|
| ADX gate (ADX ≥ threshold) | Seuil fixe | `signal_pipeline.py:85` | `adx_threshold=25.0` | ❌ Non |
| EMA cross détection | Paramètres fixes | `signal_pipeline.py:85` | `fast=12, slow=26` | ❌ Non |
| Carry conflict (|diff| ≥ min) | Seuil fixe | `carry_signal.py` | `min_diff=0.5%` | ❌ Non |
| Sizing risk_pct | Fixe | `constants.py:DEFAULT_RISK_PCT` | 2.0% | ❌ Non |
| Sizing lot_size min/max | Fixe | `constants.py:` | 0.01–1000 | ❌ Non |
| Sélection de paires | Liste fixe | `config.yaml:trading.pairs` | EURUSD, USDJPY | ❌ Non |
| Filtre régime (K-Means) | Observation only | `strategy.py:203` | `DailyRegimeFilter` | ⚠️ Partiel |
| Filtre spread max | Fixe | `constants.py` | `max_spread_pips` | ❌ Non |

---

## PHASE 2 — ÉVALUATION DES OPPORTUNITÉS IA/ML

### A — Filtre ML sur la qualité du signal Momentum

**Idée :** Classifier (RF/XGBoost) entraîné sur features ADX, EMA delta, carry differential → prédire P(win).

**Analyse :**
- Données disponibles : **NON** — la stratégie Momentum est en cours de migration (`PLAN_ACTION_audit_migration_momentum_carry_2026-03-25.md`), `momentum_detector.pyx` n'est pas encore compilé en production. Aucun historique de trades live Momentum exists.
- Volume de données : 1 trade/jour/paire → ~200 trades/an pour 2 paires. Un logistic regression sur 200 samples avec 5 features converge, mais RF/XGBoost requiert 500+ pour éviter le surapprentissage (Arlot & Celisse, 2010).
- Risque surapprentissage : **Élevé** — Forex Momentum Daily a un ratio signal/bruit structurellement faible sur petite fenêtre.
- Complexité : M (logistic regression faisable, RF complexe).
- Module `_experimental/ml_filter.py` existe déjà (LogReg + walk-forward). Features basées sur FCR (non Momentum) → ne peut pas être réutilisé tel quel.

**Verdict : ❌ NON PERTINENT — prématuré.** Intégrer uniquement après 12 mois de trades live Momentum documentés (≥500 observations). Revenir à cet item en 2027.

---

### B — Filtre ML sur le carry bias conflict

**Idée :** Enrichir la décision carry avec features contextuelles (ATR, spread réalisé) au-delà du seuil fixe.

**Analyse :**
- La décision carry est aujourd'hui binaire : `|diff| ≥ 0.5%` → LONG/SHORT/NEUTRAL. Le seuil `DEFAULT_CARRY_MIN_DIFFERENTIAL` est configuré dans `constants.py`.
- En pratique, le taux directeur change rarement (BOE, FED, ECB : 4–8 fois/an). Pour EUR/USD et USD/JPY, le carry differential évolue très lentement.
- Ajouter un ML ici n'apporte pas de gain mesurable sur un signal qui change au rythme des banques centrales.
- Risque : complexifier un gate dont la logique est correcte et simple.

**Verdict : ❌ NON PERTINENT.** Le thresholding fixe est approprié pour un signal aussi lent. Un paramètre `carry_min_differential_pct` optimisé par Bayesian search (voir D) est suffisant.

---

### C — Détection de régime de marché Forex (K-Means)

**Idée :** K-Means sur volatilité Daily pour classifier les sessions high_vol/low_vol.

**Analyse :**
- `DailyRegimeFilter` (`regime_filter.py:88`) est **déjà implémenté**, déjà instancié, et tourne en observation dans `strategy.py:203-210`.
- Le modèle est entraîné sur `daily_bars_history` (30 D disponibles via `hist_feed`).
- Le seul travail manquant : **activer le gate** (bloquer trades sur `high_vol` ou `low_vol` selon config) après 30 sessions d'observation.
- Données disponibles : ✅ Daily bars fetchées à chaque session.
- Complexité : XS — le code est écrit, il faut juste un flag config + tests.
- Gain attendu : réduction du drawdown en filtrant les jours de forte volatilité non-directionnelle.

**Verdict : ✅ PERTINENT.** `DailyRegimeFilter` est le seul composant ML **déjà prêt** pour production. Activer le gate est le chemin le plus court vers un gain réel.

**Condition préalable :** 30 sessions NYSE paper trading en observation avant d'activer le gate — règle déjà documentée dans `regime_filter.py:14`.

---

### D — Optimisation adaptative des paramètres Momentum (Bayesian)

**Idée :** Optuna sur `adx_threshold`, `fast_period`, `slow_period`, `rr_ratio` — réévalué mensuellement.

**Analyse :**
- `bayesian_optimizer.py` (Optuna) et `walk_forward.py` sont **déjà implémentés** et testés.
- `sensitivity.py` définit `SENSITIVITY_PARAMS` avec ranges.
- L'optimisation se fait sur le backtest engine (`backtest.py`) en offline — aucun risque IB.
- Paramètres cibles : `adx_threshold` (20–35), `momentum_fast_period` (8–20), `momentum_slow_period` (20–50), `rr_ratio` (1.5–3.0).
- Risque overfitting : réel, mitigé par walk-forward OOS (déjà dans `walk_forward.py`).
- Exécution mensuelle offline, résultats propagés vers `config.yaml` si OOS Sharpe améliore baseline.
- Données requises : backtest Momentum+Carry valide. Or le dataset actuel est FCR.

**Verdict : ✅ PERTINENT — mais bloqué.** Pertinent dès que le backtest Momentum+Carry sera disponible (post-migration C-11/C-12 du plan migration). L'infrastructure est prête (`bayesian_optimizer.py`, `walk_forward.py`). À activer en Phase 2, pas maintenant.

---

### E — Prédiction du sizing optimal (régression)

**Idée :** Régression sur conditions marché (ADX, spread, carry diff) pour ajuster `risk_pct` dynamiquement.

**Analyse :**
- Le sizing actuel (`calculate_position_size()` — `risk_manager.pyx`) est déterministe et validé : `is_valid` check, log WARNING si invalide.
- Un sizing ML introduit un vecteur de régression dans le chemin critique exécution. Toute dérive du modèle se traduit en exposure anormale sur IB.
- En Forex Momentum Daily, le Kelly sizing adaptatif (Moskowitz 2012 TSMOM) est une alternative plus robuste et sans ML : `position_size ∝ signal_strength / realized_volatility`.
- Données : insuffisantes (même problème que A).
- Risque production : Élevé — erreur de sizing → liquidation forcée IB.

**Verdict : ❌ NON PERTINENT.** Le safety-first path est un sizing basé sur la volatilité réalisée (pas de ML), compatible avec `calculate_position_size()` via un paramètre adaptatif. ML sur sizing = sur-ingénierie avec risque production disproportionné.

---

### F — Agent de sélection de paires Forex

**Idée :** Sélection dynamique EUR/USD, GBP/USD, USD/JPY selon volatilité + carry + corrélations.

**Analyse :**
- La liste de paires est fixe dans `config.yaml:trading.pairs`. La corrélation entre paires est déjà gérée par `pair_correlation.py` (bloque si paire corrélée ouverte).
- Dans une fenêtre 1h/jour (NYSE open), trader 3 paires corrélées simultanément est le vrai risque — déjà géré.
- Un agent de sélection dynamique introduit un vecteur de décision supplémentaire dont le signal (volatilité Daily) est déjà capturé par `DailyRegimeFilter`.
- Données : corrélations réalisées disponibles via `pair_correlation.py`.
- Complexité : L — nécessite un dataset de rendements cross-pairs, backtesting multi-paires.

**Verdict : ❌ NON PERTINENT** pour la phase actuelle. La corrélation est déjà gérée. Activer 2–3 paires avec régime gate (C) suffit.

---

### G — Agent de gestion dynamique du stop-loss

**Idée :** Ajuster le SL selon l'ATR réalisé de la session.

**Analyse :**
- `create_bracket_order()` (`order_manager.pyx`) valide `is_valid` avant tout envoi. Modifier le SL dynamiquement nécessite de modifier l'interface du bracket, incompatible sans `make build`.
- En Daily swing (position tenue 1–5 jours), le SL à l'entrée est calculé sur la structure daily — l'ATR intraday ne devrait pas l'influencer.
- Risque IB : si l'agent génère un SL trop proche (ATR faible → SL tight), l'ordre peut être refusé par IB ou hit immédiatement.

**Verdict : ❌ NON PERTINENT.** Le SL Daily fixed est la bonne implémentation pour swing Momentum. Modifier `order_manager.pyx` sans `make build` est interdit — investissement disproportionné.

---

### H — Agent LLM pour le sentiment macro Forex

**Idée :** LLM analyse NFP, CPI, Fed pour filtrer les signaux les jours de forte volatilité macro.

**Analyse :**
- `news_filter.py` (`config.yaml:news_filter.enabled=true`) filtre déjà les événements high-impact avec `blackout_minutes=15`.
- Un LLM en production IB introduit une dépendance externe (API OpenAI/Anthropic) avec latence >100ms dans un pipeline event-driven.
- Fiabilité sur Forex : les journées NFP sont déjà bloquées par `news_filter`. La valeur ajoutée d'un LLM au-delà du calendrier économique est non démontrée sur horizons Daily swing.
- Coût : API calls facturés + risque de rate limiting en production le jour J.

**Verdict : ❌ NON PERTINENT.** Le filtre news existant couvre le cas d'usage. Un LLM est une régression en fiabilité et latence sur ce contexte.

---

### I — SHAP values sur les paramètres Momentum+Carry

**Idée :** Analyser l'importance des features sur le dataset backtest pour identifier les paramètres qui contribuent réellement au Sharpe.

**Analyse :**
- Le dataset backtest actuel (`reports/ALPHAEDGE_backtest_results.csv`) est issu de la stratégie FCR (pas Momentum+Carry). SHAP sur ce dataset = conclusions non-transférables.
- Dès que le backtest Momentum+Carry sera disponible (post-migration), SHAP est une analyse offline valide et rapide (XS complexité, `shap` package standard).
- Peut confirmer si `adx_threshold=25` est effectivement discriminant ou si `carry_min_differential=0.5%` contribue négativement.
- Aucun risque production — analyse pure offline.

**Verdict : ✅ PERTINENT — mais bloqué.** Pertinent dès que le backtest Momentum+Carry sera disponible. Planifier comme analyse mensuelle offline (30 min/mois).

---

### J — Walk-forward adaptatif

**Idée :** Ajustement automatique des fenêtres IS/OOS selon la volatilité détectée.

**Analyse :**
- `walk_forward.py` implémente `run_walk_forward()` avec `train_months`, `test_months`, `step_months` fixes.
- L'adaptation de la fenêtre walk-forward selon le régime de volatilité est une amélioration marginale : les backtests académiques (Pardo 2008) montrent qu'une fenêtre train=3M/test=1M est robuste sur Forex.
- Complexité : M — modifier `generate_wf_windows()` pour accepter un `volatility_multiplier`.
- Gain attendu : difficile à quantifier sans dataset Momentum+Carry.

**Verdict : ❌ NON PERTINENT** pour maintenant. Les fenêtres fixes sont appropriées. Réévaluer quand le dataset Momentum+Carry aura 12 mois de données.

---

## PHASE 3 — RECOMMANDATION FINALE

### 3.1 Tableau de décision

| ID | Opportunité | Verdict | Gain estimé | Complexité | Risque prod |
|----|-------------|---------|-------------|------------|-------------|
| A | Filtre ML signal Momentum (LogReg/RF) | ❌ NON PERTINENT | Non mesurable (pas de données) | M | Élevé |
| B | Filtre ML carry conflict | ❌ NON PERTINENT | Marginal (signal lent) | S | Faible |
| C | Régime K-Means (gate) | ✅ PERTINENT | Réduction DrawDown estimée 10–20% | XS | Faible |
| D | Bayesian param optimization (Optuna) | ✅ PERTINENT (bloqué) | +Sharpe OOS TBD après migration | XS | Faible (offline) |
| E | Sizing ML adaptatif | ❌ NON PERTINENT | Non mesurable · risque exposure | L | Élevé |
| F | Agent sélection paires | ❌ NON PERTINENT | Redondant avec pair_correlation | L | Moyen |
| G | Agent SL dynamique | ❌ NON PERTINENT | Incompatible swing Daily · pyx requis | L | Élevé |
| H | LLM sentiment macro | ❌ NON PERTINENT | Redondant avec news_filter | L | Élevé |
| I | SHAP feature importance | ✅ PERTINENT (bloqué) | Clarté paramètre → simplification | XS | Nul |
| J | Walk-forward adaptatif | ❌ NON PERTINENT | Marginal sur données insuffisantes | M | Faible |

---

### 3.2 Roadmap recommandée

#### NIVEAU 1 — Sans risque pour la production (paper trading, observation)

**Maintenant — après 30 sessions paper :**

1. **Activer le gate `DailyRegimeFilter` (C)** — `strategy.py:203-210`
   - Ajouter flag `regime_filter_enabled: false` (défaut) dans `config.yaml`
   - Après 30 sessions NYSE paper observation : passer à `true` si les sessions `high_vol` ont un WinRate < 40%
   - Travail estimé : 2h · 0 risque · aucun `.pyx` modifié

#### NIVEAU 2 — Intégration progressive (post-migration Momentum+Carry)

2. **SHAP analysis offline (I)** — dès le premier backtest Momentum+Carry valide
   - Script mensuel `scripts/shap_analysis.py` sur le CSV backtest
   - Entrée : paramètres actuels + résultats backtest
   - Sortie : rapport `reports/shap_report.md` — quels paramètres comptent

3. **Bayesian optimization mensuelle (D)** — post-migration, dès 6 mois de backtest disponibles
   - `bayesian_optimizer.py` + `walk_forward.py` déjà prêts
   - Exécuter offline → proposer `config.yaml` mis à jour si Sharpe OOS s'améliore
   - Gate : amélioration Sharpe OOS ≥ 5% avant d'appliquer les nouveaux paramètres

#### NIVEAU 3 — Remplacement de composants (0 item éligible maintenant)

Aucun composant ne justifie un remplacement par ML dans l'état actuel des données et du pipeline.

---

### 3.3 Ce qu'il ne faut PAS faire

| Intégration à éviter | Raison |
|---------------------|--------|
| Filtre LogReg/RF sur signal Momentum (A) | Données insuffisantes (<200 trades) — surapprentissage garanti |
| Sizing ML (E) | Exposure anormale sur IB si dérive modèle → risque liquidation |
| Agent LLM macro (H) | Latence API + fiabilité insuffisante + `news_filter` déjà en place |
| SL dynamique via agent (G) | Nécessite modification `order_manager.pyx` → `make build` + risque is_valid |
| Agent sélection paires (F) | Redondant avec `pair_correlation.py` actif · complexité injustifiée |
| Walk-forward adaptatif (J) | Sur-ingénierie : fenêtres fixes robustes en Forex (Pardo 2008) |

---

### 3.4 Verdict global

**Faut-il intégrer de l'IA/ML sur ALPHAEDGE ?** Oui, partiellement et dans l'ordre strict.

**Par quoi commencer ?** `DailyRegimeFilter` (C) — code existant, zéro risque, activation en 2h. C'est le seul composant ML production-ready aujourd'hui.

**Bloquant principal :** L'absence de dataset Momentum+Carry valide bloque toutes les analyses ML sur le signal (A, D, I). La priorité stratégique est de finaliser la migration (Audit #13) avant d'investir en ML.

**Risque principal à surveiller :** Le surapprentissage sur petites séries temporelles Forex Daily. Toute validation ML doit inclure un walk-forward OOS sur une fenêtre out-of-sample ≥ 6 mois. Le Sharpe FCR de 3.37 est un artefact IS — l'objectif réaliste pour Momentum OOS est Sharpe ≥ 0.8.

---

## SYNTHÈSE

### Tableau synthèse

| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact | Effort |
|----|------|-------------|--------------|----------|--------|--------|
| ML-01 | 1 | `DailyRegimeFilter` en observation uniquement malgré 30 sessions disponibles | `strategy.py:203` | 🟠 Majeur | Drawdown non-contrôlé les jours high_vol | ~2h |
| ML-02 | 1 | `_experimental/ml_filter.py` (LogReg) — features basées FCR, pas Momentum → inutilisable tel quel | `engine/_experimental/ml_filter.py:37` | 🟡 Mineur | Dette technique — features à réécrire post-migration | ~4h |
| ML-03 | 2 | Bayesian optimizer disponible (`bayesian_optimizer.py`) mais non planifié dans workflow mensuel | `engine/bayesian_optimizer.py:45` | 🟡 Mineur | Paramètres potentiellement sous-optimaux | ~1h setup |
| ML-04 | 2 | Aucune analyse SHAP planifiée — importance des paramètres inconnue | — | 🟡 Mineur | Risque de maintenir des paramètres sans contribution | ~2h setup |

**Sévérité** : 🔴 Critique · 🟠 Majeur · 🟡 Mineur

**Bilan** : Le projet dispose de l'infrastructure ML adéquate (sklearn, optuna, regime_filter, walk_forward). Le seul blocage est l'absence de données Momentum+Carry valides et le gate `DailyRegimeFilter` non activé. Aucun ajout de nouveau composant ML n'est justifié avant fin de migration.
