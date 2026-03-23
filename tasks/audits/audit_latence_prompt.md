# AUDIT LATENCE — ALPHAEDGE
**Date :** 2026-03-23
**Scope :** Chemin critique signal→ordre, Cython vs stubs, IBKR, asyncio event loop, I/O, données, résilience
**Outil :** Analyse statique codebase (pas de profiling runtime)

---

## BLOC 1 — CHEMIN CRITIQUE SIGNAL → ORDRE

### 1.1 Pipeline complet (réception M1 → bracket envoyé)

| # | Étape | Fonction | Fichier:Ligne | Latence estimée | Nature |
|---|-------|----------|--------------|-----------------|--------|
| 1 | Réception barre 5s (ib_insync) | `barUpdateEvent` | `ib_insync` (externe) | ~5–50 ms RTT | Réseau IB |
| 2 | Dispatch barre | `_on_bar_update()` | [data_feed.py:685](../../../alphaedge/engine/data_feed.py) | < 1 ms | Callback ib_insync (thread interne) |
| 3 | Agrégation M1 | `M1BarAggregator.process()` | [data_feed.py:168](../../../alphaedge/engine/data_feed.py) | < 1 ms | Python, min/max accumulation |
| 4 | Entrée callback M1 | `_on_new_m1_bar()` | [session_lifecycle.py:378](../../../alphaedge/engine/session_lifecycle.py) | — | Callback synchrone (thread IB) |
| 5 | Checks état/risque | state checks, news, correlation | [session_lifecycle.py:381–410](../../../alphaedge/engine/session_lifecycle.py) | < 5 ms | Pure Python (dict lookups) |
| 6 | Détection gap | `detect_gap()` (Cython) | [signal_pipeline.py:55](../../../alphaedge/engine/signal_pipeline.py) | 0.1–0.5 ms | Cython ; 1–3 ms si stub Python |
| 7 | Détection engulfing | `detect_engulfing()` (Cython) | [signal_pipeline.py:80](../../../alphaedge/engine/signal_pipeline.py) | 0.5–2 ms | Cython ; 2–5 ms si stub Python |
| 8 | Dispatch coroutine | `asyncio.ensure_future(...)` | [session_lifecycle.py:448](../../../alphaedge/engine/session_lifecycle.py) | < 1 ms | Fire-and-forget vers event loop |
| 9 | Acquisition lock | `async with _trade_lock` | [session_lifecycle.py:467](../../../alphaedge/engine/session_lifecycle.py) | 0–500 ms | Contention si signal multi-pair simultané |
| 10 | Re-validation sous lock | checks pair limit, trade limit | [session_lifecycle.py:468–485](../../../alphaedge/engine/session_lifecycle.py) | < 5 ms | Cython + dict |
| 11 | **Spread live (reqMktData + sleep 1s)** | `get_live_spread()` | [data_feed.py:728](../../../alphaedge/engine/data_feed.py) | **1 000 ms** 🔴 | `await asyncio.sleep(1.0)` hardcodé |
| 12 | Validation spread | comparaison seuil | [session_lifecycle.py:502](../../../alphaedge/engine/session_lifecycle.py) | < 1 ms | Pure Python |
| 13 | Mid-price si JPY (reqMktData + sleep 1s) | `get_mid_price()` | [data_feed.py:762](../../../alphaedge/engine/data_feed.py) | **1 000 ms** 🔴 | `await asyncio.sleep(1.0)` hardcodé, JPY uniquement |
| 14 | Sizing position | `calculate_position_size()` (Cython) | [session_lifecycle.py:523](../../../alphaedge/engine/session_lifecycle.py) | < 1 ms | O(1), math pure |
| 15 | Construction bracket | `create_bracket_order()` | [session_lifecycle.py:79](../../../alphaedge/engine/session_lifecycle.py) | < 5 ms | Python, validation + slippage |
| 16 | Token bucket (rate limiter IB) | `await _throttler.acquire()` | [broker.py:79](../../../alphaedge/engine/broker.py) | 0–30 ms 🟠 | Peut attendre si bucket vide |
| 17 | Envoi ordre | `ib.placeOrder()` | [broker.py:351](../../../alphaedge/engine/broker.py) | ~10–50 ms | IB Gateway (réseau local) |
| 18 | Attente fill (event wait) | `asyncio.wait_for(fill_event, timeout=10s)` | [session_lifecycle.py:111](../../../alphaedge/engine/session_lifecycle.py) | 100–10 000 ms | Marché |

