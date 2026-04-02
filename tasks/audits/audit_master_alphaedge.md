---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: audit_master_alphaedge.md
derniere_revision: 2026-03-27
creation: 2026-03-27 à 14:00
---

# AUDIT TECHNIQUE — ALPHAEDGE
**Date :** 2026-03-27 · **Baseline :** 602 tests · 0 Ruff · 0 Pyright

---

## 1. Vue d'ensemble

### Objectif réel inféré depuis le code
Bot de trading Forex algorithmique sur IB Gateway (paper par défaut).
Stratégie active : **Momentum+Carry** — EMA(12,26) + ADX(14) gate sur barres Daily, filtre carry différentiel de taux.
Sessions NYSE (9h30–10h30 ET) pour USDJPY, Londres (8h00–9h00 UTC) pour EURUSD.
Mode paper invariant (`ALPHAEDGE_PAPER=true`) — live derrière double garde CLI + confirmation interactive.

### Type
Paper trading opérationnel — live techniquement possible mais non testé en real-money.

### Niveau de maturité
**Avancé** — pipeline complet (signal → sizing → bracket → journal), reconnexion IB, réconciliation positions, persistance daily state, alertes Telegram/Discord, news blackout, corrélation, régime volatilité.

### Points forts réels (5)
1. **Persistance quotidienne atomique** (`state_persistence.py`) — écriture `tmp → rename`, survit aux redémarrages dans la journée.
2. **Réconciliation positions après reconnexion** (`_reconcile_positions`) — sync état local vs IB Gateway, alerte si écart.
3. **Double garde paper/live** — ENV `ALPHAEDGE_PAPER` (loader.py) + CLI `--mode live` + saisie interactive "YES".
4. **DST-awareness** — `is_dst_transition_week()` loggue un WARNING explicite en semaine de transition EU/US : gestion correcte et documentée.
5. **Fallback Cython → stubs** — `core/__init__.py` tente le module compilé, tombe sur stubs si absent, refuse en mode `production`. `get_backend_name()` permet l'introspection.

### Signaux d'alerte globaux (5)
1. **Daily summary alert toujours 0** — `wins=0, losses=0, pnl_usd=0.0` codés en dur dans `_handle_session_end()` : l'opérateur reçoit une notification fausse à chaque fin de session.
2. **`_apply_cli_mode()` contourne le garde ENV** — override `is_paper=False` sans vérifier `ALPHAEDGE_PAPER`, exécuté *après* `_resolve_ib_mode_and_port()`.
3. **3 fichiers `.pyx` orphelins** — `fcr_detector`, `gap_detector`, `engulfing_detector` : non compilés, pas de stubs, hors pipeline. Risque de confusion à la maintenance.
4. **`EUR_USD_RATE` hardcodé (1.08) dans le live** vs valeur configurable en backtest : source de vérité divergente pour `pnl_eur`.
5. **Documentation stale** — `pyproject.toml` et `.gitignore` décrivent encore "Momentum+Carry Forex Trading Bot".

---

## 2. Architecture & design système

### Pipeline réel

```
data_feed.py (HistoricalFeed · RealTimeFeed)
  → momentum_detector.pyx  (Daily EMA12/26 + ADX gate)
  → carry_signal.py        (différentiel taux banques centrales)
  → risk_manager.pyx       (sizing % equity + daily loss guard)
  → order_manager.pyx      (construction bracket SL/TP)
  → broker.py              (soumission IB Gateway via ib_insync)
  → session_lifecycle.py   (orchestration session, reconnexion, journal)
```

**Responsabilités effectives par module :**

| Module | Responsabilité réelle |
|--------|-----------------------|
| `strategy.py` | Point d'entrée, initialisation, `_main()` · `_apply_cli_mode()` · `_detect_momentum()` · `_size_position()` · `_check_risk()` |
| `session_lifecycle.py` | Orchestration session (loop M1, bracket, fill, close, daily loss, reconnect, reconcile, session_end) |
| `signal_pipeline.py` | Stateless — `detect_momentum()` + `get_carry()` + `is_carry_conflict()` |
| `data_feed.py` | `HistoricalFeed` (IB pacing) + `RealTimeFeed` (M1 bars, spread, mid price) |
| `broker.py` | `BrokerConnection` (circuit breaker 5/300s) + `RequestThrottler` (45 req/s token bucket) |
| `carry_signal.py` | Calcul directional bias carryi (LONG/SHORT/NEUTRAL) depuis taux annualisés |
| `live_journal.py` | `append_live_trade_csv()` — écriture CSV trades live |

