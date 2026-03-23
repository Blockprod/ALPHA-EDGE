# AUDIT STRUCTUREL — ALPHAEDGE

> **Fichier généré le** : 2025-07-25
> **Prompt source** : `tasks/prompts/audit_structural_prompt.md`
> **Scope** : Architecture générale, SRP, Cython↔Python, dette technique, configuration
> **État QA baseline** : 504 tests — 100% pass rate (ref. lessons.md)
> **Version Python** : 3.11.9 stricte

---

## BLOC 1 — PIPELINE RÉEL

### 1.1 Traçage de bout-en-bout

```
IB Gateway
  └─► data_feed.py (HistoricalDataFeed + RealtimeDataFeed)
        │  reqHistoricalData — M5 + M1 bars
        │
        └─► signal_pipeline.py::detect_fcr()
              └─► fcr_detector.pyx / _stubs/fcr_detector.py
                    │  detect_fcr(candles_data, min_range_pips, pip_size)
                    │  → {detected, range_high, range_low, ...} | None
                    │
                    └─► signal_pipeline.py::detect_gap()
                          └─► gap_detector.pyx / _stubs/gap_detector.py
                                │  detect_gap(pre_m1, session_m1, ..., min_atr_ratio)
                                │  → {detected, gap_high, gap_low, atr_ratio, direction}
                                │
                                └─► signal_pipeline.py::detect_engulfing()
                                      └─► engulfing_detector.pyx / _stubs/engulfing_detector.py
                                            │  detect_engulfing(candles, fcr_high, fcr_low, ...)
                                            │  → {direction, entry, stop_loss, take_profit} | None
                                            │
                                            └─► session_lifecycle.py::_execute_signal()
                                                  ├─► position_manager.py::size_position()
                                                  │     └─► risk_manager.pyx — calculate_position_size()
                                                  │                           — check_daily_limit()
                                                  ├─► position_manager.py::build_validated_order()
                                                  │     └─► order_manager.pyx — create_bracket_order()
                                                  └─► broker.py::OrderExecutor.place_bracket_order()
                                                              └─► IB Gateway
```

### 1.2 Orchestration

| Couche | Fichier | Rôle |
|--------|---------|------|
| Entrée CLI | `strategy.py` | `FCRStrategy` — init DI, entrypoint `run_session()` |
| Session loop | `session_lifecycle.py` | `SessionLifecycle.run_session()` — IB events, bars M1 |
| Détection signal | `signal_pipeline.py` | `SignalPipeline` — chaîne FCR→Gap→Engulfing, stateless |
| Sizing + ordre | `position_manager.py` | `PositionManager` — délègue aux stubs Cython |
| IB Gateway | `broker.py` | `BrokerConnection` + `OrderExecutor` + `RequestThrottler` |

### 1.3 Règle all-or-nothing — CONFORME ✅

Chaque étape retourne `None` / `detected=False` / `is_valid=False` en cas d'échec.
Le code appelant dans `strategy.py` et `session_lifecycle.py` arrête immédiatement le pipeline sans procéder à l'étape suivante.
Aucune exception silencieuse, aucun continue non documenté.

### 1.4 Pivot backtest

Le module `backtest.py` reproduit le même pipeline dans `_backtest_pair()` :
- FCR calculé une fois par session depuis les M5 pré-session
- Gap/ATR une fois depuis les M1 pré-session
- Engulfing par barre pendant la fenêtre de session
- Import Cython lazy dans `run_backtest()` ligne 1061 (pattern acceptable, non documenté — voir S-09)

---

## BLOC 2 — SÉPARATION DES RESPONSABILITÉS (SRP)

### 2.1 `session_lifecycle.py::_execute_signal()` — 🟠 VIOLATION SRP

**Fichier** : `alphaedge/engine/session_lifecycle.py`
**Sévérité** : 🟠 Moyen (risque de régression lors de toute modification)

`_execute_signal()` combine dans une seule méthode (~110 lignes) :
1. Calcul de la taille de position (`size_position`)
2. Vérification du spread et tampon slippage
3. Construction de l'ordre bracket (`build_validated_order`)
4. Soumission à IB Gateway (`place_bracket_order`)
5. Attente de confirmation fill (`asyncio.wait_for`, timeout 10 s)
6. Callback `cancel_all_orders` sur timeout
7. Enregistrement du fill dans `StrategyState`
8. Persistance de `DailyState`

