# PLAN D'ACTION — ALPHAEDGE — 2026-03-20

Sources : `tasks/audits/audit_structural_alphaedge.md`
Total : 🔴 0 · 🟠 3 · 🟡 5 · 🔵 2 · Effort estimé : 2 jours

> **✅ ALL 10 CORRECTIONS COMPLETED — 2026-03-20**
> `make qa` : 504 tests pass, 89% coverage, 0 lint errors, 0 pyright errors

---

## PHASE 1 — CRITIQUES 🔴

> Aucun point critique identifié dans cet audit. ✅

---

## PHASE 2 — MAJEURES 🟠

### [C-01] Décomposer `_execute_signal()` en sous-méthodes

Fichier : `alphaedge/engine/session_lifecycle.py:83`
Problème : `_execute_signal()` (~110 lignes) mélange 8 responsabilités distinctes : sizing, vérification spread, construction ordre, soumission IB, attente fill (asyncio.wait_for 10 s), cancel sur timeout, enregistrement fill dans StrategyState, persistance DailyState. Un bug dans l'une force la relecture de toutes les autres.
Correction : Extraire 3 sous-méthodes privées :
  - `_size_and_validate_order(signal)` → sizing + construction bracket (sync)
  - `_submit_and_await_fill(order)` → soumission IB + asyncio.wait_for + cancel timeout (async)
  - `_record_and_persist_fill(fill)` → mise à jour StrategyState + save_daily_state (sync)
  `_execute_signal()` devient un orchestrateur de 3 appels séquentiels (~20 lignes).
  Chaque sous-méthode peut être testée indépendamment via mock.
  ⚠️ Aucun `.pyx` modifié — `make build` non requis.
Validation :
  ```powershell
  make qa
  # Attendu : 504 tests passing, coverage ≥ 80%, zéro lint error
  ```
Dépend de : Aucune
Statut : ✅ 2026-03-20

---

### [C-02] Supprimer le `pylint: disable` de `run_session()`

Fichier : `alphaedge/engine/session_lifecycle.py:579`
Problème : `# pylint: disable=too-many-branches,too-many-statements` présent sur `run_session()`. Ce disable masque une violation SRP sans la résoudre. Il sera naturellement résolu en extrayant la logique de signal vers `_execute_signal()` (déjà fait via C-01) et en extrayant les handlers d'événements IB.
Correction : Après C-01, vérifier si le disable devient inutile. S'il reste nécessaire, extraire le corps du loop principal en une méthode `_process_bar(bar)` (~30 lignes) et supprimer le disable. La méthode `run_session()` ne doit plus contenir que la boucle de souscription IB et la gestion session start/end.
  ⚠️ Aucun `.pyx` modifié — `make build` non requis.
Validation :
  ```powershell
  make qa-strict
  # Attendu : make qa pass + zéro pylint disable restant sur run_session()
  ```
Dépend de : C-01
Statut : ✅ 2026-03-20

---

### [C-03] Décomposer `backtest.py` (~1 400 lignes)

Fichier : `alphaedge/engine/backtest.py:1`
Problème : Module monolithique mélangeant simulation d'exit, slippage, grouping sessions, filtres USD/global, détection signal, construction TradeRecord, boucle backtest principale, fetch IB, stats, export, vectorbt. Refactorisation partielle déjà engagée (backtest_stats.py, backtest_export.py, backtest_types.py extraits) mais le noyau reste surchargé.
Correction : Extraire dans `alphaedge/engine/` les modules suivants :
  - `backtest_simulation.py` : `_simulate_trade_exit`, `_simulate_trade_exit_fast`, `_simulate_partial_exit_fast`, `_simulate_trailing_partial_exit_fast`, `_close_trade`, `_sl_hit_first`, `_check_sl_tp_hit`
  - `backtest_filters.py` : `_apply_usd_correlation_filter`, `_apply_global_session_limit`, `_group_bars_by_session`
  - `backtest_runner.py` (ou renommer `backtest.py` en `backtest_runner.py`) : `_detect_signal_at_bar`, `_build_trade_record`, `_backtest_pair`, `run_backtest`, `_fetch_pair_trades`
  Mettre à jour `backtest.py` pour qu'il ne soit plus qu'un fichier `__all__` + imports de compatibilité (pattern déjà utilisé pour backtest_stats/export/types).
  ⚠️ Aucun `.pyx` modifié — `make build` non requis.
  ⚠️ Risque régressions imports : vérifier tous les `from alphaedge.engine.backtest import` dans les tests.
