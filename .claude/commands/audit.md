# /audit — Pipeline complet A → B → C

Lance le pipeline d'audit AlphaEdge en 3 étapes.

## Prérequis
Lire le skill complet avant de commencer :
`.github/skills/audit-workflow/SKILL.md`

## Étape A — Audit
1. Demande le type d'audit (structural / technique / best-practices / pipeline / autre)
2. Charge ou génère le prompt d'audit correspondant depuis `tasks/audits/code/`
3. Exécute l'audit sur le codebase
4. Crée le fichier résultat dans `tasks/audits/resultats/audit_<type>_alphaedge.md`

## Étape B — Plan d'action
1. Lit le résultat d'audit
2. Génère `tasks/corrections/plans/PLAN_ACTION_audit_<type>_alphaedge_<date>.md`
3. Structure : 🔴 → 🟠 → 🟡 · séquence d'exécution · estimation effort

## Étape C — Exécution
1. Charge `tasks/corrections/execute_corrections_prompt.md`
2. Exécute les corrections séquentiellement (🔴 → 🟠 → 🟡)
3. Valide avec `make qa` après chaque correction `.py`
4. Coche ✅ dans le plan après chaque correction validée

## Règles
- Ne jamais modifier `core/*.pyx` sans instruction explicite
- `make qa` doit passer (610+ tests · 0 Ruff) avant de passer à la correction suivante
- Mettre à jour `tasks/WORKFLOW.md` à la fin de l'étape B