### 1.2 Tableau résumé — latence totale estimée

```
ÉTAPE                  | MODULE                       | LATENCE EST.
-----------------------|------------------------------|------------------
Réception données      | data_feed.py:685             | ~5–50 ms (réseau)
Agrégation M1          | data_feed.py:168             | < 1 ms
Détection signaux      | signal_pipeline.py:55/80     | 1–7 ms (Cython)
Dispatch coroutine     | session_lifecycle.py:448     | < 1 ms
Acquisition lock       | session_lifecycle.py:467     | 0–500 ms (contention)
Spread live (sleep!)   | data_feed.py:728             | ~1 000 ms 🔴
Mid-price JPY (sleep!) | data_feed.py:762             | ~1 000 ms 🔴 (JPY only)
Size + bracket         | session_lifecycle.py:523     | < 10 ms
Token bucket           | broker.py:79                 | 0–30 ms
ib.placeOrder()        | broker.py:351                | ~10–50 ms
-----------------------|------------------------------|------------------
TOTAL non-JPY          |                              | ~1 020–1 640 ms
TOTAL JPY              |                              | ~2 020–2 640 ms
(hors fill event)      |                              |
```

### 1.3 Architecture du chemin critique

**Entièrement séquentiel** — aucun appel parallèle sur le hot path.

Le pipeline est event-driven (barre M1 → callback → coroutine), mais chaque étape attend la précédente. Il n'y a pas de pipeline async avec des étapes en parallèle.

**Premier await bloquant :** `await get_live_spread()` → [data_feed.py:728](../../../alphaedge/engine/data_feed.py)
Introduit **1 000 ms fixes** avant chaque ordre, sans exception.

---

## BLOC 2 — CYTHON VS STUBS : RISQUE DE LATENCE CACHÉ

### 2.1 Mécanisme d'import Cython

**Stratégie : try/except avec fallback automatique** [core/\_\_init\_\_.py:30–60]

```python
backend = os.getenv("ALPHAEDGE_CORE_BACKEND", "auto").strip().lower()

# Mode "auto" (défaut) :
try:
    module = importlib.import_module(f"alphaedge.core.{name}")
    _record_backend(name, "compiled")
    return module
except ImportError:
    _FALLBACK_MODULES.add(name)
    logger.warning("ALPHAEDGE core fallback: compiled module {} unavailable; using stubs", name)
    return importlib.import_module(f"alphaedge.core._stubs.{name}")
```

**Modes disponibles** (variable `ALPHAEDGE_CORE_BACKEND`) :
- `auto` (défaut) → Cython si disponible, sinon stubs Python — **fallback silencieux**
- `compiled` → Cython obligatoire, `ImportError` si absent
- `stubs` → Force stubs (CI/tests)

### 2.2 Flag CYTHON_AVAILABLE ?

❌ **Pas de flag `CYTHON_AVAILABLE`** dans le sens strict.
✅ **Log WARNING** si fallback activé [core/\_\_init\_\_.py:57] : `"ALPHAEDGE core fallback: compiled module {} unavailable; using stubs"`
✅ **Log au démarrage** [strategy.py:73–86] : affiche `backend=auto|compiled|stubs` + liste des modules en fallback.
❌ **Pas de CRITICAL ni d'arrêt du bot** si Cython absent en mode `auto`. Le bot démarre et trade avec les stubs.

### 2.3 Tableau par module

| Module | .pyx présent | .pyd compilé requis | Statut en ALPHAEDGE_CORE_BACKEND=auto | Impact latence si stub |
|--------|-------------|---------------------|--------------------------------------|----------------------|
| `fcr_detector` | ✅ | si build OK | CYTHON ACTIF (ou auto-fallback) | +2–5 ms par appel (O(n) scan) |
| `gap_detector` | ✅ | si build OK | CYTHON ACTIF (ou auto-fallback) | +1–3 ms par appel (ATR double-loop) 🟠 |
| `engulfing_detector` | ✅ | si build OK | CYTHON ACTIF (ou auto-fallback) | +2–5 ms par appel (volume avg loop) 🟠 |
| `risk_manager` | ✅ | si build OK | CYTHON ACTIF (ou auto-fallback) | < 1 ms (O(1)) 🟡 |
| `order_manager` | ✅ | si build OK | CYTHON ACTIF (ou auto-fallback) | < 1 ms (O(1)) 🟡 |