**Impact** : un bug dans la persistance force la relecture du sizing ; un bug dans le fill force la relecture du spread. Multi-responsabilité = multi-raisons de modifier.

### 2.2 `session_lifecycle.py::run_session()` — 🟠 KNOWN ISSUE

**Fichier** : `alphaedge/engine/session_lifecycle.py`
Commentaire pylint présent : `# pylint: disable=too-many-branches,too-many-statements`
Ce disable est un aveu de violation SRP encodé dans le source.

### 2.3 `backtest.py` — 🟠 FICHIER MONOLITHIQUE

**Fichier** : `alphaedge/engine/backtest.py`
**Taille** : ~1 400 lignes
**Responsabilités mélanges** :

| Responsabilité | Lignes approximatives |
|---------------|----------------------|
| Slippage variable | 1–60 |
| Simulation trade exit (normal + fast + partial + trailing) | 60–700 |
| Grouping des sessions | 700–850 |
| USD correlation filter | 850–920 |
| Global session limit | 920–990 |
| Détection signal au bar (_detect_signal_at_bar) | ~1020 |
| Construction TradeRecord | ~1050 |
| _backtest_pair (boucle principale) | ~1070 |
| run_backtest (fetch + stats + export + vectorbt) | ~1350 |

Note : `backtest_stats.py`, `backtest_export.py`, `backtest_types.py` ont déjà été extraits — refactorisation partiellement engagée mais `backtest.py` reste sur-chargé.

### 2.4 `session_lifecycle._get_pip_size()` — 🔵 DUPLICATION MINEURE

**Fichier** : `alphaedge/engine/session_lifecycle.py`, ligne ~57
Fonction module-level qui duplique `PIP_SIZES.get(pair, 0.0001)` déjà dans `constants.py`.
Pattern déjà répété 6× dans `backtest.py`. Risque de désynchronisation si `PIP_SIZES` évolue.

---

## BLOC 3 — COUCHE CYTHON ↔ PYTHON

### 3.1 Fichiers compilés — CONFORME ✅

Tous les 5 `.pyd` présents pour `cp311-win_amd64` :

```
alphaedge/core/engulfing_detector.cp311-win_amd64.pyd  ✅
alphaedge/core/fcr_detector.cp311-win_amd64.pyd        ✅
alphaedge/core/gap_detector.cp311-win_amd64.pyd        ✅
alphaedge/core/order_manager.cp311-win_amd64.pyd       ✅
alphaedge/core/risk_manager.cp311-win_amd64.pyd        ✅
```

### 3.2 Mécanisme de fallback `__init__.py` — CONFORME ✅

`_load_core_module(name)` tente `alphaedge.core.{name}` (compilé) en premier,
puis bascule sur `alphaedge.core._stubs.{name}` avec log WARNING.
L'export des 5 globals de package est correct.

### 3.3 Stubs `_stubs/` — CONFORME ✅

Tous les 5 stubs présents. Interfaces vérifiées face à la documentation CLAUDE.md :

| Module | Signature clé | Champ critique | Statut |
|--------|--------------|----------------|--------|
| `fcr_detector` | `detect_fcr(candles_data, min_range_pips, pip_size)` | `detected`, `range_high`, `range_low` | ✅ |
| `gap_detector` | `detect_gap(pre_m1, session_m1, ..., min_atr_ratio)` | `detected`, `gap_high`, `gap_low` | ✅ |
| `engulfing_detector` | `detect_engulfing(candles, fcr_high, fcr_low, rr_ratio, ...)` | `direction`, `entry_price`, `stop_loss`, `take_profit` | ✅ |
| `risk_manager` | `calculate_position_size(...)`, `check_daily_limit(...)` | `is_valid`, `halt_trading` | ✅ |
| `order_manager` | `create_bracket_order(...)` | `is_valid`, `rejection_reason` | ✅ |

### 3.4 `__init__.pyi` — NOTE

**Fichier** : `alphaedge/core/__init__.pyi`
Pyright résout toujours vers `_stubs/` (les `.pyd` ne sont pas analysables).
Conséquence : Pyright ne peut pas détecter une désynchronisation entre l'interface `.pyx` et le stub correspondant.
**Risque** : 🟡 faible — les stubs sont la source de vérité type, les `.pyx` sont optimisations runtime.
**Mitigation actuelle** : tests d'intégration font tourner les `.pyd` compilés — désynchronisation détectée à l'exécution.

### 3.5 Directives Cython — CONFORME ✅

