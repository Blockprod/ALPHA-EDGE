---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/fix_errors/FINAL_QA_result.md
derniere_revision: 2026-03-26
creation: 2026-03-26 à 00:00
---

#codebase

Tu es un Release Manager ALPHAEDGE. Tu valides la readiness complète
du système avant merge / déploiement.

─────────────────────────────────────────────
INPUT
─────────────────────────────────────────────
Lire tasks/audits/fix_errors/VERIFY_result.md.
Si VERDICT GLOBAL = FAIL → arrêter immédiatement et indiquer
"❌ FINAL QA bloqué — relancer P3 + P4 d'abord".

─────────────────────────────────────────────
CHECKLIST ALPHAEDGE (10 points)
─────────────────────────────────────────────

1. Qualité statique (depuis VERIFY_result.md)
  - [ ] ruff : 0 violation
  - [ ] ARG  : 0 violation
  - [ ] pyright : 0 erreur dans les 5 dossiers

2. Tests
  - [ ] pytest alphaedge/tests/ -q → >= 610 passed, 0 failed, 0 error
  - [ ] DeprecationWarning check
        .venv\Scripts\python.exe -m pytest alphaedge/tests/ -W error::DeprecationWarning -q --tb=no 2>&1 | Select-Object -Last 3

3. Garde paper/live
  - [ ] ALPHAEDGE_PAPER=true dans l'ENV (jamais false en default)
        .venv\Scripts\python.exe -c "import os; print(os.getenv('ALPHAEDGE_PAPER', 'true'))"
  - [ ] _apply_cli_mode('live') bloqué si ENV=true
        .venv\Scripts\python.exe -m pytest alphaedge/tests/test_paper_live_separation.py -q --tb=short

4. Modules Cython
  - [ ] order_manager importable
        .venv\Scripts\python.exe -c "from alphaedge.core import order_manager; print('order_manager OK')"
  - [ ] risk_manager importable
        .venv\Scripts\python.exe -c "from alphaedge.core import risk_manager; print('risk_manager OK')"
  - [ ] momentum_detector importable
        .venv\Scripts\python.exe -c "from alphaedge.core import momentum_detector; print('momentum_detector OK')"

5. Pipeline critique — smoke test
  - [ ] Imports de tous les modules productifs sans erreur
        .venv\Scripts\python.exe -c "
        from alphaedge.config.loader import load_config
        from alphaedge.engine.strategy import AlphaEdgeStrategy
        from alphaedge.engine.signal_pipeline import SignalPipeline
        from alphaedge.engine.session_lifecycle import SessionLifecycle
        print('Pipeline imports OK')
        "

6. Interdictions ALPHAEDGE — vérification grep
  - [ ] Aucun # type: ignore
        $hits = (Select-String -Path "alphaedge\**\*.py" -Pattern "# type: ignore" -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.Path -notmatch "__pycache__" })
        if ($hits) { Write-Host "FAIL type:ignore : $($hits.Count)" } else { Write-Host "OK 0 type:ignore" }

  - [ ] Aucun datetime.utcnow()
        .venv\Scripts\python.exe -m ruff check alphaedge/ --select DTZ003 2>&1 | Select-Object -Last 3

  - [ ] Aucun print() hors tests/scripts
        $printhits = (Select-String -Path "alphaedge\**\*.py" -Pattern "^\s*print\(" -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.Path -notmatch "tests|__pycache__" })
        if ($printhits) { Write-Host "FAIL print() : $($printhits.Count)" } else { Write-Host "OK 0 print()" }

7. CI
  - [ ] .github/workflows/ci.yml présent et syntaxe YAML valide
        Test-Path ".github\workflows\ci.yml"

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Créer tasks/audits/fix_errors/FINAL_QA_result.md avec :

  FINAL_QA_ALPHAEDGE:

    QUALITÉ STATIQUE :
      ruff          : ✅ / ❌
      ARG           : ✅ / ❌
      pyright       : ✅ / ❌

    TESTS :
      pytest        : ✅ N passed / ❌ N failed
      DeprecWarning : ✅ / ❌

    SÉCURITÉ :
      paper_guard   : ✅ true / ❌ FAIL
      cli_guard     : ✅ / ❌

    CYTHON :
      order_manager     : ✅ / ❌
      risk_manager      : ✅ / ❌
      momentum_detector : ✅ / ❌

    PIPELINE :
      imports       : ✅ / ❌

    INTERDICTIONS :
      type:ignore   : ✅ 0 / ❌ N hits
      utcnow        : ✅ 0 / ❌ N hits
      print         : ✅ 0 / ❌ N hits

    INFRA :
      ci.yml        : ✅ / ❌

  SYSTÈME : READY ✅ / NOT READY ❌

  BLOCKERS RESTANTS:
    - [description] ou "aucun"

  ACTIONS REQUISES AVANT MERGE:
    - [action] ou "aucune"

Confirmer dans le chat :
"✅ FINAL QA ALPHAEDGE : READY — N/10 checks passés"
ou
"❌ FINAL QA ALPHAEDGE : NOT READY — blockers : [liste courte]"
