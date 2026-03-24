---
type: plan_action
audit_source: tasks/audits/resultats/audit_best_practices_alphaedge.md
date: 2026-03-24
statut: ✅ TERMINÉ
---

# PLAN D'ACTION — ALPHAEDGE — 2026-03-24
**Sources :** `audit_best_practices_alphaedge.md` (2026-03-24)
**Total :** 🔴 1 · 🟠 2 · 🟡 2 · **Effort estimé : 2 jours**
**Périmètre :** Fichiers de contexte AI-Driven uniquement — aucun fichier `.pyx` / code source touché

---

## PHASE 1 — CRITIQUES 🔴

### [C-01] Réduire CLAUDE.md de 386 à ≤ 200 lignes

**Fichier :** `CLAUDE.md` (386 lignes)
**Problème :** À 386 lignes, CLAUDE.md dépasse le seuil recommandé de 200 lignes.
Au-delà de cette limite, Claude ignore des règles même marquées MUST/NEVER.
Sections verbosas actuelles : interfaces Cython publiques complètes (≈80 l.),
tableau de responsabilité des modules (≈30 l.), QA commands dupliqués (≈20 l.),
return value contracts complets (≈30 l.).
**Correction :**
  1. Extraire les interfaces Cython publiques → `docs/ALPHAEDGE_INTERFACES.md`
     (signatures de fonctions + return contracts — déjà présentes dans CLAUDE.md:250–340)
  2. Extraire le tableau des modules (Module / Language / Role) → `architecture/module_responsibilities.md`
  3. Dans CLAUDE.md, remplacer chaque bloc extrait par une référence courte :
     `> Interfaces détaillées : docs/ALPHAEDGE_INTERFACES.md`
     `> Modules : architecture/module_responsibilities.md`
  4. Supprimer ou condenser la section "QA Workflow" complète (couverte par copilot-instructions.md — voir C-02)
  5. Vérifier que CLAUDE.md conserve : startup checklist · hard stops · workflow orchestration · core principles
  **Cible : CLAUDE.md ≤ 200 lignes**

**Validation :**
```powershell
(Get-Content "CLAUDE.md").Count
# Attendu : ≤ 200
# Vérifier manuellement que les 10 hard stops sont toujours présents
# make qa non requis (fichiers .md uniquement — aucun code modifié)
```
**Dépend de :** Aucune
**Statut :** ⏳

---

## PHASE 2 — MAJEURES 🟠

### [C-02] Dédupliquer CLAUDE.md / copilot-instructions.md

**Fichier :** `CLAUDE.md` · `.github/copilot-instructions.md`
**Problème :** Les deux fichiers dupliquent : pipeline architecture (ASCII diagram),
hard stops (10 règles), règles Python 3.11, return value contracts, commandes QA.
Doublon = maintenance double + risque de désynchronisation + contexte consommé deux fois.
**Correction :**
  1. Conserver `copilot-instructions.md` intact (chargé automatiquement par GitHub Copilot — source canonique des règles)
  2. Dans `CLAUDE.md`, remplacer les sections dupliquées par :
     ```
     > Règles complètes Copilot : .github/copilot-instructions.md
     ```
  3. Sections à retirer de CLAUDE.md si déjà dans copilot-instructions.md :
     - ASCII architecture diagram
     - Tableau "Module Responsibilities"
     - Return Value Contracts complets
     - QA commands block
     - Absolute Rules (garder uniquement un lien + les 3 règles non présentes dans copilot-instructions.md)
  4. Ne retirer de CLAUDE.md que ce qui est identiquement présent dans copilot-instructions.md — vérifier ligne par ligne avant suppression

