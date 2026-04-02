---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/corrections/plans/PLAN_ACTION_audit_latence_alphaedge_2026-03-26.md
derniere_revision: 2026-03-26
creation: 2026-03-26
---

# PLAN D'ACTION — ALPHAEDGE — 2026-03-26
Sources : `tasks/audits/audit_latence_alphaedge.md`
Total : 🔴 1 · 🟠 3 · 🟡 5 · Effort estimé : 1.5 jours

---

## PHASE 1 — CRITIQUES 🔴

### [C-01] Sortir `accountSummary()` du chemin critique dans `_check_margin()`
Fichier : `alphaedge/engine/broker.py:377`
Problème : `_check_margin()` est appelée dans `place_bracket_order()` sur le chemin critique
signal→ordre. Elle appelle `ib.accountSummary()` de manière synchrone, ce qui peut bloquer
l'event loop de 1 à 50ms selon l'état du cache interne d'ib_insync. Ceci introduit une latence
non déterministe sur chaque envoi d'ordre.
Correction : Mettre en cache la marge disponible dans `StrategyState` (ou un attribut de
`BrokerConnection`). La rafraîchir lors du risk check périodique (toutes les 5–30s via la boucle
principale) et lors du `get_account_equity()` au démarrage de session. Dans `_check_margin()`,
lire uniquement la valeur en cache — aucun appel IB sur le chemin critique.
```python
# BrokerConnection : nouvel attribut
_cached_available_funds: float = 0.0

# Méthode de mise à jour (appelable depuis risk check loop)
async def refresh_account_funds(self) -> None:
    await self._throttler.acquire()
    account_values = self._ib.accountSummary()
    for av in account_values:
        if av.tag == "AvailableFunds":
            self._cached_available_funds = float(av.value)
            return

# _check_margin() — lire le cache uniquement
def _check_margin(self, quantity, entry_price, leverage_estimate=50.0) -> bool:
    available_funds = self._broker._cached_available_funds
    if available_funds <= 0.0:
        logger.warning("ALPHAEDGE: margin cache not initialized — trade blocked")
        return False
    required = (quantity * entry_price / leverage_estimate) * 1.2
    if available_funds < required:
        logger.warning(...)
        return False
    return True
```
Validation :
  make qa
  # Attendu : 590 tests pass · 0 Ruff · 0 Pyright
  # Vérifier : _check_margin ne fait plus d'appel IB (mock dans test)
Dépend de : Aucune
Statut : ⏳

---

## PHASE 2 — MAJEURES 🟠

### [C-02] Passer `_persist_daily_state()` en fire-and-forget post-fill
Fichier : `alphaedge/engine/session_lifecycle.py:226`
Problème : `_persist_daily_state()` est appelée dans `_record_fill()` de manière synchrone,
bloquant l'event loop le temps d'une écriture disk (~1–10ms selon OS/VM). Retarde les
autres coroutines en attente (ex : barres M1 multi-paires).
Correction : Envelopper dans `asyncio.ensure_future()` avec `add_done_callback(_on_task_done)`
— le même pattern que les alertes. Transformer `_persist_daily_state()` en coroutine async si
nécessaire, ou la déléguer à `loop.run_in_executor()`.
```python
# session_lifecycle.py — dans _record_fill()
# AVANT
self._persist_daily_state()

# APRÈS
task = asyncio.ensure_future(asyncio.to_thread(self._persist_daily_state))
task.add_done_callback(self._on_task_done)
```
Validation :
  make qa
  # Attendu : 590 tests pass · 0 Ruff · 0 Pyright
Dépend de : Aucune
Statut : ⏳

### [C-03] Éliminer le doublon `get_live_spread()` dans `_execute_signal()`
Fichier : `alphaedge/engine/session_lifecycle.py:372`
Problème : `get_live_spread()` est appelée une première fois dans `_check_spread_and_execute()`
(ligne 730) puis à nouveau dans `_execute_signal()` (ligne 372). Doublon redondant — même ticker
cache. En plus d'être inutile, les deux valeurs peuvent diverger si le spread change entre
les deux appels, créant une incohérence dans le log LATENCE.
Correction : Passer le `spread_pips` déjà calculé dans `_check_spread_and_execute()` comme
paramètre à `_execute_signal()`. Supprimer le second appel dans `_execute_signal()`.
```python
# _check_spread_and_execute() : passer spread_pips
return await self._execute_signal(state, signal, pip_size, spread_pips=spread_pips)

# _execute_signal() : accepter spread_pips en paramètre
async def _execute_signal(self, state, signal, pip_size, spread_pips: float | None = None):
    ...
    if spread_pips is None:
        spread = await self._s._rt_feed.get_live_spread(state.pair)
        spread_pips = spread / pip_size if spread else 0.0
    # ← supprimer l'appel redondant qui suit
```
Validation :
  make qa
  # Attendu : 590 tests pass · 0 Ruff · 0 Pyright
