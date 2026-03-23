---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/plans/PLAN_ACTION_[NOM_AUDIT]_[DATE].md
derniere_revision: 2026-03-20
---

#codebase

Je suis le chef de projet ALPHAEDGE.

Scanne le workspace, détecte tous les fichiers d'audit
disponibles (*.md contenant : critique, P0, 🔴,
NON CONFORME, fichier:ligne) et affiche-les numérotés.

Demande : "Quel(s) audit(s) utiliser ?
[TOUS] ou [1][2]..."

Puis génère dans `tasks/plans/` le fichier plan en nommant
le fichier d'après l'audit source (sans extension) :
  PLAN_ACTION_[NOM_AUDIT]_[DATE].md

Exemple : audit source = `audit_structural_alphaedge.md`
  → `tasks/plans/PLAN_ACTION_audit_structural_alphaedge_2026-03-20.md`

Exemple : audit source = `audit_master_alphaedge.md`
  → `tasks/plans/PLAN_ACTION_audit_master_alphaedge_2026-03-20.md`

─────────────────────────────────────────────
STRUCTURE OBLIGATOIRE DU FICHIER
─────────────────────────────────────────────
# PLAN D'ACTION — ALPHAEDGE — [DATE]
Sources : [audits utilisés]
Total : 🔴 X · 🟠 X · 🟡 X · Effort estimé : X jours

## PHASE 1 — CRITIQUES 🔴
## PHASE 2 — MAJEURES 🟠
## PHASE 3 — MINEURES 🟡

Pour chaque correction :
### [C-XX] Titre
Fichier : alphaedge/chemin/fichier.py:ligne
Problème : [description]
Correction : [ce qui doit être fait]
Validation :
  make qa
  # Attendu : [résultat attendu]
  # Si .pyx modifié : make build → make qa
Dépend de : [C-XX ou Aucune]
Statut : ⏳

## SÉQUENCE D'EXÉCUTION
[ordre tenant compte des dépendances]
[Toujours make build avant make qa si .pyx touché]

## CRITÈRES PASSAGE EN PRODUCTION
- [ ] Zéro 🔴 ouvert
- [ ] make qa : 100% pass (lint + mypy + pytest ≥80%)
- [ ] Zéro credential dans les logs loguru
- [ ] ALPHAEDGE_PAPER=true intact dans .env.example
- [ ] Bracket order is_valid vérifié avant envoi IB
- [ ] check_daily_limit() appelé chaque cycle
- [ ] Paper trading validé 5 sessions NYSE minimum

## TABLEAU DE SUIVI
| ID | Titre | Sévérité | Fichier | Effort | Statut | Date |

─────────────────────────────────────────────
RÈGLES
─────────────────────────────────────────────
- Ne modifier aucun fichier de code source
- Ne jamais modifier .env ou alphaedge/logs/
- Ne jamais modifier core/*.pyx sans noter
  "⚠️ make build requis après cette correction"
- Problème dans plusieurs audits = une seule entrée
- Effort inconnu → "À ESTIMER"
- Fichier compatible avec execute_corrections_prompt.md
- Nommer le fichier plan d'après l'audit source

Confirme dans le chat uniquement :
"✅ tasks/plans/PLAN_ACTION_[NOM_AUDIT]_[DATE].md créé
 🔴 X · 🟠 X · 🟡 X · Effort : X jours
 👉 Lance execute_corrections_prompt.md pour démarrer."
