---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/fix_errors/PLAN_result.md
derniere_revision: 2026-03-26
creation: 2026-03-26 à 00:00
---

#codebase

Tu es un Software Architect spécialisé systèmes Python temps réel.
Tu crées un plan de correction OPTIMAL à partir du SCAN.

─────────────────────────────────────────────
INPUT
─────────────────────────────────────────────
Lire tasks/audits/fix_errors/SCAN_result.md (FILES_TO_FIX).

─────────────────────────────────────────────
RAISONNEMENT
─────────────────────────────────────────────
Ne modifie rien. Raisonne sur les dépendances et groupe
les fichiers de façon à minimiser le nombre d'itérations
de vérification inter-batch.

─────────────────────────────────────────────
RÈGLES DE PRIORITÉ ALPHAEDGE
─────────────────────────────────────────────
Batch 1 (fondations — dépendances de tous les autres) :
  alphaedge/config/

Batch 2 (utilitaires — importés par core et engine) :
  alphaedge/utils/

Batch 3 (Cython + stubs — pipeline cœur) :
  alphaedge/core/      ← order_manager, risk_manager, momentum_detector
  alphaedge/core/_stubs/

Batch 4 (orchestration live) :
  alphaedge/engine/

Batch 5+ (tests — grouper par module miroir) :
  alphaedge/tests/  →  test_<config>* → test_<utils>* → test_<core>* → test_<engine>*

─────────────────────────────────────────────
RÈGLES DE GROUPEMENT
─────────────────────────────────────────────
1. Max 20 fichiers par batch
2. Fichiers du même module = même batch
3. Si A importe B → B dans un batch antérieur
4. Erreurs Cython (order_manager.pyx, risk_manager.pyx) → toujours Batch 3
5. Ne jamais mélanger alphaedge/engine/ avec alphaedge/core/ dans le même batch

─────────────────────────────────────────────
CATALOGUE DE PATTERNS CONNUS ALPHAEDGE
─────────────────────────────────────────────
(pour qualifier la difficulté de chaque batch)

  Pattern                          | Fix                                   | Difficulté
  dict[str, Any] retourné          | Typer avec TypedDict ou dataclass     | Moyen
  int | None non narrowed          | assert x is not None / isinstance    | Facile
  ARG004 unused static param       | connecter au calcul ou supprimer      | Moyen
  Cython signature mismatch        | aligner .pyx ↔ _stubs/               | Complexe
  import circulaire engine→core    | injecter via paramètre ou protocol    | Complexe
  return type None vs TypedReturn  | corriger le contrat dans l'appelant   | Moyen

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Créer tasks/audits/fix_errors/PLAN_result.md avec :

  PLAN = [
    {
      batch: 1,
      module: "alphaedge/config/",
      files: ["alphaedge/config/loader.py", ...],
      error_types: ["typing"],
      estimated_fixes: N,
      difficulty: Facile | Moyen | Complexe
    },
    ...
  ]

  RÉSUMÉ:
    total_batches    : X
    total_files      : Y
    estimated_fixes  : Z
    ordre_validation : pytest alphaedge/tests/ → ruff → pyright par batch

─────────────────────────────────────────────
CONTRAINTES ABSOLUES
─────────────────────────────────────────────
- Aucune modification de code
- Si FILES_TO_FIX est vide → écrire "PLAN : rien à corriger ✅"
- Confirmer dans le chat : "✅ PLAN_result.md créé · X batches · Y fichiers"
