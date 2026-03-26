---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: audit_best_practices_alphaedge.md
derniere_revision: 2026-03-27
creation: 2026-03-27 à 09:00
---

# Audit — Best Practices IA/Copilot ALPHAEDGE
**Date :** 2026-03-27 · **Baseline :** 602 tests · 0 Ruff · 0 Pyright

---

## 1. Header

| Champ | Valeur |
|-------|--------|
| Stack IA | Claude Sonnet 4.6 via Copilot Pro+ / VSCode |
| Scope | Fichiers de contexte AI : `CLAUDE.md` · `copilot-instructions.md` · `skills/` · `prompts/` · `specs/` · `agents/` · `tasks/` · `.claude/` |
| Baseline tests | 602 |

| # | Source | URL | Statut |
|---|--------|-----|--------|
| 1 | shanraisshan/claude-code-best-practice | https://github.com/shanraisshan/claude-code-best-practice | ✅ Analysée |
| 2 | Anthropic blog — Using CLAUDE.md files | https://claude.com/fr-fr/blog/using-claude-md-files | ✅ Analysée |
| 3 | claude.com/fr-fr/product/overview | https://claude.com/fr-fr/product/overview | Contenu général — pas de best practices fichiers contexte spécifiques |
| 4 | platform.claude.com/docs/en/home | https://platform.claude.com/docs/en/home | Documentation API Anthropic — non applicable (CLI/API) |

---

## 2. Best Practices Déjà en Place

| # | Practice | Source | Fichier:Ligne | Statut |
|---|----------|--------|---------------|--------|
| 1 | `CLAUDE.md` au root — chargé automatiquement par Copilot | Anthropic blog | `CLAUDE.md:1` | ✅ |
| 2 | `.github/copilot-instructions.md` — règles système Copilot | Anthropic blog | `.github/copilot-instructions.md:1` | ✅ |
| 3 | Checklist de démarrage de session (5 étapes ordonnées) | Anthropic blog | `CLAUDE.md:7–17` | ✅ |
| 4 | Hard stops listés avec rationales et liens vers fichier source | shanraisshan | `CLAUDE.md:19–32` | ✅ |
| 5 | Diagramme ASCII du signal pipeline (architecture lisible par IA) | shanraisshan | `.github/copilot-instructions.md:22–32` | ✅ |
| 6 | Skills dans `.github/skills/` avec descriptions déclencheurs ("Use when:") | shanraisshan | `.github/skills/*/SKILL.md:1–8` | ✅ |
| 7 | Progressive disclosure dans `cython-build` (examples/ + references/) | shanraisshan | `.github/skills/cython-build/` | ✅ |
| 8 | Prompts réutilisables dans `.github/prompts/` (add-test, cython-build, new-util) | shanraisshan (commands) | `.github/prompts/*.prompt.md` | ✅ |
| 9 | Spécifications techniques dans `.github/specs/` (4 contrats comportementaux) | shanraisshan | `.github/specs/*.md` | ✅ |
| 10 | `tasks/lessons.md` mis à jour après chaque correction | shanraisshan + Anthropic | `tasks/lessons.md:1` | ✅ |
| 11 | Pipeline A→B→C — workflow par phases avec gates explicites | shanraisshan | `.github/skills/audit-workflow/SKILL.md:18–34` | ✅ |
| 12 | Rôles agents spécialisés dans `agents/` (code_auditor, dev_engineer, quant_researcher, risk_manager) | shanraisshan (subagents) | `agents/*.md` | ✅ |
| 13 | Documentation architecture dans `architecture/` (ADR + module responsibilities) | Anthropic blog | `architecture/module_responsibilities.md` | ✅ |
| 14 | Domain knowledge dans `knowledge/` (IBKR + Forex constraints) | Anthropic blog | `knowledge/*.md` | ✅ |
| 15 | Return value contracts — tableau 6 fonctions critiques | Anthropic blog | `CLAUDE.md:68–78` | ✅ |
| 16 | Seuil de couverture documenté par dossier (≥80% sur config/utils/core/) | shanraisshan | `.github/skills/run-qa/SKILL.md:20–27` | ✅ |
| 17 | Convention de nommage des tests (`test_<module>_<scenario>.py`) | shanraisshan | `.github/copilot-instructions.md:88–93` | ✅ |
| 18 | `CLAUDE.md` concis (~150 lignes, sous le seuil de 200) | shanraisshan + Anthropic | `CLAUDE.md` | ✅ |
| 19 | `.claude/context.md` + `.claude/rules.md` — contexte Claude séparé | Anthropic blog | `.claude/` | ✅ |
| 20 | Politique secrets — `.env` jamais commité, listé dans gitignored | Anthropic blog | `CLAUDE.md:146–150` | ✅ |