Dépend de : Aucune
Statut : ⏳

### [C-04] Ajouter reset automatique du circuit breaker sur timer
Fichier : `alphaedge/engine/broker.py:156`
Problème : Après 5 failures consécutives, `connect()` retourne `False` immédiatement pour
toute éternité jusqu'à redémarrage du processus. Pour un process long-running 24h,
si IB Gateway redémarre après une maintenance et que le bot a accumulé 5 failures pendant
la fenêtre de downtime, il ne peut plus se reconnecter sans intervention manuelle.
Correction : Ajouter un timestamp `_circuit_breaker_opened_at` et un cooldown configurable
(`IB_CIRCUIT_BREAKER_RESET_SECONDS = 300`, i.e. 5 minutes). Si le cooldown est écoulé depuis
l'ouverture, réinitialiser le compteur et retenter la connexion.
```python
# constants.py — nouvelle constante
IB_CIRCUIT_BREAKER_RESET_SECONDS: int = 300  # 5 minutes avant auto-reset

# broker.py — connect()
import time
if self._consecutive_failures >= IB_CIRCUIT_BREAKER_MAX_FAILURES:
    elapsed = time.monotonic() - self._circuit_breaker_opened_at
    if elapsed < IB_CIRCUIT_BREAKER_RESET_SECONDS:
        logger.critical("circuit breaker OPEN — %.0fs remaining", ...)
        return False
    logger.warning("ALPHAEDGE: circuit breaker AUTO-RESET after %.0fs", elapsed)
    self._consecutive_failures = 0  # reset
    self._circuit_breaker_opened_at = 0.0
```
Validation :
  make qa
  # Attendu : 590 tests pass · 0 Ruff · 0 Pyright
  # Ajouter test : test_broker_circuit_breaker_reset.py
Dépend de : Aucune
Statut : ⏳

---

## PHASE 3 — MINEURES 🟡

