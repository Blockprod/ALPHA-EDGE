---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: PLAN_ACTION_audit_technical_alphaedge_2026-03-25.md
derniere_revision: 2026-03-25
creation: 2026-03-25
---

# PLAN D'ACTION — ALPHAEDGE — 2026-03-25
Sources : `tasks/audits/resultats/audit_technical_alphaedge.md`
Total : 🔴 0 · 🟠 2 · 🟡 3 · Effort estimé : ~4h

---

## PHASE 1 — CRITIQUES 🔴

_Aucune correction critique._

---

## PHASE 2 — MAJEURES 🟠

### [C-01] Alerte opérateur sur discordance position IB ≠ état local

Fichier : `alphaedge/engine/session_lifecycle.py:_reconcile_positions()`
Problème : Quand `_reconcile_positions()` détecte une position IB ouverte absente du
state local (ou inversement), elle corrige le flag et log un WARNING — mais **aucune
alerte Telegram/Discord n'est envoyée**. Le canal d'alerte couvre déjà `ib_disconnected`,
`kill_switch`, `trade_executed`. Cette discordance critique (position fantôme, state
divergent) passe silencieusement si l'opérateur ne consulte pas les logs.
Correction :
  1. Lire `session_lifecycle.py:_reconcile_positions()` en entier.
  2. Après chaque bloc `logger.warning(f"ALPHAEDGE RECONCILE: {pair} position state corrected...")`,
     ajouter un envoi d'alerte `AlertEvent.TRADE_EXECUTED` (niveau WARNING) via
     `asyncio.ensure_future(self._s._alert_manager.send_async(Alert(...)))`.
  3. Utiliser le niveau `AlertLevel.WARNING` et un titre explicite, par exemple :
     `f"⚠️ Position discordance rekoncilée — {pair}: {was_open} → {is_open}"`
  4. Ajouter `.add_done_callback(self._on_task_done)` pour la tâche fire-and-forget.
  5. Importer `Alert`, `AlertEvent`, `AlertLevel` si pas déjà présents dans le bloc
     d'imports de `session_lifecycle.py`.
  6. Vérifier que les imports existants couvrent ces symboles — ils sont déjà présents
     (lignes 36–48 de `session_lifecycle.py`).

Validation :
  ```powershell
  python -m pytest alphaedge/tests/ -x -q
  # Attendu : tous tests passent · 0 ruff · 0 pyright
  # Aucun fichier .pyx modifié — make build NON requis
  ```
Dépend de : Aucune
Statut : ⏳

---

### [C-02] Test couvrant shutdown_triggered=True bloquant le restart

Fichier : `alphaedge/engine/session_lifecycle.py:949–953` · `alphaedge/tests/` (nouveau fichier)
Problème : `run_session()` contient un guard critique :
  ```python
  persisted = load_daily_state()
  if persisted and persisted.shutdown_triggered:
      logger.critical("ALPHAEDGE: Daily loss shutdown was triggered ...")
      return
  ```
Ce chemin est le kill switch persisté. Aucun test ne le couvre — une régression serait
indétectable par `make qa`. Le test `test_graceful_shutdown.py` existant ne vérifie
pas le redémarrage bloqué.
Correction :
  1. Créer `alphaedge/tests/test_session_restart_blocked.py`.
  2. Pattern : nommer conforme à la convention `test_<module>_<scenario>.py`.
  3. Scénarios minimum (2 tests) :
     - **`test_shutdown_triggered_blocks_restart`** : sauvegarder un `DailyState(shutdown_triggered=True)`
       via `save_daily_state()`, puis appeler `strategy._lifecycle.run_session()` avec le broker
       patché (`connect()` qui réussit) — vérifier que `run_session()` retourne immédiatement
       sans appeler `connect()`.
     - **`test_shutdown_not_triggered_allows_restart`** : même setup avec
       `DailyState(shutdown_triggered=False)` — vérifier que `connect()` est bien appelé.
  4. Utiliser `tmp_path` et `monkeypatch` pour isoler le fichier de state.
  5. Pattern de patching identique à `test_daily_state_persistence.py`.

Validation :
  ```powershell
  python -m pytest alphaedge/tests/test_session_restart_blocked.py -v
  python -m pytest alphaedge/tests/ -x -q
  # Attendu : nouveau test vert · tous tests passent · 0 ruff · 0 pyright
  # Aucun fichier .pyx modifié — make build NON requis
  ```
Dépend de : Aucune
Statut : ⏳

---

## PHASE 3 — MINEURES 🟡

### [C-03] Gérer la corruption du cache pickle dans BarDiskCache.load()

Fichier : `alphaedge/engine/data_feed.py:62–66` (`BarDiskCache.load()`)
Problème : `pickle.load()` est appelé sans try/except. Si le fichier `.pkl` de cache
est corrompu (troncature disque, écriture interrompue, downgrade Python), l'exception
non gérée propage jusqu'au caller `fetch_bars()` et provoque un cold restart impossible.
Correction :
  1. Entourer `pickle.load(fh)` d'un try/except dans `BarDiskCache.load()` :
     ```python
     try:
         return pickle.load(fh)  # nosec B301
     except Exception:
         logger.warning(
             "ALPHAEDGE cache: corrupt cache file for %s — purging",
             p,
         )
         try:
             p.unlink()
         except OSError:
             pass
         return None
     ```
  2. Importer `get_logger` si pas déjà fait (déjà présent dans `data_feed.py`).
  3. Le `return None` déclenche un cold fetch — comportement gracieux.