---

## 3. Best Practices Manquantes

### BP-01 — Tags XML `<important>` sur les règles critiques

**Source :** shanraisshan (context engineering — tips)
**Description :** Baliser les règles irréversibles avec des tags XML sémantiques (`<important if="...">`) dans les fichiers de contexte pour que le modèle accorde une priorité accrue aux gardes high-stakes.
**Pourquoi pertinent pour ALPHAEDGE + Copilot VSCode :**
`CLAUDE.md` et `copilot-instructions.md` utilisent bold + emoji (⛔) qui sont traités comme du texte plat par le transformer. Les balises XML créent une structure sémantique explicite que le modèle interprète comme un signal de priorité — particulièrement utile en session longue où le contexte se dilue. Ce projet a 10 hard stops irréversibles (`ALPHAEDGE_PAPER=false`, `core/*.pyx` sans instruction, `.env` commit…) — s'assurer qu'aucun n'est ignoré est critique.
**Comment l'appliquer concrètement :**
  - Dans `CLAUDE.md` section ⛔ Hard Stops, encapsuler le bloc de règles :
    ```xml
    <important if="modifying any file">
    Never set ALPHAEDGE_PAPER=false in any file, ever.
    Never modify core/*.pyx without explicit user instruction.
    Never commit .env, *.log, or proprietary action plan files.
    </important>
    ```
  - Idem dans `.github/copilot-instructions.md` section "Hard Stops — Never Do These"
  - Réserver ces balises aux règles irréversibles uniquement — ne pas sur-baliser les sections informatives.

**Effort :** XS (15 min)
**Impact estimé :** Réduction du risque de dérive sur les gardes de sécurité en session longue.

---

### BP-02 — Liens Lessons → Skills (Gotchas cross-référencés)

