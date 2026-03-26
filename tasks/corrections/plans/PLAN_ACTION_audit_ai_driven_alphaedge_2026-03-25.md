---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: PLAN_ACTION_audit_ai_driven_alphaedge_2026-03-25.md
derniere_revision: 2026-03-25
creation: 2026-03-25 à 00:00
---

# PLAN D'ACTION — ALPHAEDGE — AI-Driven File Engineering — 2026-03-25

Sources : `tasks/audits/audit_ai_driven_alphaedge.md`
Total : 🔴 0 · 🟠 0 · 🟡 2 · Effort estimé : < 30 min

> **Note** : L'audit AI-Driven est de type "audit & restructuration" — toutes les corrections
> principales (mise à jour du compteur de tests 504→574, convention `DEFAULT_PIP_SIZE`,
> rebranding du rôle `quant_researcher`) ont été appliquées **inline** lors de l'audit.
> Ce plan capture les deux résidus non couverts par la passe automatique.

---

## PHASE 1 — CRITIQUES 🔴

*Aucune.*

---

## PHASE 2 — MAJEURES 🟠

*Aucune.*

---

## PHASE 3 — MINEURES 🟡

### [C-01] Déplacer le résultat d'audit vers `tasks/audits/resultats/`

Fichier : `tasks/audits/audit_ai_driven_alphaedge.md` → `tasks/audits/resultats/audit_ai_driven_alphaedge.md`
Problème : Le fichier résultat a été créé dans `tasks/audits/` alors que `WORKFLOW.md` section 2
  spécifie **Produit A** : `tasks/audits/resultats/audit_ai_driven_alphaedge.md`.
  Écart de convention par rapport aux autres audits (ex: `audit_structural_alphaedge.md`
  est également à la racine de `tasks/audits/` — mais `resultats/` contient
  `audit_migration_momentum_carry_alphaedge.md`).
  Impact : rupture de cohérence dans le pipeline A→B→C — l'étape B ne trouve pas
  l'audit au bon endroit lors d'une exécution future.
Correction :
  Déplacer le fichier :
    mv tasks/audits/audit_ai_driven_alphaedge.md tasks/audits/resultats/audit_ai_driven_alphaedge.md
  Vérifier qu'aucun fichier ne référence l'ancienne localisation.
Validation :
  Test-Path tasks/audits/resultats/audit_ai_driven_alphaedge.md  # doit retourner True
  Test-Path tasks/audits/audit_ai_driven_alphaedge.md            # doit retourner False
Dépend de : Aucune
Statut : ✅

---

### [C-02] Mettre à jour le titre de `WORKFLOW.md`

Fichier : `tasks/WORKFLOW.md:11`
Problème : La ligne 11 contient encore `# ALPHAEDGE — FCR Forex Trading Bot (IB Gateway)`.
  Toutes les occurrences de "FCR Forex Trading Bot" ont été mises à jour dans les fichiers
  `engine/`, `core/`, `config/`, mais le fichier guide du workflow lui-même n'a pas été mis à jour.
  La session courante a déjà rebrandé `constants.py`, `data_feed.py`, `broker.py`,
  `position_manager.py`, `core/__init__.py` (corrections C-10 de l'audit structural).
Correction :
  Remplacer la ligne 11 :
    # ALPHAEDGE — FCR Forex Trading Bot (IB Gateway)
  par :
    # ALPHAEDGE — Momentum+Carry Forex Trading Bot (IB Gateway)
Validation :
  grep "FCR Forex Trading Bot" tasks/WORKFLOW.md  # doit retourner aucun résultat
Dépend de : Aucune
Statut : ✅

---

## SÉQUENCE D'EXÉCUTION

```
C-01 → mv fichier audit  [indépendant, XS]
C-02 → éditer WORKFLOW.md  [indépendant, XS]
```

Les deux corrections sont indépendantes et peuvent être appliquées dans n'importe quel ordre.
**Aucun fichier `.pyx` touché → `make build` non requis.**

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

| ID | Titre | Sévérité | Fichier principal | Effort | Statut | Date |
|----|-------|----------|-------------------|--------|--------|------|
| C-01 | Déplacer résultat audit AI-Driven | 🟡 | `tasks/audits/audit_ai_driven_alphaedge.md` | XS (< 5min) | ✅ | 2026-03-25 |
| C-02 | Titre WORKFLOW.md FCR → Momentum+Carry | 🟡 | `tasks/WORKFLOW.md:11` | XS (< 5min) | ✅ | 2026-03-25 |
