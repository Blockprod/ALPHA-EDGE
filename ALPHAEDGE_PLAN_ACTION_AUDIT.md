# ALPHAEDGE — PLAN D'ACTION POST-AUDIT TECHNIQUE

> **Généré le** : 2026-03-08
> **Source** : Audit technique complet du repository ALPHAEDGE
> **Objectif** : Corriger les 20 findings identifiés, de P0 (bloquant prod) à P3 (long terme)
> **Contrainte** : Aucun correctif ne doit casser les mécanismes identifiés comme "Points forts à conserver"

---

## TABLE DES MATIÈRES

1. [Graphe de dépendances](#1-graphe-de-dépendances)
2. [SPRINT 1 — P0 Bloquants production](#2-sprint-1--p0-bloquants-production)
3. [SPRINT 2 — P1 Fiabilité IB Gateway](#3-sprint-2--p1-fiabilité-ib-gateway)
4. [SPRINT 3 — P2 Backtest & Persistance](#4-sprint-3--p2-backtest--persistance)
5. [SPRINT 4 — P3 Long terme](#5-sprint-4--p3-long-terme)
6. [Checklist de validation finale](#6-checklist-de-validation-finale)
7. [Fichiers impactés (matrice)](#7-fichiers-impactés-matrice)

---

## 1. GRAPHE DE DÉPENDANCES

```
P0-01 (asyncio.Lock)
  │
  ├──► P1-01 (SIGINT/SIGTERM handler) — le graceful shutdown doit acquérir le lock
  │
  └──► P0-03 (daily_loss persisté) ──► P2-05 (state persistence complète)

P0-02 (spread return 0.0) — indépendant
P1-02 (fill verification) — indépendant
P1-03 (backoff exponentiel) — indépendant
P1-04 (IB error codes) — indépendant
P1-05 (mid_price return 0.0) — indépendant, peut être groupé avec P0-02
P2-01…P2-07 — tous indépendants entre eux
P3-01…P3-04 — tous indépendants, à ne démarrer qu'après les P0/P1
```

**Règle absolue** : Implémenter P0-01 EN PREMIER. Les correctifs P1-01 et P0-03 en dépendent.

---

## 2. SPRINT 1 — P0 BLOQUANTS PRODUCTION

> **Objectif** : Éliminer les 3 risques de perte financière directe
> **Effort estimé** : 2 jours
> **Validation** : Tous les tests existants passent + nouveaux tests ajoutés

---

### P0-01 — Race condition asyncio : ajouter un Lock global

**Fichier** : `alphaedge/engine/strategy.py`
**Lignes impactées** : ~182, ~556-570, ~369

**Problème** : Aucun `asyncio.Lock` dans le projet. Les vérifications `check_pair_limit()` → `_execute_signal()` ne sont pas atomiques. Deux signaux simultanés sur deux paires peuvent ouvrir 2 positions, violant la règle "max 1 pair open".

**Correction** :

- [ ] **1.** Ajouter un attribut `_trade_lock: asyncio.Lock` dans `FCRStrategy.__init__()`
```python
self._trade_lock = asyncio.Lock()
```

- [ ] **2.** Protéger la section critique dans `_on_new_m1_bar()` : wrapper l'appel `_check_spread_and_execute()` dans un `async with self._trade_lock`
```python
async def _atomic_check_and_execute(self, state, signal, pip_size):
    async with self._trade_lock:
        # Re-vérifier pair limit SOUS le lock
        open_pairs = [p for p, s in self._states.items() if s.is_position_open]
        pair_check = self._modules.risk_manager.check_pair_limit(
            pair=state.pair, open_pairs=open_pairs, max_open_pairs=1,
        )
        if not pair_check["allowed"]:
            return False
        # Re-vérifier trade count SOUS le lock
        if state.trades_today >= self._config.trading.max_trades_per_session:
            return False
        return await self._check_spread_and_execute(state, signal, pip_size)
```

- [ ] **3.** Remplacer l'appel direct `_check_spread_and_execute()` dans `_on_new_m1_bar()` par `_atomic_check_and_execute()`

- [ ] **4.** Protéger `_on_trade_closed()` : wrapper la mutation `state.is_position_open = False` dans le même lock (schedule une coroutine)

- [ ] **5.** Écrire un test `test_race_condition_multi_pair.py` :
  - Simuler 2 signaux quasi-simultanés sur 2 paires
  - Vérifier qu'un seul trade est exécuté

**Tests à exécuter** :
```bash
python -m pytest alphaedge/tests/ -v --tb=short
```

**Critère de succès** : Le test de race condition passe. Aucun test existant ne casse.

---

### P0-02 — Spread retourné à 0.0 en cas d'erreur IB

**Fichiers** : `alphaedge/engine/data_feed.py`
**Lignes impactées** : ~410-420, ~440-450

**Problème** : `get_live_spread()` et `get_mid_price()` retournent `0.0` sur exception. Un spread à 0 passe systématiquement le filtre `max_spread_pips=2.0` → trade exécuté sans vérification réelle du spread.

**Correction** :

- [ ] **1.** Modifier `get_live_spread()` pour retourner `None` au lieu de `0.0` en cas d'erreur
```python
async def get_live_spread(self, pair: str) -> float | None:
    ...
    except Exception:
        logger.exception(f"ALPHAEDGE get_live_spread failed: {pair}")
        return None
```

- [ ] **2.** Modifier `get_mid_price()` idem : retourner `None` en cas d'erreur

- [ ] **3.** Adapter l'appelant `_check_spread_and_execute()` dans `strategy.py` :
```python
spread = await self._rt_feed.get_live_spread(state.pair)
if spread is None:
    logger.error(f"ALPHAEDGE: Cannot verify spread for {state.pair} — signal SKIPPED")
    return False
spread_pips = spread / pip_size
```

- [ ] **4.** Adapter `_execute_signal()` : vérifier que `get_live_spread()` et `get_mid_price()` ne retournent pas `None` avant de continuer

- [ ] **5.** Écrire un test `test_spread_error_blocks_trade.py` :
  - Mock `get_live_spread()` → `None`
  - Vérifier que le signal est rejeté

**Critère de succès** : Quand IB Gateway ne fournit pas de spread, le trade est systématiquement bloqué.

---

### P0-03 — Daily loss limit non persisté entre redémarrages

**Fichier** : Nouveau fichier `alphaedge/utils/state_persistence.py` + modifications dans `strategy.py`

**Problème** : `starting_equity` est recalculé à chaque `run_session()`. Un redémarrage après -3% de drawdown réinitialise le compteur → contournement du kill-switch.

**Correction** :

- [ ] **1.** Créer `alphaedge/utils/state_persistence.py` avec :
```python
STATE_FILE = "alphaedge_daily_state.json"

@dataclass
class DailyState:
    date: str                  # YYYY-MM-DD
    starting_equity: float
    trades_today: int
    shutdown_triggered: bool

def save_daily_state(state: DailyState) -> None:
    """Écriture atomique : .tmp → rename."""
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(asdict(state), f)
    os.replace(tmp, STATE_FILE)  # Atomique sur POSIX et Windows

def load_daily_state() -> DailyState | None:
    """Charger l'état du jour. None si fichier absent ou date différente."""
    if not Path(STATE_FILE).exists():
        return None
    data = json.loads(Path(STATE_FILE).read_text())
    if data["date"] != date.today().isoformat():
        return None  # Nouveau jour → reset autorisé
    return DailyState(**data)
```

- [ ] **2.** Dans `FCRStrategy.run_session()` : avant de calculer `starting_equity` via IB, vérifier `load_daily_state()` :
  - Si l'état du jour existe ET `shutdown_triggered=True` → refuser de démarrer
  - Si l'état du jour existe → utiliser `starting_equity` et `trades_today` persistés
  - Sinon → utiliser l'equity live comme aujourd'hui

- [ ] **3.** Persister l'état après chaque trade (`_execute_signal`) et à chaque `_check_daily_loss_shutdown`

- [ ] **4.** Ajouter `alphaedge_daily_state.json` et `*.tmp` au `.gitignore`

- [ ] **5.** Écrire un test `test_daily_state_persistence.py` :
  - Simuler un shutdown -3%, sauvegarder l'état
  - Simuler un redémarrage → vérifier que le bot refuse de trader

**Critère de succès** : Un redémarrage après kill-switch ne permet pas de reprendre le trading le même jour.

---

## 3. SPRINT 2 — P1 FIABILITÉ IB GATEWAY

> **Objectif** : Robustifier la connexion IB et les ordres
> **Effort estimé** : 3 jours
> **Prérequis** : P0-01 terminé (pour P1-01)

---

### P1-01 — Handler SIGINT/SIGTERM pour graceful shutdown

**Fichier** : `alphaedge/engine/strategy.py`
**Lignes impactées** : ~797-826 (`_main()`)

**Problème** : Aucun handler de signal système. Un Ctrl+C tue le process sans `_handle_session_end()`.

**Correction** :

- [ ] **1.** Ajouter un handler dans `_main()` :
```python
import signal

async def _main() -> None:
    ...
    strategy = FCRStrategy(config)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.ensure_future(strategy.graceful_shutdown()))

    await strategy.run_session()
```

- [ ] **2.** Ajouter une méthode `graceful_shutdown()` dans `FCRStrategy` :
```python
async def graceful_shutdown(self) -> None:
    logger.warning("ALPHAEDGE: Graceful shutdown initiated (signal received)")
    self._shutdown_requested = True
    # run_session() vérifiera _shutdown_requested et appellera _handle_session_end()
```

- [ ] **3.** Note Windows : `add_signal_handler` ne supporte que `SIGINT` sur Windows. Ajouter un try/except pour `SIGTERM` :
```python
try:
    loop.add_signal_handler(signal.SIGTERM, ...)
except NotImplementedError:
    pass  # Windows — SIGTERM not supported
```

- [ ] **4.** Écrire un test dans `test_reconnect.py` ou nouveau fichier `test_graceful_shutdown.py`

**Critère de succès** : Un Ctrl+C pendant une session active déclenche `_handle_session_end()` et `disconnect()`.

---

### P1-02 — Vérification du fill de l'ordre parent bracket

**Fichier** : `alphaedge/engine/strategy.py`
**Lignes impactées** : ~356-375

**Problème** : `_execute_signal()` met `state.is_position_open = True` immédiatement après `place_bracket_order()` sans attendre la confirmation du fill.

**Correction** :

- [ ] **1.** Après `place_bracket_order()`, vérifier que la liste de trades n'est pas vide :
```python
trades_placed = await self._executor.place_bracket_order(...)
if not trades_placed:
    logger.error(f"ALPHAEDGE: Bracket order returned empty — {state.pair}")
    return False
```

- [ ] **2.** Attendre le fill du parent (premier trade) avec timeout :
```python
parent_trade = trades_placed[0]
try:
    await asyncio.wait_for(parent_trade.fillEvent.wait(), timeout=10.0)
except asyncio.TimeoutError:
    logger.error(f"ALPHAEDGE: Parent order not filled within 10s — {state.pair}")
    # Annuler le bracket entier
    await self._executor.cancel_all_orders()
    return False
```

- [ ] **3.** Seulement APRÈS le fill confirmé : `state.is_position_open = True`

- [ ] **4.** Écrire un test mock simulant un fill timeout

**Critère de succès** : `is_position_open` n'est jamais `True` si le fill n'est pas confirmé.

---

### P1-03 — Backoff exponentiel avec jitter sur reconnect

**Fichier** : `alphaedge/engine/broker.py`
**Lignes impactées** : ~155-165

**Problème** : Backoff linéaire `2.0 * attempt` au lieu d'exponentiel + jitter.

**Correction** :

- [ ] **1.** Remplacer le calcul du délai :
```python
import random

# Backoff exponentiel avec jitter: 2^attempt + random(0, 1)
delay = (2 ** attempt) + random.uniform(0, 1)
delay = min(delay, 30.0)  # Cap à 30 secondes
logger.warning(f"ALPHAEDGE reconnect attempt {attempt}/{max_retries} — waiting {delay:.1f}s")
await asyncio.sleep(delay)
```

- [ ] **2.** Mettre à jour le test `test_reconnect.py` si nécessaire

**Critère de succès** : Les délais de reconnection sont 2s, 4s, 8s (+ jitter) au lieu de 2s, 4s, 6s.

---

### P1-04 — Handlers pour les codes d'erreur IB spécifiques

**Fichier** : `alphaedge/engine/broker.py`
**Lignes impactées** : Nouveau code dans `BrokerConnection`

**Problème** : Aucun handler pour les erreurs IB codes 162 (historical data pacing), 200 (no security definition), 321 (server validation), 504 (not connected).

**Correction** :

- [ ] **1.** Enregistrer un handler d'erreur IB dans `BrokerConnection.connect()` :
```python
self._ib.errorEvent += self._on_ib_error

def _on_ib_error(self, reqId: int, errorCode: int, errorString: str, contract: Any) -> None:
    if errorCode == 162:
        logger.warning(f"ALPHAEDGE IB PACING: Historical data pacing violation — {errorString}")
    elif errorCode == 200:
        logger.error(f"ALPHAEDGE IB: No security definition — {errorString}")
    elif errorCode == 321:
        logger.error(f"ALPHAEDGE IB: Server validation error — {errorString}")
    elif errorCode == 504:
        logger.critical(f"ALPHAEDGE IB: Not connected — {errorString}")
    elif errorCode in (1100, 1101, 1102):
        logger.critical(f"ALPHAEDGE IB CONNECTION: code={errorCode} — {errorString}")
    else:
        logger.warning(f"ALPHAEDGE IB error {errorCode}: {errorString}")
```

- [ ] **2.** Pour le code 162 (pacing) : ajouter un délai supplémentaire dans le throttler
- [ ] **3.** Écrire un test simulant chaque code d'erreur

**Critère de succès** : Les erreurs IB sont loguées avec le niveau de sévérité approprié.

---

### P1-05 — `get_mid_price()` retourne 0.0 → pip value JPY incorrecte

**Fichier** : `alphaedge/engine/data_feed.py`
**Lignes impactées** : ~440-450

**Problème** : `get_mid_price()` retourne `0.0` en cas d'erreur. Le `exchange_rate=0.0` saute la conversion pip value pour JPY → sizing très incorrect.

**Correction** :

- [ ] **1.** Modifier `get_mid_price()` : retourner `None` au lieu de `0.0`
- [ ] **2.** Dans `_execute_signal()` de `strategy.py` : vérifier `exchange_rate is not None` avant de continuer
```python
exchange_rate_result = await self._rt_feed.get_mid_price(state.pair)
if exchange_rate_result is None:
    logger.error(f"ALPHAEDGE: Cannot get exchange rate for {state.pair} — signal SKIPPED")
    return False
exchange_rate = exchange_rate_result
```
- [ ] **3.** Combiner le test avec celui de P0-02

**Critère de succès** : Un trade sur USD/JPY est bloqué si le mid price n'est pas disponible.

---

## 4. SPRINT 3 — P2 BACKTEST & PERSISTANCE

> **Objectif** : Améliorer la fiabilité du backtest et la résilience du bot
> **Effort estimé** : 5 jours
> **Prérequis** : P0-03 terminé (pour P2-05)

---

### P2-01 — Spread cost variable par paire dans le backtest

**Fichier** : `alphaedge/config/constants.py` + `alphaedge/engine/backtest.py`

**Problème** : `BASE_SPREAD_PIPS=0.8` est une constante unique appliquée à toutes les paires. Sous-estime le coût pour GBP/JPY (~3-5 pips réels).

**Correction** :

- [ ] **1.** Ajouter un dictionnaire de spreads par paire dans `constants.py` :
```python
BASE_SPREAD_BY_PAIR: dict[str, float] = {
    "EURUSD": 0.8,
    "GBPUSD": 1.2,
    "USDJPY": 0.9,
    "AUDUSD": 1.0,
    "USDCAD": 1.2,
    "USDCHF": 1.2,
    "NZDUSD": 1.5,
    "EURJPY": 2.0,
    "GBPJPY": 3.0,
}
```

- [ ] **2.** Modifier `compute_variable_slippage()` dans `backtest.py` pour accepter un paramètre `pair` et utiliser le spread correspondant

- [ ] **3.** Propager le paramètre `pair` dans `_build_trade_record()` et `_backtest_pair()`

- [ ] **4.** Mettre à jour `test_variable_slippage.py`

---

### P2-02 — PnL USD hardcodé → calcul via pip value réel

**Fichier** : `alphaedge/engine/backtest.py`
**Ligne impactée** : ~287

**Problème** : `trade.pnl_usd = trade.pnl_pips * 10.0` hardcode $10/pip (micro lot EUR/USD). Incorrect pour JPY pairs et lot types différents.

**Correction** :

- [ ] **1.** Remplacer la constante par un calcul via `PIP_SIZES` et le lot type :
```python
pip_size = PIP_SIZES.get(trade.pair, 0.0001)
# Micro lot = 1000 units, pip value = 1000 * pip_size
pip_value = 1000.0 * pip_size  # Pour micro lot
trade.pnl_usd = trade.pnl_pips * pip_value
```

- [ ] **2.** Idéalement, utiliser `risk_manager.calculate_position_size()` pour récupérer la `pip_value` exacte. Mais en backtest offline (pas d'exchange rate live), utiliser le calcul simplifié ci-dessus.

- [ ] **3.** Mettre à jour les tests de backtest qui vérifient les montants USD

---

### P2-03 — News filter absent du backtest

**Fichier** : `alphaedge/engine/backtest.py`
**Lignes impactées** : ~1012-1070 (`_backtest_pair()`)

**Problème** : Le news filter est actif en live mais absent du backtest → surestimation du win rate.

**Correction** :

- [ ] **1.** Charger le calendrier news dans `_backtest_pair()` ou le recevoir en paramètre
- [ ] **2.** Avant chaque détection engulfing (`_detect_signal_at_bar()`), vérifier `news_filter.is_news_blackout(bar_time, pair)`
- [ ] **3.** Si blackout → skip le signal (comme en live)
- [ ] **4.** Écrire un test vérifiant qu'un signal pendant un événement news est rejeté en backtest

---

### P2-04 — Intégrer `volatility_regime` et `pair_correlation` (ou supprimer)

**Fichiers** : `alphaedge/engine/strategy.py`, `alphaedge/utils/volatility_regime.py`, `alphaedge/utils/pair_correlation.py`

**Problème** : Code mort — ces modules existent avec tests mais ne sont jamais appelés dans la boucle live ni dans le backtest.

**Correction** :

- [ ] **Option A (recommandée)** : Intégrer dans `run_session()` avant le subscribe :
  - Appeler `check_volatility_regime()` pour décider si la session est tradable
  - Appeler `check_signal_allowed()` dans `_on_new_m1_bar()` avant `_execute_signal()`

- [ ] **Option B** : Si les modules ne sont pas encore validés OOS, les documenter comme "disabled pending validation" et ne pas les supprimer

---

### P2-05 — Persistance d'état complète

**Fichier** : Extension de `alphaedge/utils/state_persistence.py` (créé en P0-03)

**Problème** : Aucun état persisté au-delà du daily loss. Après un crash, le bot ne sait pas combien de trades ont été faits ni si une position est ouverte.

**Correction** :

- [ ] **1.** Étendre `DailyState` avec :
```python
@dataclass
class DailyState:
    date: str
    starting_equity: float
    trades_today: int
    shutdown_triggered: bool
    open_pairs: list[str]        # paires avec positions ouvertes
    last_update_utc: str         # timestamp dernière mise à jour
```

- [ ] **2.** Sauvegarder l'état à chaque événement significatif :
  - Après chaque trade exécuté
  - Après chaque fill SL/TP
  - Après chaque check_daily_loss
  - Au shutdown (graceful)

- [ ] **3.** Au démarrage, réconcilier `DailyState.open_pairs` avec les positions IB réelles (`_reconcile_positions()`)

---

### P2-06 — Validation de config étendue

**Fichier** : `alphaedge/config/loader.py`
**Lignes impactées** : ~174-188 (`_validate_trading_config()`)

**Problème** : Pas de validation de `pairs`, `lot_type`, `port`.

**Correction** :

- [ ] **1.** Valider les paires :
```python
from alphaedge.config.constants import PIP_SIZES
for pair in cfg.pairs:
    if pair not in PIP_SIZES:
        raise ValueError(f"Unknown pair '{pair}'. Supported: {list(PIP_SIZES.keys())}")
```

- [ ] **2.** Valider `lot_type` :
```python
if cfg.lot_type not in ("standard", "mini", "micro"):
    raise ValueError(f"Invalid lot_type '{cfg.lot_type}'. Must be standard/mini/micro.")
```

- [ ] **3.** Valider le port IB dans `_build_ib_config()` :
```python
if ib_config.port not in (4001, 4002):
    logger.warning(f"ALPHAEDGE: Non-standard IB port {ib_config.port} (expected 4001 or 4002)")
```

- [ ] **4.** Mettre à jour `test_loader_validation.py` avec les cas invalides

---

### P2-07 — Éliminer la duplication session check

**Fichiers** : `alphaedge/utils/timezone.py`, `alphaedge/engine/strategy.py`

**Problème** : `is_session_active()` dans `timezone.py` et `SessionWindow.contains()` dans `session_manager.py` font la même chose.

**Correction** :

- [ ] **1.** Faire de `is_session_active()` un wrapper de `NYSE_SESSION.contains()` :
```python
def is_session_active(dt_utc: datetime | None = None) -> bool:
    from alphaedge.utils.session_manager import NYSE_SESSION
    if dt_utc is None:
        dt_utc = now_utc()
    return NYSE_SESSION.contains(dt_utc)
```

- [ ] **2.** Vérifier que tous les appelants fonctionnent toujours
- [ ] **3.** Exécuter `test_timezone_dst.py` et `test_session_manager.py`

---

## 5. SPRINT 4 — P3 LONG TERME

> **Objectif** : Maintenabilité et fiabilité du backtest
> **Effort estimé** : 2 semaines
> **Prérequis** : Tous les P0/P1/P2 terminés

---

### P3-01 — Refactorer `strategy.py` (SRP)

**Fichier** : `alphaedge/engine/strategy.py` (~700+ lignes)

**Correction** :

- [ ] **1.** Extraire un `SignalPipeline` responsable de la chaîne FCR → Gap → Engulfing
- [ ] **2.** Extraire un `PositionManager` responsable de l'exécution et du suivi de position
- [ ] **3.** Extraire un `SessionLifecycle` responsable de la boucle session + cleanup
- [ ] **4.** `FCRStrategy` devient un orchestrateur fin (~150 lignes max)
- [ ] **5.** Tous les tests existants doivent passer sans modification

---

### P3-02 — Refactorer `backtest.py` (SRP)

**Fichier** : `alphaedge/engine/backtest.py` (~1100+ lignes)

**Correction** :

- [ ] **1.** Extraire `backtest_stats.py` : `compute_stats()`, `_compute_winrate()`, `_compute_profit_factor()`, `_compute_max_drawdown()`, `_compute_sharpe()`
- [ ] **2.** Extraire `backtest_export.py` : `export_results_csv()`, `plot_equity_curve()`
- [ ] **3.** Extraire `walk_forward.py` : `generate_wf_windows()`, `run_walk_forward()` (déjà partiellement modulaire)
- [ ] **4.** `backtest.py` conserve `_backtest_pair()`, `run_backtest()`, `_simulate_trade_exit()`

---

### P3-03 — Log WARNING pendant la semaine de transition DST EU/US

**Fichier** : `alphaedge/utils/timezone.py`

**Correction** :

- [ ] **1.** Ajouter une fonction `is_dst_transition_week()` qui détecte la semaine où EU et US ont un offset DST différent (EU change le dernier dimanche de mars, US le 2ème dimanche de mars)
- [ ] **2.** Appeler cette fonction dans `run_session()` et logger un WARNING si la semaine de transition est active :
```
ALPHAEDGE WARNING: DST transition week detected — EU and US offsets differ by 1h.
Session window is 14:30-15:30 UTC instead of usual 13:30-14:30 UTC (summer) or 14:30-15:30 UTC (winter).
```

---

### P3-04 — Walk-forward avec ré-optimisation par fold IS

**Fichier** : `alphaedge/engine/backtest.py`

**Correction** :

- [ ] **1.** Modifier `run_walk_forward()` pour accepter une fonction d'optimisation
- [ ] **2.** Sur chaque fold IS, faire un grid-search (via `sensitivity.py`) sur les paramètres clés (min_atr_ratio, min_volume_ratio, rr_ratio)
- [ ] **3.** Appliquer les meilleurs paramètres IS au fold OOS
- [ ] **4.** Comparer le résultat avec le walk-forward actuel (même paramètres partout) pour mesurer le gain

---

## 6. CHECKLIST DE VALIDATION FINALE

Après chaque sprint, exécuter la checklist complète :

```bash
# 1. Formattage
python -m black alphaedge/ --check

# 2. Lint
python -m ruff check alphaedge/ --config pyproject.toml

# 3. Type checking
python -m mypy alphaedge/ --config-file mypy.ini

# 4. Tests unitaires + couverture
python -m pytest alphaedge/tests -v --tb=short --cov=alphaedge --cov-fail-under=80

# 5. Build Cython (vérifier que les .pyx compilent)
python setup.py build_ext --inplace

# 6. Pipeline complète
make qa
```

**Critères de réception par sprint** :

| Sprint | Critères |
|--------|----------|
| Sprint 1 (P0) | Zéro race condition multi-pair. Spread `None` bloque le trade. Daily loss persisté entre restarts. `make qa` pass. |
| Sprint 2 (P1) | SIGINT déclenche graceful shutdown. Fill vérifié avant state update. Backoff exponentiel. IB error codes loggés. `make qa` pass. |
| Sprint 3 (P2) | Backtest avec spread par paire. PnL USD correct. News filter dans backtest. Config validation étendue. State persistence complète. `make qa` pass. |
| Sprint 4 (P3) | `strategy.py` <200 lignes. `backtest.py` <400 lignes. DST transition warning. Walk-forward avec ré-optimisation. `make qa` pass. |

---

## 7. FICHIERS IMPACTÉS (MATRICE)

| Fichier | P0-01 | P0-02 | P0-03 | P1-01 | P1-02 | P1-03 | P1-04 | P1-05 | P2-01 | P2-02 | P2-03 | P2-04 | P2-05 | P2-06 | P2-07 | P3-01 | P3-02 | P3-03 | P3-04 |
|---------|:-----:|:-----:|:-----:|:-----:|:-----:|:-----:|:-----:|:-----:|:-----:|:-----:|:-----:|:-----:|:-----:|:-----:|:-----:|:-----:|:-----:|:-----:|:-----:|
| `engine/strategy.py` | ✏️ | ✏️ | ✏️ | ✏️ | ✏️ | | | ✏️ | | | | ✏️ | ✏️ | | | ✏️ | | | |
| `engine/broker.py` | | | | | | ✏️ | ✏️ | | | | | | | | | | | | |
| `engine/data_feed.py` | | ✏️ | | | | | | ✏️ | | | | | | | | | | | |
| `engine/backtest.py` | | | | | | | | | ✏️ | ✏️ | ✏️ | | | | | | ✏️ | | ✏️ |
| `config/constants.py` | | | | | | | | | ✏️ | | | | | | | | | | |
| `config/loader.py` | | | | | | | | | | | | | | ✏️ | | | | | |
| `utils/timezone.py` | | | | | | | | | | | | | | | ✏️ | | | ✏️ | |
| `utils/state_persistence.py` | | | 🆕 | | | | | | | | | | ✏️ | | | | | | |
| `.gitignore` | | | ✏️ | | | | | | | | | | | | | | | | |
| TESTS | 🆕 | 🆕 | 🆕 | 🆕 | ✏️ | ✏️ | 🆕 | 🆕 | ✏️ | ✏️ | 🆕 | | ✏️ | ✏️ | ✏️ | ✏️ | ✏️ | 🆕 | 🆕 |

**Légende** : ✏️ = modification, 🆕 = création

---

> **NE PAS MODIFIER** les mécanismes validés par l'audit :
> bracket order atomique (`broker.py:213-238`), throttler IB pacing (`broker.py:42-70`), DST natif zoneinfo (`timezone.py`), fallback Cython→stubs (`core/__init__.py`), confirmation live trading (`strategy.py:810-818`), variable slippage model (`backtest.py:116-146`), QA toolchain (`Makefile` + `pyproject.toml` + `mypy.ini` + `.pylintrc`), walk-forward validation (`backtest.py:530-680`).
