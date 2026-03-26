---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/audit_latence_alphaedge.md
derniere_revision: 2026-03-26
creation: 2026-03-26
---

# AUDIT LATENCE INSTITUTIONNEL — ALPHAEDGE
> Audit orienté latence chemin critique signal→ordre · Cython vs stubs · IBKR · asyncio · I/O

---

## BLOC 1 — CHEMIN CRITIQUE : CARTOGRAPHIE

### 1.1 Architecture stratégie

ALPHAEDGE est une stratégie **swing Daily/H4**, pas une stratégie intraday.
Le signal momentum est détecté **une seule fois au démarrage de session**, pas sur chaque barre M1.
Les barres M1 servent uniquement à **déclencher l'exécution** d'un signal déjà validé.

Cela modifie fondamentalement le profil de latence : le chemin critique n'est pas
« détection de signal » mais « réception barre M1 → envoi ordre IB ».

### 1.2 Chemin complet boot → ordre

```
run_session()                         session_lifecycle.py:955
  ├─ broker.connect()                 broker.py:161           ~100–500ms (TCP + IB auth)
  ├─ get_account_equity()             broker.py:520           ~1–10ms   (accountSummary sync)
  └─ _init_session_pairs()            session_lifecycle.py:863
       ├─ fetch_bars() Daily          data_feed.py:388        ~1–30s    (IB hist, ou cache <100ms)
       ├─ check_volatility_regime()   utils/volatility_regime ~<1ms
       ├─ _detect_momentum()          strategy.py:196         ~<1ms Cython / ~1–5ms stubs
       └─ _reconcile_positions()      session_lifecycle.py:470 ~10–50ms (IB positions)
```

### 1.3 Chemin critique M1 bar → ordre (hot path)

```
ÉTAPE                              MODULE                         LATENCE EST.
──────────────────────────────────────────────────────────────────────────────
Réception barre 5s IB              data_feed.py RealtimeDataFeed  ~0ms (push event)
Agrégation M1                      M1BarAggregator.process()       ~<0.1ms
Callback _on_new_m1_bar()          session_lifecycle.py:574        ~<0.5ms (checks only)
  stale bar check (90s)            session_lifecycle.py:584        ~<0.1ms
  news filter check                news_filter (in-memory)         ~<0.1ms
  pair limit pre-check (Cython)    risk_manager.check_pair_limit() ~<0.5ms
  signal gate check                state.signal_result             ~<0.1ms
  ensure_future(_atomic_check..)   asyncio.ensure_future()         ~<0.1ms (non-bloquant)

[yield asyncio — coroutine schedulée]

_atomic_check_and_execute()        session_lifecycle.py:646        ~<0.5ms (lock acquire)
  asyncio.Lock acquire             _trade_lock                     0ms (solo pair) ou variable
  check_pair_limit() (Cython)      risk_manager                    ~<0.5ms
  lock released
  → _check_spread_and_execute()

_check_spread_and_execute()        session_lifecycle.py:722
  get_live_spread()  [1ère fois]   ticker cache (in-memory)        ~<0.5ms  ← OK
  spread > max check               in-memory                       ~<0.1ms
  → _execute_signal()

_execute_signal()                  session_lifecycle.py:349
  get_mid_price()                  ticker cache (in-memory)        ~<0.5ms
  _size_position() / Cython        risk_manager                    ~<1ms
  get_live_spread()  [2ème fois]   ticker cache (in-memory)        ~<0.5ms  ← DOUBLON
  _prepare_bracket() / Cython      order_manager                   ~<1ms
  → place_bracket_order()

place_bracket_order()              broker.py:400
  _throttler.acquire()             token-bucket                    ~0ms (capacité 45 req/s)
  _check_margin() → accountSummary() [SYNCHRONE BLOQUANT]          ~1–50ms  ← L-01 🔴
  _submit_bracket()                broker.py:305
    placeOrder(parent) [SYNC]      ib.placeOrder()                 ~1–5ms   ← L-02
    placeOrder(TP)     [SYNC]      ib.placeOrder()                 ~1–5ms   ← L-02
    placeOrder(SL)     [SYNC]      ib.placeOrder()                 ~1–5ms   ← L-02
  wait_for(fill_event, 10s)        asyncio.wait_for                IB fill time (variable)

_record_fill()                     session_lifecycle.py:185
  _persist_daily_state()           state_persistence (fichier)     ~1–10ms  ← L-04 (post-ordre)
──────────────────────────────────────────────────────────────────────────────
TOTAL chemin critique (hors fill)                                  ~8–85ms
```