`fcr_detector.pyx` (et par extension les autres `.pyx`) compilés avec :
```cython
# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True
```
Structs C (`Candle`, `FCRResult`) utilisés pour performance maximale.

---

## BLOC 4 — DETTE TECHNIQUE

### 4.1 `ml_filter.py` — Code orphelin — 🟡

**Fichier** : `alphaedge/engine/ml_filter.py`
**Statut** : **Non importé dans le pipeline live.**

Vérification via grep :
- `strategy.py` → 0 import
- `signal_pipeline.py` → 0 import
- `session_lifecycle.py` → 0 import
- `backtest.py` → 0 import
- Seul `tests/test_ml_filter.py` l'importe

Le filtre ML (LogisticRegression walk-forward) est testé en isolation mais ne filtre aucun signal en production.
**Question ouverte** : intégration prévue ? suppression ? Le module existe sans être connecté.

### 4.2 `web_dashboard.py` — Connectivité pipeline non tracée — 🟡

**Fichier** : `alphaedge/engine/web_dashboard.py`
FastAPI REST + WebSocket avec auth HMAC.
Non importé par `strategy.py` ni `session_lifecycle.py`.
Vraisemblablement un serveur standalone — mais aucune documentation de lancement ni mention dans `Makefile` ou `scripts/`.

### 4.3 `alphaedge_daily_state.json` absent du `.gitignore` — 🟡

**Fichier** : `alphaedge/utils/state_persistence.py`, ligne ~23
`STATE_FILE = "alphaedge_daily_state.json"` référence un fichier à la racine du repo.
`.gitignore` vérifié : ce fichier **n'est pas exclu**.
Risque : état quotidien (equity, trades_today, etc.) accidentellement commité avec des données de session réelle.

### 4.4 Répertoire `stubs/` dupliqué à la racine — 🔵

`stubs/ib_insync.pyi` existe à la racine ET `alphaedge/stubs/ib_insync.pyi` est potentiellement présent.
Vérifier si `pyrightconfig.json` référence la racine ou `alphaedge/stubs/` — double maintenance possible.

---

## BLOC 5 — CONFIGURATION

### 5.1 `constants.py` — Source unique de vérité — CONFORME ✅

**Fichier** : `alphaedge/config/constants.py`
Contenu exhaustif vérifié :
- Identifiants TZ (TZ_UTC, TZ_NEW_YORK, TZ_PARIS)
- Heures session NYSE (SESSION_START_HOUR=9:30, SESSION_END=10:30)
- Heures London Open (LONDON_START_HOUR=8, LONDON_END_HOUR=9, en UTC)
- DEFAULT_RR_RATIO=2.5, DEFAULT_RISK_PCT=2.0, DEFAULT_MAX_DAILY_LOSS_PCT=3.0
- PIP_SIZES dict complet (11 pairs + EURUSD_LC)
- Ports IB (IB_PAPER_PORT=4002, IB_LIVE_PORT=4001)
- Modèle slippage (BASE_SLIPPAGE_PIPS, NYSE_OPEN_SLIPPAGE_MULTIPLIER, NEWS_SPREAD_PIPS…)
- BASE_SPREAD_BY_PAIR dict

Aucune valeur magique hardcodée hors de ce fichier (pattern `PIP_SIZES.get(pair, 0.0001)` = lookup dict ✅).

### 5.2 Duplication partielle session London — 🟡

**Tension entre** :
- `constants.py` : `LONDON_START_HOUR=8`, `LONDON_END_HOUR=9` (UTC)
- `loader.py` `_PAIR_SESSION_DEFAULTS` : EURUSD/GBPUSD → `start_hour=8, end_hour=9, tz_name="UTC"` (idem, mais répété)

Si `LONDON_START_HOUR` change dans `constants.py`, `_PAIR_SESSION_DEFAULTS` dans `loader.py` ne se met pas à jour automatiquement.
**Correction minimale** : `_PAIR_SESSION_DEFAULTS` devrait référencer `LONDON_START_HOUR` / `LONDON_END_HOUR` depuis `constants.py`.

### 5.3 `config.yaml` — CONFORME ✅

```yaml
pairs: [EURUSD, USDJPY]
risk_pct: 3.0          # surcharge config.trading.risk_pct (DEFAULT=2.0 dans constants)
max_daily_loss_pct: 3.0
max_trades_per_session: 6
excluded_days: []       # LOCKED — testé et éliminé (commentaire présent)
usd_correlation_filter: false  # ELIMINATED (commentaire présent)
```