### 2.4 Quantification Cython vs Stub (hot path)

| Module | Cython | Stub Python | Gain |
|--------|--------|-------------|------|
| `detect_engulfing()` | < 0.1 ms | 0.5–2 ms | ~10–20× 🟠 |
| `detect_gap()` | < 0.5 ms | 1–3 ms | ~5–10× 🟠 |
| `calculate_position_size()` | < 0.1 ms | < 0.5 ms | ~3× 🟡 |

**Verdict :** Le gain Cython est réel mais **marginal** par rapport aux 1 000 ms de `asyncio.sleep(1.0)`. Le stub n'est jamais le bottleneck principal — c'est le sleep hardcodé.

### 2.5 Risque en production

🟠 **Risque : bot démarre silencieusement avec les stubs si le .pyd n'est pas présent.**
Il n'y a pas de garde empêchant le trading en mode dégradé.
**Recommandation :** Passer `ALPHAEDGE_CORE_BACKEND=compiled` en production pour forcer un crash explicite plutôt qu'un fallback silencieux.

---

## BLOC 3 — LATENCE DES APPELS IBKR

### 3.1 Architecture de connexion

- **ib_insync** intègre son réseau TCP dans l'event loop asyncio via `connectAsync()` [broker.py:143]
- Callbacks IB (`barUpdateEvent`, `filledEvent`, `disconnectedEvent`) sont dispatchés depuis le **thread interne ib_insync**, pas depuis l'event loop asyncio principal
- `_on_new_m1_bar()` est donc exécuté dans un **thread IB séparé**, ce qui signifie que les appels Cython qu'il contient **ne starvent pas l'event loop asyncio**
- `asyncio.ensure_future()` [session_lifecycle.py:448] transfère l'exécution vers l'event loop asyncio pour la suite (_atomic_check_and_execute)

### 3.2 Appels bloquants identifiés — citations exactes

**🔴 get_live_spread() — await asyncio.sleep(1.0)**

```python
# data_feed.py:728-730
self._broker.ib.reqMktData(contract)
await asyncio.sleep(1.0)   # ← HARDCODÉ 1 000 ms à chaque appel
ticker = self._broker.ib.ticker(contract)
```
- Appelé AVANT chaque ordre [session_lifecycle.py:493]
- **SOUS le trade_lock** donc bloque les autres paires
- Latence fixe garantie : **1 000 ms minimum**

**🔴 get_mid_price() — await asyncio.sleep(1.0)**

```python
# data_feed.py:762
self._broker.ib.reqMktData(contract)
await asyncio.sleep(1.0)   # ← HARDCODÉ 1 000 ms
ticker = self._broker.ib.ticker(contract)
```
- Appelé pour les paires JPY uniquement [session_lifecycle.py:191]
- Latence fixe supplémentaire : **+1 000 ms pour EUR/JPY, USD/JPY, GBP/JPY**

**Timeout si IB ne répond pas :**
❌ **Pas de timeout sur ces sleeps** — le sleep s'écoule toujours, réponse IB ou non.
Si IB ne répond pas, le ticker retourne `None`, le spread est rejeté, l'ordre n'est pas placé.

### 3.3 Latence d'envoi d'ordre

- Construction bracket : `create_bracket_order()` → `_prepare_bracket()` → ~5 ms [session_lifecycle.py:79]
- Envoi : `ib.placeOrder()` [broker.py:351] → RTT IB Gateway local ~10–50 ms
- Fill event : `await asyncio.wait_for(fill_event.wait(), timeout=10.0)` [session_lifecycle.py:111] → 100–10 000 ms

**Timeout fill :**
✅ 10 secondes configuré. Si expiré → `cancel_all_orders()` [session_lifecycle.py:113].

### 3.4 Rate limiting IBKR

**Token bucket** [broker.py:45–94] :
- Rate : **45 req/s** (constant `IB_TOKEN_BUCKET_RATE` dans [constants.py:196])
- Burst : **10 tokens** au démarrage
- Latence par `acquire()` : 0 ms en burst, ~22 ms en régime soutenu, max ~22 ms (1 token / 45 req/s)

**Semaphore historique** [data_feed.py:216] :
- `IB_MAX_CONCURRENT_HIST_REQUESTS = 3`
- ✅ **NON sur le chemin critique** — uniquement pour `_request_bars()` en phase pré-session

