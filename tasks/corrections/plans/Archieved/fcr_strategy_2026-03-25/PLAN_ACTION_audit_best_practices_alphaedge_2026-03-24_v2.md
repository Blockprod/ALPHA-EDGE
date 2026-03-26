---
source: tasks/audits/resultats/audit_best_practices_alphaedge.md
version: v2 (4ème source — Anthropic API Docs)
date: 2026-03-24
statut: ✅ TERMINÉ
---

# PLAN D'ACTION — ALPHAEDGE BEST PRACTICES — 2026-03-24 v2
Sources : `audit_best_practices_alphaedge.md` (mis à jour — 4ème source : Anthropic API Docs Prompting best practices)
Total : 🔴 0 · 🟠 2 · 🟡 2 · Effort estimé : 0.5 jour

> Ce plan couvre uniquement les nouvelles corrections BP-06 à BP-09 issues de l'analyse
> de la 4ème source. Les corrections BP-01 à BP-05 sont traitées dans le plan v1 (✅ TERMINÉ).

---

## PHASE 2 — MAJEURES 🟠

### [C-01] Ajouter `<investigate_before_answering>` dans les agents et prompts d'audit

**Source BP :** BP-08
**Fichiers :**
- `agents/dev_engineer.md`
- `agents/code_auditor.md`
- `tasks/audits/methode/best practices_prompt.md`
- `tasks/audits/methode/audit_ai_driven_prompt.md`
- `tasks/audits/methode/audit_structural_prompt.md` (si applicable)

**Problème :** Plusieurs sessions ont produit des réponses sans lecture préalable des fichiers référencés (ex: "l'audit existe déjà" sans relire le prompt pour détecter une modification). Aucun fichier agent ne contient de garde explicite contre ce comportement.

**Correction :**
1. Dans `agents/dev_engineer.md` et `agents/code_auditor.md`, ajouter le bloc suivant dans la section des règles comportementales :
```xml
<investigate_before_answering>
Never speculate about code or files you have not opened. Read relevant files
before answering questions about the codebase. If the user references a prompt
or result file, read it first to detect any changes before assuming its current
state matches a previous version.
</investigate_before_answering>
```
2. Dans `tasks/audits/methode/best practices_prompt.md`, ajouter dans la MISSION : "Lis toujours le fichier prompt complet avant de vérifier si un audit existant est encore valide."
3. Appliquer le même ajout aux autres prompts d'audit si leur section MISSION est analogue.

**Validation :**
```
make qa
# Attendu : 100% pass — aucun fichier Python modifié, lint/mypy/pytest inchangés
```
**Dépend de :** Aucune
**Statut :** ⏳

---

### [C-02] Ajouter les WHY (motivations) aux Hard Stops dans copilot-instructions.md

**Source BP :** BP-09
**Fichier :** `.github/copilot-instructions.md` — section "Hard Stops — Never Do These"

**Problème :** Les Hard Stops donnent le QUOI sans le POURQUOI. Sans contexte, Claude peut considérer une situation comme "différente" et contourner la règle inconsciemment.

**Correction :** Enrichir les 7 règles prioritaires avec une justification ≤ 1 ligne entre parenthèses :

| Règle actuelle | Justification à ajouter |
|---|---|
| `Never set ALPHAEDGE_PAPER=false` | silences the paper/live guard — no recovery path exists |
| `Never modify core/*.pyx without explicit instruction` | proprietary FCR logic — changes invalidate all backtest results |
| `Never use # type: ignore` | silences real type errors — fix the root cause instead |
| `Never use Any as a type annotation` | Any poisons downstream type inference — use proper union or protocol |
| `Never hardcode pip/RR/risk parameters outside constants.py` | breaks single source of truth — silent divergence between backtest and live |
| `Never run make build unless .pyx was modified` | slow and irreversible mid-session — triggers full recompilation |
| `Never mark a task complete without make qa green` | partial passes hide regressions — 504 tests is the contract |

Ne modifier que la section "Hard Stops — Never Do These" de `.github/copilot-instructions.md`.
Ne pas toucher `CLAUDE.md` (il référence déjà copilot-instructions.md pour les règles).

**Validation :**
```
make qa
# Attendu : 100% pass — aucun fichier Python modifié
```
**Dépend de :** Aucune
**Statut :** ⏳

---

## PHASE 3 — MINEURES 🟡

### [C-03] XML structuring dans les fichiers de prompt d'audit

**Source BP :** BP-06
**Fichiers :**
- `tasks/audits/methode/best practices_prompt.md`
- `tasks/audits/methode/audit_ai_driven_prompt.md`
- (optionnel) autres prompts dans `tasks/audits/methode/` et `tasks/audits/code/`

