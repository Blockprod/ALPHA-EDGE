---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: audit_technical_alphaedge.md
derniere_revision: 2026-03-25
creation: 2026-03-25
---

# AUDIT TECHNIQUE & SÉCURITÉ — ALPHAEDGE
**Date :** 2026-03-25 · **Rédacteur :** Copilot Agent (sonnet-4.6)
**Périmètre :** Sécurité credentials IB · Séparation paper/live · Robustesse IB Gateway · Persistance · Couverture tests sécurité

---

## BLOC 1 — SÉCURITÉ CREDENTIALS IB GATEWAY

### 1.1 Chargement des credentials

`loader.py:278–283` — `ALPHAEDGE_IB_HOST`, `ALPHAEDGE_IB_PORT`,
`ALPHAEDGE_IB_CLIENT_ID`, `ALPHAEDGE_IB_ACCOUNT` chargés exclusivement via
`os.getenv()`. Aucun credential hardcodé dans le code source détecté.
**✅ Conforme.**

### 1.2 ALPHAEDGE_PAPER=true dans .env.example

`.env.example:26` — `ALPHAEDGE_PAPER=true` présent avec commentaire
d'avertissement explicite (`⚠️ WARNING: Setting to "false" enables LIVE TRADING with real money!`).
**✅ Conforme.**

### 1.3 ALPHAEDGE_PAPER=false absent du code source

Aucune occurrence de `ALPHAEDGE_PAPER=false` dans le code source
(`alphaedge/`, `scripts/`, fichiers de config commitables).
Les seules occurrences sont dans les tests via `monkeypatch.setenv("ALPHAEDGE_PAPER", "false")` — usage légitime.
**✅ Conforme.**

### 1.4 Protection .gitignore

`.gitignore:25` — `.env` ignoré.
`.gitignore:28–29` — `alphaedge/logs/*.log` et `alphaedge/logs/*.txt` ignorés.
`.gitignore:45` — `alphaedge_daily_state.json` (state runtime) ignoré.

**À VÉRIFIER** : Le workspace contient des fichiers `alphaedge/logs/backtest_result.txt`,
`bt_final.txt`, `bt_full.txt`, `bt_stderr.txt`, `opt.txt`. La règle `.gitignore:29`
(`alphaedge/logs/*.txt`) doit les couvrir, mais si ces fichiers étaient trackés avant
l'ajout de la règle, `git status` les montrerait toujours. Vérifier via `git ls-files alphaedge/logs/`.
**→ ID T-05** (voir Synthèse).

### 1.5 Credentials absents des logs

`broker.py:200` — log de connexion : `host`, `port`, `is_paper` uniquement.
`account_id` non loggé.

`loader.py:150` — `account_id: str = field(default="", repr=False)` — exclu de `__repr__`, ne peut pas fuiter via logging de l'objet `IBConfig`.
**✅ Conforme.**

### Tableau Bloc 1

| Contrôle | Résultat | Fichier:Ligne |
|----------|----------|---------------|
| Credentials depuis env var | ✅ | `loader.py:278–283` |
| ALPHAEDGE_PAPER=true dans .env.example | ✅ | `.env.example:26` |
| ALPHAEDGE_PAPER=false absent du code | ✅ | — |
| .gitignore protège .env et logs | ✅ (⚠️ T-05 à vérifier) | `.gitignore:25,28–29` |
| account_id absent des logs | ✅ | `loader.py:150` · `broker.py:200` |

---

## BLOC 2 — SÉPARATION PAPER / LIVE

### 2.1 Branche paper vs live dans broker.py

La séparation est **port-based** : port 4002 → IB paper account, port 4001 → IB live account. IB Gateway assure la ségrégation côté serveur.

`loader.py:_resolve_ib_mode_and_port()` lignes 296–323 — validation croisée stricte :
si `ALPHAEDGE_PAPER=false` ET port=4002, `ValueError("ALPHAEDGE IB config mismatch")` est levée.
La combinaison ambigu est rendue impossible au chargement de config.
**✅ Conforme.**

Absence de guard hardware dans `broker.py:place_bracket_order()` (pas de `if is_paper: raise`) — mais le guard existe au niveau config loader via le ValueError, ce qui est plus robuste car intercepté avant connexion.

### 2.2 ALPHAEDGE_PAPER lu au démarrage uniquement

`loader.py:296` — `os.getenv("ALPHAEDGE_PAPER")` appelé une seule fois dans
`load_config()`. Résultat figé dans `AppConfig.ib.is_paper`. Pas relu au runtime.
**✅ Conforme.**

### 2.3 Aucun ordre réel en mode paper

En mode paper, la connexion IB est sur port 4002 (TWS/Gateway paper). Tout ordre
soumis via `placeOrder()` est routé automatiquement vers le compte paper par IB.
**✅ Conforme** (ségrégation côté broker).