---

## BLOC 4 — EVENT LOOP ASYNCIO ET STARVATION

### 4.1 Nature de _on_new_m1_bar()

`_on_new_m1_bar()` est un **callback synchrone** [session_lifecycle.py:378] exécuté dans le **thread interne ib_insync**, pas dans l'event loop asyncio principal.

**Opérations synchrones dans ce callback :**
1. Dict lookups / bool checks (µs) [session_lifecycle.py:381–387]
2. Append + slice list 200 éléments (µs) [session_lifecycle.py:384–387]
3. `check_pair_limit()` — appel Cython (µs) [session_lifecycle.py:408]
4. `detect_gap()` — appel Cython (~0.5 ms) [session_lifecycle.py:420]
5. `detect_engulfing()` — appel Cython (~1 ms) [session_lifecycle.py:439]
6. `logger.info()` — Loguru (~1–2 ms) [session_lifecycle.py:442]

**Durée estimée totale :** 5–15 ms
**Risque starvation event loop :** ✅ **AUCUN** — le callback tourne dans le thread IB, pas dans l'event loop asyncio. Aucune starvation possible via ce chemin.

**Dispatch vers l'event loop :**
```python
# session_lifecycle.py:448
asyncio.ensure_future(self._atomic_check_and_execute(state, signal, pip_size))
```
→ La coroutine est ajoutée au loop asyncio pour exécution ultérieure (fire-and-forget depuis le callback).

### 4.2 Sections synchrones dans les coroutines asyncio

Les appels Cython (`detect_gap`, `detect_engulfing`) dans `_on_new_m1_bar` sont **syncrones mais dans un thread IB**, pas dans l'event loop. Pas de blocage asyncio.

En revanche, si un appel Cython était effectué directement dans une coroutine `async def` sans `run_in_executor`, il **bloquerait l'event loop** pendant sa durée. Ce cas n'est pas observé sur le hot path.

### 4.3 Trade lock — scope et contention

🟠 **Le trade_lock contient les 1s sleeps**

```python
# session_lifecycle.py:467–486
async with self._s._trade_lock:           # ← ACQUIRE
    # ... ~5ms de re-validation ...
    return await self._check_spread_and_execute(...)  # ← SOUS LE LOCK
    #   └─ await get_live_spread()  ← 1 000 ms DANS LE LOCK
    #   └─ await _execute_signal()  ← 1 000 ms JPY + ordre + fill wait
# ← RELEASE (après execution complète)
```

**Conséquence :** Si deux signaux arrivent simultanément sur deux paires différentes (multi-pair), la seconde paire attend **jusqu'à 2+ secondes** que la première libère le lock.

**Sévérité :** 🟠 Majeur (non déterministe, dépend du multi-pair activé).
**Périmètre actuel :** En configuration mono-pair typique, le risque est nul.

### 4.4 Boucle principale

```python
# session_lifecycle.py:784
while is_session_active() and not self._s._shutdown_requested:
    await asyncio.sleep(1.0)   # cadence 1s
    risk_check_counter += 1
    interval = RISK_CHECK_INTERVAL_POSITION if self._has_open_position() else RISK_CHECK_INTERVAL_IDLE
    if risk_check_counter >= interval:
        await self._check_daily_loss_shutdown()
```

- RISK_CHECK_INTERVAL_POSITION = **5** (5s si position ouverte) [constants.py:176]
- RISK_CHECK_INTERVAL_IDLE = **30** (30s si idle) [constants.py:177]
- **Aucun signal** n'est détecté depuis cette boucle — les signaux viennent exclusivement des callbacks M1.
- ✅ **Pas de risque de délai de 1s sur la détection de signal** — la boucle ne fait que le risk check.

---

## BLOC 5 — I/O SYNCHRONES SUR LE CHEMIN CRITIQUE

### 5.1 asyncio.sleep hardcodés — le plus grand problème

| Fonction | Fichier:Ligne | Sleep | Fréquence | Latence ajoutée |
|----------|--------------|-------|-----------|-----------------|
| `get_live_spread()` | [data_feed.py:728](../../../alphaedge/engine/data_feed.py) | `asyncio.sleep(1.0)` | **Chaque ordre** | 🔴 +1 000 ms |
| `get_mid_price()` | [data_feed.py:762](../../../alphaedge/engine/data_feed.py) | `asyncio.sleep(1.0)` | **Chaque ordre JPY** | 🔴 +1 000 ms |