Validation :
  ```powershell
  make qa
  # Attendu : 504 tests passing, aucun ImportError, coverage ≥ 80%
  ```
Dépend de : Aucune (peut être fait en parallèle de C-01/C-02)
Statut : ✅ 2026-03-20

---

## PHASE 3 — MINEURES 🟡

### [C-04] Ajouter `alphaedge_daily_state.json` au `.gitignore`

Fichier : `.gitignore`
Problème : `STATE_FILE = "alphaedge_daily_state.json"` (`alphaedge/utils/state_persistence.py:23`) écrit un fichier à la racine du repo. Ce fichier n'est pas dans `.gitignore`. Risque : état quotidien réel (equity courante, trades_today) commité accidentellement.
Correction : Ajouter une ligne dans `.gitignore` :
  ```
  alphaedge_daily_state.json
  alphaedge_daily_state.json.tmp
  ```
  (Le fichier `.tmp` est l'artefact de l'écriture atomique.)
Validation :
  ```powershell
  make qa
  # Attendu : 504 tests passing (changement .gitignore — pas d'impact tests)
  # Vérifier : git status ne montre plus alphaedge_daily_state.json
  ```
Dépend de : Aucune
Statut : ✅ 2026-03-20

---

### [C-05] Lier `_PAIR_SESSION_DEFAULTS` aux constantes LONDON_*

Fichier : `alphaedge/config/loader.py:51`
Problème : Les heures London Open (8:00–9:00 UTC) sont codées en dur dans `_PAIR_SESSION_DEFAULTS` alors que `LONDON_START_HOUR` et `LONDON_END_HOUR` existent dans `constants.py`. Si ces constantes changent dans `constants.py`, `loader.py` ne se met pas à jour automatiquement.
Correction : Remplacer les valeurs hardcodées dans `_PAIR_SESSION_DEFAULTS` par les constantes importées :
  ```python
  from alphaedge.config.constants import (
      LONDON_START_HOUR, LONDON_END_HOUR,
      SESSION_START_HOUR, SESSION_START_MINUTE,
      SESSION_END_HOUR, SESSION_END_MINUTE,
  )

  _PAIR_SESSION_DEFAULTS: dict[str, SessionSpec] = {
      "EURUSD": SessionSpec(LONDON_START_HOUR, 0, LONDON_END_HOUR, 0, "UTC"),
      "GBPUSD": SessionSpec(LONDON_START_HOUR, 0, LONDON_END_HOUR, 0, "UTC"),
      # ...
      "USDJPY": SessionSpec(SESSION_START_HOUR, SESSION_START_MINUTE,
                            SESSION_END_HOUR, SESSION_END_MINUTE,
                            "America/New_York"),
      # ...
  }
  ```
  ⚠️ Vérifier que LONDON_START_MINUTE et LONDON_END_MINUTE existent dans constants.py
  (si non : ajouter `LONDON_START_MINUTE = 0` et `LONDON_END_MINUTE = 0`).
Validation :
  ```powershell
  make qa
  # Attendu : 504 tests passing, aucune régression sur les tests de session
  ```
Dépend de : Aucune
Statut : ✅ 2026-03-20

---

### [C-06] Statuer sur `ml_filter.py` — intégrer ou supprimer

Fichier : `alphaedge/engine/ml_filter.py:1`
Problème : `ml_filter.py` (LogisticRegression walk-forward) est testé en isolation dans `tests/test_ml_filter.py` mais n'est importé nulle part dans le pipeline live (`strategy.py`, `signal_pipeline.py`, `session_lifecycle.py`, `backtest.py` → 0 import chacun). Le module est un orphelin fonctionnel.
Correction : Décision requise — deux options :
  **Option A — Intégration** : brancher `MLSignalFilter` dans `SignalPipeline.detect_engulfing()` comme post-filtre optionnel (activable via `config.yaml`). Documenter l'impact sur le Sharpe (baseline 3.37).
  **Option B — Archivage** : déplacer `ml_filter.py` vers `alphaedge/engine/_experimental/ml_filter.py` et mettre à jour `test_ml_filter.py`. Documenter la décision dans `tasks/lessons.md`.
  ⚠️ Ne pas supprimer sans décision explicite du propriétaire de la stratégie.
