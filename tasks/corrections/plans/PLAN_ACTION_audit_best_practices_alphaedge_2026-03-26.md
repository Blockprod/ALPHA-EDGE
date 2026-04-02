---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: PLAN_ACTION_audit_best_practices_alphaedge_2026-03-26.md
derniere_revision: 2026-03-26
creation: 2026-03-26 à 09:30
---

# PLAN D'ACTION — ALPHAEDGE — 2026-03-26
**Sources :** `tasks/audits/resultats/audit_best_practices_alphaedge.md`
**Total :** 🔴 1 · 🟠 2 · 🟡 4 · **Effort estimé :** ~1 jour (~5h30)

> ⚠️ Toutes les corrections portent sur des fichiers Markdown de contexte IA.
> Aucun `.pyx` touché → `make build` NON requis.
> `make qa` doit rester vert à chaque étape (602 tests, 0 Ruff, 0 Pyright).

---

## PHASE 1 — CRITIQUES 🔴

### [C-01] Gotchas cross-référencés Lessons → Skills (3 skills)

**Fichiers :**
- `.github/skills/run-qa/SKILL.md` (après la section "Common Errors")
- `.github/skills/cython-build/SKILL.md` (après la section "Common Errors")
- `.github/skills/run-backtest/SKILL.md` (après la section "Common Errors")

**Problème :** `tasks/lessons.md` accumule des leçons critiques réelles (ARG01 invisible, stub alignment silencieux, EURUSD/NYSE confusion, U+26A1 crash Rich) mais ces connaissances ne sont pas exposées dans les skills correspondantes. Un agent invoquant `run-qa` ignorera que `ruff check` doit être complété par `--select ARG`. Les mêmes erreurs IA se répètent à chaque session.

**Correction :**

_Dans `.github/skills/run-qa/SKILL.md`_ — ajouter après la section "Common Errors" :
```markdown
## Gotchas (from tasks/lessons.md)
- `ruff check` seul ne détecte pas les paramètres de fonctions orphelins → toujours lancer `ruff check --select ARG` en complément (2026-03-22)
- Un paramètre `_param`-préfixé doit être utilisé dans le corps de la fonction — le préfixe `_` est occulté par `ruff --select ARG` mais visible dans Pylance WARNING (2026-03-23)
- `# type: ignore` et `# pyright: ignore` sont interdits → trouver et corriger la cause racine (règle absolue)
- `Any` comme annotation est interdit → utiliser le bon union ou protocol
```

_Dans `.github/skills/cython-build/SKILL.md`_ — ajouter après la section "Common Errors" (fin du fichier) :
```markdown
## Gotchas (from tasks/lessons.md)
- Après tout edit `.pyx`, vérifier `_stubs/<module>.py` — une divergence de signature (nom de paramètre, ordre, clé du dict retourné) est silencieuse au chargement du `.pyd` et produit des bugs runtime subtils (2026-03-22)
- `make build` ne doit JAMAIS être lancé sans modification `.pyx` intentionnelle — lent et irréversible mid-session
- Nommer le commit `cython: <description>` après chaque edit `.pyx` réussi
```

_Dans `.github/skills/run-backtest/SKILL.md`_ — ajouter après la section "DST Critical Dates" :
```markdown
## Gotchas (from tasks/lessons.md)
- EURUSD utilise London Open (08:00–09:00 UTC), PAS NYSE — tout diagnostic basé sur NYSE pour EURUSD produit de faux positifs (2026-03-24)
- `PROJECT_TITLE` contient ⚡ (U+26A1) — ne jamais passer directement à Rich `Text()`/`Panel()` sur Windows cp1252 (crash LegacyWindowsTerm) (2026-03-24)
- Un taux signal ~1-2% sur EURUSD London Open est statistiquement normal (88% sessions rejetées par filtre FCR) — ne pas modifier les paramètres sans N ≥ 30 trades post-modification (2026-03-24)
- `_backtest_pair` directement sans `session_spec` utilise NYSE par défaut — toujours passer `session_spec=config.trading.pair_sessions.get(pair)` (2026-03-24)
```

**Validation :**
```powershell
make qa
# Attendu : 602 tests · 0 Ruff · 0 Pyright (fichiers .md non impactés par QA)
```
**Dépend de :** Aucune
**Statut :** ✅ 2026-03-26

---

## PHASE 2 — MAJEURES 🟠

### [C-02] Arbre de répertoires clés dans CLAUDE.md (section Architecture)

**Fichier :** `CLAUDE.md` — section "Architecture" (lignes ~52–58)

**Problème :** La section Architecture contient 2 liens uniquement. Un agent débutant une tâche doit explorer le workspace (list_dir, file_search) pour découvrir où se trouvent tests, prompts, specs, leçons, etc. Un arbre compact élimine 2-3 appels outils d'exploration initiale.

**Correction :** Remplacer la section Architecture par :
```markdown
## Architecture