### [C-05] Ajouter point de mesure `perf_counter_ns()` sur `accountSummary()` dans `_check_margin()`
Fichier : `alphaedge/engine/broker.py:377`
Problème : Absence de mesure de latence sur l'appel le plus risqué du chemin critique.
Sans mesure en production, impossible de détecter une régression (IB cache froid, charge réseau).
Correction : Encadrer l'appel `accountSummary()` avec `time.perf_counter_ns()` et logguer en DEBUG.
Note : ce point de mesure devient obsolète si C-01 est appliqué (le cache remplace l'appel). Si C-01
est implémenté, déplacer la mesure sur `refresh_account_funds()`.
```python
_t0 = time.perf_counter_ns()
account_values = self._broker.ib.accountSummary()
_t_ns = (time.perf_counter_ns() - _t0) / 1e6
logger.debug("LATENCE accountSummary=%.2fms", _t_ns)
```
Validation :
  make qa
  # Attendu : 590 tests pass · 0 Ruff · 0 Pyright
Dépend de : C-01 (implémenter après, ou adapter si C-01 fait en premier)
Statut : ⏳

### [C-06] Ajouter TTL sur les données ticker in-memory (`get_live_spread` / `get_mid_price`)
Fichier : `alphaedge/engine/data_feed.py:736`
Problème : Si le flux de ticks bid/ask s'arrête sans déclencher `disconnectedEvent`,
`get_live_spread()` et `get_mid_price()` retournent des données silencieusement périmées.
Ce cas est possible en cas de perte de flux partielle côté IB (ex: data farm disconnect ≠
connexion principale).
Correction : Stocker le timestamp du dernier tick reçu par paire dans `RealtimeDataFeed`.
Retourner `None` si plus de `MAX_TICK_STALENESS_SECONDS` (ex: 30s) s'est écoulé sans nouveau tick.
```python
# RealtimeDataFeed
_last_tick_ts: dict[str, float] = {}  # pair → time.monotonic()
MAX_TICK_STALENESS_SECONDS = 30

# Dans _on_bar_update() : mettre à jour le timestamp
self._last_tick_ts[pair] = time.monotonic()

# Dans get_live_spread() : checker avant de lire le ticker
ts = self._last_tick_ts.get(pair, 0.0)
if time.monotonic() - ts > MAX_TICK_STALENESS_SECONDS:
    logger.warning("ALPHAEDGE STALE TICK: %s — no tick for %.0fs", pair, ...)
    return None
```
Validation :
  make qa
  # Attendu : 590 tests pass · 0 Ruff · 0 Pyright
Dépend de : Aucune
Statut : ⏳

### [C-07] Déplacer l'import inline `from datetime import date as _date`
Fichier : `alphaedge/engine/strategy.py:203`
Problème : Import dans le corps d'une fonction — anti-pattern, cosmétique mais mesurable
(lookup dict module cache à chaque appel de `_detect_momentum()`).
Correction : Déplacer en haut du module avec les autres imports `datetime`.
```python
# strategy.py — en-tête du module (avec les autres imports)
from datetime import date as _date_cls  # ou simplement 'date'

# Dans _detect_momentum() — supprimer la ligne d'import inline
```
Validation :
  make qa
  # Attendu : 590 tests pass · 0 Ruff · 0 Pyright
Dépend de : Aucune
Statut : ⏳

### [C-08] Ajouter `IB_CIRCUIT_BREAKER_RESET_SECONDS` dans `constants.py`
Fichier : `alphaedge/config/constants.py`
Problème : Dépendance de C-04 — la nouvelle constante doit être définie dans le fichier
central de constantes (règle absolue du projet : aucune valeur hardcodée hors `constants.py`).
Correction : Ajouter la constante avec commentaire explicatif.
```python
# constants.py — section IB Gateway (après IB_CIRCUIT_BREAKER_MAX_FAILURES)
IB_CIRCUIT_BREAKER_RESET_SECONDS: int = 300  # auto-reset cooldown after circuit breaker opens
```
Validation :
  make qa
  # Attendu : 590 tests pass · 0 Ruff · 0 Pyright
Dépend de : C-04
Statut : ⏳

### [C-09] Ajouter test `test_broker_circuit_breaker_reset.py`
Fichier : `alphaedge/tests/test_broker_circuit_breaker_reset.py` (nouveau)
Problème : C-04 n'est pas couvert par les tests existants — le reset automatique
doit être validé avant de marquer la correction terminée.
Correction : Créer un fichier de test couvrant :
  - circuit breaker s'ouvre après N failures
  - connect() retourne False pendant le cooldown
  - connect() retente après le cooldown expiré
  - reset du compteur si connexion réussit après cooldown
Validation :
  make qa
  # Attendu : ≥593 tests pass (590 + ≥3 nouveaux)
Dépend de : C-04, C-08
Statut : ⏳

---

## SÉQUENCE D'EXÉCUTION

```
C-07  (import inline — trivial, sans dépendance)
C-08  (constante constants.py — prérequis C-04)
C-01  (cache accountSummary — chemin critique 🔴, priorité max)
C-05  (mesure latence accountSummary — adapter après C-01)
C-02  (persist fire-and-forget — post-fill)
C-03  (doublon spread — trivial)
C-04  (circuit breaker reset — dépend C-08)
C-09  (test circuit breaker — dépend C-04)
C-06  (TTL tick staleness — indépendant)

→ make qa après chaque correction
→ make build NON REQUIS (aucun .pyx touché)
```

---

## CRITÈRES PASSAGE EN PRODUCTION

- [ ] Zéro 🔴 ouvert
- [ ] `make qa` : 100% pass (lint + mypy + pytest ≥80%)
- [ ] Zéro credential dans les logs loguru
- [ ] `ALPHAEDGE_PAPER=true` intact dans `.env.example`
- [ ] Bracket order `is_valid` vérifié avant envoi IB
- [ ] `check_daily_limit()` appelé chaque cycle
- [ ] `_check_margin()` ne fait plus d'appel IB sur le chemin critique (C-01)
- [ ] Circuit breaker se reset automatiquement après cooldown (C-04)
- [ ] Paper trading validé 5 sessions NYSE minimum

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier | Effort | Statut | Date |
|---|---|---|---|---|---|---|
| C-01 | Cache `accountSummary()` hors chemin critique | 🔴 | `broker.py:377` | 0.5j | ⏳ | |
| C-02 | `_persist_daily_state()` post-fill async | 🟠 | `session_lifecycle.py:226` | 0.25j | ⏳ | |
| C-03 | Doublon `get_live_spread()` dans `_execute_signal` | 🟠 | `session_lifecycle.py:372` | 0.25j | ⏳ | |
| C-04 | Circuit breaker auto-reset | 🟠 | `broker.py:156` | 0.25j | ⏳ | |
| C-05 | Mesure latence `accountSummary()` DEBUG | 🟡 | `broker.py:377` | 0.1j | ⏳ | |
| C-06 | TTL tick staleness `get_live_spread` | 🟡 | `data_feed.py:736` | 0.25j | ⏳ | |
| C-07 | Import inline `from datetime import date` | 🟡 | `strategy.py:203` | 0.05j | ⏳ | |
| C-08 | Constante `IB_CIRCUIT_BREAKER_RESET_SECONDS` | 🟡 | `constants.py` | 0.05j | ⏳ | |
| C-09 | Test circuit breaker reset | 🟡 | `tests/test_broker_circuit_breaker_reset.py` | 0.25j | ⏳ | |

**Effort total estimé : 1.5 jours**