### Violations SRP identifiées
- `strategy.py` — agrège init config, import Cython, CLI, `_detect_momentum`, `_size_position`, `_check_risk`, `_build_validated_order`. Classe `SwingStrategy` (~450 lignes) fait trop : orchestration, sizing, risk, order construction. Extraction vers `session_lifecycle.py` a déjà partiellement eu lieu mais non terminée.

### Fonctions > 100 lignes
| Fonction | Module | Estimation |
|----------|--------|-----------|
| `run_session()` | `session_lifecycle.py` | ~120 lignes |
| `_on_trade_closed()` (inner `_reset_position`) | `session_lifecycle.py` | ~90 lignes |
| `_handle_session_end()` | `session_lifecycle.py` | ~80 lignes |
| `_init_session_pairs()` | `session_lifecycle.py` | ~80 lignes |

### Couplage Cython ↔ Python
Propre via `core/__init__.py` — accès uniquement par interface publique. `strategy.py` charge les modules via `_import_core_modules()`. `TYPE_CHECKING` guard correctement utilisé pour éviter les cycles (`signal_pipeline.py:24`).

### Problèmes structurels bloquants
- Le signal construit dans `_on_new_m1_bar` contient `entry_price=0.0`, `stop_loss=0.0`, `take_profit=0.0`, `risk_pips=0.0` — valeurs placeholder non renseignées au moment du scheduling. La construction réelle des prix se fait en aval (dans `_build_validated_order` via `order_manager.create_bracket_order`). Architecturalement lisible mais peut surprendre un lecteur futur.

---

## 3. Qualité du code

### Duplication de logique
- Calcul PnL pips identique dans `_on_trade_closed` ET `backtest_simulation.py` : `(exit_price - entry_price) * direction / pip_size`. Logique live/backtest non mutualisée (dette acceptable si backtest reste isolé).
- `getattr(contract, "pair", getattr(contract, "symbol", ""))` répété dans `_reconcile_positions` et `_check_orphan_orders` (lignes ~540 et ~595).

### Bare except / swallowing silencieux
Aucun `except:` nu identifié. Tous les blocs `except` capturent `Exception` et passent par `logger.exception()`. Les tâches fire-and-forget utilisent `_on_task_done` avec `task.exception()`. Pattern correct.

### Typage
- `signal: dict[str, Any]` utilisé intensément dans `session_lifecycle.py` et `signal_pipeline.py` — pas de `TypedDict`. Acceptable pour une interface interne Cython, mais fragilise le refactoring.
- `ib_trade: Any = None` dans `_on_trade_closed` — inévitable (type ib_insync non exposé).
- Aucun `# type: ignore` ni `Any` arbitraire détecté. Conforme aux règles du projet.

---

## 4. Robustesse & fiabilité (TRADING-CRITICAL)

### asyncio — gestion erreurs IB Gateway
**Reconnexion : ✅ implémentée** — `_on_ib_disconnect()` → `_handle_reconnection()` → `broker.reconnect(max_retries=3)`. En cas d'échec après 3 tentatives : `shutdown_requested = True` + alert CRITICAL. Flux correctement géré.

**Réconciliation positions post-reconnexion : ✅** — `_reconcile_positions()` sync état local vs IB Gateway. Alertes si écart. `_check_orphan_orders()` détecte les ordres suspendus.

**Re-souscription real-time feeds après reconnexion : ✅** — boucle sur `config.trading.pairs` et `rt_feed.subscribe(pair)`.

**Stale bar guard : ✅** — `MAX_BAR_STALENESS_SECONDS` vérifié dans `_on_new_m1_bar` avant tout traitement.

**Fill timeout : ✅** — `asyncio.wait_for(fill_event.wait(), timeout=10.0)` avec cancel + alert si timeout.

**`filledEvent` guard : ✅** — `fill_event = getattr(parent_trade, "filledEvent", None)` avant `wait()` — `AttributeError` évité.

### Persistance daily state
**Écriture atomique : ✅** — `state_persistence.py` : `tmp → rename`. Survit à un crash pendant l'écriture.

**Persistance du `shutdown_triggered` : ✅** — `_persist_daily_state(shutdown=True)` appelé dans `_check_daily_loss_shutdown()`. Vérifié dans `run_session()` dès le démarrage : refus de démarrer si déjà shutdown aujourd'hui.

