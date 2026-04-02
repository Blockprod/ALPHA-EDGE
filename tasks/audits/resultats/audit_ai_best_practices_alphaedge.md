---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: audit_ai_best_practices_alphaedge.md
derniere_revision: 2026-03-26
creation: 2026-03-26
---

# AUDIT — MEILLEURES PRATIQUES AI AGENT — ALPHAEDGE
**Date :** 2026-03-26 · **Rédacteur :** Copilot Agent (sonnet-4.6)
**Périmètre :** Infrastructure AI-agent · Hooks · MCP · Memory · Workflow · Finance best practices
**Sources :** Top 100 Claude Code For Finance Use Cases · How to Build an AI Agent · HyperAgents · Comment utiliser Claude à 99% · Claude Code workspace best practices

---

## BLOC 1 — HOOKS SYSTÈME (`.claude/settings.json`)

### 1.1 Situation actuelle

Les Hard Stops définis dans `CLAUDE.md` et `.claude/rules.md` sont **déclaratifs** —
l'agent peut les ignorer sans mécanisme de blocage automatique. Il n'existe aucun fichier
`.claude/settings.json`, aucun `PreToolUse`, `PostToolUse`, `SessionStart`, `SessionEnd`,
ni `PreCommit` hook dans le projet.

### 1.2 Impact

Sans hooks déterministes :
- Un agent peut exécuter `make build` sans modification `.pyx` préalable
- Un agent peut modifier un fichier `.py` sans déclencher `ruff check` automatiquement
- Un agent peut fermer une session sans sauvegarder les leçons apprises


### 1.3 Solution

Créer `.claude/settings.json` avec :

```json
{
  "permissions": {
    "allow": ["Bash(make qa)", "Bash(make test)", "Bash(make build)"],
    "deny": ["Bash(git push --force)", "Bash(rm -rf *)"]
  },
  "hooks": {
    "PostToolUse": [{
      "matcher": "Write",
      "hooks": [{"type": "command",
                 "command": ".venv/Scripts/python.exe -m ruff check $FILE"}]
    }],
    "PreCommit": [{
      "matcher": ".*",
      "hooks": [{"type": "command",
                 "command": ".venv/Scripts/python.exe scripts/pre_commit_guard.py"}]
    }],
    "SessionStart": [{
      "matcher": ".*",
      "hooks": [{"type": "command",
                 "command": ".venv/Scripts/python.exe -m pytest alphaedge/tests/ -q --tb=no --co -q 2>&1 | tail -1"}]
    }]
  },
  "env": {
    "MAX_THINKING_TOKENS": "15000",
    "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "60"
  }
}
```

**Sévérité :** 🔴 Critique
**Impact :** Hard stops deviennent non-contournables — zéro dépendance à la discipline de l'agent.
**Effort :** 2h

---

## BLOC 2 — SLASH COMMANDS (`.claude/commands/`)

### 2.1 Situation actuelle

Les prompts de workflows sont dans `tasks/` (audits, corrections, fix_errors) mais sont
**passifs** : l'utilisateur doit les ouvrir, copier et coller. Il n'existe aucun répertoire
`.claude/commands/`. Les skills `.github/skills/` nécessitent une invocation manuelle via
`copilot-skill:`.

### 2.2 Impact

- Friction d'invocation élevée pour les workflows répétés (QA, audit, backtest, fix)
- Risque d'erreur sur le choix du bon prompt parmi 11 fichiers audit + 5 fix_errors
- Aucun raccourci pour les actions les plus fréquentes de session

### 2.3 Solution

Créer `.claude/commands/` avec 6 commandes :

| Commande | Fichier | Action |
|----------|---------|--------|
| `/qa` | `commands/qa.md` | Lance `make qa`, affiche résumé pass/fail |
| `/audit` | `commands/audit.md` | Pipeline A→B→C complet (skill audit-workflow) |
| `/backtest` | `commands/backtest.md` | Lance backtest + skill run-backtest |
| `/fix` | `commands/fix.md` | Pipeline P1→P5 (SCAN→PLAN→FIX→VERIFY→FINAL QA) |
| `/lessons` | `commands/lessons.md` | Affiche `tasks/lessons.md` + propose entrée |
| `/session-end` | `commands/session-end.md` | Résumé session + mise à jour plan structurel |

**Sévérité :** 🔴 Critique
**Impact :** Temps d'invocation workflow : 3 secondes au lieu de 2 minutes.
**Effort :** 1h