**Problème :** Les sections MISSION et FILTRE sont délimitées par des séparateurs textuels (`─────`) qui sont moins discriminants pour Claude que des balises XML sémantiques. Sur des prompts longs (60+ lignes), le risque de confusion entre sections augmente.

**Correction :**
1. Dans `best practices_prompt.md` et `audit_ai_driven_prompt.md`, remplacer les blocs MISSION / FILTRE par :
```xml
<instructions>
  [contenu actuel de la section MISSION]
</instructions>

<filter>
  [contenu actuel de la section FILTRE OBLIGATOIRE]
</filter>

<output_format>
  [structure attendue du fichier produit]
</output_format>
```
2. Conserver les séparateurs visuels `─────` comme commentaires si souhaité, mais les balises XML priment.
3. Utiliser des noms de balises cohérents à travers tous les prompts du projet.

**Validation :**
```
make qa
# Attendu : 100% pass — fichiers markdown uniquement, aucun impact Python
```
**Dépend de :** Aucune
**Statut :** ⏳

---

### [C-04] Ajouter des exemples few-shot dans les prompts d'audit

**Source BP :** BP-07
**Fichiers :**
- `tasks/audits/methode/best practices_prompt.md`
- `tasks/audits/methode/audit_ai_driven_prompt.md`

**Problème :** Les prompts d'audit ne contiennent aucun exemple du format de sortie attendu. Claude doit deviner le niveau d'analyse (bullet résumé vs tableau détaillé avec source + ligne + statut). Résultat : format variable entre les relances.

**Correction :** Ajouter dans chaque prompt une section `<examples>` avec 2 entrées courtes :

```xml
<examples>
  <example>
    <!-- Cas 1 : Best practice déjà en place -->
    | CLAUDE.md au root - fichier de contexte persistant chargé à chaque session | Anthropic blog | CLAUDE.md:1 | ✅ |
  </example>
  <example>
    <!-- Cas 2 : Best practice manquante, pertinente -->
    ### BP-XX — Titre
    **Source :** [source]
    **Description :** [1-2 phrases]
    **Pourquoi pertinent :** [contexte Copilot VSCode spécifique]
    **Comment l'appliquer :** [étapes concrètes]
    **Effort :** XS/S/M/L
    **Impact estimé :** [une ligne]
  </example>
  <example>
    <!-- Cas 3 : Best practice non applicable (CLI) -->
    | Hooks PreToolUse/PostToolUse | shanraisshan | Requiert la commande `claude` CLI | 🚫 Non applicable |
  </example>
</examples>
```

**Validation :**
```
make qa
# Attendu : 100% pass — fichiers markdown uniquement
```
**Dépend de :** C-03 (recommandé — intégrer les exemples dans la structure XML une fois les balises en place)
**Statut :** ⏳

---

## SÉQUENCE D'EXÉCUTION

```
C-01  (agents + prompt guard)     → indépendant — commencer ici
C-02  (hard stops WHY)            → indépendant — en parallèle avec C-01
C-03  (XML structuring prompts)   → indépendant — après C-01/C-02 si contexte disponible
C-04  (few-shot examples)         → après C-03 de préférence (intégration XML)
```

> ⚠️ Aucun fichier `.pyx` n'est modifié dans ce plan. `make build` n'est pas requis.
> `make qa` doit passer après chaque correction (baseline de contrôle).

---

## CRITÈRES PASSAGE EN PRODUCTION

- [ ] Zéro 🟠 ouvert (C-01 et C-02 complétés)
- [ ] `make qa` : 100% pass (lint + mypy + pytest ≥80%)
- [ ] Zéro credential dans les logs loguru
- [ ] `ALPHAEDGE_PAPER=true` intact dans `.env.example`
- [ ] Bracket order `is_valid` vérifié avant envoi IB
- [ ] `check_daily_limit()` appelé chaque cycle
- [ ] Paper trading validé 5 sessions NYSE minimum

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier(s) | Effort | Statut | Date |
|----|-------|----------|------------|--------|--------|------|
| C-01 | `<investigate_before_answering>` dans agents/prompts | 🟠 | agents/dev_engineer.md · agents/code_auditor.md · prompts d'audit | XS | ✅ 2026-03-24 | 2026-03-24 |
| C-02 | WHY aux Hard Stops (copilot-instructions.md) | 🟠 | .github/copilot-instructions.md | S | ✅ 2026-03-24 | 2026-03-24 |
| C-03 | XML structuring des prompts d'audit | 🟡 | methode/best practices_prompt.md · audit_ai_driven_prompt.md | XS | ✅ 2026-03-24 | 2026-03-24 |
| C-04 | Few-shot examples dans les prompts d'audit | 🟡 | methode/best practices_prompt.md | S | ✅ 2026-03-24 | 2026-03-24 |