Validation :
  ```powershell
  make qa
  # Attendu : 504 tests passing (quel que soit le choix)
  # Option A : vérifier nouveau test de régression sur Sharpe backtest
  ```
Dépend de : Aucune
Statut : ✅ 2026-03-20 — Option B appliquée : archivé dans `_experimental/`, shim de compatibilité dans `ml_filter.py`

---

### [C-07] Documenter le lancement de `web_dashboard.py`

Fichier : `alphaedge/engine/web_dashboard.py:1`
Problème : Serveur FastAPI REST + WebSocket avec auth HMAC. Non importé par `strategy.py` ni `session_lifecycle.py`. Vraisemblablement un processus standalone, mais aucune target `Makefile`, aucun script `scripts/`, aucune mention dans `README.md`.
Correction : Ajouter une target dans le `Makefile` :
  ```makefile
  dashboard:
      .venv/Scripts/python -m uvicorn alphaedge.engine.web_dashboard:app --port 8080
  ```
  Et une section dans `README.md` : "Web Dashboard — Lancer en parallèle de la stratégie via `make dashboard`."
  ⚠️ Confirmer que `web_dashboard.py` lit l'état partagé via `load_daily_state()` et non via une référence directe à `FCRStrategy` (risque de couplage caché).
Validation :
  ```powershell
  make qa
  # Attendu : 504 tests passing (changement Makefile + doc uniquement)
  ```
Dépend de : Aucune
Statut : ✅ 2026-03-20

---

### [C-08] Documenter la limitation Pyright sur `core/__init__.pyi`

Fichier : `alphaedge/core/__init__.pyi:1`
Problème : Pyright résout tous les imports Cython vers `_stubs/` (les `.pyd` sont opaques). Une désynchronisation entre l'interface `.pyx` et le stub correspondant n'est pas détectable statiquement — uniquement à l'exécution.
Correction : Ajouter un commentaire d'avertissement en tête de `__init__.pyi` :
  ```python
  # NOTE: Pyright resolves all core imports to _stubs/ (compiled .pyd are not
  # statically analysable). Interface drift between .pyx and stubs is only
  # detected at runtime or via integration tests. Run `make qa` after any
  # .pyx change to ensure stub compatibility.
  ```
  Envisager d'ajouter un test de fumée dans `conftest.py` qui importe chaque module Cython et appelle la fonction principale avec des données minimes — pour détecter un mismatch d'interface au plus tôt.
Validation :
  ```powershell
  make qa
  # Attendu : 504 tests passing (commentaire uniquement — pas d'impact runtime)
  ```
Dépend de : Aucune
Statut : ✅ 2026-03-20

---

## PHASE 4 — COSMÉTIQUES 🔵

### [C-09] Documenter l'import lazy dans `run_backtest()`

Fichier : `alphaedge/engine/backtest.py:1061`
Problème : `from alphaedge.engine.broker import BrokerConnection` et `from alphaedge.engine.data_feed import HistoricalDataFeed` sont importés à l'intérieur de `run_backtest()` sans commentaire explicatif. Raison probable : éviter un import circulaire et permettre l'import de `backtest.py` sans IB Gateway disponible (tests offline).
Correction : Ajouter un commentaire avant les imports :
  ```python
  # Lazy imports: avoids circular dependency (backtest → broker → backtest)
  # and allows importing this module without IB Gateway present (offline tests).
  from alphaedge.engine.broker import BrokerConnection
  from alphaedge.engine.data_feed import HistoricalDataFeed
  ```
Validation :
  ```powershell
  make qa
  # Attendu : 504 tests passing (commentaire uniquement)
  ```
Dépend de : Aucune
Statut : ✅ 2026-03-20

---

### [C-10] Supprimer `_get_pip_size()` redondant