Ces sleeps sont un **polling pattern déguisé** : on lance `reqMktData`, on attend 1s en espérant que la réponse soit arrivée, puis on lit `ticker.bid/ask`. Si IB répond en 50ms, on attend quand même 1s.

**Alternative correcte :** Utiliser un ticker subscription permanente ou un event-based pattern (`ticker.updateEvent` en ib_insync) pour éliminer le sleep.

### 5.2 Logging sur le chemin critique

✅ Présent mais **négligeable** (~1–2 ms par appel, Loguru asynchrone).
Les appels `logger.info/error/critical` sont nombreux [session_lifecycle.py:414, 432, 442, 475, 505] mais n'impactent pas significativement la latence.

### 5.3 Persistance d'état (JSON write)

✅ **Hors du chemin critique** — appelé APRÈS fill confirmé [session_lifecycle.py:165–172].
`save_daily_state()` → JSON write atomique (~10–50 ms) [state_persistence.py:42–54] — acceptable, rare (1×/trade).

### 5.4 Config YAML re-read

✅ **Pas de re-read pendant la session** — config chargée une fois au démarrage [strategy.py:158].

### 5.5 I/O réseau hors IBKR

✅ Pas d'HTTP synchrone sur le chemin critique.
Alertes Telegram/Discord : `asyncio.ensure_future(alert.send_async(...))` [session_lifecycle.py:153] → fire-and-forget, aucun blocage.

---

## BLOC 6 — QUALITÉ ET FRAÎCHEUR DES DONNÉES

### 6.1 Timestamping

✅ **Timestamps serveur IB** (UTC) — `bar.date` de ib_insync BarData.
Convertis en epoch UTC `int` + `datetime` aware-UTC [data_feed.py:87–95].
Le timestamps est celui d'IB, pas de l'horloge locale — pas de dérive liée au CPU.

### 6.2 Seuil d'obsolescence (staleness check)

🟡 **Aucun staleness check explicite.**
Les barres M1 sont consommées dans la minute où elles arrivent (délai buffer ~5–30s, intrinsèque à l'agrégation 5s→M1).
**Risque :** En cas de retard IB (data farm lent), une barre périmée pourrait déclencher un signal sans vérification d'âge.

### 6.3 Rolling buffer candles

- **Max candles :** 200 M1 [strategy.py:58–59] = ~3h20 de données
- **Trim :** list slice O(n) à chaque barre [session_lifecycle.py:386] — négligeable (200 éléments, µs)

### 6.4 Buffer de données

✅ M1BarAggregator accumule les barres 5s intra-minute, émet une M1 à la limite de minute — pas d'obsolescence introduite.
Latence buffer : ~5–30s (acceptable pour M1 signal).

### 6.5 Sync horloge locale vs IBKR

🟡 **Pas de synchronisation NTP / horloge locale** avec le serveur IB.
Les timestamps viennent d'IB, ce qui est correct. Mais si l'horloge locale dérive (session times, `now_utc()`), les comparaisons de session pourraient être biaisées.

---

## BLOC 7 — RÉSILIENCE ET LATENCE DE RECONNEXION

### 7.1 Reconnexion IBKR

**Algorithme :** Exponentiel avec jitter ±10% [broker.py:218–239]

| Tentative | Base | Range |
|-----------|------|-------|
| 1 | 2s | 1.8–2.2s |
| 2 | 4s | 3.6–4.4s |
| 3 | 8s | 7.2–8.8s |

**Latence totale worst-case :** ~12.6–15.4s (3 échecs)
**Max retries** configurable, défaut = 3.

### 7.2 Ordres pendant déconnexion

✅ Les ordres bracket (SL/TP) restent **actifs sur IBKR** pendant la déconnexion.
Au reconnect : `_reconcile_positions()` + `_check_orphan_orders()` [session_lifecycle.py:263–273].
**Risque :** Pendant la durée de reconnexion (~13s), le bot n'a pas de visibilité sur les fills. Si SL/TP se déclenche pendant ce laps, l'état local sera incohérent jusqu'à la réconciliation.

### 7.3 Nature de la reconnexion

✅ **Entièrement asyncio** — `await broker.reconnect()` depuis une coroutine, pas de thread séparé.
L'event loop principal reste opérationnel pendant le wait du backoff (d'autres coroutines peuvent tourner).

### 7.4 Reprise après crash / redémarrage