Validation :
  ```powershell
  python -m ruff check alphaedge/engine/data_feed.py
  python -m pyright alphaedge/engine/data_feed.py
  python -m pytest alphaedge/tests/ -x -q
  # Attendu : 0 ruff · 0 pyright · tous tests passent
  # Aucun fichier .pyx modifié — make build NON requis
  ```
Dépend de : Aucune
Statut : ⏳

---

### [C-04] Ajouter le mode paper/live dans le log session start (loguru)

Fichier : `alphaedge/engine/session_lifecycle.py:run_session()` (~ligne 946)
Problème : Le log loguru de démarrage de session est :
  ```python
  logger.info(f"ALPHAEDGE session starting at {format_dual_time(now_utc())}")
  ```
Il n'indique pas PAPER ou LIVE. Le `print()` console dans `strategy.py` l'indique, mais
loguru (fichier log) ne le capture pas. Si l'opérateur consulte les logs archivés, il
ne peut pas savoir en quel mode la session a tourné.
Correction :
  1. Modifier la ligne dans `run_session()` pour inclure le mode :
     ```python
     logger.info(
         "ALPHAEDGE session starting at %s | mode=%s",
         format_dual_time(now_utc()),
         "PAPER" if self._s._config.ib.is_paper else "LIVE",
     )
     ```
  2. Une seule ligne modifiée — aucun import supplémentaire requis.

Validation :
  ```powershell
  python -m ruff check alphaedge/engine/session_lifecycle.py
  python -m pyright alphaedge/engine/session_lifecycle.py
  python -m pytest alphaedge/tests/ -x -q
  # Attendu : 0 ruff · 0 pyright · tous tests passent
  # Aucun fichier .pyx modifié — make build NON requis
  ```
Dépend de : Aucune
Statut : ⏳

---

### [C-05] Vérifier les fichiers logs trackés par git

Fichier : `.gitignore:29` · `alphaedge/logs/`
Problème : La règle `.gitignore:29` (`alphaedge/logs/*.txt`) couvre les fichiers de logs,
mais si ces fichiers ont été committés avant l'ajout de la règle, git continue de les
tracker. Les fichiers `backtest_result.txt`, `bt_final.txt`, `bt_full.txt`, `bt_stderr.txt`,
`opt.txt` présents dans `alphaedge/logs/` sont des données runtime — ne doivent pas être
dans le dépôt.
Correction :
  1. **Vérifier** (non-destructif) :
     ```powershell
     git ls-files alphaedge/logs/
     ```
  2. Si des fichiers apparaissent (tracked), les désindexer sans les supprimer :
     ```powershell
     git rm --cached alphaedge/logs/*.txt
     git rm --cached alphaedge/logs/*.log
     ```
  3. Vérifier que `.gitignore` couvre aussi `alphaedge/logs/__init__.py` — ce fichier
     doit rester tracké (il initialise le module). La règle actuelle `alphaedge/logs/*.txt`
     ne le touche pas.
  4. Aucune modification de code source — opération git uniquement.

> ⚠️ Cette correction nécessite `git commit` pour prendre effet.
> Valider le contenu de `git diff --cached` avant de committer pour ne pas
> désindexer `alphaedge/logs/__init__.py` par erreur.

Validation :
  ```powershell
  git ls-files alphaedge/logs/
  # Attendu : seul __init__.py listé (ou liste vide si __init__.py aussi ignoré)
  ```
Dépend de : Aucune (opération hors code source)
Statut : ⏳

---

## SÉQUENCE D'EXÉCUTION

```
C-03 → BarDiskCache corruption (isolé, data_feed.py seul)
C-04 → Log session start (isolé, session_lifecycle.py 1 ligne)
C-05 → Vérification git ls-files (hors code, aucun risque)
C-01 → Alerte reconcile positions (session_lifecycle.py, alerte fire-and-forget)
C-02 → Test shutdown_triggered blocks restart (nouveau test)
```

> C-03, C-04, C-05 : indépendants, exécutables dans n'importe quel ordre.
> C-01 avant C-02 : le test C-02 peut valider indirectement le comportement post-C-01.
> Aucun fichier .pyx modifié dans ce plan — `make build` NON requis.

---

## CRITÈRES PASSAGE EN PRODUCTION

- [ ] Zéro 🔴 ouvert
- [ ] `make qa` : 100% pass (lint + mypy + pytest ≥80%)
- [ ] Zéro credential dans les logs loguru
- [ ] `ALPHAEDGE_PAPER=true` intact dans `.env.example`
- [ ] Bracket order `is_valid` vérifié avant envoi IB
- [ ] `check_daily_limit()` appelé chaque cycle
- [ ] Paper trading validé 5 sessions NYSE minimum

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier | Effort | Statut | Date |
|----|-------|----------|---------|--------|--------|------|
| C-01 | Alerte opérateur sur discordance position IB ≠ état local | 🟠 Majeur | `session_lifecycle.py:_reconcile_positions()` | ~1h | ✅ | 2026-03-25 |
| C-02 | Test couvrant shutdown_triggered bloquant restart | 🟠 Majeur | `tests/test_session_restart_blocked.py` (nouveau) | ~1h | ✅ | 2026-03-25 |
| C-03 | Gérer corruption cache pickle `BarDiskCache.load()` | 🟡 Mineur | `data_feed.py:62–66` | ~30min | ✅ | 2026-03-25 |
| C-04 | Mode paper/live dans log session start loguru | 🟡 Mineur | `session_lifecycle.py:run_session()` | ~15min | ✅ | 2026-03-25 |
| C-05 | Vérifier fichiers logs trackés par git | 🟡 Mineur | `.gitignore:29` · `alphaedge/logs/` | ~15min | ✅ | 2026-03-25 |
