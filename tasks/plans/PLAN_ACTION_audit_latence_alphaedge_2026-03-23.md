# PLAN D'ACTION — ALPHAEDGE — 2026-03-23
**Sources :** `tasks/audits/AUDIT_LATENCE_ALPHAEDGE.md`
**Total :** 🔴 2 · 🟠 3 · 🟡 3 · **Effort estimé : 3–5 jours**

---

## PHASE 1 — CRITIQUES 🔴

---

### [C-01] Éliminer asyncio.sleep(1.0) dans get_live_spread()

**Fichier :** `alphaedge/engine/data_feed.py:728`

**Problème :**
`get_live_spread()` utilise un pattern `reqMktData → sleep(1.0) → read ticker` qui impose **1 000 ms fixes** avant chaque ordre. C'est un polling déguisé : si IB répond en 50ms, on attend quand même 1s intégrale. Appelé systématiquement avant chaque ordre [session_lifecycle.py:493].

**Correction :**
Supprimer le `reqMktData` + `asyncio.sleep(1.0)`. Lire directement le ticker déjà maintenu à jour par ib_insync via la subscription permanente ouverte en début de session (`subscribe()`). Le ticker `bid/ask` est mis à jour en continu via `barUpdateEvent` — aucune requête ponctuelle nécessaire.

```python
# Avant (data_feed.py:728)
self._broker.ib.reqMktData(contract)
await asyncio.sleep(1.0)
ticker = self._broker.ib.ticker(contract)

# Après
ticker = self._broker.ib.ticker(contract)  # déjà subscrit et maintenu à jour
```

Vérifier que `ticker` est non-None et que `ticker.bid > 0` et `ticker.ask > 0` avant lecture.
Si le ticker n'est pas encore peuplé (cas rare, démarrage), retourner `None` → spread rejeté → ordre annulé (comportement déjà existant).

**Validation :**
```
make qa
# Attendu : 553 tests passés, lint OK, mypy OK
# Note : aucun .pyx modifié, make build inutile
```

**Dépend de :** Aucune

**Statut :** ✅ 2026-03-23 — reqMktData déplacé dans subscribe()/unsubscribe(), sleep(1.0) + throttler éliminés. 553 tests · lint OK · pyright OK.

---

### [C-02] Éliminer asyncio.sleep(1.0) dans get_mid_price()

**Fichier :** `alphaedge/engine/data_feed.py:762`

**Problème :**
Même pattern que C-01. `get_mid_price()` impose **+1 000 ms** supplémentaires pour les paires JPY (EUR/JPY, USD/JPY, GBP/JPY). Résultat : **2 000 ms garanties** avant chaque ordre JPY [session_lifecycle.py:191].

**Correction :**
Identique à C-01 : lire le ticker directement sans `reqMktData` ni sleep.

```python
# Avant (data_feed.py:762)
self._broker.ib.reqMktData(contract)
await asyncio.sleep(1.0)
ticker = self._broker.ib.ticker(contract)

# Après
ticker = self._broker.ib.ticker(contract)
```

Retourner `None` si ticker non peuplé → `_execute_signal()` gère déjà ce cas [session_lifecycle.py:193–195].

**Validation :**
```
make qa
# Attendu : 553 tests passés, lint OK, mypy OK
```

**Dépend de :** Aucune (indépendant de C-01, peut être fait en parallèle)

**Statut :** ✅ 2026-03-23 — Traité avec C-01. Même fix appliqué. 553 tests · lint OK · pyright OK.

---

## PHASE 2 — MAJEURES 🟠

---

### [C-03] Réduire le scope du trade_lock (hors des awaits longs)

**Fichier :** `alphaedge/engine/session_lifecycle.py:467`