**Source :** shanraisshan — "Gotchas: highest-signal content — add Claude's failure points over time"
**Description :** Chaque skill doit exposer une section **Gotchas** référençant les leçons pertinentes de `tasks/lessons.md`, transformant les expériences passées en guardrails actifs.
**Pourquoi pertinent pour ALPHAEDGE + Copilot VSCode :**
`tasks/lessons.md` accumule des leçons critiques réelles (ex: "`ruff check` seul ne détecte pas ARG01", "stub alignment silencieux après .pyx edit", "PROJECT_TITLE ⚡ crashe Rich Windows") mais ces connaissances restent inactives dans les skills correspondantes. Résultat : un agent qui invoque `run-qa` ignorera que `ruff check` doit être complété par `--select ARG`. Un agent qui invoque `cython-build` ne sait pas vérifier l'alignement `_stubs/` après edit. Les leçons qui coûtent 1h à apprendre se répètent à chaque session.
**Comment l'appliquer concrètement :**
  - Dans `.github/skills/run-qa/SKILL.md`, ajouter après "Common Errors" :
    ```markdown
    ## Gotchas (from tasks/lessons.md)
    - `ruff check` seul ne détecte pas les paramètres orphelins → toujours lancer `ruff check --select ARG` (2026-03-22)
    - Un paramètre `_param`-préfixé doit être utilisé dans le corps de fonction — le préfixe `_` n'est pas un blanc-seing (2026-03-23)
    - `# type: ignore` est interdit → trouver et corriger la cause racine (projet rule)
    ```
  - Dans `.github/skills/cython-build/SKILL.md`, ajouter après "Common Errors" :
    ```markdown
    ## Gotchas (from tasks/lessons.md)
    - Après tout edit `.pyx`, vérifier `_stubs/<module>.py` — une divergence de signature est silencieuse au chargement du `.pyd` (2026-03-22)
    - `make build` ne doit JAMAIS être lancé sans modification `.pyx` intentionnelle (règle permanente)
    ```
  - Dans `.github/skills/run-backtest/SKILL.md`, ajouter :
    ```markdown
    ## Gotchas (from tasks/lessons.md)
    - EURUSD utilise London Open (08:00–09:00 UTC), pas NYSE — tout diagnostic NYSE sur EURUSD produit de faux positifs (2026-03-24)
    - `PROJECT_TITLE` contient ⚡ (U+26A1) — ne jamais passer directement à Rich `Text()`/`Panel()` (2026-03-24)
    - Un taux signal ~1-2% sur EURUSD London Open est normal — ne pas ajuster FCR sans N ≥ 30 trades (2026-03-24)
    ```
  - **Règle d'entretien :** à chaque mise à jour de `tasks/lessons.md`, évaluer si la leçon appartient à un skill — si oui, la propager.

**Effort :** S (1h — 3 skills à enrichir)
**Impact estimé :** 🔴 Direct — élimine la répétition des mêmes erreurs IA qui ont déjà coûté des corrections en session.

---

### BP-03 — Arbre de répertoires clés dans CLAUDE.md

**Source :** Anthropic blog — "Include a high-level directory tree showing which directories contain what types of code"
**Description :** Ajouter un arbre de répertoires non exhaustif dans la section Architecture de `CLAUDE.md`, indiquant la responsabilité de chaque dossier pertinent pour l'IA.
**Pourquoi pertinent pour ALPHAEDGE + Copilot VSCode :**
La section Architecture actuelle de `CLAUDE.md` contient 2 liens uniquement. Un agent débutant une tâche doit explorer le workspace (`list_dir`, `file_search`) pour découvrir que les tests sont dans `alphaedge/tests/`, les prompts dans `.github/prompts/`, les specs dans `.github/specs/`, les leçons dans `tasks/lessons.md`, etc. Un arbre compact élimine 2-3 appels outils d'exploration systématique.
**Comment l'appliquer concrètement :**
  - Remplacer la section Architecture dans `CLAUDE.md` par :
    ```markdown
    ## Architecture
    > Contrats complets : [docs/ALPHAEDGE_INTERFACES.md](docs/ALPHAEDGE_INTERFACES.md)
    > Modules + responsabilités : [architecture/module_responsibilities.md](architecture/module_responsibilities.md)

    ```
    alphaedge/
      config/       — constantes + loader YAML (toujours éditer constants.py, jamais hardcoder)
      core/         — détecteurs Cython (.pyx) + stubs Python (_stubs/) — ne jamais éditer sans instruction
      engine/       — orchestration live + backtest (engine/ exclue de la couverture)
      tests/        — pytest (602 tests, couverture ≥80% sur config/utils/core/)
    .github/
      skills/       — workflows réutilisables (audit-workflow, cython-build, run-qa, run-backtest)
      prompts/      — templates tâches récurrentes (add-test, cython-build, new-util)
      specs/        — contrats comportement fonctions critiques (fcr, order, risk, backtest)
    tasks/
      audits/       — prompts code/ et methode/ + resultats/ (rapports d'audit)
      corrections/  — plans d'action + prompts d'exécution
      lessons.md    — leçons IA accumulées — LIRE EN PREMIER
    agents/         — rôles spécialisés (#file:agents/<role>.md pour activer)
    architecture/   — ADR + responsabilités modules
    knowledge/      — contraintes IBKR + marché Forex
    ```
  - Ne pas lister `build/`, `logs/`, `reports/`, `scripts/` — non pertinents pour l'IA.

**Effort :** XS (20 min)
**Impact estimé :** 🟠 Réduit la phase d'exploration initiale des agents — navigation directe vers les bons fichiers.

---

### BP-04 — Checklist pré-code 4 questions dans le workflow

**Source :** Anthropic blog — "Define standard workflows for different task types"
**Description :** Ajouter 4 questions de réflexion obligatoires avant toute modification de code pour prévenir les modifications prématurées.
**Pourquoi pertinent pour ALPHAEDGE + Copilot VSCode :**
"Plan mode obligatoire pour ≥ 3 étapes" est en place mais sans checklist pré-code structurée. Des erreurs passées auraient été évitées : le diagnostic EURUSD basé sur NYSE (2026-03-24) se serait arrêté à la question "ai-je lu les fichiers impliqués ?". La règle "Audit Before Modify" dans Core Principles est déclarative — la transformer en 4 questions concrètes la rend actionnable.
**Comment l'appliquer concrètement :**
  - Dans `CLAUDE.md` section Workflow Orchestration, ajouter après le premier bullet :
    ```markdown
    **Avant toute modification de code — 4 questions :**
    1. Ai-je lu tous les fichiers que je vais modifier ? (citer fichier:ligne)
    2. Ai-je un plan en N étapes validé avant d'agir ?
    3. Y a-t-il des informations manquantes ? (explorer d'abord, modifier ensuite)
    4. Comment vais-je valider le changement ? (`make qa` suffit ? test dédié requis ?)
    ```
  - Idem dans `.claude/rules.md` section modification priority (alignement Claude-specific).

