# AUDIT BEST PRACTICES — ALPHAEDGE
**Date :** 2026-03-24 à 16:00
**Mis à jour :** 2026-03-24 à 17:30 (4ème source analysée)
**Créé le :** 2026-03-24 à 16:00
**Sources analysées :**
- https://github.com/shanraisshan/claude-code-best-practice
- https://claude.com/fr-fr/blog/using-claude-md-files
- https://claude.com/fr-fr/product/overview
- https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices

**Stack analysée :** Claude Sonnet 4.6 · Copilot Pro+ · VSCode (pas Claude Code CLI)
**Scope :** Fichiers de contexte AI-Driven · Skills · Prompts · Agents · Workflows · Mémoire

---

## BEST PRACTICES DÉJÀ EN PLACE

| Practice | Source | Fichier:Ligne | Statut |
|----------|--------|--------------|--------|
| CLAUDE.md au root — fichier de contexte persistant chargé à chaque session | Anthropic blog | CLAUDE.md:1 | ✅ |
| copilot-instructions.md dans .github/ — chargé automatiquement par Copilot | Anthropic / GitHub | .github/copilot-instructions.md:1 | ✅ |
| `copilot-instructions.md` < 200 lignes (165 lignes) | shanraisshan | .github/copilot-instructions.md | ✅ |
| Agents spécialisés par domaine (pas d'agent générique) | shanraisshan · Boris | agents/code_auditor.md, agents/risk_manager.md, agents/quant_researcher.md, agents/dev_engineer.md | ✅ |
| Skill avec description rédigée comme trigger ("Use when: …") | shanraisshan · Thariq | .github/skills/cython-build/SKILL.md:3 | ✅ |
| Section Gotchas / Common Errors dans la skill | shanraisshan · Thariq | .github/skills/cython-build/SKILL.md:35 | ✅ |
| Prompt files réutilisables pour les workflows inner-loop | Anthropic blog + GitHub | .github/prompts/add-test.prompt.md, cython-build.prompt.md, new-util.prompt.md | ✅ |
| Fichier leçons apprises relu à chaque session | shanraisshan (planning tips) | tasks/lessons.md | ✅ |
| Plan mode enforced avant toute implémentation | shanraisshan · Boris | CLAUDE.md:49–55 | ✅ |
| Checklist de démarrage de session | Anthropic blog (workflows) | CLAUDE.md:10–20 | ✅ |
| Arborescence du projet documentée dans le contexte | Anthropic blog | copilot-instructions.md:11–22 | ✅ |
| Commandes build/test documentées (make qa, make build) | Anthropic blog | CLAUDE.md:160–175 ; copilot-instructions.md:105–115 | ✅ |
| Documentation ADR (Architecture Decision Records) | shanraisshan (architecture docs) | architecture/decisions.md | ✅ |
| Base de connaissances domaine (IBKR, trading FCR) | Anthropic blog (connect tools) | knowledge/ibkr_constraints.md, knowledge/trading_constraints.md | ✅ |
| Workflows standards documentés (Audit → Plan → Corrections) | Anthropic blog (standard workflows) | tasks/WORKFLOW.md | ✅ |
| ASCII diagrams pour l'architecture dans les fichiers de contexte | shanraisshan · Boris | CLAUDE.md:45–58 ; copilot-instructions.md:30–42 | ✅ |
| Informations sensibles exclues des fichiers de contexte | Anthropic blog | .env exclu, .env.example utilisé, CLAUDE.md:18 | ✅ |
| "Run the tests and it just works" — one-liner documenté | shanraisshan · Dex | CLAUDE.md:160 (`make qa`) | ✅ |
| Séparation contexte par sous-agent (Explore subagent) | shanraisshan · Boris | .github/copilot-instructions.md (agents section) | ✅ |

---

## BEST PRACTICES MANQUANTES — PERTINENTES COPILOT VSCODE

### BP-01 — CLAUDE.md dépasse 200 lignes (386 lignes actuellement)

**Source :** shanraisshan ("CLAUDE.md should target under 200 lines") + Anthropic blog ("restez concis")
**Description :** Un fichier de contexte trop long dilue le signal. Au-delà de 200 lignes, Claude commence à ignorer des règles même marquées MUST.
**Pourquoi pertinent pour ALPHAEDGE + Copilot VSCode :** `CLAUDE.md` est injecté dans chaque session Copilot via `#codebase`. À 386 lignes, il consomme du contexte pour des sections rarement pertinentes (ex: interfaces Cython publiques complètes, retails de reconnexion).
**Comment l'appliquer concrètement :**
  - Extraire les interfaces Cython publiques → `docs/ALPHAEDGE_INTERFACES.md`
  - Extraire le tableau des modules → `architecture/module_responsibilities.md` (existe déjà partiellement dans `architecture/system_design.md`)
  - Garder dans CLAUDE.md : startup checklist, hard stops (10 règles), workflow orchestration, core principles
  - Référencer avec `@path` en bas du CLAUDE.md (compatible Claude Code) ou via `#file:` dans les prompts Copilot
  - **Cible :** CLAUDE.md ≤ 200 lignes

**Effort :** S
**Impact estimé :** Meilleure attention sur les règles critiques (hard stops), réduction du contexte consommé par conversation.

---

### BP-02 — Une seule skill (cython-build) — manque de couverture des workflows répétitifs

**Source :** shanraisshan · Boris ("if you do something more than once a day, turn it into a skill or command")
**Description :** Les skills doivent couvrir tous les workflows inner-loop fréquents, pas seulement le build Cython.
**Pourquoi pertinent pour ALPHAEDGE + Copilot VSCode :** Les workflows `make qa`, `make test`, lancement d'un backtest, création d'un plan d'action depuis un audit — sont répétés quotidiennement et méritent chacun une skill.
**Comment l'appliquer concrètement :**
  - `.github/skills/run-qa/SKILL.md` — workflow QA complet (ruff + mypy + pytest), erreurs fréquentes, seuils coverage
  - `.github/skills/run-backtest/SKILL.md` — paramètres backtest, lecture des résultats, pièges courants (warmup, DST)
  - `.github/skills/audit-workflow/SKILL.md` — pipeline A→B→C, référence vers WORKFLOW.md
  - Description de chaque skill rédigée comme trigger : "Use when: …"
  - Chaque skill avec section **Common Errors / Gotchas**

**Effort :** M (3 skills à créer)
**Impact estimé :** Copilot invoque automatiquement la bonne skill selon le contexte, sans prompt manuel répétitif.

---

### BP-03 — Structure progressive dans les skills (pas de subdirectories)

**Source :** shanraisshan · Thariq ("skills are folders, not files — use references/, scripts/, examples/ subdirectories")
**Description :** Une skill peut grandir sans bloater le SKILL.md principal. Les sous-répertoires permettent la disclosure progressive.
**Pourquoi pertinent pour ALPHAEDGE + Copilot VSCode :** `cython-build` est pour l'instant un fichier plat. Quand les cas d'erreur croissent, le SKILL.md va dépasser 100 lignes.
**Comment l'appliquer concrètement :**
```
.github/skills/cython-build/
├── SKILL.md              ← corps principal (≤ 60 lignes)
├── examples/
│   ├── add_field.md      ← exemple concret d'ajout d'un champ Cython
│   └── new_module.md     ← exemple ajout d'un nouveau .pyx
└── references/
    └── cython_types.md   ← types Cython autorisés, équivalences Python
```
  - Le SKILL.md principal référence les sous-fichiers via des liens relatifs
  - Copilot charge le SKILL.md principal, et accède aux sous-fichiers via #file: si besoin

**Effort :** XS
**Impact estimé :** Skill maintenable sur le long terme, disclosure progressive sans bruit.

---

### BP-04 — Pas de spec files par feature

**Source :** shanraisshan (Spec Kit, spec-driven development) + Anthropic blog
**Description :** Chaque feature majeure devrait avoir un fichier de spec markdown décrivant comportement attendu, interface, edge cases — avant le code.
**Pourquoi pertinent pour ALPHAEDGE + Copilot VSCode :** ALPHAEDGE n'a pas de spec pour `fcr_detector`, `gap_detector`, `risk_manager`, etc. Le "Return Value Contracts" dans CLAUDE.md est un début mais n'est pas un spec complet.
**Comment l'appliquer concrètement :**
```
.github/specs/
├── fcr-detection.md      ← comportement attendu, inputs/outputs, edge cases
├── risk-management.md    ← daily loss limit, position sizing, contrats retour
├── order-execution.md    ← bracket order, spread check, fill handling
└── backtest-engine.md    ← hypothèses, biais à éviter, métriques de sortie
```
  - Usage Copilot : `#file:.github/specs/risk-management.md` dans un prompt de modification
  - Valeur immédiate : Copilot peut valider ses implémentations contre la spec

**Effort :** M (4 specs à rédiger depuis le code existant)
**Impact estimé :** Réduction des hallucinations sur les interfaces core, validation comportementale explicite.

---

### BP-05 — CLAUDE.md duplique des infos présentes dans copilot-instructions.md

**Source :** Anthropic blog ("évitez les doublons, scindez en fichiers référencés")
**Description :** Les deux fichiers contiennent le pipeline d'architecture, les hard stops, les règles Python 3.11, les return value contracts — en quasi-doublon.
**Pourquoi pertinent pour ALPHAEDGE + Copilot VSCode :** Doublon = maintenance double + risque de désynchronisation + contexte consommé deux fois.
**Comment l'appliquer concrètement :**
  - `copilot-instructions.md` = règles Copilot (chargé auto par GitHub Copilot) → garder complet
  - `CLAUDE.md` = entry point Claude/session → référencer copilot-instructions.md pour les règles communes plutôt que les dupliquer
  - Supprimer de CLAUDE.md les sections déjà couvertes par copilot-instructions.md (architecture pipeline, return contracts, QA commands)

**Effort :** S
**Impact estimé :** CLAUDE.md descend sous 200 lignes (BP-01 résolu en partie), maintenance centralisée.

---

### BP-06 — Pas de XML structuring dans les fichiers de prompt

**Source :** Anthropic API Docs — Prompting best practices ("Structure prompts with XML tags")
**Description :** Envelopper les instructions, le contexte et les exemples dans des balises XML (`<instructions>`, `<context>`, `<output_format>`) réduit les mauvaises interprétations sur les prompts complexes qui mêlent instructions, contexte repo et critères de sortie.
**Pourquoi pertinent pour ALPHAEDGE + Copilot VSCode :** Les fichiers `tasks/audits/methode/*.md` et `.github/prompts/*.prompt.md` utilisent un formatage markdown plat (titres, tirets). Sur des prompts longs (audit complet = 60+ lignes), Claude peut confondre les sections.
**Comment l'appliquer concrètement :**
  - Convertir les sections MISSION + FILTRE des prompt files en `<instructions>`…`</instructions>`
  - Envelopper le format attendu en sortie dans `<output_format>`…`</output_format>`
  - Utiliser des noms de balises cohérents à travers tous les prompts du projet
  - Applicable immédiatement à `best practices_prompt.md`, `audit_structural_prompt.md`, `audit_ai_driven_prompt.md`

**Effort :** XS (modifications rédactionnelles, pas de code)
**Impact estimé :** Réduction des mauvaises interprétations sur les prompts d'audit complexes — validé par Anthropic comme technique de réduction d'erreur.

---

### BP-07 — Aucun exemple few-shot dans les fichiers de prompt

**Source :** Anthropic API Docs — Prompting best practices ("Use examples effectively — few-shot / multishot prompting")
**Description :** 3–5 exemples concrets dans des balises `<example>` améliorent significativement l'alignement du format et du niveau de détail. Claude généralise le style depuis les exemples et les applique à de nouveaux cas.
**Pourquoi pertinent pour ALPHAEDGE + Copilot VSCode :** Les prompts d'audit (`best practices_prompt.md`, `audit_structural_prompt.md`, `audit_ai_driven_prompt.md`) ne contiennent aucun exemple du format attendu en sortie. Claude doit deviner le niveau d'analyse voulu (résumé bullet vs tableau détaillé avec source + ligne + statut).
**Comment l'appliquer concrètement :**
  - Ajouter un court `<example>` dans chaque prompt d'audit, montrant 1 entrée complète du tableau attendu (source, description, pertinence, application concrète, statut)
  - Les exemples doivent être variés : 1 BP "déjà en place ✅" et 1 BP "manquante 🔴" pour couvrir les deux cas
  - Un exemple doit couvrir un cas "non applicable (CLI)" pour que Claude sache comment traiter ce cas

**Effort :** S
**Impact estimé :** Output des audits plus homogène entre les relances, niveau de détail prévisible, réduction des omissions de champs.

---

### BP-08 — Pas d'instruction explicite "lire avant de répondre" dans les agents/prompts

**Source :** Anthropic API Docs — Prompting best practices ("Minimizing hallucinations in agentic coding — `<investigate_before_answering>`")
**Description :** "Never speculate about code you have not opened. If the user references a specific file, you MUST read the file before answering." Envelopper dans un bloc XML `<investigate_before_answering>` donne un poids structurel à cette contrainte.
**Pourquoi pertinent pour ALPHAEDGE + Copilot VSCode :** Plusieurs sessions ont produit des réponses incorrectes parce que Copilot a inféré l'état d'un fichier sans le lire (ex: réponse "l'audit existe déjà" sans lire le prompt pour détecter le changement). Le motif `<investigate_before_answering>` est une défense explicite contre ce type d'erreur.
**Comment l'appliquer concrètement :**
  - Ajouter dans `agents/dev_engineer.md` et `agents/code_auditor.md` :
    ```
    <investigate_before_answering>
    Never speculate about code you have not opened. Read relevant files before
    answering questions about the codebase. If the user references a file or
    prompt, read it first to detect any changes before assuming its current state.
    </investigate_before_answering>
    ```
  - Ajouter dans les prompts d'audit (`best practices_prompt.md`, `audit_structural_prompt.md`) : "Lis toujours le fichier prompt complet avant de vérifier si un audit existant est encore valide."

**Effort :** XS
**Impact estimé :** Réduction directe des erreurs de type "réponse sans lecture préalable" — pattern validé par Anthropic dans leur guide de prompting agentic.

---

### BP-09 — Règles sans motivation (WHY manquant dans copilot-instructions.md)

**Source :** Anthropic API Docs — Prompting best practices ("Add context to improve performance — provide the reason why a behavior is important")
**Description :** Fournir le contexte/la motivation derrière les règles aide Claude à généraliser correctement dans des situations non explicitement prévues. Un modèle suffisamment intelligent peut inférer le comportement juste si il comprend l'intention.
**Pourquoi pertinent pour ALPHAEDGE + Copilot VSCode :** Plusieurs Hard Stops dans `copilot-instructions.md` et `CLAUDE.md` donnent le QUOI sans le POURQUOI. Ex: "Never use `# type: ignore`" — sans explication, Claude peut contourner cette règle s'il juge que la situation est "différente".
**Comment l'appliquer concrètement :**
  - Pour chaque Hard Stop, ajouter une justification courte entre parenthèses ou en sous-bullet :
    - `"Never use # type: ignore` — silences real type errors; fix the root cause instead"
    - `"Never hardcode risk parameters outside constants.py` — breaks single source of truth, creates silent divergence between backtest and live"
    - `"Never run make build unless .pyx was modified` — Cython compilation is slow and irreversible mid-session"
  - Cible : 5–8 règles prioritaires (Hard Stops), pas toutes les règles
  - Ne pas surcharger — 1 ligne de justification max par règle

**Effort :** S
**Impact estimé :** Meilleure généralisation des règles dans des situations limites imprévues, réduction des contournements inadvertants.

---

## BEST PRACTICES NON APPLICABLES (Claude Code CLI uniquement)

| Practice | Source | Raison |
|----------|--------|--------|
| Hooks (PreToolUse, PostToolUse) | shanraisshan | Requiert la commande `claude` CLI |
| `.claude/commands/` slash commands | shanraisshan / Anthropic | Spécifique Claude Code CLI — `.github/prompts/*.prompt.md` est l'équivalent Copilot |
| `/init` pour générer CLAUDE.md | Anthropic blog | Commande Claude Code CLI |
| `/compact`, `/clear`, `/rewind` | shanraisshan | Commandes Claude Code CLI |
| `/loop`, `/schedule` (tâches récurrentes) | shanraisshan | Claude Code CLI + infrastructure Anthropic |
| `.claude/settings.json` | shanraisshan | Fichier de config Claude Code CLI |
| `.mcp.json` — MCP servers | shanraisshan | API directe Anthropic / Claude Code |
| `.claude/rules/` (split instructions) | shanraisshan | Claude Code CLI — équivalent Copilot: multiple `.instructions.md` |
| Git worktrees + agent teams (tmux) | shanraisshan | Requiert environnement multi-agents CLI |
| `attribution.commit:` (settings.json) | shanraisshan | Claude Code CLI uniquement |
| `/voice`, `/model`, `/context` | shanraisshan | Commandes Claude Code CLI |
| CLAUDE.md auto-exécution | shanraisshan | Le CLAUDE.md est utile comme **contexte** Copilot (#file:CLAUDE.md) mais n'est pas auto-exécuté comme en Claude Code |
| Paramètre `effort` (low/medium/high) | Anthropic API Docs | API Anthropic directe — non exposé via Copilot Pro+ |
| Extended thinking / `budget_tokens` | Anthropic API Docs | Configuration API directe — non disponible via Copilot |
| Prefilled responses (assistant-turn) | Anthropic API Docs | Manipulation directe de la conversation API — hors scope Copilot |
| Adaptive thinking (`thinking: {type: "adaptive"}`) | Anthropic API Docs | API directe — Copilot gère le thinking de façon transparente |
| Subagent orchestration via API | Anthropic API Docs | API directe — l'équivalent Copilot est le subagent `Explore` déjà utilisé |
| Model migration config (Sonnet 4.5 → 4.6) | Anthropic API Docs | Paramètres API — non applicable à Copilot Pro+ |
| LaTeX output control (`\( \)`, MathJax) | Anthropic API Docs | Hors scope — ALPHAEDGE est un projet Python/trading, pas de rendu mathématique |

---

## BEST PRACTICES MANQUANTES — NON PERTINENTES (Claude Code CLI ou hors scope)

| Practice | Source | Raison non pertinente |
|----------|--------|-----------------------|
| Ralph Wiggum Loop (autonomous dev loop) | shanraisshan | Nécessite Claude Code CLI en local |
| Cross-model workflow (Claude Code + Codex) | shanraisshan | Hors scope VSCode Copilot |
| Checkpointing automatique (git-based) | shanraisshan | Fonctionnalité Claude Code interne |
| Status line (context usage bar) | shanraisshan | Interface Claude Code CLI |
| Agent Teams avec coordination parallèle | shanraisshan | Multi-agents CLI simultanés |

---

## SYNTHÈSE PRIORITAIRE

| ID | Description | Effort | Impact | Priorité |
|----|-------------|--------|--------|----------|
| BP-01 | Réduire CLAUDE.md (386→≤200 lignes) | S | 🔴 Élevé | 1 |
| BP-05 | Dédupliquer CLAUDE.md / copilot-instructions.md | S | 🟠 Moyen | 2 |
| BP-02 | Créer 3 skills manquantes (qa, backtest, audit) | M | 🟠 Moyen | 3 |
| BP-08 | Ajouter `<investigate_before_answering>` dans agents/prompts | XS | 🟠 Moyen | 4 |
| BP-09 | Ajouter motivations (WHY) aux Hard Stops | S | 🟠 Moyen | 5 |
| BP-06 | XML structuring dans les fichiers de prompt | XS | 🟡 Mineur | 6 |
| BP-04 | Créer spec files features core | M | 🟡 Futur | 7 |
| BP-07 | Ajouter exemples few-shot dans les prompts d'audit | S | 🟡 Mineur | 8 |
| BP-03 | Structure progressive dans skills | XS | 🟡 Mineur | 9 |

---

*Audit généré par analyse statique + sources web — validé sur codebase ALPHAEDGE au 2026-03-24.*
*Mis à jour le 2026-03-24 après analyse de la 4ème source : Anthropic API Docs — Prompting best practices.*