**Problème :**
Le `trade_lock` est acquis au début de `_atomic_check_and_execute()` et reste maintenu pendant toute l'exécution incluant `get_live_spread()` (1s), `get_mid_price()` (1s JPY), la soumission de l'ordre et l'attente du fill (jusqu'à 10s). En configuration multi-pair, un second signal sur une paire différente peut être bloqué jusqu'à **12+ secondes**.

**Correction :**
Réduire la section sous lock à la seule re-validation atomique (dict lookups, µs). Marquer la paire comme "en cours d'exécution" dans un set thread-safe sous le lock, puis relâcher le lock avant les awaits longs.

```python
async def _atomic_check_and_execute(self, state, signal, pip_size) -> bool:
    async with self._s._trade_lock:           # lock court : µs seulement
        if not self._can_trade_atomic(state):
            return False
        self._s._executing_pairs.add(state.pair)  # marque atomique
    # lock relâché ici — AVANT les 1s sleeps
    try:
        return await self._check_spread_and_execute(state, signal, pip_size)
    finally:
        self._s._executing_pairs.discard(state.pair)
```

Adapter `_can_trade_atomic()` pour vérifier `state.pair in self._s._executing_pairs` (double-signal guard).
Ajouter `_executing_pairs: set[str] = field(default_factory=set)` dans `StrategyState` [strategy.py].

**Validation :**
```
make qa
# Attendu : 553 tests passés, lint OK, mypy OK
# Vérifier les tests d'intégration trade_lock dans tests/
```