### 1.4 Analyse séquentiel vs parallèle

- **Toutes les étapes sont séquentielles** sur le chemin critique.
- Les alertes (Telegram/Discord) sont correctement détachées via `ensure_future()` — elles ne bloquent pas.
- Le regime filter est appelé séquentiellement à session start mais en dehors du hot path.

### 1.5 Budget latence

```
Latence cible swing (acceptable)    : < 200ms (signal → ordre soumis)
Latence actuelle estimée            : ~ 20–85ms (hors fill)
Écart au budget                     : aucun — budget respecté en nominal
Risque hors-nominal                  : accountSummary() > 50ms sous charge IB
```

---

## BLOC 2 — CYTHON VS STUBS : RISQUE DE LATENCE CACHÉ

### 2.1 Mécanisme de fallback

**Source :** `alphaedge/core/__init__.py:81–110`

```python
# core/__init__.py:81
def _load_core_module(name: str) -> ModuleType:
    backend = os.getenv("ALPHAEDGE_CORE_BACKEND", "auto").strip().lower()
    if backend == "stubs":
        return importlib.import_module(f"alphaedge.core._stubs.{name}")   # forcé stubs
    if backend == "compiled":
        return importlib.import_module(f"alphaedge.core.{name}")          # forcé compilé
    try:
        module = importlib.import_module(f"alphaedge.core.{name}")        # auto: compiled first
        _record_backend(name, "compiled")
        return module
    except ImportError:
        _FALLBACK_MODULES.add(name)
        if _is_production():
            logger.critical(...)
            raise ImportError(...)                                         # bloque en prod
        logger.warning(...)
        return importlib.import_module(f"alphaedge.core._stubs.{name}")  # silencieux sinon
```

### 2.2 Tableau modules Cython actif / stub / ambigu

| Module | Usage sur hot path | Fallback visible ? | Log niveau | Impact latence stub vs Cython |
|---|---|---|---|---|
| `momentum_detector` | Session start uniquement (`_detect_momentum`) | WARNING (WARNING visible) | WARNING | ~1–5ms stub vs ~<1ms compiled — hors hot path |
| `risk_manager` | Hot path (`check_pair_limit`, `calculate_position_size`) | WARNING (WARNING visible) | WARNING | ~0.5–2ms stub vs ~<0.5ms compiled |
| `order_manager` | Hot path (`create_bracket_order`, `lots_to_units`, `apply_slippage_buffer`) | WARNING (WARNING visible) | WARNING | ~0.5–2ms stub vs ~<0.5ms compiled |

### 2.3 Diagnostic du flag CYTHON_AVAILABLE

- **Pas de flag `CYTHON_AVAILABLE`** — le mécanisme repose sur `_FALLBACK_MODULES` et `_LOADED_BACKENDS`.
- **En développement** (`ALPHAEDGE_ENV` ≠ `production`) : fallback silencieux — WARNING loggé mais le bot démarre.
- **En production** (`ALPHAEDGE_ENV=production`) : `ImportError` levée → le bot refuse de démarrer ✅
- **Vérification au startup** : `get_fallback_modules()` est appelé dans `strategy.py:_import_core_modules()` et loggé — **OK**.
- **Conclusion** : le mécanisme est correct. Pour une stratégie swing, l'impact latence du fallback stub est négligeable (~1–3ms par session, non sur hot path critique).

---

## BLOC 3 — LATENCE DES APPELS IBKR

### 3.1 Architecture connexion

- **IB Gateway local** (localhost:4001 paper / 4002 live) → latence réseau ~<1ms.
- `ib_insync.IB` tourne dans l'event loop asyncio principal (pas de thread séparé).
- Les callbacks IB (`barUpdateEvent`, `filledEvent`) sont dispatchés par ib_insync via `call_soon()` sur l'event loop — non bloquants pour la boucle principale.
- Timeout connexion : `IB_TIMEOUT_SECONDS = 15.0` (`constants.py:193`).

### 3.2 — L-01 🔴 `accountSummary()` synchrone dans `_check_margin()` (broker.py:377)

```python
# broker.py:377 — DANS place_bracket_order() → _check_margin()
account_values = self._broker.ib.accountSummary()   # ← SYNCHRONE, bloque event loop
```

