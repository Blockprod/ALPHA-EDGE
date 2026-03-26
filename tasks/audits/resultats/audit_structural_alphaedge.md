---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: audit_structural_alphaedge.md
derniere_revision: 2026-03-25
creation: 2026-03-25
---

# AUDIT STRUCTUREL — ALPHAEDGE
Date : 2026-03-25

---

## BLOC 1 — PIPELINE RÉEL

Pipeline attendu : `data_feed.py → momentum_detector.pyx → carry_signal.py → risk_manager.pyx → order_manager.pyx → broker.py`

### Trace effective

| Étape | Module | Type | Entrée | Sortie | Lien vers étape suivante |
|-------|--------|------|--------|--------|--------------------------|
| 1 | `data_feed.py` | Python | IB Gateway (reqHistoricalData) | `list[dict[str, Any]]` (barres Daily) | `state.daily_bars` via `strategy.py`/`session_lifecycle.py` |
| 2 | `momentum_detector.pyx` (via stub) | Cython/Python | `daily_bars: list[dict]`, fast/slow/adx params | `dict[str, Any] \| None` | `signal_pipeline.py:90-97` → `state.signal_result` |
| 3 | `carry_signal.py` | Python pur | `pair: str`, `rates: dict[str, float]` | `CarrySignal` (dataclass frozen) | `signal_pipeline.py:110-118` |
| 4 | `risk_manager.pyx` (via stub) | Cython/Python | equity, risk_pct, sl_pips, pair… | `dict` (`is_valid`, `lot_size`) | `position_manager.py:53-63` |
| 5 | `order_manager.pyx` (via stub) | Cython/Python | direction, entry_price, SL, TP, lot_size… | `dict` (`is_valid`, `rejection_reason`) | `position_manager.py` → `session_lifecycle.py` |
| 6 | `broker.py` | Python | `Trade` IB object | IB order confirmation | `strategy.py` via `OrderExecutor` |

**Pipeline all-or-nothing confirmé** dans `signal_pipeline.py:62-65` (docstring Steps 1-4) et dans `session_lifecycle.py` (garde-fous avant chaque étape).

### Déviations par rapport à l'architecture déclarée

🔴 **S-01 — Méthode FCR résiduelle toujours active dans le pipeline live**
- `strategy.py:200-219` — `_fetch_pre_session_data()` : fetche des barres **M5 + M1** (FCR legacy)
- Appelée à `session_lifecycle.py:810` depuis le loop de session
- Ce flux M5/M1 est **sans consommateur** dans la stratégie Momentum+Carry :
  les champs `state.m5_candles` et `state.pre_session_m1_candles` ne sont utilisés
  par aucune étape de `signal_pipeline.py`
- La méthode utilise `self._config.trading.fcr_lookback_candles` (FCR param)
  et `self._config.trading.entry_timeframe` — requêtes IB inutiles à chaque session

🔴 **S-02 — Paramètre FCR actif dans TradingConfig**
- `loader.py:188` — `fcr_lookback_candles: int = 6` dans `TradingConfig`
- `loader.py:387` — lu depuis `config.yaml` section `structure.lookback_candles`
- `loader.py:495-497` — validé (exception levée si ≤ 0)
- Utilisé à `strategy.py:206` — paramètre vivant mais sans utilité dans la stratégie Momentum+Carry

---

## BLOC 2 — SÉPARATION DES RESPONSABILITÉS

### Fonctions > 100 lignes

| Fichier | Ligne | Fonction | Lignes | Verdict |
|---------|-------|----------|--------|---------|
| `alphaedge/config/loader.py` | 343 | `_build_trading_config()` | 114 | 🟠 monolithique |
| `alphaedge/engine/backtest.py` | 157 | `run_backtest()` | 132 | 🟠 monolithique |
| `alphaedge/engine/backtest_simulation.py` | 303 | `_simulate_partial_exit_fast()` | 121 | 🟡 acceptable (algorithme dense) |
| `alphaedge/engine/backtest_simulation.py` | 429 | `_simulate_trailing_partial_exit_fast()` | 105 | 🟡 acceptable |
| `alphaedge/engine/backtest_stats.py` | 452 | `print_rich_summary()` | 142 | 🟠 mélange calcul + affichage |
| `alphaedge/engine/data_feed.py` | 438 | `fetch_bars_chunked()` | 118 | 🟡 acceptable (retry/chunking) |