**Dépend de :** C-01, C-02 (optimiser d'abord les sleeps pour mesurer le vrai gain du lock)

**Statut :** ✅ 2026-03-23 — `_executing_pairs` ajouté à FCRStrategy. Lock réduit à µs (check + réservation atomique). Execute hors lock. 5 tests race condition OK · 553 tests · lint OK · pyright OK.

---

### [C-04] Forcer ALPHAEDGE_CORE_BACKEND=compiled en production

**Fichier :** `.env.example` · `alphaedge/core/__init__.py:52`

**Problème :**
En mode `auto` (défaut), si le `.pyd` Cython n'est pas présent (build manquant, déploiement incomplet), le bot démarre silencieusement avec les stubs Python. Aucun CRITICAL, aucun arrêt. Le trading continue avec ~5–10ms de latence supplémentaire par cycle sans que l'opérateur soit alerté.

**Correction :**
1. Documenter dans `.env.example` que `ALPHAEDGE_CORE_BACKEND=compiled` est obligatoire en production.
2. Dans `core/__init__.py`, élever le log WARNING en CRITICAL si un fallback se produit en mode `auto` et que l'environnement est production (`ALPHAEDGE_PAPER=false` ou nouvelle variable `ALPHAEDGE_ENV=production`).

```python
# core/__init__.py — après le fallback
if _is_production():
    logger.critical(
        "ALPHAEDGE CRITICAL: Cython module '{}' unavailable in production — "
        "compiled extensions required. Run 'make build' and restart.",
        name,
    )
    raise ImportError(f"Compiled module '{name}' required in production")
```

Ne pas modifier `core/*.pyx`.

**Validation :**
```
make qa
# Attendu : 553 tests passés (les tests CI utilisent ALPHAEDGE_CORE_BACKEND=stubs)
# Tester manuellement le comportement en mode production avec .pyd absent
```

**Dépend de :** Aucune

**Statut :** ✅ 2026-03-23 — `_is_production()` ajouté (ALPHAEDGE_ENV=production). Fallback auto en prod élève CRITICAL + ImportError. `.env.example` documenté. 553 tests · lint OK.

---

### [C-05] Token bucket — latence non déterministe acceptable (monitoring)

**Fichier :** `alphaedge/engine/broker.py:79`

**Problème :**
Le token bucket IB (45 req/s) peut imposer ~22 ms d'attente en régime soutenu. Cette latence est **imposée par IB** (rate limit contractuel) et ne peut être réduite sans risquer des erreurs Pacing 162. Aucune correction de code possible.

**Correction :**
Action de monitoring uniquement : ajouter un log DEBUG sur le temps d'attente effectif du token bucket pour mesurer l'impact réel en production.

```python
# broker.py — dans acquire()
wait_start = time.perf_counter_ns()
await asyncio.sleep(wait_time)
wait_ms = (time.perf_counter_ns() - wait_start) / 1e6
logger.debug("ALPHAEDGE throttler: waited {:.1f}ms (tokens={:.2f})", wait_ms, self._tokens)
```

**Validation :**
```
make qa
# Attendu : 553 tests passés
```

**Dépend de :** Aucune

**Statut :** ✅ 2026-03-23 — Log DEBUG `perf_counter_ns` ajouté dans `TokenBucketThrottler.acquire()`. 553 tests · lint OK.

---

## PHASE 3 — MINEURES 🟡

---

### [C-06] Ajouter un staleness check sur les barres M1

**Fichier :** `alphaedge/engine/session_lifecycle.py:384`

**Problème :**
Aucune vérification de l'âge des barres M1 avant usage. Si la data farm IB est lente ou en retard, une barre périmée peut déclencher un signal sans que le bot s'en aperçoive.

**Correction :**
Après l'append de la barre [session_lifecycle.py:384], vérifier que l'âge de la barre est < seuil (ex. `MAX_BAR_STALENESS_SECONDS` dans `constants.py`, valeur suggérée : 90s pour M1).

```python
# session_lifecycle.py — après state.m1_candles.append(candle)
bar_age_s = (now_utc() - candle["datetime"]).total_seconds()
if bar_age_s > MAX_BAR_STALENESS_SECONDS:
    logger.warning("ALPHAEDGE STALE BAR: {} — age={:.0f}s — skipping", pair, bar_age_s)
    return
```

Ajouter `MAX_BAR_STALENESS_SECONDS: int = 90` dans `constants.py`.

**Validation :**
```
make qa
# Attendu : 553 tests passés
# Vérifier que le test de freshness data passe dans tests/
```

**Dépend de :** Aucune

**Statut :** ✅ 2026-03-23 — `MAX_BAR_STALENESS_SECONDS=90` dans constants.py. Check `.get("datetime")` défensif dans `_on_new_m1_bar`. Test fill_verification mis à jour (timestamps frais). 553 tests · lint OK.

---

### [C-07] Instrumenter le chemin critique avec perf_counter_ns

**Fichier :** `alphaedge/engine/session_lifecycle.py` · `alphaedge/engine/data_feed.py`

**Problème :**
Aucune mesure de latence runtime dans le pipeline signal→ordre. Impossible de valider les gains après C-01/C-02 ou de détecter des régressions en production.

**Correction :**
Ajouter des points de mesure `time.perf_counter_ns()` aux étapes clés, loggués en DEBUG (off par défaut en production, activables via log level).

Points de mesure cibles :
1. Entrée `_on_new_m1_bar()` → `t_bar`
2. Signal détecté → `t_signal`
3. Avant/après `get_live_spread()` → `t_spread_start`, `t_spread_end`
4. Avant `ib.placeOrder()` → `t_order`

Log synthèse :
```python
logger.debug(
    "LATENCE: signal={:.1f}ms spread={:.1f}ms order_submit={:.1f}ms total={:.1f}ms",
    (t_signal - t_bar) / 1e6,
    (t_spread_end - t_spread_start) / 1e6,
    (t_order - t_spread_end) / 1e6,
    (t_order - t_bar) / 1e6,
)
```

**Validation :**
```
make qa
# Attendu : 553 tests passés
```

**Dépend de :** C-01, C-02 (instrumenter après les corrections pour mesurer le gain réel)

**Statut :** ✅ 2026-03-23 — `time` importé. Points de mesure `perf_counter_ns` : `_t_bar`/`_t_signal` dans `_on_new_m1_bar`, `_t0`/`_t_spread_end`/`_t_order` dans `_execute_signal`. Logs DEBUG activés via log level. 553 tests · lint OK.

---

### [C-08] Améliorer la visibilité de l'état pendant reconnexion

**Fichier :** `alphaedge/engine/session_lifecycle.py:263`

**Problème :**
Pendant les ~13s de reconnexion, le bot n'a aucune visibilité sur les fills potentiels (SL/TP bracket). L'état local peut devenir incohérent jusqu'à la réconciliation post-reconnect.

**Correction :**
Au déclenchement de la reconnexion, logguer immédiatement un CRITICAL avec l'état des ordres ouverts connus, et forcer une réconciliation complète (`reqOpenOrders` + `reqPositions`) dès que la connexion est rétablie. Ce mécanisme existe déjà partiellement (`_check_orphan_orders`) — s'assurer qu'il est toujours déclenché, même si `max_retries` est épuisé.

**Validation :**
```
make qa
# Attendu : 553 tests passés
```

**Dépend de :** Aucune

**Statut :** ✅ 2026-03-23 — `_on_ib_disconnect` logge CRITICAL avec positions connues. `_handle_reconnection` tente reconcile + orphan check même avant shutdown. 553 tests · lint OK.

---

## SÉQUENCE D'EXÉCUTION

```
1. C-01  ← Aucune dépendance, gain maximal, commencer ici
2. C-02  ← Parallélisable avec C-01
3. C-04  ← Aucune dépendance, sécurité prod
4. C-05  ← Aucune dépendance, monitoring uniquement
5. C-06  ← Aucune dépendance, safety guard
6. C-03  ← Après C-01/C-02 (sleep réduits → scope lock plus significatif à mesurer)
7. C-07  ← Après C-01/C-02 (mesurer les gains réels post-correction)
8. C-08  ← Aucune dépendance, peut être fait à tout moment
```

> ✅ Aucun fichier `.pyx` modifié dans ce plan → **`make build` non requis**.
> Toutes les corrections sont dans des fichiers `.py`.

---

## CRITÈRES PASSAGE EN PRODUCTION

- [ ] Zéro 🔴 ouvert
- [ ] `make qa` : 100% pass (lint + mypy + pytest ≥80%)
- [ ] Zéro credential dans les logs loguru
- [ ] `ALPHAEDGE_PAPER=true` intact dans `.env.example`
- [ ] Bracket order `is_valid` vérifié avant envoi IB
- [ ] `check_daily_limit()` appelé chaque cycle
- [ ] Paper trading validé 5 sessions NYSE minimum
- [ ] **Latence signal→ordre mesurée < 200ms** (avec C-01/C-02 appliqués)
- [ ] **`ALPHAEDGE_CORE_BACKEND=compiled`** configuré dans `.env` production

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier | Effort | Statut | Date |
|----|-------|----------|---------|--------|--------|------|
| C-01 | Éliminer sleep(1s) dans get_live_spread() | 🔴 | data_feed.py:728 | 2h | ⏳ | — |
| C-02 | Éliminer sleep(1s) dans get_mid_price() | 🔴 | data_feed.py:762 | 1h | ⏳ | — |
| C-03 | Réduire scope trade_lock hors awaits longs | 🟠 | session_lifecycle.py:467 | 4h | ⏳ | — |
| C-04 | Forcer CORE_BACKEND=compiled en production | 🟠 | core/__init__.py:52 | 1h | ⏳ | — |
| C-05 | Token bucket — log de monitoring | 🟠 | broker.py:79 | 30min | ⏳ | — |
| C-06 | Staleness check barres M1 | 🟡 | session_lifecycle.py:384 | 1h | ⏳ | — |
| C-07 | Instrumentation perf_counter_ns | 🟡 | session_lifecycle.py + data_feed.py | 2h | ⏳ | — |
| C-08 | Visibilité état pendant reconnexion | 🟡 | session_lifecycle.py:263 | 1h | ⏳ | — |