- **État rechargé depuis JSON** (`load_daily_state()`) au démarrage [session_lifecycle.py:startup]
- Réconciliation IBKR : `reqPositions` + `reqOpenOrders` → quelques RTT IB (~100–500ms total)
- **Cold start** uniquement — pas de mode "warm start" différencié.

### 7.5 Circuit breaker (halt trading)

✅ `check_daily_limit()` [risk_manager.pyx / stubs] retourne `can_trade: False` si daily loss dépassée.
Mécanisme de reset : via `_check_daily_loss_shutdown()` [session_lifecycle.py:789] → arrêt de session, redémarrage le lendemain.
**Pas de timer de reset automatique intra-session** — le halt est définitif pour la journée.

---

## SYNTHÈSE FINALE

### Tableau des problèmes — par sévérité

| ID | Bloc | Description | Fichier:Ligne | Sévérité | Latence estimée | Effort correction |
|----|------|-------------|--------------|----------|-----------------|-------------------|
| L-01 | 3.2 / 5.1 | `asyncio.sleep(1.0)` hardcodé dans `get_live_spread()` | [data_feed.py:728](../../../alphaedge/engine/data_feed.py) | 🔴 Critique | +1 000 ms fixe à chaque ordre | Moyen (event-based ticker) |
| L-02 | 3.2 / 5.1 | `asyncio.sleep(1.0)` hardcodé dans `get_mid_price()` | [data_feed.py:762](../../../alphaedge/engine/data_feed.py) | 🔴 Critique | +1 000 ms fixe pour JPY | Moyen (même fix que L-01) |
| L-03 | 4.3 | `trade_lock` contient les 1s sleeps → bloque les autres paires | [session_lifecycle.py:467](../../../alphaedge/engine/session_lifecycle.py) | 🟠 Majeur | +1 000–2 000 ms en cas de signal multi-pair simultané | Faible (refactoring scope lock) |
| L-04 | 2.5 | Fallback silencieux stubs Python si `.pyd` absent | [core/\_\_init\_\_.py:52](../../../alphaedge/core/__init__.py) | 🟠 Majeur | +5–10 ms par cycle en mode stubs | Faible (forcer `ALPHAEDGE_CORE_BACKEND=compiled`) |
| L-05 | 3.4 | Token bucket ~22 ms d'attente en régime soutenu | [broker.py:79](../../../alphaedge/engine/broker.py) | 🟠 Majeur | 0–30 ms non déterministe | Infrastructure IB (inévitable) |
| L-06 | 6.2 | Pas de staleness check sur les barres M1 | [session_lifecycle.py:384](../../../alphaedge/engine/session_lifecycle.py) | 🟡 Mineur | Données potentiellement périmées si IB lag | Faible (ajouter timestamp check) |
| L-07 | 6.5 | Pas de sync horloge locale / IBKR | — | 🟡 Mineur | Dérive session times possible | Faible (NTP ou validation timestamp) |
| L-08 | 7.2 | Reconnexion : pas de visibilité fills pendant ~13s | [session_lifecycle.py:263](../../../alphaedge/engine/session_lifecycle.py) | 🟡 Mineur | Incohérence d'état transitoire | Infrastructure |

---

### Budget latence total estimé

```
                          Non-JPY         JPY pairs
─────────────────────────────────────────────────────
signal detection          ~2–7 ms         ~2–7 ms
lock + validation         ~5 ms           ~5 ms
get_live_spread (sleep)   ~1 000 ms 🔴    ~1 000 ms 🔴
get_mid_price (sleep)     N/A             ~1 000 ms 🔴
token bucket              ~0–30 ms        ~0–30 ms
ib.placeOrder()           ~10–50 ms       ~10–50 ms
─────────────────────────────────────────────────────
Total signal→ordre        ~1 017–1 092 ms ~2 017–2 092 ms
─────────────────────────────────────────────────────

Cible raisonnable (avec fix L-01/L-02) :  ~20–100 ms
Écart à combler :                         ~1 000–1 900 ms
```

---

### Top 3 optimisations prioritaires

**1. 🔴 Éliminer les asyncio.sleep(1.0) dans get_live_spread / get_mid_price**
_Gain potentiel : -1 000 à -2 000 ms par ordre_

Remplacer le pattern `reqMktData → sleep(1s) → read ticker` par une **subscription permanente** au ticker IB et une lecture directe (le ticker est maintenu à jour par ib_insync en temps réel) :