`ib.accountSummary()` au sens ib_insync retourne les données déjà reçues en cache.
C'est un appel mémoire, **pas un appel réseau** — mais il **bloque l'event loop** si IB n'a pas encore
reçu les données `accountSummary` depuis le dernier cycle de mise à jour.

La durée réelle dépend de l'état du cache ib_insync :
- Cache présent (cas normal après startup) : ~<1ms
- Cache absent / première connexion : peut déclencher un `reqAccountSummary` interne — variable

**Impact :** sur le chemin critique signal → ordre, une durée de 1–50ms est injectée de manière
non déterministe selon l'état interne d'ib_insync.

### 3.3 — L-02 🟠 `placeOrder()` ×3 synchrones dans `_submit_bracket()` (broker.py:305–325)

```python
# broker.py:305
for order in [parent, tp_order, sl_order]:
    trade = self._broker.ib.placeOrder(contract, order)   # ← SYNCHRONE
    trades.append(trade)
```

`ib.placeOrder()` est synchrone dans ib_insync — il envoie le message au socket TWS et retourne immédiatement.
L'écriture socket est ~<1ms par appel en local, mais **bloque l'event loop** pendant l'envoi.
Trois appels consécutifs = ~3–15ms bloquants sur l'event loop.

Pour une stratégie swing faisant 1–3 trades/jour, c'est acceptable mais mesurable.

### 3.4 Appels IBKR résumé

| Appel | Sync/Async | Chemin critique | Latence est. | Problème |
|---|---|---|---|---|
| `accountSummary()` dans `_check_margin()` | SYNC | Oui | ~<1ms (cache) / 1–50ms | L-01 🔴 |
| `placeOrder()` ×3 | SYNC | Oui | ~3–15ms | L-02 🟠 |
| `ticker()` dans `get_live_spread()` / `get_mid_price()` | SYNC mémoire | Oui | ~<0.5ms | OK ✅ |
| `accountSummary()` dans `get_account_equity()` | SYNC | Non (risk check) | ~1–10ms | L-09 🟡 |
| `positions()` dans `get_open_positions()` | SYNC | Non (reconcile) | ~<1ms (cache) | Acceptable |
| `reqHistoricalDataAsync()` | Async ✅ | Non (session start) | 1–30s | OK (hors hot) |
| `reqRealTimeBars()` | Sync puis push | Non (subscribe) | ~<5ms | OK |

### 3.5 Rate limiting

- Token bucket `45 req/s`, burst `10` (`constants.py:191-192`).
- Pour une stratégie swing : 1–3 ordres/jour + quelques données historiques au démarrage.
- **Aucun risque de throttling en production normale.**
- `IB_MAX_CONCURRENT_HIST_REQUESTS = 3` (`constants.py:195`) — semaphore hors hot path.

---

## BLOC 4 — EVENT LOOP ASYNCIO ET STARVATION

### 4.1 Callback `_on_bar_update()` (data_feed.py:695)

```python
# data_feed.py:695
def _on_bar_update(self, pair, bars, has_new):
    if not has_new or not bars:
        return
    bar_5s = _bar_to_dict(bars[-1])           # sync, O(1)
    m1_candle = self._aggregator.process(...)  # sync, O(1)
    if m1_candle is not None:
        for callback in self._bar_callbacks:
            callback(pair, m1_candle)          # déclenche _on_new_m1_bar (sync)
```

Toute la chaîne `_on_bar_update → _on_new_m1_bar` est **synchrone** sur l'event loop.
Dans `_on_new_m1_bar`, les vérifications rapides (news, spread gate, signal_result) sont O(1).
La partie longue (`_atomic_check_and_execute`) est correctement détachée via `ensure_future()`.

**Durée synchrone totale sur event loop estimée :** ~<2ms par barre M1.

ib_insync dispatche ses events via `loop.call_soon_threadsafe()` depuis son reader thread,
ce qui est correct — pas de starvation de la boucle principale.

### 4.2 — L-04 🟠 `_persist_daily_state()` — I/O fichier synchrone post-fill (session_lifecycle.py:226)

```python
# session_lifecycle.py:226 — dans _record_fill() appelé après fill
self._persist_daily_state()   # ← écriture JSON/pickle synchrone sur event loop
```

Cette écriture est **postérieure à la confirmation de fill**, donc hors du chemin signal→ordre strict.
Mais elle bloque l'event loop pendant ~1–10ms (selon OS/disque), retardant d'autres coroutines
en attente (ex : prochaine barre M1 pendant une session multi-paires).