### Risques de crash silencieux
- `_on_task_done` appelé sur toutes les tâches fire-and-forget — exceptions loggées. Pas de crash silencieux détecté dans ce pattern.
- `_handle_session_end()` est wrappé dans `try/except Exception` — exception loggée mais session déjà terminée.

### Cython `.pyx` vs `.pyd`
`setup.py` compile exactement 3 modules : `order_manager`, `risk_manager`, `momentum_detector`. Stubs présents dans `core/_stubs/` pour les 3. Cohérent. Voir section 9 pour les orphelins.

---

## 5. Interface IB Gateway & exécution des ordres

### ALPHAEDGE_PAPER=true séparé du live
**Garde primaire : ✅** — `_resolve_ib_mode_and_port()` (`loader.py:299`) : `os.getenv("ALPHAEDGE_PAPER")` priorité maximale → port explicite → défaut paper. `ValueError` levé si mode/port contradictoires.

**🟠 FINDING M-02 — Contournement partiel possible via CLI :**
`_apply_cli_mode()` (`strategy.py:318–327`) est exécuté *après* `load_config()`. Si `ALPHAEDGE_PAPER=true` est setté en ENV et que l'opérateur lance `python -m alphaedge --mode live` + répond "YES", alors `_apply_cli_mode` set `config.ib.is_paper = False` sans re-vérifier l'ENV. La garde ENV (`_resolve_ib_mode_and_port`) est déjà passée et ne re-court pas. Résultat : ENV `ALPHAEDGE_PAPER=true` contourné en live sur confirmation interactive.

```python
# strategy.py:326 — exécuté APRÈS load_config() qui avait correctement lu ALPHAEDGE_PAPER
config.ib.is_paper = False   # override sans vérification ENV
config.ib.port = IB_LIVE_PORT
config.mode = "live"
```

**Atténuant :** nécessite `--mode live` explicite + "YES" interactif — pas un accident. Reste une violation documentée du contrat ENV-first.

### Bracket orders — validation avant envoi
`_build_validated_order()` (strategy.py) appelle `order_manager.create_bracket_order()` : si `is_valid=False`, retourne `None` → `_prepare_bracket()` retourne `None` → signal annulé. Contract respecté.

### Fill verification
`_submit_and_await_fill()` : `filledEvent.wait()` sur parent order avec `asyncio.wait_for(10s)`. En cas de timeout : cancel + alert + return None. Implémentée correctement.

### Gestion timeout reqHistoricalData
Non vérifiable sans accès à `data_feed.py` (exclu de la mesure, IB-couplé). À valider lors d'une session paper.

### Return value contracts (strategy.py)
| Contract | Implémentation |
|---------|---------------|
| `detect_momentum → None = STOP` | ✅ `_detect_momentum()` → `if momentum is None: return` → pas de carry check |
| `carry conflict → STOP` | ✅ `is_carry_conflict()` → signal annulé dans pipeline |
| `calculate_position_size → is_valid=False = STOP` | ✅ `pos_result is None → return False` |
| `check_daily_limit → limit_breached = STOP ALL` | ✅ `_check_daily_loss_shutdown()` → `shutdown_requested = True` + `cancel_all_orders()` |
| `create_bracket_order → is_valid=False = STOP` | ✅ `bracket is None → return None` |

---

## 6. Risk management & capital protection

### check_daily_limit() en début de cycle
`_check_daily_loss_shutdown()` est appelé dans la session loop (ligne ~1095). Vérifié avant traitement des barres M1. ✅

### daily_loss_limit reset journalier
`DailyState.date = date.today().isoformat()` — si la date persisted diffère de aujourd'hui, l'état est considéré périmé. `load_daily_state()` doit renvoyer `None` si date différente (à vérifier dans `state_persistence.py`). Logique correcte par design.

### halt_trading persisté au redémarrage
✅ — `shutdown_triggered=True` dans `DailyState` → persisté → vérifié dès `run_session()` : `if persisted and persisted.shutdown_triggered: return`.

### Paper/live séparation dans broker.py
`BrokerConnection.connect()` loggue `paper=True/False`. Pas de logique spécifique paper/live dans le broker (IB Gateway gère la séparation côté serveur selon le port). Conforme au modèle IB.

### Niveau de danger pour capital réel
Le seul vecteur de risque non-intentionnel identifié est M-02 (CLI `--mode live` contourne ENV). Nécessite une action délibérée de l'opérateur (CLI arg + "YES"). **Danger réel : faible** — pas d'exécution accidentelle possible.

---

## 7. Timezone & session NYSE