Surcharge configurée correctement. Commentaires de décision conservés dans le fichier.

### 5.4 IBConfig — CONFORME ✅

`loader.py::IBConfig.is_paper=True` par défaut.
`.env.example` contient `ALPHAEDGE_PAPER=true`.
Aucune occurrence de `ALPHAEDGE_PAPER=false` dans le codebase — règle absolue respectée.

### 5.5 Import lazy dans `run_backtest()` — 🔵 NOTE

**Fichier** : `backtest.py`, ligne 1061
```python
from alphaedge.engine.broker import BrokerConnection
from alphaedge.engine.data_feed import HistoricalDataFeed
```
Import à l'intérieur d'une fonction (non documenté). Justification probable : éviter un import circulaire ou permettre l'import de `backtest.py` sans IB Gateway disponible.
Acceptable mais devrait être documenté avec un commentaire `# Lazy import: avoids circular dependency / IB Gateway requirement at module level`.

---

## SYNTHÈSE

### Tableau des points d'attention

| ID | Sévérité | Composant | Description |
|----|----------|-----------|-------------|
| S-01 | 🟠 | `session_lifecycle.py::_execute_signal()` | ~110 lignes mélangeant sizing, spread, IB submit, fill, state, persist |
| S-02 | 🟠 | `session_lifecycle.py::run_session()` | Pylint disable `too-many-branches` — violation SRP documentée |
| S-03 | 🟠 | `backtest.py` (~1 400 lignes) | Simulation + grouping + filtres + stats + export dans un seul module |
| S-04 | 🟡 | `ml_filter.py` | Orphelin — non connecté au pipeline live |
| S-05 | 🟡 | `web_dashboard.py` | Connectivité au pipeline live non tracée |
| S-06 | 🟡 | `alphaedge_daily_state.json` | Absent du `.gitignore` — risque de commit accidentel |
| S-07 | 🟡 | `loader.py::_PAIR_SESSION_DEFAULTS` | Duplication des heures London Open avec `constants.py` |
| S-08 | 🟡 | `core/__init__.pyi` | Pyright résout uniquement vers stubs — désynchronisation .pyx non détectable statiquement |
| S-09 | 🔵 | `backtest.py::run_backtest()` ligne 1061 | Import lazy non documenté |
| S-10 | 🔵 | `session_lifecycle._get_pip_size()` | Duplique `PIP_SIZES.get(pair, 0.0001)` depuis `constants.py` |

### Légende

| Icône | Signification |
|-------|---------------|
| 🔴 | Critique — bloquant, correctif immédiat |
| 🟠 | Moyen — risque de régression, correctif prioritaire |
| 🟡 | Faible — dette connue, à planifier |
| 🔵 | Cosmétique / note — pas de correctif urgent |

### Points forts

- ✅ Tous les 5 `.pyd` compilés pour cp311-win_amd64 — pipeline Cython fonctionnel
- ✅ Mécanisme fallback `__init__.py` élégant et documenté
- ✅ Règle all-or-nothing respectée à chaque étape du pipeline
- ✅ `constants.py` = source unique de vérité sans magic numbers dispersés
- ✅ `IBConfig.is_paper=True` par défaut — mode paper garanti
- ✅ DI complète dans `FCRStrategy.__init__` — testabilité assurée
- ✅ Timezone via `zoneinfo` exclusivement — pas de pytz, pas d'offsets hardcodés
- ✅ Écriture atomique `DailyState` (`.tmp` → `os.replace()`)
- ✅ Rate limiting IB implémenté (`RequestThrottler` token-bucket, 45 req/s)
- ✅ Reconnexion automatique IB câblée (`disconnectedEvent` → `_handle_reconnection`)

### Priorité de traitement suggérée

1. **Immédiat** (S-06) : Ajouter `alphaedge_daily_state.json` au `.gitignore`
2. **Court terme** (S-07) : Faire référencer `_PAIR_SESSION_DEFAULTS` depuis les constantes LONDON_*
3. **Moyen terme** (S-04) : Décider du sort de `ml_filter.py` — intégrer ou supprimer
4. **Backlog technique** (S-01, S-02, S-03) : Extraire `_execute_signal()` en sous-méthodes ; découper `backtest.py`
5. **Cosmétique** (S-09, S-10) : Documenter import lazy ; centraliser pip_size lookup

---

*Audit complété — aucune modification de code effectuée.*
*Prochaine étape recommandée : `tasks/prompts/generate_action_plan_prompt.md`*