```python
# Pattern actuel (polling déguisé) :
self._broker.ib.reqMktData(contract)
await asyncio.sleep(1.0)
ticker = self._broker.ib.ticker(contract)

# Pattern élégant (lecture directe du ticker subscrit) :
ticker = self._broker.ib.ticker(contract)   # déjà subscrit en début de session
if ticker and ticker.bid > 0 and ticker.ask > 0:
    return float(ticker.ask - ticker.bid)
```

Si le ticker est subscrit dès `subscribe()` en début de session, `ticker.bid/ask` sont mis à jour en continu par ib_insync — le sleep est inutile.

**2. 🟠 Réduire le scope du trade_lock (hors des 1s sleeps)**
_Gain potentiel : -1 000 à -2 000 ms de contention en multi-pair_

Sortir `get_live_spread()` et `_execute_signal()` du lock :

```python
async def _atomic_check_and_execute(...):
    async with self._s._trade_lock:    # ← lock court : re-validation seulement
        if not self._can_trade(state): return False
        # marquer la paire comme "en cours" dans un set (atomic sous lock)
        self._s._executing_pairs.add(state.pair)
    # ← lock relâché AVANT les 1s awaits
    try:
        spread = await self._s._rt_feed.get_live_spread(state.pair)
        await self._execute_signal(...)
    finally:
        self._s._executing_pairs.discard(state.pair)
```

**3. 🟠 Passer ALPHAEDGE_CORE_BACKEND=compiled en production**
_Gain potentiel : -5 à -10 ms, surtout : éviter un trading silencieux en mode dégradé_

Configurer `.env.production` :
```
ALPHAEDGE_CORE_BACKEND=compiled
```
Si `.pyd` absent → `ImportError` explicite au démarrage, pas de fallback silencieux.

---

### Ce qui est déjà optimal — ne pas toucher

| Mécanisme | Pourquoi c'est bon |
|-----------|-------------------|
| Event-driven M1 (barUpdateEvent) | Aucun polling — callbacks push-based ✅ |
| `asyncio.ensure_future()` depuis callback IB | Dispatche vers event loop sans bloquer le thread IB ✅ |
| Token bucket (45 req/s) avec burst | Conforme IB, implémentation `time.monotonic()` correcte ✅ |
| `asyncio.wait_for(fill_event, timeout=10s)` | Event-based, pas de polling, timeout robuste ✅ |
| JSON persist atomic (`.tmp` → `os.replace`) | Write-safe, hors chemin critique ✅ |
| Reconnect exponentiel backoff + jitter | Standard, empêche thundering herd ✅ |
| Réconciliation ordres orphelins au reconnect | Garantit cohérence état post-déco ✅ |
| Logs Loguru avec dual-time UTC/Paris | Diagnostics facilités, async-friendly ✅ |

---

### Recommandations de mesure en production

**Points de mesure prioritaires :**

```python
import time

# Point A : entrée callback M1
t_bar_received = time.perf_counter_ns()

# Point B : signal détecté
t_signal_detected = time.perf_counter_ns()

# Point C : avant get_live_spread
t_before_spread = time.perf_counter_ns()

# Point D : après get_live_spread
t_after_spread = time.perf_counter_ns()

# Point E : avant ib.placeOrder()
t_before_order = time.perf_counter_ns()

# Point F : après ib.placeOrder() (avant fill)
t_order_submitted = time.perf_counter_ns()

# Log synthèse
logger.info(
    "LATENCE signal={:.1f}ms spread={:.1f}ms order={:.1f}ms total={:.1f}ms",
    (t_signal_detected - t_bar_received) / 1e6,
    (t_after_spread - t_before_spread) / 1e6,
    (t_order_submitted - t_before_order) / 1e6,
    (t_order_submitted - t_bar_received) / 1e6,
)
```

**Outils recommandés :**
- `time.perf_counter_ns()` — mesure en nanosecondes, précision OS, zero-overhead
- `py-spy` — flamegraph async Python sans instrumentation (profiling non-intrusif)
- `cProfile` + `snakeviz` — profiling des appels Cython en mode stubs (compare stubs vs compiled)
- Loguru avec `logger.trace()` en mode dev pour les timings détaillés

---

*Fichier généré par analyse statique — les latences marquées "À MESURER EN PRODUCTION" nécessitent un profiling runtime pour confirmation.*
