# /fix — Pipeline de correction d'erreurs P1 → P5

Exécute le pipeline complet de correction des erreurs Ruff / Mypy / Pytest.

## Étapes

### P1 — SCAN
Lire et exécuter : `tasks/audits/fix_errors/P1- SCAN_prompt_alphaedge.md`
- Scanner `alphaedge/config/`, `utils/`, `core/`, `engine/`, `tests/`
- Lister toutes les erreurs groupées par type et sévérité

### P2 — PLAN
Lire et exécuter : `tasks/audits/fix_errors/P2- PLAN_prompt_alphaedge.md`
- Ordre de correction : `config → utils → core → engine → tests`
- Regrouper les corrections par fichier pour minimize les passes QA

### P3 — FIX
Lire et exécuter : `tasks/audits/fix_errors/P3- FIX_core_prompt_alphaedge.md`
- Appliquer les corrections dans l'ordre défini au P2
- Après chaque fichier modifié : exécuter `make qa`
- Si QA fail > 2 itérations sur un fichier → STOP + re-plan

### P4 — VERIFY
Lire et exécuter : `tasks/audits/fix_errors/P4- VERIFY_prompt_alphaedge.md`
- Vérifier que chaque correction est complète
- Confirmer : 610+ tests · 0 Ruff · 0 Mypy

### P5 — FINAL QA
Lire et exécuter : `tasks/audits/fix_errors/P5- FINAL QA_prompt_alphaedge.md`
- Run final `make qa` complet
- Vérifier que `ALPHAEDGE_PAPER=true` est intact
- Confirmer le résumé final

## Règles absolues
- Jamais `# type: ignore` — trouver la vraie cause
- Jamais `Any` comme type — utiliser union ou Protocol
- Jamais hardcoder pip/RR/sessions hors `alphaedge/config/constants.py`