### Champs FCR orphelins dans StrategyState

🟠 **S-03 — StrategyState retient 3 champs FCR inutilisés**
- `strategy.py:52` — `m5_candles: list[dict]` — jamais peuplé par le pipeline Momentum+Carry
- `strategy.py:53` — `pre_session_m1_candles: list[dict]` — idem
- `strategy.py:54` — `m1_candles: list[dict]` — idem
- Peuplés uniquement via `_fetch_pre_session_data()` (S-01) — à supprimer avec S-01

### Valeurs hardcodées hors constants.py

🟠 **S-04 — `rr_ratio: float = 3.0` hardcodé en paramètre de fonction**
- `backtest.py:635` — `def _collect_daily_trades(..., rr_ratio: float = 3.0, ...)`
- `backtest.py:716` — `def _backtest_pair(..., rr_ratio: float = 3.0, ...)`
- Devrait être `DEFAULT_RR_RATIO` (`constants.py:57`) = 2.5 — valeur divergente

🟡 **S-05 — Fallback pip_size hardcodé 0.0001**
- `backtest.py:312,483,668` et `session_lifecycle.py:306,527,674,813`
- `PIP_SIZES.get(pair, 0.0001)` — le fallback `0.0001` est une valeur numérique
  sans constante nommée (ex: `DEFAULT_PIP_SIZE`)
- Mitigé : tous les cas JPY ont une entrée dans `PIP_SIZES`

### Couplage et imports croisés

🟠 **S-06 — Chaîne d'imports croisés engine/ (cycles mitigés por TYPE_CHECKING)**

| Fichier | Import | Ligne |
|---------|--------|-------|
| `signal_pipeline.py` | `from alphaedge.engine.strategy import CoreModules, StrategyState` | 24 |
| `position_manager.py` | `from alphaedge.engine.strategy import CoreModules, StrategyState` | 21 |
| `session_lifecycle.py` | `from alphaedge.engine.strategy import StrategyState, SwingStrategy` | 61 |
| `strategy.py` | `from alphaedge.engine.signal_pipeline import SignalPipeline` | 31 |
| `strategy.py` | `from alphaedge.engine.position_manager import PositionManager` | 28 |
| `strategy.py` | `from alphaedge.engine.session_lifecycle import SessionLifecycle` | 30 |
| `sensitivity.py` | `from alphaedge.engine.backtest import ...` | 20 (cyclic-import déclaré) |
| `walk_forward.py` | `from alphaedge.engine.backtest import _backtest_pair` | 168 (noqa: PLC0415) |

- Les cycles `strategy ↔ signal_pipeline`, `strategy ↔ position_manager`, `strategy ↔ session_lifecycle`
  sont réels mais contenus par `if TYPE_CHECKING:` dans les imports sensibles
- `sensitivity.py:20` déclare explicitement `# pylint: disable=cyclic-import` → cycle confirmé

---

## BLOC 3 — COUCHE CYTHON ↔ PYTHON

### Inventaire modules

| Module .pyx | Stub `_stubs/` | __init__.pyi | Verdict |
|-------------|----------------|-------------|---------|
| `momentum_detector.pyx` | `_stubs/momentum_detector.py` ✅ | ✅ ligne 9 | CONFORME |
| `risk_manager.pyx` | `_stubs/risk_manager.py` ✅ | ✅ ligne 10 | CONFORME |
| `order_manager.pyx` | `_stubs/order_manager.py` ✅ | ✅ ligne 11 | CONFORME |

3 modules — 3 stubs — `__init__.pyi` à jour. ✅

### Mécanisme de fallback

- `core/__init__.py` : `_load_core_module(name)` — compiled → stubs avec log WARNING
- Mode `ALPHAEDGE_CORE_BACKEND=stubs` force le fallback (CI sans compilateur) ✅
- Mode `ALPHAEDGE_CORE_BACKEND=compiled` + production : lève `ImportError` si .pyd absent ✅
- `strategy.py:88-105` importe via `from alphaedge.core import momentum_detector, ...` ✅
  (passe par `core/__init__.py`, pas import direct du .pyx compilé)

