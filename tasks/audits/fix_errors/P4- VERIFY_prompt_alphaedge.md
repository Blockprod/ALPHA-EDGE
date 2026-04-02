---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/fix_errors/VERIFY_result.md
derniere_revision: 2026-03-26
creation: 2026-03-26 à 00:00
---

#codebase

Tu es un QA Engineer indépendant. Tu valides UNIQUEMENT — tu ne corriges rien.
Vérification complète post-correction ALPHAEDGE.

─────────────────────────────────────────────
RAISONNEMENT
─────────────────────────────────────────────
Lance chaque commande, capture le résultat COMPLET,
puis formule un verdict binaire par catégorie.

─────────────────────────────────────────────
ACTIONS (dans cet ordre exact)
─────────────────────────────────────────────

  # 1. Ruff global
  .venv\Scripts\python.exe -m ruff check alphaedge/ 2>&1 | Select-Object -Last 5

  # 2. Ruff ARG
  .venv\Scripts\python.exe -m ruff check alphaedge/ --select ARG 2>&1 | Select-Object -Last 5

  # 3. Pyright par dossier — mêmes 5 répertoires que P1
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
    if ($e -and $e -ne "0") { Write-Host "❌ $d : $e erreur(s)" }
    else { Write-Host "✅ $d" }
  }

  # 4. Suite de tests complète
  .venv\Scripts\python.exe -m pytest alphaedge/tests/ -q --tb=no 2>&1 | Select-Object -Last 5

  # 5. Vérification config ALPHAEDGE_PAPER
  .venv\Scripts\python.exe -c "
  import os
  paper = os.getenv('ALPHAEDGE_PAPER', 'true')
  assert paper.lower() == 'true', f'ALPHAEDGE_PAPER={paper} (expected true)'
  print('ALPHAEDGE_PAPER OK:', paper)
  "

  # 6. Import config smoke test
  .venv\Scripts\python.exe -c "
  from alphaedge.config.loader import load_config
  cfg = load_config()
  print('config OK — pairs:', cfg.trading.pairs)
  "

─────────────────────────────────────────────
SEUIL DE RÉUSSITE
─────────────────────────────────────────────
  Catégorie      | Seuil PASS
  ruff           | 0 violation
  ARG            | 0 violation
  pyright        | 0 erreur dans chaque dossier
  pytest         | >= 610 passed, 0 failed
  paper_guard    | ALPHAEDGE_PAPER = true
  config_import  | load_config() sans exception

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Créer tasks/audits/fix_errors/VERIFY_result.md avec :

  VERIFY_STATUS:
    ruff         : ✅ OK / ❌ FAIL (X violations)
    ARG          : ✅ OK / ❌ FAIL (X violations)
    pyright      : ✅ OK / ❌ FAIL — dossiers KO : [...]
    tests        : ✅ OK (N passed) / ❌ FAIL (N failed)
    paper_guard  : ✅ OK / ❌ FAIL
    config       : ✅ OK / ❌ FAIL

  VERDICT GLOBAL : PASS ✅ / FAIL ❌
  BLOCKERS RESTANTS:
    - [fichier:ligne — description] ou "aucun"

Confirmer dans le chat :
"✅ VERIFY terminé · ruff OK · pyright OK · N tests pass"
ou
"❌ VERIFY : X blockers — relancer P3 batch Y"