**Validation :**
```powershell
(Get-Content "CLAUDE.md").Count
# Attendu : ≤ 200 (C-01 + C-02 combinés)
# Vérifier que .github/copilot-instructions.md est inchangé
```
**Dépend de :** C-01 (effectuer l'analyse de CLAUDE.md après extraction C-01)
**Statut :** ⏳

---

### [C-03] Créer 3 skills manquantes — run-qa, run-backtest, audit-workflow

**Fichier :** `.github/skills/run-qa/SKILL.md` (à créer)
              `.github/skills/run-backtest/SKILL.md` (à créer)
              `.github/skills/audit-workflow/SKILL.md` (à créer)
**Problème :** Seule la skill `cython-build` existe. Les workflows `make qa`, backtest,
et audit A→B→C sont exécutés quotidiennement sans skill dédiée — Copilot ne les
invoque pas automatiquement.
**Correction — pour chaque skill :**

**Skill `run-qa` :**
```yaml
name: run-qa
description: >
  Use when: running make qa, fixing lint/mypy/pytest errors, checking coverage threshold,
  or validating code after any change to alphaedge/ files.
```
  - Section `## Steps` : séquence make qa, lecture output, interprétation coverage
  - Section `## Common Errors` : erreurs ruff courantes, mypy strict, pytest markers manquants
  - Section `## Thresholds` : ≥80% coverage sur config/ · utils/ · core/ — engine/ exclu

**Skill `run-backtest` :**
```yaml
name: run-backtest
description: >
  Use when: launching a backtest, interpreting backtest results, diagnosing DST-related
  bias, adjusting warmup period, or exporting results to CSV.
```
  - Section `## Steps` : commande, paramètres, lecture des métriques clés
  - Section `## Common Errors` : warmup insuffisant, DST gap, biais look-ahead
  - Section `## Output` : fichiers produits (logs/, reports/)

**Skill `audit-workflow` :**
```yaml
name: audit-workflow
description: >
  Use when: launching any audit (structural, technical, best practices, etc.),
  generating an action plan from an audit result, or executing corrections.
```
  - Section `## Pipeline` : A (audit) → B (plan) → C (exécution)
  - Section `## Files` : référence vers tasks/WORKFLOW.md
  - Section `## Common Errors` : lancer B avant A complet, ne pas relire lessons.md

**Validation :**
```powershell
Test-Path ".github/skills/run-qa/SKILL.md"
Test-Path ".github/skills/run-backtest/SKILL.md"
Test-Path ".github/skills/audit-workflow/SKILL.md"
# Attendu : True × 3
# Vérifier que chaque SKILL.md a description rédigée comme trigger "Use when: …"
# make qa non requis
```
**Dépend de :** Aucune
**Statut :** ⏳

---

## PHASE 3 — MINEURES 🟡

### [C-04] Créer spec files par feature core

**Fichier :** `.github/specs/fcr-detection.md` (à créer)
              `.github/specs/risk-management.md` (à créer)
              `.github/specs/order-execution.md` (à créer)
              `.github/specs/backtest-engine.md` (à créer)
**Problème :** Aucun spec file par feature. Les interfaces core (fcr_detector, risk_manager,
order_manager) sont documentées uniquement dans CLAUDE.md sous forme de signatures.
Un spec file complet (comportement attendu + edge cases) permet à Copilot de valider
ses implémentations sans inventer les contrats.
**Correction :**
  - Créer `.github/specs/` (nouveau répertoire)
  - Pour chaque spec, extraire depuis CLAUDE.md + `alphaedge/core/_stubs/` :
    - Inputs / Outputs complets avec types
    - Comportements attendus (happy path)
    - Edge cases et comportements de rejet
    - Return value contracts (déjà présents dans CLAUDE.md — à déplacer ici)
  - Référencer dans copilot-instructions.md : `> Specs features : .github/specs/`

**Validation :**
```powershell
Test-Path ".github/specs/fcr-detection.md"
Test-Path ".github/specs/risk-management.md"
Test-Path ".github/specs/order-execution.md"
Test-Path ".github/specs/backtest-engine.md"
# Attendu : True × 4
# Vérifier que chaque spec contient : Inputs, Outputs, Edge Cases, Return Contracts
```
**Dépend de :** C-01, C-02 (les return contracts sont ensuite supprimés de CLAUDE.md et pointent vers les specs)
**Statut :** ⏳

---

### [C-05] Structure progressive dans la skill cython-build

**Fichier :** `.github/skills/cython-build/SKILL.md`
              `.github/skills/cython-build/examples/` (répertoire à créer)
              `.github/skills/cython-build/references/` (répertoire à créer)
**Problème :** La skill cython-build est un fichier plat. Quand les cas d'erreur augmentent,
elle va dépasser 100 lignes et noyer le signal principal.
**Correction :**
  1. Créer `.github/skills/cython-build/examples/add_field.md`
     → Exemple concret : ajouter un champ `cdef` dans un `.pyx` existant
  2. Créer `.github/skills/cython-build/examples/new_module.md`
     → Exemple concret : créer un nouveau module `.pyx` complet
  3. Créer `.github/skills/cython-build/references/cython_types.md`
     → Table de correspondance types Cython ↔ Python 3.11
  4. Dans SKILL.md principal, ajouter en fin de fichier :
     ```markdown
     ## Références et exemples
     - [Ajouter un champ](.github/skills/cython-build/examples/add_field.md)
     - [Nouveau module .pyx](.github/skills/cython-build/examples/new_module.md)
     - [Types Cython](.github/skills/cython-build/references/cython_types.md)
     ```
  5. Vérifier que SKILL.md reste ≤ 60 lignes après ajout des liens

**Validation :**
```powershell
Test-Path ".github/skills/cython-build/examples/add_field.md"
Test-Path ".github/skills/cython-build/examples/new_module.md"
Test-Path ".github/skills/cython-build/references/cython_types.md"
(Get-Content ".github/skills/cython-build/SKILL.md").Count
# Attendu : True × 3 + SKILL.md ≤ 60 lignes
```
**Dépend de :** Aucune
**Statut :** ⏳

---

## SÉQUENCE D'EXÉCUTION

```
C-01  →  C-02  →  C-04   (chaîne de déduplication CLAUDE.md)
C-03                       (indépendant — skills nouvelles)
C-05                       (indépendant — amélioration skill existante)
```

**Ordre recommandé :**
1. **C-01** — Extraire les blocs verbeux de CLAUDE.md vers docs/ et architecture/
2. **C-02** — Supprimer les doublons restants entre CLAUDE.md et copilot-instructions.md
3. **C-05** — Enrichir cython-build avec examples/ et references/ (XS, rapide)
4. **C-03** — Créer les 3 nouvelles skills
5. **C-04** — Créer les spec files (plus long, dépend de C-01/C-02 pour les return contracts)

> ⚠️ Aucun fichier `.pyx` n'est modifié dans ce plan — `make build` n'est pas requis.
> Ces corrections portent exclusivement sur des fichiers `.md` de contexte AI-Driven.

---

## CRITÈRES PASSAGE EN PRODUCTION

- [ ] `CLAUDE.md` ≤ 200 lignes
- [ ] Zéro doublon entre `CLAUDE.md` et `copilot-instructions.md` (vérification manuelle)
- [ ] 3 nouvelles skills créées avec description "Use when: …" et section Common Errors
- [ ] `cython-build` enrichi de `examples/` et `references/`
- [ ] 4 spec files créés dans `.github/specs/`
- [ ] `make qa` : 100% pass (lint + mypy + pytest ≥80%) — pour confirmer aucun impact code
- [ ] `ALPHAEDGE_PAPER=true` intact dans `.env.example`

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier | Effort | Statut | Date |
|----|-------|----------|---------|--------|--------|------|
| C-01 | Réduire CLAUDE.md ≤ 200 lignes | 🔴 | CLAUDE.md | S | ✅ | 2026-03-24 |
| C-02 | Dédupliquer CLAUDE.md / copilot-instructions | 🟠 | CLAUDE.md · copilot-instructions.md | S | ✅ | 2026-03-24 |
| C-03 | Créer 3 skills (run-qa, run-backtest, audit) | 🟠 | .github/skills/ | M | ✅ | 2026-03-24 |
| C-04 | Créer 4 spec files core | 🟡 | .github/specs/ | M | ✅ | 2026-03-24 |
| C-05 | Structure progressive cython-build skill | 🟡 | .github/skills/cython-build/ | XS | ✅ | 2026-03-24 |