> Contrats complets + signatures : [docs/ALPHAEDGE_INTERFACES.md](docs/ALPHAEDGE_INTERFACES.md)
> Modules + responsabilités : [architecture/module_responsibilities.md](architecture/module_responsibilities.md)

`engine/` → `core/` → `config/` → `utils/` — top-down uniquement, aucun import circulaire.

```
alphaedge/
  config/     — constantes + loader YAML (toujours éditer constants.py, jamais hardcoder)
  core/       — détecteurs Cython (.pyx) + stubs Python (_stubs/) — ne jamais éditer sans instruction
  engine/     — orchestration live + backtest (exclu de la couverture tests)
  tests/      — pytest (602 tests, couverture ≥80% sur config/utils/core/)
.github/
  skills/     — workflows réutilisables (audit-workflow · cython-build · run-qa · run-backtest)
  prompts/    — templates tâches récurrentes (add-test · cython-build · new-util)
  specs/      — contrats comportement fonctions critiques (fcr · order · risk · backtest)
tasks/
  audits/     — prompts code/ et methode/ + resultats/ (rapports d'audit)
  corrections/ — plans d'action datés + prompts d'exécution (generate · execute)
  lessons.md  — leçons IA accumulées — LIRE EN PREMIER
agents/       — rôles spécialisés (#file:agents/<role>.md pour activer)
architecture/ — ADR + responsabilités modules
knowledge/    — contraintes IBKR + marché Forex
```
```

**Validation :**
```powershell
make qa
# Attendu : 602 tests · 0 Ruff · 0 Pyright
```
**Dépend de :** Aucune
**Statut :** ✅ 2026-03-26

---

### [C-03] Checklist pré-code 4 questions dans Workflow Orchestration

**Fichiers :**
- `CLAUDE.md` — section "Workflow Orchestration" (lignes ~97–103)
- `.claude/rules.md` — section modification priority

**Problème :** "Plan mode obligatoire pour ≥ 3 étapes" est en place mais sans checklist pré-code structurée. La règle "Audit Before Modify" dans Core Principles est déclarative — des erreurs passées (diagnostic EURUSD/NYSE, 2026-03-24) auraient été évitées avec 4 questions de réflexion obligatoires avant toute modification.

**Correction :**

_Dans `CLAUDE.md`_ — dans la section "Workflow Orchestration", ajouter après le premier bullet (plan mode obligatoire) :
```markdown
- **Avant toute modification de code — 4 questions :**
  1. Ai-je lu tous les fichiers que je vais modifier ? (citer fichier:ligne avant d'agir)
  2. Ai-je un plan en N étapes validé avant d'agir ?
  3. Y a-t-il des informations manquantes ? (explorer d'abord, modifier ensuite)
  4. Comment vais-je valider le changement ? (`make qa` suffit ? test dédié requis ?)
```

_Dans `.claude/rules.md`_ — dans la section "Modification priority" ou équivalente, ajouter le même bloc 4 questions.

**Validation :**
```powershell
make qa
# Attendu : 602 tests · 0 Ruff · 0 Pyright
```
**Dépend de :** Aucune
**Statut :** ✅ 2026-03-26

---

## PHASE 3 — MINEURES 🟡

### [C-04] Tags XML `<important>` sur les hard stops

**Fichiers :**
- `CLAUDE.md` — section "⛔ Hard Stops — Never Do These" (lignes ~19–32)
- `.github/copilot-instructions.md` — section "Hard Stops — Never Do These" (lignes ~44–59)

**Problème :** Les règles irréversibles utilisent bold + emoji (⛔) traités comme texte plat. Les balises XML créent une structure sémantique explicite — particulièrement utile en session longue où le contexte se dilue.

**Correction :**

_Dans `CLAUDE.md`_ — encapsuler la liste des 10 hard stops :
```markdown
<important if="modifying any file">

- Never modify core/*.pyx without explicit user instruction
- Never commit .env, *.log, or proprietary action plan files
- Never run make build unless a .pyx file was intentionally modified
- Never use # type: ignore / # pyright: ignore — fix the root cause
- Never use Any as a type annotation — it is a rustine
- Never hardcode pip values, RR ratios, session times, or risk parameters outside alphaedge/config/constants.py
- Never touch timezone.py or session_manager.py without re-running DST edge case tests
- Never mark a task complete without make qa green (602 tests)
- Never push a .pyx edit without make build followed by make qa
</important>
```

_Dans `.github/copilot-instructions.md`_ — même encapsulation autour de la section "Hard Stops — Never Do These".

**Validation :**
```powershell
make qa
# Attendu : 602 tests · 0 Ruff · 0 Pyright
```
**Dépend de :** Aucune
**Statut :** ✅ 2026-03-26

---

### [C-05] Référence aux `agents/` dans CLAUDE.md et audit-workflow SKILL.md

**Fichiers :**
- `CLAUDE.md` — section "Workflow Orchestration"
- `.github/skills/audit-workflow/SKILL.md` — section "Steps"

**Problème :** Le dossier `agents/` contient 4 rôles spécialisés (code_auditor, dev_engineer, quant_researcher, risk_manager) mais ni `CLAUDE.md` ni la skill audit-workflow ne les mentionnent. Ces fichiers restent des ressources mortes non découvertes.

**Correction :**

_Dans `CLAUDE.md`_ — dans la section "Workflow Orchestration", ajouter :
```markdown
- **Agents spécialisés disponibles :** invoquer via `#file:agents/<role>.md`
  (`code_auditor` · `dev_engineer` · `quant_researcher` · `risk_manager`)
```

_Dans `.github/skills/audit-workflow/SKILL.md`_ — dans la section "Steps → A — Audit", ajouter :
```markdown
**Agent suggéré selon le type d'audit :**
- Code/sécurité → `#file:agents/code_auditor.md`
- Stratégique/statistique → `#file:agents/quant_researcher.md`
- Implémentation → `#file:agents/dev_engineer.md`
- Risque capital → `#file:agents/risk_manager.md`
```

**Validation :**
```powershell
make qa
# Attendu : 602 tests · 0 Ruff · 0 Pyright
```
**Dépend de :** Aucune
**Statut :** ✅ 2026-03-26

---

### [C-06] Convention git documentée dans CLAUDE.md

**Fichier :** `CLAUDE.md` — section "Core Principles" (lignes ~126–132)

**Problème :** Les corrections multi-étapes sont appliquées en série sans point de sauvegarde git intermédiaire. Un commit tardif en session longue expose l'ensemble du travail si QA échoue. Seul cython-build mentionne une convention de commit (`cython: <desc>`).

**Correction :** Dans `CLAUDE.md` section "Core Principles", ajouter :
```markdown
- **Git workflow :** committer dès qu'une correction passe `make qa` — ne pas attendre la fin du plan multi-étapes
  - Format : `fix(scope): description` · `feat(scope): description` · `cython: description`
  - Ex: `fix(journal): atomic CSV write`, `feat(backtest): add sl_pips column`
  - PRs focalisées : une correction / un audit par PR · squash merge
```

**Validation :**
```powershell
make qa
# Attendu : 602 tests · 0 Ruff · 0 Pyright
```
**Dépend de :** Aucune
**Statut :** ✅ 2026-03-26

---

### [C-07] Progressive disclosure dans 3 skills (fichiers référence)

**Fichiers à créer :**
- `.github/skills/audit-workflow/examples/example_audit_section.md`
- `.github/skills/run-qa/references/known_errors.md`
- `.github/skills/run-backtest/references/config_params.md`

**Problème :** `cython-build` est exemplaire avec `examples/` et `references/`. Les 3 autres skills n'ont qu'un SKILL.md seul, sans contenu de référence — un agent doit réinférer les patterns à chaque session.

**Correction :**

_`.github/skills/audit-workflow/examples/example_audit_section.md`_ — extrait d'un bloc d'audit bien formé, avec header, structure de section (###, Fichier:Ligne, Problème, Correction), tableau SYNTHÈSE final avec colonnes ID/Bloc/Description/Fichier:Ligne/Sévérité/Impact/Effort, et confirmation chat attendue.

_`.github/skills/run-qa/references/known_errors.md`_ — table des erreurs Ruff/Pyright réellement rencontrées sur ce projet : ARG001 (orphan parameter), E501 (line too long), S101 (assert in prod code), N803 (argument lowercase), missing return type, `Any` annotation interdit, `# type: ignore` interdit.

_`.github/skills/run-backtest/references/config_params.md`_ — table des paramètres clés `config.yaml` + `alphaedge/config/constants.py` avec valeurs nominales actuelles (RR=2.0, risk_pct=3.0, min_range_pips, sl_buffer_pips, spread_max_pips, EUR_USD_RATE=1.08, SESSION windows par paire).

**Validation :**
```powershell
make qa
# Attendu : 602 tests · 0 Ruff · 0 Pyright
```
**Dépend de :** Aucune
**Statut :** ✅ 2026-03-26

---

## SÉQUENCE D'EXÉCUTION

```
Lot XS — Sans dépendances, maximum de parallélisme :
  C-02  → CLAUDE.md arbre répertoires        (20 min)
  C-03  → CLAUDE.md + .claude/rules.md       (15 min)
  C-04  → Tags XML <important> (2 fichiers)  (15 min)
  C-05  → Agents/ référence (2 fichiers)     (15 min)
  C-06  → Convention git CLAUDE.md           (10 min)
  → make qa ✅

Lot S — Enrichissement skills :
  C-01  → Gotchas dans 3 skills SKILL.md     (1h)
  → make qa ✅

Lot S — Création fichiers référence :
  C-07  → 3 nouveaux fichiers référence      (2h)
  → make qa ✅
```

> ⚠️ Aucun fichier `.pyx` modifié → `make build` NON requis dans toute la séquence.
> `make qa` doit rester vert (602 tests, 0 Ruff, 0 Pyright) à chaque checkpoint.

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

| ID | Titre | Sévérité | Fichiers | Effort | Statut | Date |
|----|-------|----------|---------|--------|--------|------|
| C-01 | Gotchas Lessons → 3 Skills | 🔴 | skills/run-qa · cython-build · run-backtest | S (1h) | ✅ | 2026-03-26 |
| C-02 | Arbre répertoires CLAUDE.md | 🟠 | CLAUDE.md | XS (20min) | ✅ | 2026-03-26 |
| C-03 | Checklist 4 questions pré-code | 🟠 | CLAUDE.md · .claude/rules.md | XS (15min) | ✅ | 2026-03-26 |
| C-04 | Tags XML `<important>` hard stops | 🟡 | CLAUDE.md · copilot-instructions.md | XS (15min) | ✅ | 2026-03-26 |
| C-05 | Référence agents/ dans CLAUDE.md + skill | 🟡 | CLAUDE.md · audit-workflow/SKILL.md | XS (15min) | ✅ | 2026-03-26 |
| C-06 | Convention git documentée | 🟡 | CLAUDE.md | XS (10min) | ✅ | 2026-03-26 |
| C-07 | Progressive disclosure 3 skills (fichiers ref) | 🟡 | 3 nouveaux fichiers .github/skills/ | S (2h) | ✅ | 2026-03-26 |