**Effort :** XS (10 min)
**Impact estimé :** 🟠 Prévient les diagnostics erronés — opérationnalise le principe "Audit Before Modify" déjà posé.

---

### BP-05 — Progressive disclosure dans les skills sans sous-dossiers

**Source :** shanraisshan — "Skills are folders, not just files — use references/, scripts/, examples/ subdirs for heavy content"
**Description :** Les skills `audit-workflow`, `run-qa` et `run-backtest` n'ont qu'un `SKILL.md` seul. `cython-build` est déjà exemplaire avec `examples/` et `references/`.
**Pourquoi pertinent pour ALPHAEDGE + Copilot VSCode :**
- `audit-workflow` sans exemples de format de sortie → un agent peut produire un audit qui ne respecte pas les sections obligatoires (Date, Blocs, Synthèse, severité 🔴/🟠/🟡).
- `run-qa` sans référence aux erreurs Ruff/Mypy réelles vues sur ce projet → l'agent doit réinférer les patterns à chaque session.
- `run-backtest` sans référence aux paramètres `config.yaml` clés → l'agent doit explorer `constants.py` avant d'interpréter un résultat.
**Comment l'appliquer concrètement :**
  - `audit-workflow/examples/` → créer `example_audit_section.md` : extrait de bloc d'un audit existant (`audit_trade_journal_alphaedge.md`) comme modèle de format
  - `run-qa/references/` → créer `known_errors.md` : erreurs Ruff/Pyright réelles du projet (ARG001, E501, S101, N803, missing return type)
  - `run-backtest/references/` → créer `config_params.md` : table des paramètres `config.yaml` + `constants.py` clés avec valeurs nominales

**Effort :** S (2h — 3 skills, 1 fichier référence chacun)
**Impact estimé :** 🟡 Améliore la cohérence et la rapidité des sorties skills.

---

### BP-06 — Référence aux `agents/` dans CLAUDE.md et audit-workflow