### Imports dans les tests

À VÉRIFIER — l'audit de tests (`alphaedge/tests/`) n'est pas dans le périmètre structurel strict,
mais les tests du momentum_detector utilisent le backend stubs via `ALPHAEDGE_CORE_BACKEND`.

BLOC 3 : **CONFORME**

---

## BLOC 4 — DETTE TECHNIQUE

### Logs

- `.gitignore` contient `logs/`, `*.log`, `alphaedge/logs` ✅ — les `.log` ne sont pas commités
- `alphaedge/logs/__init__.py` présent — seul fichier commité ✅
- `alphaedge/logs/*.txt` (`backtest_result.txt`, `bt_final.txt`, `bt_full.txt`, `bt_stderr.txt`, `opt.txt`)
  — ces fichiers `.txt` ne sont PAS couverts par `.gitignore` (seul `*.log` est ignoré)

🟡 **S-07 — Fichiers .txt dans alphaedge/logs/ potentiellement commités**
- `alphaedge/logs/backtest_result.txt`, `bt_final.txt`, `bt_full.txt`, `bt_stderr.txt`, `opt.txt`
- `.gitignore` ne couvre pas les `.txt` dans `alphaedge/logs/`
- À vérifier avec `git status`

### reports/

- `.gitignore` contient `reports/` ✅ — les CSV ne sont pas commités

### scripts/

Scripts actifs : `param_sweep.py`, `_opt_run.py`, `_sl_sweep.py`, `_cv_sweep.py`, `manage_task.bat`, `start_alphaedge.ps1`
Artefacts de sweep présents dans le dossier : `sweep_output.txt`, `targeted_sweep.txt`, `sweep_done.txt`

