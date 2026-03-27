---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/fix_errors/BATCH_result.md
derniere_revision: 2026-03-26
creation: 2026-03-26 à 00:00
---

#codebase

Tu es un Senior Python Engineer spécialisé typage statique / Cython.
Tu corriges UN seul batch du plan ALPHAEDGE.

─────────────────────────────────────────────
INPUT
─────────────────────────────────────────────
Lire tasks/audits/fix_errors/PLAN_result.md.
Traiter le batch demandé (précisé par l'utilisateur ou batch 1 par défaut).

─────────────────────────────────────────────
PROTOCOLE DE CORRECTION — 5 ÉTAPES
─────────────────────────────────────────────

ÉTAPE A — LIRE avant d'écrire
Pour chaque fichier du batch :
1. Lire les lignes d'erreur exactes (pyright output de P1)
2. Lire le fichier autour de chaque ligne (+/- 15 lignes)
3. Identifier la cause racine (pas le symptôme)

ÉTAPE B — APPLIQUER les patterns ALPHAEDGE

CATALOGUE DE FIXES OBLIGATOIRES :

  # ── Typing : Optional non narrowed ──────────────────────────
  # ❌  def f(x: int | None) -> int: return x + 1
  # ✅  def f(x: int | None) -> int:
  #        assert x is not None
  #        return x + 1

  # ── Typing : dict retour non typé ────────────────────────────
  # ❌  def result() -> dict[str, Any]: ...
  # ✅  Créer un TypedDict ou utiliser un dataclass existant

  # ── Typing : cast pour retour ambigu ─────────────────────────
  # ❌  ts = some_call()   # retourne X | Y
  # ✅  from typing import cast
  #    ts = cast(ExpectedType, some_call())

  # ── ARG004 : paramètre static non utilisé ────────────────────
  # ❌  def compute(self, a, b):  # b ignoré
  # ✅  inclure b dans le calcul ou supprimer si inutile

IMPORT À AJOUTER si absent :
  from typing import cast   # toujours en haut du bloc imports typing

ÉTAPE C — CONTRAINTES ABSOLUES ALPHAEDGE

  ❌ INTERDIT — jamais écrire ces lignes :
     # type: ignore
     Any  (comme raccourci de type — utiliser union explicite ou protocol)
     datetime.utcnow()          → utiliser datetime.now(timezone.utc)

     EUR_USD_RATE hardcodé      → utiliser config.trading.eur_usd_rate
     pip / RR / session_time hardcodés → utiliser alphaedge/config/constants.py
     import circulaire engine → core   → refactorer via injection

RÈGLE CYTHON :
Si une erreur vient d'un appel à order_manager, risk_manager ou
momentum_detector : vérifier en premier la signature dans le .pyx
correspondant ET le stub dans alphaedge/core/_stubs/.
Ne pas modifier le .pyx sans recompiler avec :
  .venv\Scripts\python.exe setup.py build_ext --inplace
Après recompilation : make qa (obligatoire).

ÉTAPE D — VÉRIFICATION PAR FICHIER (max 3 itérations)

Après chaque fichier corrigé :
  # Pyright sur le seul fichier modifié
  .venv\Scripts\python.exe -m pyright alphaedge/chemin/fichier.py 2>&1 | Select-Object -Last 3

  # Ruff sur le seul fichier
  .venv\Scripts\python.exe -m ruff check alphaedge/chemin/fichier.py 2>&1 | Select-Object -Last 3

Si encore des erreurs après itération 3 → marquer BLOCKER
et passer au fichier suivant sans s'acharner.

ÉTAPE E — VÉRIFICATION BATCH COMPLÈTE

Quand tous les fichiers du batch sont traités :
  .venv\Scripts\python.exe -m pytest alphaedge/tests/ -q --tb=no 2>&1 | Select-Object -Last 3

─────────────────────────────────────────────
STOP RULE
─────────────────────────────────────────────
- Max 3 itérations par fichier
- Max 20 fichiers par batch
- Si le fix d'un fichier crée de nouvelles erreurs dans un autre :
  noter comme BLOCKER, ne pas cascader indéfiniment

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Mettre à jour tasks/audits/fix_errors/BATCH_result.md avec :

  BATCH_RESULT:
    batch           : N
    fixed_files     : X
    remaining_errors: Y
    blockers        : ["fichier:ligne — raison"]
    tests           : X passed / Y failed

Confirmer dans le chat :
"✅ Batch N terminé · X fixes · Y erreurs restantes · Z tests pass"