### 4.3 — L-05 🟠 Lock global unique `_trade_lock` (session_lifecycle.py:648)

```python
# session_lifecycle.py:648
async with self._s._trade_lock:
    ...
    self._s._executing_pairs.add(state.pair)
# lock relâché — long awaits hors lock ✅
```

Le lock est correctement minimisé : seules les vérifications rapides + ajout à `_executing_pairs`
sont sous lock. Les awaits longs (`_check_spread_and_execute`) sont hors lock.

Pour `max_open_pairs=1` (configuration actuelle), il n'y a pas de contention en pratique.
En multi-paires, deux signaux simultanés sur paires différentes se serialiseraient sur le lock
pour la section critique (~<1ms), ce qui est acceptable.

### 4.4 Boucle principale `asyncio.sleep(1.0)` (session_lifecycle.py:1020)

```python
while is_session_active() and not self._s._shutdown_requested:
    await asyncio.sleep(1.0)   # ← libère l'event loop correctement ✅
    risk_check_counter += 1
    ...
```

Ce sleep libère correctement l'event loop. Il n'affecte **pas** la réception des barres M1
(gérée par push events ib_insync, indépendant de cette boucle).

Il affecte uniquement la latence du risk check (jusqu'à 1s de délai avant chaque vérification)
et la détection de `shutdown_requested`. Pour une stratégie swing : acceptable.

### 4.5 — L-06 🟡 Import inline `from datetime import date as _date` (strategy.py:203)

```python
# strategy.py:203 — dans _detect_momentum(), appelé à session start
from datetime import date as _date
```

Import dans le corps d'une fonction — CPython cache les modules après premier import,
donc pas d'overhead réel. Anti-pattern mais non critique.

---

## BLOC 5 — I/O SYNCHRONES SUR LE CHEMIN CRITIQUE

### 5.1 Inventaire complet des I/O sur le hot path

| I/O | Endroit | Sync/Async | Chemin critique | Impact |
|---|---|---|---|---|
| `accountSummary()` | `broker.py:377` | SYNC bloquant | Oui | 🔴 L-01 |
| `placeOrder()` ×3 | `broker.py:312–325` | SYNC bloquant | Oui | 🟠 L-02 |
| Log `logger.info()` | `session_lifecycle.py:225` | SYNC (post-fill) | Post-fill | 🟡 acceptable |
| `_persist_daily_state()` | `session_lifecycle.py:226` | SYNC fichier | Post-fill | 🟠 L-04 |
| `ticker()` spread/mid | `data_feed.py:736,757` | SYNC mémoire | Oui | ✅ <0.5ms |
| Carry signal | `carry_signal.py` | SYNC mémoire | Session start | ✅ <1ms |
| News filter | `news_filter.py` | SYNC mémoire | Oui | ✅ <0.1ms |

### 5.2 `get_live_spread()` appelé deux fois (session_lifecycle.py:730 + :372)

```python
# session_lifecycle.py:730 — _check_spread_and_execute()
spread = await self._s._rt_feed.get_live_spread(state.pair)  # 1ère fois

# session_lifecycle.py:372 — _execute_signal()
spread = await self._s._rt_feed.get_live_spread(state.pair)   # 2ème fois, doublon
```

Les deux appels lisent le même ticker cache in-memory — ~<0.5ms chacun.
L'impact latence est négligeable, mais c'est un doublon logique : entre les deux appels,
le spread peut avoir changé, ce qui peut conduire à des vérifications incohérentes
(passé le premier check, spread vérifié à nouveau avec une valeur possiblement différente).

### 5.3 Appels HTTP externes

Aucun appel HTTP sur le chemin critique. Le news filter est in-memory.
Les alertes (Telegram/Discord) sont correctement délachées via `ensure_future()`.

---

## BLOC 6 — QUALITÉ ET FRAÎCHEUR DES DONNÉES

### 6.1 Fraîcheur des barres de marché

- Seuil `MAX_BAR_STALENESS_SECONDS = 90` (`constants.py:209`) — vérifié dans `_on_new_m1_bar()`.
- La barre M1 est timestampée à la réception via `bar_5s["datetime"]` (datetime UTC de la barre IB).
- **Point aveugle :** l'offset clock local vs serveur IB n'est pas mesuré ni compensé.

### 6.2 Architecture données temps réel

- `reqRealTimeBars(barSize=5)` → 5s bars poussées par IB (`data_feed.py:668`).
- `reqMktData()` → tick bid/ask mis en cache par ib_insync (utilisé pour spread/mid) (`data_feed.py:679`).
- Le spread et le mid price sont lus depuis le cache ticker ib_insync — **zéro round-trip IB en production**.
- L'agrégateur M1 maintient un buffer par paire en mémoire — O(1) en lecture.

### 6.3 Potentiel de données périmées

- Si ib_insync perd la connexion tick sans déclencher `disconnectedEvent`, le ticker peut devenir périmé silencieusement.
- `_on_ib_disconnect()` re-subscribe les feeds après reconnexion (`session_lifecycle.py:540`).
- Pas de TTL sur les données ticker — si le tick s'arrête sans événement de déconnexion, `get_live_spread()` retourne des données potentiellement périmées.

---

## BLOC 7 — RÉSILIENCE ET LATENCE DE RECONNEXION

### 7.1 Reconnexion IB Gateway

```
Tentative 1 : ~2s delay (±10% jitter)    broker.py:241
Tentative 2 : ~4s delay (±10% jitter)
Tentative 3 : ~8s delay (±10% jitter)
Total max   : ~14s + overhead
```

Pendant la reconnexion : `asyncio.sleep(delay)` libère correctement l'event loop.
Les callbacks ib_insync ne peuvent pas arriver — connexion coupée.
Les ordres en cours sur IB sont maintenus côté broker (bracket SL/TP actifs sur IB Gateway).

### 7.2 — L-08 🟡 Pas de mécanisme de reset circuit breaker (broker.py:156)

```python
# broker.py:156
if self._consecutive_failures >= IB_CIRCUIT_BREAKER_MAX_FAILURES:  # 5 failures
    logger.critical("circuit breaker OPEN ...")
    return False
```

Après 5 échecs consécutifs, `connect()` retourne `False` immédiatement (sans délai).
Il n'existe pas de mécanisme de reset automatique basé sur un timer — seul un redémarrage
du processus reset le compteur. Pour un process long-running 24h, c'est un risque.

### 7.3 Démarrage : cold vs warm start

- **Warm start** (cache historique frais) : `fetch_bars()` ne fait qu'un gap minimal — ~1s par paire.
- **Cold start** (premier run ou cache expiré) : fetche toute l'historique — 1–30s par paire.
- Pas de mode "warm start" qui court-circuite le fetch — mais le disk cache `BarDiskCache` réduit
  efficacement le cold start à un warm start dès le second lancement.

### 7.4 Réconciliation au démarrage

`_reconcile_positions()` est appelée au startup (`session_lifecycle.py:979`) :
appel `ib.positions()` synchrone → lecture cache ib_insync → ~<5ms local.
Correct — détecte les positions orphelines avant d'accepter de nouveaux signaux.

---

## SYNTHÈSE FINALE

### Tableau complet des problèmes

| ID | Bloc | Description | Fichier:Ligne | Sévérité | Latence est. | Effort |
|---|---|---|---|---|---|---|
| L-01 | 3 | `accountSummary()` synchrone bloquant dans `_check_margin()` — bloque event loop sur chemin critique | `broker.py:377` | 🔴 Critique | 1–50ms | Moyen |
| L-02 | 3 | `placeOrder()` ×3 synchrones dans `_submit_bracket()` — bloquent event loop | `broker.py:312–325` | 🟠 Majeur | 3–15ms | Faible* |
| L-03 | 5 | `get_live_spread()` appelé deux fois dans `_execute_signal()` — doublon dans même cycle | `session_lifecycle.py:372` | 🟡 Mineur | <1ms | Trivial |
| L-04 | 4 | `_persist_daily_state()` — écriture fichier synchrone post-fill sur event loop | `session_lifecycle.py:226` | 🟠 Majeur | 1–10ms | Faible |
| L-05 | 4 | Lock global `_trade_lock` sérialise toutes les paires — impact si multi-paires | `session_lifecycle.py:648` | 🟠 Majeur | 0ms actuel / variable | Complexe |
| L-06 | 4 | `from datetime import date as _date` inline dans `_detect_momentum()` | `strategy.py:203` | 🟡 Mineur | ~0ms | Trivial |
| L-07 | 2 | Pas de point de mesure `perf_counter_ns()` sur appels Cython risk/order manager | `session_lifecycle.py:349` | 🟡 Mineur | À MESURER | Faible |
| L-08 | 7 | Circuit breaker sans reset automatique — bloque redémarrage après 5 failures | `broker.py:156` | 🟡 Mineur | N/A | Moyen |
| L-09 | 3 | `accountSummary()` dans `get_account_equity()` — synchrone (risk check toutes 5–30s) | `broker.py:530` | 🟡 Mineur | 1–10ms | Moyen |

> *`placeOrder()` est fondamentalement synchrone dans ib_insync — aucune API async disponible.
> La seule optimisation possible est `run_in_executor()`, mais l'overhead du thread pool rendrait cela contre-productif pour 3 appels.

---

### Budget latence final

```
Latence cible swing (acceptable)      : <200ms signal → ordre soumis
Latence actuelle estimée (nominal)    :  ~10–30ms  (accountSummary cache chaud + 3× placeOrder)
Latence actuelle estimée (dégradé)    :  ~50–100ms (accountSummary cache froid)
Budget résiduel nominal               : +170ms marge confortable pour stratégie swing
```

**Conclusion :** Pour une stratégie swing Daily/H4, le budget latence est respecté même en mode dégradé.
L'écart avec un système HFT est volontaire et assumé. Les risques réels sont :
- L-01 : non-déterminisme du `accountSummary()` sous charge IB
- L-04 : contention I/O post-fill si le disque est lent (VM/réseau)

---

### Top 3 optimisations prioritaires

**1. L-01 — Déplacer `_check_margin()` hors du chemin critique**
Au lieu de vérifier la marge à chaque ordre, la vérifier une fois au démarrage de session
et stocker le résultat dans `StrategyState`. Re-vérifier toutes les 30s via le risk check loop.
Cela élimine l'appel `accountSummary()` non-déterministe du chemin critique.

**2. L-04 — Passer `_persist_daily_state()` en fire-and-forget async**
Envelopper l'écriture dans `asyncio.ensure_future()` ou `run_in_executor()` pour
ne pas bloquer l'event loop post-fill. Même pattern que les alertes.

**3. L-03 — Éliminer le doublon `get_live_spread()`**
Passer le `spread_pips` déjà calculé dans `_check_spread_and_execute()` comme argument
à `_execute_signal()` — supprime le second appel redondant.

---

### Ce qui est déjà optimal ✅

| Mécanisme | Commentaire |
|---|---|
| Spread / mid price → ticker cache in-memory | Zero round-trip IB sur hot path |
| Alertes Telegram/Discord → `ensure_future()` | Non-bloquant, correctement détaché |
| `_atomic_check_and_execute()` → lock minimisé | Long awaits hors lock ✅ |
| `asyncio.sleep(1.0)` boucle principale | Libère l'event loop correctement |
| `reqMktData()` subscribé au démarrage | Ticker disponible immédiatement |
| Cython hot path correct | `risk_manager` et `order_manager` sur signal path |
| Fallback stub bloquant en production | `ALPHAEDGE_ENV=production` → `ImportError` |
| Reconnexion async avec backoff | `asyncio.sleep()` — non bloquant |
| Timeout fill 10s + cancel | Bracket annulé proprement sur timeout |

---

### Recommandations de mesure en production

Points de mesure recommandés (à ajouter en DEBUG) :

```python
# Dans _execute_signal() — session_lifecycle.py:349
_t0 = time.perf_counter_ns()
# ... _check_margin + place_bracket_order ...
_t1 = time.perf_counter_ns()
logger.debug("LATENCE order_submit=%.2fms — %s", (_t1 - _t0) / 1e6, state.pair)

# Dans _submit_bracket() — broker.py:305
_t0 = time.perf_counter_ns()
account_values = self._broker.ib.accountSummary()   # mesurer ce call spécifiquement
_t1 = time.perf_counter_ns()
logger.debug("LATENCE accountSummary=%.2fms", (_t1 - _t0) / 1e6)
```

> Note : un log DEBUG partiel existe déjà dans `_execute_signal()` à `session_lifecycle.py:414–420`
> qui mesure spread + order_submit. Étendre pour inclure `accountSummary()` isolément.

**Outils recommandés :**
- `time.perf_counter_ns()` — mesure haute résolution en ns, déjà utilisé dans le code
- `py-spy` — profiler async Python, capture l'event loop
- ib_insync `util.startLoop()` debug mode — log des messages IB

---
*Audit réalisé le 2026-03-26 · ALPHAEDGE Latency Audit v1.0*