---

## BLOC 3 — PROFIL UTILISATEUR (`.claude/about-me.md`)

### 3.1 Situation actuelle

`.claude/rules.md` décrit les règles du **projet** — pas le profil de l'**utilisateur**.
L'agent doit lire 340 lignes de `CLAUDE.md` pour inférer le style de communication, le
niveau d'autonomie accordé et le fuseau horaire. Aucun fichier `about-me.md` n'existe.

### 3.2 Impact

- Calibrage de l'agent plus lent à chaque nouvelle session
- Style de réponses (verbosité, langue, confirmation attendue) non explicité
- Niveau d'autonomie (commit OUI/NON, architecture OUI/NON) non déclaré explicitement

### 3.3 Solution

Créer `.claude/about-me.md` avec :
- Rôle : trader indépendant + développeur Python solo, expertise IB Gateway
- Timezone : Europe/Paris (CET/CEST)
- Style : réponses courtes, citer fichier:ligne, français sauf code
- Autonomie : modifications fichiers OUI · commits NON · architecture → valider d'abord

**Sévérité :** 🔴 Critique
**Impact :** Calibrage immédiat de l'agent sans lecture complète de CLAUDE.md.
**Effort :** 20 min

---

## BLOC 4 — SERVEUR MCP (`.mcp.json`)

### 4.1 Situation actuelle

Aucun fichier `.mcp.json` n'existe. Aucun serveur MCP n'est configuré. L'agent ne peut
pas interagir avec GitHub (PRs, issues), des bases de données externes, ni exécuter des
outils custom depuis le pipeline d'agent.

### 4.2 Impact

- Création de PRs post-correction = manuelle
- Aucune query possible vers un historique structuré des audits
- Impossible d'appeler des APIs IBKR de diagnostic depuis l'agent

### 4.3 Solution

Créer `.mcp.json` avec au minimum le serveur GitHub :

```json
{
  "mcpServers": {
    "github": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-github"],
      "env": {"GITHUB_TOKEN": "${GITHUB_TOKEN}"}
    }
  }
}
```

**Sévérité :** 🟠 Majeur
**Impact :** PRs de correction créées automatiquement après plan validé.
**Effort :** 1h

---

## BLOC 5 — MEMORY SYSTÈME QUERYABLE

### 5.1 Situation actuelle

La mémoire du projet est entièrement file-based (`.md` non structurés) :
- `tasks/lessons.md` — format libre, non queryable
- `tasks/audits/resultats/` — 13 fichiers .md non indexés
- Aucun SQL, aucun vecteur, aucun JSONL

### 5.2 Impact

- Impossible de répondre à "quels fichiers ont été corrigés le plus souvent ?"
- Impossible de tracker l'évolution du nombre de tests au fil des sessions
- Aucune détection automatique de patterns récurrents entre audits

### 5.3 Solution

Créer deux fichiers structurés dans `alphaedge/cache/` :

```
alphaedge/cache/
  sessions.jsonl      ← journal structuré des sessions AI (date, QA résultat, nb fixes)
  audit_index.json    ← index des audits (date, sévérité, fichiers, statut corrections)
```

Format `sessions.jsonl` (une ligne par session) :
```json
{"date": "2026-03-26", "tests": 610, "ruff": 0, "fixes": 7, "blockers": 0}
```

**Sévérité :** 🟠 Majeur
**Impact :** Mémoire queryable via `python -c` ou `grep` depuis l'agent.
**Effort :** 1h

---

## BLOC 6 — LATENCY BENCHMARK PIPELINE

### 6.1 Situation actuelle

`make qa` = lint + types + coverage. La latence du pipeline signal (signal → order) n'est
pas mesurée ni testée. Pour un bot de trading live, la latence est aussi critique que la
correction fonctionnelle.

### 6.2 Impact

- Une régression de performance post-refactoring n'est pas détectée
- Aucun seuil de latence n'est contractualisé (ex. < 100ms signal → order)
- `engine/` exclu de la couverture mais aucun benchmark compensatoire

### 6.3 Solution

Ajouter dans `Makefile` :
```makefile
bench:
    python -m pytest alphaedge/tests/ -k "benchmark" -q --tb=no
```

Créer `alphaedge/tests/test_pipeline_latency.py` avec un test vérifiant que le cycle
complet signal → order generation < 100ms (via `time.perf_counter`).