**Source :** shanraisshan — "Use subagents for different phases — isolate context"
**Description :** Le dossier `agents/` contient 4 rôles spécialisés mais ni `CLAUDE.md` ni `copilot-instructions.md` ne les mentionnent, ni n'indiquent quand les invoquer.
**Pourquoi pertinent pour ALPHAEDGE + Copilot VSCode :**
Un agent recevant une demande de validation de stratégie ne sait pas instancier `#file:agents/quant_researcher.md` pour activer le mode anti-biais. Un audit de sécurité ne sait pas utiliser `#file:agents/code_auditor.md`. Ces rôles restent des fichiers morts — une seule ligne dans `CLAUDE.md` suffit à les rendre découvrables et utilisables.
**Comment l'appliquer concrètement :**
  - Dans `CLAUDE.md` section Workflow Orchestration, ajouter :
    ```markdown
    - **Agents spécialisés :** `#file:agents/<role>.md` pour activer un rôle contextuel
      (`code_auditor` · `dev_engineer` · `quant_researcher` · `risk_manager`)
    ```
  - Dans `.github/skills/audit-workflow/SKILL.md`, section Steps → ajouter :
    ```markdown
    **Agent suggéré :** `#file:agents/code_auditor.md` (audits code) · `#file:agents/quant_researcher.md` (audits stratégiques)
    ```

**Effort :** XS (15 min)
**Impact estimé :** 🟡 Rend les agents spécialisés découvrables — passage de fichiers morts à outils actifs.

---

### BP-07 — Stratégie git documentée (commits fréquents + convention messages)

**Source :** shanraisshan — "commit at least once per hour, as soon as the task is completed; keep PRs small and focused (squash merge)"
**Description :** Aucun fichier de contexte AI ne documente une stratégie git au-delà du format `cython: <description>` (dans cython-build uniquement).
**Pourquoi pertinent pour ALPHAEDGE + Copilot VSCode :**
Les corrections multi-étapes (ex: 8 corrections Audit #10) sont appliquées en série sans point de sauvegarde git intermédiaire. Si un commit tardif échoue QA, toute la session est à risque. Une convention de commit générale (pas seulement Cython) avec fréquence recommandée réduit ce risque sans alourdir le workflow.
**Comment l'appliquer concrètement :**
  - Dans `CLAUDE.md` section Core Principles (ou nouvelle entrée Workflow), ajouter :
    ```markdown
    **Git workflow :**
    - Committer dès qu'une correction passe `make qa` — ne pas attendre la fin du plan multi-étapes
    - Format : `type(scope): description` → ex: `fix(journal): atomic CSV write`, `feat(backtest): add sl_pips column`
    - PRs focalisées : une correction / un audit par PR (squash merge)
    ```

**Effort :** XS (15 min)
**Impact estimé :** 🟡 Réduit le risque de perte en session longue — sécurité du code produit.

---

## 4. Best Practices Non Applicables (CLI / API uniquement)

| Practice | Source | Raison d'exclusion |
|----------|--------|--------------------|
| Hooks PreToolUse / PostToolUse | shanraisshan | Requiert la commande `claude` CLI — non disponible dans Copilot VSCode |
| `/compact`, `/clear`, `/init`, `/loop` | shanraisshan | Commandes Claude Code CLI exclusivement |
| `/sandbox` (isolation réseau) | shanraisshan | Claude Code CLI — mode bac à sable CLI |
| Git worktrees + multi-agent swarms | shanraisshan | Nécessite Claude Code CLI avec plusieurs instances concurrentes |
| CLAUDE.md auto-exécuté par Claude Code | shanraisshan + Anthropic | Dans Copilot, `CLAUDE.md` est contexte passif (#codebase) — non exécuté automatiquement |
| MCP Servers integration | shanraisshan | Requiert API Anthropic ou Claude Code CLI avec configuration `.claude/mcp.json` |
| Auto mode beta | shanraisshan | Claude Code CLI uniquement |
| `claude` install global + permissions JSON | shanraisshan | CLI — hors scope Copilot VSCode |
| `/schedule` + cloud tasks | shanraisshan | Claude.ai cloud tasks — non disponible en Copilot |
| Token API Anthropic direct | platform.claude.com/docs | Toute la doc platform.claude.com est pour l'API REST — non applicable |

---

## 5. Tableau Synthèse Prioritaire

| ID | Description | Source | Fichier cible | Sévérité | Impact | Effort |
|----|-------------|--------|--------------|----------|--------|--------|
| BP-02 | Liens Lessons → Skills (Gotchas cross-référencés) | shanraisshan | `.github/skills/*/SKILL.md` | 🔴 Critique | Élimination répétition erreurs IA | S |
| BP-03 | Arbre répertoires clés dans CLAUDE.md | Anthropic blog | `CLAUDE.md` section Architecture | 🟠 Majeur | Réduction phase exploration initiale | XS |
| BP-04 | Checklist pré-code 4 questions | Anthropic blog | `CLAUDE.md` + `.claude/rules.md` | 🟠 Majeur | Prévention modifications prématurées | XS |
| BP-01 | Tags XML `<important>` sur hard stops | shanraisshan | `CLAUDE.md` + `copilot-instructions.md` | 🟡 Mineur | Résilience gardes en session longue | XS |
| BP-05 | Progressive disclosure skills (audit-workflow, run-qa, run-backtest) | shanraisshan | `.github/skills/*/` | 🟡 Mineur | Cohérence des sorties skills | S |
| BP-06 | Référence `agents/` dans CLAUDE.md + audit-workflow skill | shanraisshan | `CLAUDE.md` + audit SKILL.md | 🟡 Mineur | Rend les rôles agents utilisables | XS |
| BP-07 | Stratégie git documentée (commits fréquents + convention) | shanraisshan | `CLAUDE.md` | 🟡 Mineur | Sécurité sessions longues multi-étapes | XS |

**Synthèse :** 🔴 1 · 🟠 2 · 🟡 4

**Effort total estimé :** ~4h30

**Ordre d'exécution recommandé :**
1. **Lot XS** — BP-03 + BP-04 + BP-06 + BP-01 + BP-07 en une passe (~1h30 total)
2. **BP-02** — Gotchas dans 3 skills (~1h)
3. **BP-05** — Fichiers référence dans 3 skills (~2h — impact le plus modeste, en dernier)