Fichier : `alphaedge/engine/session_lifecycle.py:55`
Problème : Fonction module-level `_get_pip_size(pair: str) -> float` duplique `PIP_SIZES.get(pair, 0.0001)` déjà disponible via `from alphaedge.config.constants import PIP_SIZES`. Ce pattern est déjà répété 6× dans `backtest.py` (lookup direct). Double maintenance si `PIP_SIZES` évolue.
Correction : Supprimer `_get_pip_size()` et remplacer ses appels par `PIP_SIZES.get(pair, 0.0001)` (ou une constante dédiée `DEFAULT_PIP_SIZE = 0.0001` dans `constants.py`). Grep les occurrences dans tous les modules engine avant suppression.
Validation :
  ```powershell
  make qa
  # Attendu : 504 tests passing, aucune NameError sur _get_pip_size
  ```
Dépend de : Aucune
Statut : ✅ 2026-03-20

---

## SÉQUENCE D'EXÉCUTION

```
Étape 1  →  C-04  (gitignore — 5 min, risque nul)
Étape 2  →  C-09  (commentaire backtest.py — 2 min, risque nul)
Étape 3  →  C-10  (supprimer _get_pip_size — 15 min, risque faible)
Étape 4  →  C-05  (loader.py → constantes LONDON_* — 15 min, risque faible)
Étape 5  →  C-08  (commentaire __init__.pyi — 10 min, risque nul)
Étape 6  →  C-06  (décision ml_filter — 30 min, décision stratégique)
Étape 7  →  C-07  (documenter web_dashboard — 30 min, Makefile + README)
          ── make qa ── [vérification checkpoint PHASE 3+4] ──
Étape 8  →  C-01  (décomposer _execute_signal — 3h, risque moyen)
          ── make qa ──
Étape 9  →  C-02  (nettoyer run_session() pylint disable — 1h, dépend C-01)
          ── make qa-strict ──
Étape 10 →  C-03  (décomposer backtest.py — 4h, risque moyen)
          ── make qa ──
```

> ⚠️ Aucun `.pyx` modifié dans ce plan → `make build` NON requis.
> Si une correction future touche un `.pyx` : `make build` obligatoire AVANT `make qa`.

---

## CRITÈRES PASSAGE EN PRODUCTION

- [x] Zéro 🔴 ouvert
- [x] `make qa` : 100% pass (lint + pyright + pytest ≥80%)
- [ ] Zéro credential dans les logs loguru
- [x] `ALPHAEDGE_PAPER=true` intact dans `.env.example`
- [ ] Bracket order `is_valid` vérifié avant envoi IB
- [ ] `check_daily_limit()` appelé chaque cycle
- [ ] Paper trading validé 5 sessions NYSE minimum

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier | Effort | Statut | Date |
|----|-------|----------|---------|--------|--------|------|
| C-01 | Décomposer `_execute_signal()` | 🟠 | `session_lifecycle.py:83` | ~3h | ✅ 2026-03-20 | 2026-03-20 |
| C-02 | Supprimer pylint disable `run_session()` | 🟠 | `session_lifecycle.py:579` | ~1h | ✅ 2026-03-20 | 2026-03-20 |
| C-03 | Décomposer `backtest.py` monolithique | 🟠 | `backtest.py:1` | ~4h | ✅ 2026-03-20 | 2026-03-20 |
| C-04 | Ajouter `daily_state.json` au `.gitignore` | 🟡 | `.gitignore` | ~5min | ✅ 2026-03-20 | 2026-03-20 |
| C-05 | Lier `_PAIR_SESSION_DEFAULTS` aux constantes | 🟡 | `loader.py:51` | ~15min | ✅ 2026-03-20 | 2026-03-20 |
| C-06 | Statuer sur `ml_filter.py` orphelin | 🟡 | `ml_filter.py:1` | ~30min | ✅ 2026-03-20 | 2026-03-20 |
| C-07 | Documenter lancement `web_dashboard.py` | 🟡 | `web_dashboard.py:1` | ~30min | ✅ 2026-03-20 | 2026-03-20 |
| C-08 | Documenter limitation Pyright `__init__.pyi` | 🟡 | `core/__init__.pyi:1` | ~15min | ✅ 2026-03-20 | 2026-03-20 |
| C-09 | Commenter import lazy `run_backtest()` | 🔵 | `backtest.py:1061` | ~5min | ✅ 2026-03-20 | 2026-03-20 |
| C-10 | Supprimer `_get_pip_size()` redondant | 🔵 | `session_lifecycle.py:55` | ~15min | ✅ 2026-03-20 | 2026-03-20 |