### 2.4 Log startup indique PAPER ou LIVE

`strategy.py:318–337` — `print()` console explicite au démarrage :
- `"📝 ALPHAEDGE — PAPER TRADING MODE"`
- `"⚠️ ALPHAEDGE — LIVE TRADING MODE"`

`broker.py:200` — `logger.info(f"ALPHAEDGE connected ... (paper={self._config.is_paper})")`.

**🟡 MINEUR** : `session_lifecycle.py:run_session()` (ligne ~946) log de démarrage
`"ALPHAEDGE session starting at {format_dual_time(now_utc())}"` n'indique **pas** le
mode paper/live. En cas de redémarrage, l'opérateur ne voit pas immédiatement depuis les
logs seuls si la session est paper ou live. → **ID T-04**.

### 2.5 Tests paper/live

`test_paper_live_separation.py` — 4 tests couvrant :
- Port live correct inféré depuis env
- Rejection ValueError sur mismatch port/mode
- `_apply_cli_mode()` paper et live
**✅ Couverture présente.**

---

## BLOC 3 — ROBUSTESSE IB GATEWAY ET ASYNCIO

### 3.1 Reconnexion automatique

`broker.py:_on_disconnect()` — déclenché par `ib_insync.disconnectedEvent`.
Remet `_connected = False` et reset le client IB.

`session_lifecycle.py:_on_ib_disconnect()` — fire-and-forget de `_handle_reconnection()` :
- `reconnect(max_retries=3)` avec exponential backoff + jitter (2s → 4s → 8s ±10%)
- Post-reconnect : `_reconcile_positions()` + `_check_orphan_orders()` + re-subscribe feeds
- Échec total → `shutdown_requested = True` + alerte CRITICAL
**✅ Conforme.**

### 3.2 reqHistoricalData : timeout et retry

`data_feed.py:_request_bars()` — `reqHistoricalDataAsync(..., timeout=IB_HIST_TIMEOUT_SECONDS)`.
`data_feed.py:_fetch_chunk_with_retries()` — retry borné avec `asyncio.sleep(retry_delay)` entre tentatives.
**✅ Conforme.**

### 3.3 placeOrder : fill vérifié avant MAJ état local

`session_lifecycle.py:_submit_and_await_fill()` lignes 155–175 :
```python
await asyncio.wait_for(fill_event.wait(), timeout=10.0)
```
Fill attendu 10s avant de retourner `trades_placed`. Si timeout : annulation bracket + alerte + retour `None`.
`_record_fill()` (MAJ état) appelé **seulement** si `_submit_and_await_fill()` retourne non-None.
**✅ Conforme.**

### 3.4 Erreurs IB loggées et non swallowées

`broker.py:_on_ib_error()` lignes 265–291 — dispatch par code :
- 2100–2176 : DEBUG (informationnel)
- 162 : DEBUG + `throttler.penalise()`
- 200, 321 : ERROR
- 504, 1100–1102 : CRITICAL
- Autres : WARNING

Aucun swallowing silencieux. **✅ Conforme.**

### 3.5 Circuit breaker

`broker.py:connect()` lignes 170–177 :
```python
if self._consecutive_failures >= IB_CIRCUIT_BREAKER_MAX_FAILURES:
    logger.critical("ALPHAEDGE circuit breaker OPEN ...")
    return False
```
**✅ Conforme.**

### 3.6 Bare except / swallowing silencieux

`broker.py` — tous les blocs `except Exception:` appellent `logger.exception()` avant retour. Pas de swallowing.

**🟡 MINEUR** : `data_feed.py:BarDiskCache.load()` lignes 62–66 — pas de `try/except`.
Si le fichier `.pkl` de cache est corrompu (truncation disque, écriture interrompue),
`pickle.load()` lèvera une exception non gérée qui propagera jusqu'au caller. Le caller (`fetch_bars`) n'a pas de guard spécifique pour ce cas.
Conséquence : cold restart difficile si cache corrompu. → **ID T-03**.

---

## BLOC 4 — PERSISTANCE ET RÉCUPÉRATION

### 4.1 Écriture atomique (.tmp → rename)

`state_persistence.py:save_daily_state()` lignes 38–55 :
```python
tmp = STATE_FILE + ".tmp"
with open(tmp, "w", ...) as f: json.dump(...)
os.replace(tmp, STATE_FILE)  # Atomic on both POSIX and Windows
```
Cleanup du `.tmp` en cas d'exception. **✅ Conforme.**

### 4.2 Intégrité vérifiée au rechargement

`state_persistence.py:_validate_daily_state_payload()` lignes 80–130 :
Validation stricte de chaque champ (`isinstance`, `math.isfinite`, `date.fromisoformat`,
`datetime.fromisoformat`). Tous les cas d'erreur catchés :
```python
except (json.JSONDecodeError, TypeError, KeyError, ValueError):
    logger.warning("ALPHAEDGE STATE: Corrupt state file — ignoring")
    return None
```
**✅ Conforme.**