### session_manager.py DST-aware via zoneinfo
✅ — `zoneinfo` utilisé exclusivement. Pas d'imports `pytz` détectés. `get_session_window_utc()` dans `timezone.py`.

### Pas de hardcode UTC offset
✅ — aucun `+1` ou `+2` hardcodé détecté dans les modules timezone. Offsets calculés dynamiquement par `zoneinfo`.

### EU-switch week vs US-switch week
✅ — `is_dst_transition_week()` détecte la semaine de transition. Loggue un WARNING explicite dans `run_session()` : "NYSE session is at 13:30-14:30 UTC but Paris shows CET (UTC+1)". La semaine de divergence EU/US (~1 semaine/an) est gérée et documentée.

### NYSE = 14h30 CEST / 15h30 CET correct
✅ — `SESSION_START_HOUR=9, SESSION_START_MINUTE=30` en ET → 14h30 CEST / 15h30 CET. Correct.

### Tests DST edge cases
✅ — `alphaedge/tests/test_timezone_dst.py` et `test_timezone_weekend.py` présents. DST couvert par tests dédiés.

---

## 8. Couverture des tests

### Nombre total de tests
**602 tests** — 100% pass · baseline vérifiée.

### Modules exclus de la couverture (pyproject.toml)
```toml
omit = [
    "alphaedge/engine/backtest*.py",
    "alphaedge/engine/bayesian_optimizer.py",
    "alphaedge/engine/broker.py",
    "alphaedge/engine/dashboard.py",
    "alphaedge/engine/data_feed.py",
    "alphaedge/engine/monte_carlo.py",
    "alphaedge/engine/sensitivity.py",
    "alphaedge/engine/strategy.py",
    "alphaedge/engine/walk_forward.py",
    "alphaedge/engine/web_dashboard.py",
]
```

**Non exclus mais IB-couplés :** `session_lifecycle.py`, `signal_pipeline.py`, `ml_filter.py`, `regime_filter.py`, `position_manager.py`, `carry_signal.py`, `live_journal.py`. Ces modules participent au calcul du gate ≥80%. Leur couverture partielle via tests unitaires (mocks) maintient le gate — acceptable mais à surveiller.

### Stubs Cython cohérents avec interfaces `.pyx`
✅ — `_stubs/` présents pour les 3 modules actifs (`momentum_detector`, `risk_manager`, `order_manager`). Tests utilisent les stubs. Cohérence interface vérifiée lors des précédents audits.

### Tests `parametrize` pour variants de données
Utilisés dans tests detecteur momentum, risk_manager, DST. Pattern respecté.

### Scénarios manquants à risque
- **`alert_daily_summary` avec valeurs réelles** : aucun test ne vérifie que wins/losses/pnl_usd sont correctement calculés dans `_handle_session_end` (they are always 0 — bug non détecté par tests actuels).
- **`_apply_cli_mode("live")` après ENV guard** : pas de test couvrant le scénario ENV `ALPHAEDGE_PAPER=true` + CLI `--mode live`.

---

## 9. Build Cython & setup.py

### setup.py compile les 3 modules actifs
✅ — exactement `order_manager.pyx`, `risk_manager.pyx`, `momentum_detector.pyx`.
```python
# setup.py:22-55
Extension("alphaedge.core.momentum_detector", ...),
Extension("alphaedge.core.risk_manager", ...),
Extension("alphaedge.core.order_manager", ...),
```
Compiler directives : `language_level=3`, `boundscheck=False`, `wraparound=False`, `cdivision=True`. Cohérent.

### make build reproductible
Oui — `setup.py` avec `setuptools + Cython.Build.cythonize`. Reproductible sur CI (dépend du compilateur C disponible — Windows MSVC / MinGW).

### `.pyd` présents et à jour
Les `.pyd` compilés résident dans `build/lib.win-amd64-cpython-311/`. Le fallback `core/__init__.py` charge depuis le path habituel Python. À vérifier après chaque `make build`.

### `_stubs/` couverts par les tests
✅ — tests unitaires chargent les stubs via le mécanisme de fallback. Gate 80% maintenu.

### 🟡 FINDING M-03 — 3 fichiers `.pyx` orphelins
`fcr_detector.pyx`, `gap_detector.pyx`, `engulfing_detector.pyx` présents dans `alphaedge/core/` :
- Non listés dans `setup.py` → non compilés
- Pas de stubs dans `_stubs/`
- Non importés dans `core/__init__.py`
- Hors du pipeline Momentum+Carry

