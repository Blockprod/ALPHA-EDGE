---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/fix_errors/SCAN_result.md
derniere_revision: 2026-03-26
creation: 2026-03-26 à 00:00
---

#codebase

Tu es un code quality analyst spécialisé Python / pyright.
Tu réalises un SCAN COMPLET du projet ALPHAEDGE sans rien modifier.

─────────────────────────────────────────────
RAISONNEMENT
─────────────────────────────────────────────
Explore d'abord, ne corrige jamais. Chaque commande
doit être lancée et son résultat capturé avant de passer
à la suivante.

─────────────────────────────────────────────
ÉTAPE 1 — OUTILS STATIQUES
─────────────────────────────────────────────
Lancer dans l'ordre (terminal PowerShell, venv Python 3.11) :

  # 1. Ruff général
  .venv\Scripts\python.exe -m ruff check alphaedge/ 2>&1 | Select-Object -Last 10

  # 2. Ruff ARG (arguments inutilisés)
  .venv\Scripts\python.exe -m ruff check alphaedge/ --select ARG 2>&1 | Select-Object -Last 5

  # 3. Pyright — dossier par dossier (ordre priorité ALPHAEDGE)
  $dirs = @(
    "alphaedge\config",
    "alphaedge\utils",
    "alphaedge\core",
    "alphaedge\engine",
    "alphaedge\tests"
  )
  foreach ($d in $dirs) {
    $e = (.venv\Scripts\python.exe -m pyright $d 2>&1 |
          Select-String "(\d+) error").Matches[0].Groups[1].Value
    if ($e -and $e -ne "0") { Write-Host "$d : $e erreur(s)" }
  }
  Write-Host "--- scan terminé ---"

─────────────────────────────────────────────
ÉTAPE 2 — GET_ERRORS
─────────────────────────────────────────────
Utiliser l'outil get_errors (sans argument = tous les fichiers)
pour croiser avec les PROBLEMS de l'IDE.

─────────────────────────────────────────────
ÉTAPE 3 — CLASSIFICATION
─────────────────────────────────────────────
Pour chaque fichier en erreur, identifier le TYPE :

  ruff     → style/import (F401, E501, ARG001)
  ARG      → unused param (ARG002, ARG004)
  typing   → pyright annotation incorrecte (Union, Optional, dict[str, Any])
  cython   → signature pyx ≠ stub (_stubs/) pour order_manager, risk_manager, momentum_detector
  import   → import manquant / circulaire (engine/ → core/ uniquement)
  protocol → contrat retour violé (ex. detect_fcr → None vs FCRResult)

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Créer tasks/audits/fix_errors/SCAN_result.md avec :

  FILES_TO_FIX = [
    {
      file: "chemin/relatif.py",
      errors: ["typing", "ARG"],
      count: N,
      lines: [L1, L2, ...]   ← lignes pyright exactes
    },
    ...
  ]

  TOTAUX:
    ruff    : X violation(s)
    ARG     : X violation(s)
    pyright : X erreur(s) dans Y fichiers
    dossiers_propres: [liste...]

Confirmer dans le chat :
"✅ SCAN terminé · ruff X · pyright X erreurs dans Y fichiers"