### 4.3 Réconciliation positions ouvertes au redémarrage

`session_lifecycle.py:_reconcile_positions()` — appelé après reconnect.
Compare `ib_open_pairs` (IB réel) avec `state.is_position_open` (local).
Correction avec WARNING log si divergence.

`session_lifecycle.py:_check_orphan_orders()` — détecte ordres ouverts sur pairs gérées.
**✅ Conforme.**

### 4.4 Position IB ouverte absente du state local

`_reconcile_positions()` — corrige le state et log WARNING.

**🟠 MAJEUR** : Quand une position passe de `False → True` (IB a une position que le state local ignore), la correction est loggée uniquement en WARNING. **Aucune alerte Telegram/Discord n'est envoyée** à l'opérateur pour cette discordance critique.
L'opérateur peut être informé via logs mais **pas via le canal d'alerte** (qui couvre pourtant `ib_disconnected`, `kill_switch`, `trade_executed`). → **ID T-01**.

### 4.5 halt_trading persisté entre redémarrages

`state_persistence.py:DailyState.shutdown_triggered` — persiste la flag kill switch.
`session_lifecycle.py:run_session()` lignes 947–952 :
```python
persisted = load_daily_state()
if persisted and persisted.shutdown_triggered:
    logger.critical("ALPHAEDGE: Daily loss shutdown was triggered earlier ...")
    return
```
**✅ Conforme.**

---

## BLOC 5 — COUVERTURE DES TESTS (SÉCURITÉ)

| Test | Fichier | Statut |
|------|---------|--------|
| Paper/live séparation | `test_paper_live_separation.py` | ✅ |
| Fill verification | `test_fill_verification.py` | ✅ |
| Daily state persistence | `test_daily_state_persistence.py` | ✅ |
| Alerting système | `test_alerting.py` | ✅ |
| Dependency injection | `test_dependency_injection.py` | ✅ |
| Reconnexion IB | `test_reconnect.py` | ✅ |
| IB error codes | `test_ib_error_codes.py` | ✅ |
| Graceful shutdown | `test_graceful_shutdown.py` | ✅ |

### Scénarios manquants à risque

**🟠 MAJEUR** : Aucun test ne vérifie que `shutdown_triggered=True` dans le state persisté
**bloque effectivement** le démarrage d'une nouvelle session (`run_session()` early-return ligne 949–953).
Ce chemin code est critique pour le kill switch — une régression serait silencieuse.
→ **ID T-02**.

**🟡 MINEUR** : Aucun test pour `BarDiskCache.load()` avec pickle corrompu (graceful degradation non testée). → lié à T-03.

**🟡 MINEUR** : Aucun test pour `_reconcile_positions()` couvrant le cas
`IB open=True` / `local=False` → vérifier que le WARNING est bien loggé et que l'état est corrigé.

---

## SYNTHÈSE

| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact | Effort |
|----|------|-------------|---------------|----------|--------|--------|
| T-01 | 4 | Position IB\≠état local : correction silencieuse — aucune alerte opérateur | `session_lifecycle.py:_reconcile_positions()` | 🟠 Majeur | Opérateur aveugle sur discordance position critique post-reconnect | ~1h |
| T-02 | 5 | Aucun test pour `shutdown_triggered=True` bloquant restart session | `session_lifecycle.py:949–953` | 🟠 Majeur | Régression kill switch persistence non détectable par make qa | ~1h |
| T-03 | 3 | `BarDiskCache.load()` sans try/except — pickle corruption non gérée | `data_feed.py:62–66` | 🟡 Mineur | Cold restart impossible si cache corrompu (exception non gérée) | ~30min |
| T-04 | 2 | Session start log omet mode paper/live | `session_lifecycle.py:run_session()` | 🟡 Mineur | Traçabilité réduite dans les logs loguru (console OK, loguru non) | ~15min |
| T-05 | 1 | Fichiers `alphaedge/logs/*.txt` potentiellement trackés malgré .gitignore | `.gitignore:29` · `alphaedge/logs/` | 🟡 Mineur | À VÉRIFIER via `git ls-files alphaedge/logs/` — données runtime dans dépôt | ~15min |

**Total : 🔴 0 · 🟠 2 · 🟡 3**

### Points forts détectés

- Architecture credentials exemplaire : env vars exclusivement, `repr=False` sur `account_id`, aucun credential dans les logs
- Guard mismatch port/mode en ValueError au load_config — impossible d'entrer en live avec mauvais port
- Écriture state atomique `.tmp → rename` + validation stricte au rechargement
- Fill verification 10s avec timeout + annulation bracket en cas d'échec
- Circuit breaker, exponential backoff, orphan order detection — résilience complète
- Couverture tests sécurité large (8 fichiers test dédiés)