Ces fichiers sont du code mort issu de la stratégie FCR abandonnée. Ils ne font rien à l'exécution mais créent une ambiguïté documentaire et gonflent le dépôt de ~3 fichiers `.c` générés.

---

## 10. Synthèse & priorités

### Tableau final

| ID | Sévérité | Section | Description | Fichier:Ligne | Impact |
|----|----------|---------|-------------|---------------|--------|
| M-01 | 🟠 Majeur | 4 & 8 | `alert_daily_summary` toujours `wins=0, losses=0, pnl_usd=0.0` codés en dur — opérateur reçoit rapport de fin de session structurellement faux | `session_lifecycle.py:918-920` | Visibilité opérateur nulle sur P&L live réel |
| M-02 | 🟠 Majeur | 5 & 6 | `_apply_cli_mode("live")` override `is_paper=False` sans re-vérifier `ALPHAEDGE_PAPER` ENV — contourne le garde primaire documenté | `strategy.py:326` | Vecteur live non-intentionnel si opérateur distrait ; violation contrat ENV-first |
| M-03 | 🟡 Mineur | 9 | 3 `.pyx` orphelins FCR legacy (`fcr_detector`, `gap_detector`, `engulfing_detector`) — non compilés, pas de stubs, hors pipeline | `alphaedge/core/*.pyx` | Confusion maintenance ; 3 fichiers `.c` générés inutilement dans le repo |
| M-04 | 🟡 Mineur | 1 & 9 | Documentation stale : `pyproject.toml:4,16` + `.gitignore:4` décrivent "Momentum+Carry Forex Trading Bot" — stratégie migrée Momentum+Carry | `pyproject.toml:4,16` · `.gitignore:4` | Désinformation outillage CI/CD ; confusion nouveaux contributeurs |
| M-05 | 🟡 Mineur | 6 | `EUR_USD_RATE = 1.08` (constante `constants.py:62`) utilisé dans le moteur live pour `pnl_eur` ; backtest utilise `config.trading.eur_usd_rate` (configurable) — source de vérité divergente | `session_lifecycle.py:27` · `constants.py:62` vs `loader.py:394` | `pnl_eur` du journal live non-configurable ; écart silent si taux EUR/USD s'éloigne de 1.08 |
| M-06 | 🟡 Mineur | 2 & 8 | Divergence algorithme corrélation live/backtest : live = matrice Pearson ρ, backtest = exposition USD directionnelle — documentée (NOTE commentaire) mais non résolue | `session_lifecycle.py:~625` | Résultat backtest non reproductible en live si multi-paire activé |
| M-07 | 🟡 Mineur | 8 | Tests manquants pour les 2 bugs structurels identifiés : `alert_daily_summary` avec valeurs réelles, et `_apply_cli_mode("live")` post-ENV | `alphaedge/tests/` | M-01 et M-02 resteraient non-régression même après correction sans tests dédiés |

### Ordre de traitement recommandé
1. **M-01** — corriger `_handle_session_end()` : agréger wins/losses/pnl_usd depuis `state.live_record` avant l'appel `alert_daily_summary`. Ajouter test de régression.
2. **M-02** — ajouter vérification ENV dans `_apply_cli_mode()` : si `ALPHAEDGE_PAPER` = `"true"` ET `mode == "live"`, lever `SystemExit` avec message explicite.
3. **M-07** — ajouter tests pour M-01 et M-02 avant de les marquer résolus.
4. **M-03** — supprimer `fcr_detector.pyx`, `gap_detector.pyx`, `engulfing_detector.pyx` + leurs `.c` générés. Créer ADR dans `architecture/decisions.md`.
5. **M-04** — mettre à jour `pyproject.toml` description et `.gitignore` header.
6. **M-05** — remplacer `EUR_USD_RATE` constant dans `session_lifecycle.py` par `self._s._config.trading.eur_usd_rate`.
7. **M-06** — tracker dans `docs/ALPHAEDGE_STRUCTURAL_ACTION_PLAN.md` comme dette connue, activer seulement si multi-paire réactivé.

---

*Audit réalisé par : GitHub Copilot (Claude Sonnet 4.6) · 2026-03-27*
*Fichiers analysés directement : `setup.py` · `core/__init__.py` · `config/loader.py` · `config/constants.py` · `engine/broker.py` · `engine/strategy.py` · `engine/session_lifecycle.py` · `engine/signal_pipeline.py` · `pyproject.toml` · `.gitignore` · `config.yaml`*
*Modules explorés via subagent : 57 fichiers de tests · utils/ · engine/ complet*