🟡 **S-08 — Artefacts de sweep dans scripts/** (sweep_output.txt, targeted_sweep.txt, sweep_done.txt)
- Ne sont pas dans `.gitignore`
- Doivent être soit supprimés soit ajoutés au `.gitignore`

### Stubs racine vs alphaedge/

- `stubs/ib_insync.pyi` (racine) — stub du package externe ib_insync, pas un doublon des stubs Cython ✅
- Pas de `alphaedge/stubs/` — pas de doublon avec `alphaedge/core/_stubs/` ✅

### build config

- `setup.py` + `pyproject.toml` : **coexistence normale** pour un projet Cython —
  `setup.py` gère la compilation C, `pyproject.toml` gère les outils (ruff, mypy, pytest) ✅
- `build/` dans `.gitignore` ✅

---

## BLOC 5 — CONFIGURATION ET ENVIRONNEMENTS

### constants.py — centralisation

- Toutes les valeurs numériques clés centralisées : `DEFAULT_RR_RATIO`, `DEFAULT_RISK_PCT`,
  `DEFAULT_MAX_DAILY_LOSS_PCT`, `DEFAULT_MOMENTUM_FAST_PERIOD`, `DEFAULT_ADX_THRESHOLD`,
  `PIP_SIZES`, etc. ✅
- Exception : fallback `0.0001` non nommé (S-05) et `rr_ratio=3.0` (S-04)

### loader.py — champ FCR résiduel

🟠 **S-09 — `fcr_lookback_candles` orphelin dans TradingConfig**
- `loader.py:188` — `fcr_lookback_candles: int = 6`
- `loader.py:387` — lu depuis `config.yaml → structure.lookback_candles`
- `loader.py:495-497` — validé au démarrage
- Ce champ polde les IDE (autocompletion), la doc, et les tests
- Seul consommateur : `strategy.py:206` via `_fetch_pre_session_data()` (S-01 — à supprimer)

### loader.py — `_build_trading_config()` — 114 lignes

- Construit `TradingConfig` depuis le dict YAML — logique dense mais cohérente
- Tous les champs Momentum+Carry présents : `momentum_fast_period`, `momentum_slow_period`,
  `momentum_adx_period`, `momentum_adx_threshold`, `momentum_lookback_days`,
  `carry_enabled`, `carry_rates` ✅

### loader.py — validation au démarrage

- `_validate_config()` appelle `_validate_trading_config()` et `_validate_ib_config()` ✅
- Champs critiques validés : `risk_pct`, `max_daily_loss_pct`, `max_trades_per_session`,
  `rr_ratio` ✅
- `fcr_lookback_candles` encore validé (S-09)

### Séparation paper/production

- `strategy.py:22` — importe `IB_LIVE_PORT`, `IB_PAPER_PORT`
- Guard `ALPHAEDGE_PAPER=true` présent dans `.env.example` ✅
- `ALPHAEDGE_ENV=production` déclenche le guard Cython dans `core/__init__.py:37-47` ✅

### Headers de fichiers obsolètes

🟡 **S-10 — Headers "FCR Forex Trading Bot" dans 8 fichiers**
- `data_feed.py:1,11`, `broker.py:1,11`, `position_manager.py:1`, `constants.py:1,19`,
  `core/__init__.py:1,14` — mention "FCR Forex Trading Bot" dans les headers
- Cosmétique, mais crée de la confusion dans les revues de code

---

## SYNTHÈSE

**Score global : 6 / 10 — CONDITIONNEL**

Les corrections S-01 et S-02 sont requises avant paper trading : elles créent des requêtes IB inutiles à chaque session et maintiennent une dépendance sur un paramètre FCR orphelin.

### Tableau des anomalies

| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact | Effort |
|----|------|-------------|---------------|----------|--------|--------|
| S-01 | 1 | `_fetch_pre_session_data()` FCR legacy — M5/M1 fetched inutilement | `strategy.py:200`, `session_lifecycle.py:810` | 🔴 | Requêtes IB parasites + confusion pipeline | M |
| S-02 | 1/5 | `fcr_lookback_candles` paramètre FCR actif dans TradingConfig | `loader.py:188,387,495` | 🔴 | Param validé mais sans utilité — risque de régression si `strategy.py:206` tombe en erreur | S |
| S-03 | 2 | Champs FCR orphelins dans StrategyState (m5_candles, m1_candles, pre_session_m1_candles) | `strategy.py:52-54` | 🟠 | Pollution de la dataclass, risque de confusion future | XS |
| S-04 | 2 | `rr_ratio=3.0` hardcodé (devrait être `DEFAULT_RR_RATIO=2.5`) | `backtest.py:635,716` | 🟠 | Divergence silencieuse backtest vs config | XS |
| S-05 | 2 | Fallback `0.0001` pip_size non nommé | `backtest.py:312,483,668`, `session_lifecycle.py:306,527,674,813` | 🟡 | Risque si nouvelle paire JPY manquante dans PIP_SIZES | XS |
| S-06 | 2 | Cycles d'imports `strategy ↔ signal_pipeline/position_manager/session_lifecycle` | `strategy.py:28-31`, `signal_pipeline.py:24`, `position_manager.py:21` | 🟠 | Fragilité à l'import — erreur silencieuse si TYPE_CHECKING mal géré | L |
| S-07 | 4 | Fichiers .txt dans alphaedge/logs/ non couverts par .gitignore | `alphaedge/logs/*.txt` | 🟡 | Artefacts potentiellement commités | XS |
| S-08 | 4 | Artefacts sweep dans scripts/ (sweep_output.txt, targeted_sweep.txt) | `scripts/sweep_output.txt`, `scripts/targeted_sweep.txt` | 🟡 | Pollution du repo | XS |
| S-09 | 5 | `fcr_lookback_candles` orphelin dans TradingConfig (couplé à S-01/S-02) | `loader.py:188` | 🟠 | Pollution IDE/doc, validé inutilement au démarrage | XS |
| S-10 | 5 | Headers "FCR Forex Trading Bot" dans 8 fichiers | `data_feed.py:1`, `broker.py:1`, `constants.py:1,19`, `core/__init__.py:1` | 🟡 | Confusion dans les revues de code | XS |

Sévérité : 🔴 Critique · 🟠 Majeur · 🟡 Mineur
Effort : XS (< 1h) · S (< 4h) · M (< 1j) · L (> 1j)

**Verdict : CONDITIONNEL**
S-01 et S-02 créent des requêtes IB parasites à chaque session live et maintiennent un paramètre FCR validé mais sans consommateur légitime. S-06 (cycles d'imports) est structurellement fragile mais fonctionnel. Le reste sont des dettes cosmétiques ou mineures corrigeables en XS.