**Sévérité :** 🟠 Majeur
**Impact :** Contrat de performance contractualisé et testé à chaque QA.
**Effort :** 2h

---

## BLOC 7 — FEATURE STORE AVEC SCHÉMA ENFORCED

### 7.1 Situation actuelle

`engine/ml_filter.py` et `engine/regime_filter.py` produisent des features ML sans
schéma explicite. Lors d'un re-train ou ajout de feature, aucun contrat ne garantit la
cohérence entre la définition de la feature et son usage.

### 7.2 Impact

- Régression silencieuse possible si une feature change de type ou disparaît
- Aucun test de régression sur le schéma des features
- `ml_filter.py` est exclu de la couverture : risque zero-test sur le contrat ML

### 7.3 Solution

Créer `alphaedge/engine/feature_schema.py` avec un `TypedDict` définissant les features
attendues, et un test dans `alphaedge/tests/` qui vérifie que le pipeline ML produit
exactement ce schéma.

**Sévérité :** 🟡 Mineur
**Impact :** Régression ML détectée à chaque `make qa`.
**Effort :** 3h

---

## BLOC 8 — REGIME CLASSIFIER COMME MODULE PERMANENT

### 8.1 Situation actuelle

`engine/regime_filter.py` est présent mais traité comme module périphérique (exclu de la
couverture, pas de spec dans `.github/specs/`). Son statut exact dans le pipeline n'est
pas documenté dans les ADRs.

### 8.2 Impact

- Peut être modifié sans contrat de régression
- Pas de spec comportementale → n'importe quel changement est "valide"

### 8.3 Solution

Ajouter un ADR-009 dans `architecture/decisions.md` documentant le rôle du regime
classifier dans le pipeline, et créer `alphaedge/tests/test_regime_filter_contract.py`
avec les cas limites (bull/bear/sideways).

**Sévérité :** 🟡 Mineur
**Impact :** Module soumis au même protocole de contrat que les autres.
**Effort :** 2h

---

## BLOC 9 — SESSION-END AUTO-UPDATE LESSONS.MD

### 9.1 Situation actuelle

`tasks/lessons.md` est mis à jour manuellement après chaque correction de l'utilisateur.
Le hook `SessionEnd` n'existe pas — aucun mécanisme automatique ne propose une entrée
lessons à la fin d'une session de travail.

### 9.2 Impact

- Leçons non capturées si l'utilisateur oublie de demander
- Patterns récurrents non détectés entre sessions

### 9.3 Solution

Le hook `SessionEnd` (GAP-01) appelle un prompt qui analyse les fichiers modifiés pendant
la session et génère un candidat d'entrée `lessons.md` soumis à validation avant écriture.

**Sévérité :** 🟡 Mineur
**Impact :** Mémoire AI auto-alimentée — concept HyperAgents appliqué.
**Effort :** 1h (dépend de GAP-01)

---

## SYNTHÈSE

| ID | Bloc | Description | Sévérité | Impact | Effort |
|----|------|-------------|----------|--------|--------|
| GAP-01 | Hooks système | `.claude/settings.json` + Pre/PostToolUse + SessionStart | 🔴 Critique | Hard stops déterministes | 2h |
| GAP-02 | Slash commands | `.claude/commands/` — 6 workflows invocables | 🔴 Critique | Friction invocation ÷10 | 1h |
| GAP-03 | Profil utilisateur | `.claude/about-me.md` | 🔴 Critique | Calibrage agent immédiat | 20min |
| GAP-04 | Serveur MCP | `.mcp.json` GitHub MCP | 🟠 Majeur | PRs automatiques | 1h |
| GAP-05 | Memory queryable | `cache/sessions.jsonl` + `audit_index.json` | 🟠 Majeur | Historique queryable | 1h |
| GAP-06 | Latency benchmark | `make bench` + `test_pipeline_latency.py` | 🟠 Majeur | Contrat perf contractualisé | 2h |
| GAP-07 | Feature store | `feature_schema.py` + TypedDict enforced | 🟡 Mineur | Régression ML détectée | 3h |
| GAP-08 | Regime classifier | ADR-009 + test contrat | 🟡 Mineur | Module sous contrat | 2h |
| GAP-09 | SessionEnd lessons | Hook auto-update lessons.md | 🟡 Mineur | Mémoire auto-alimentée | 1h |

**Total : 🔴 3 · 🟠 3 · 🟡 3 · Effort estimé : ~13h**
