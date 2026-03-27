# ⚡ ALPHAEDGE — AI Agent Entry Point

> **Read this file first.** Review `tasks/lessons.md` at the start of EVERY session — no exceptions.

---

## Session Startup Checklist

Execute in this exact order before touching any file:

1. Read `tasks/lessons.md` — internalize past mistakes
2. Read `docs/ALPHAEDGE_STRUCTURAL_ACTION_PLAN.md` — know what is open
3. Run `make qa` — confirm baseline is green
4. Check `.env.example` — confirm `ALPHAEDGE_PAPER=true` is intact
5. Identify minimal set of files impacted — touch nothing else

---

## ⛔ Hard Stops — Never Do These

> Full rules + rationales: [.github/copilot-instructions.md](.github/copilot-instructions.md)

<important if="modifying any file">


- **Never** modify `core/*.pyx` without explicit user instruction
- **Never** commit `.env`, `*.log`, or proprietary action plan files
- **Never** run `make build` unless a `.pyx` file was intentionally modified
- **Never** use `# type: ignore` / `# pyright: ignore` — fix the root cause
- **Never** use `Any` as a type annotation — it is a rustine
- **Never** hardcode pip values, RR ratios, session times, or risk parameters outside `alphaedge/config/constants.py`
- **Never** touch `timezone.py` or `session_manager.py` without re-running DST edge case tests (CET / CEST / EU-switch / US-switch)
- **Never** mark a task complete without `make qa` green (602 tests)
- **Never** push a `.pyx` edit without `make build` followed by `make qa`

</important>

---

## Project Identity

| Field | Value |
|-------|-------|
| Name | ALPHAEDGE — FCR Forex Trading Bot |
| Python | **3.11.9 strictly** — never use 3.12+ syntax |
| Stack | Python / Cython 3.0 / ib_insync / loguru / Rich / vectorbt |
| Broker | Interactive Brokers via IB Gateway |
| Market | Forex — EUR/USD, GBP/USD, USD/JPY (configurable) |
| Session | NYSE open 9:30–10:30 EST (15:30–16:30 CET / 14:30–15:30 CEST) |
| Mode | Paper trading default (`ALPHAEDGE_PAPER=true`) |
| Developer TZ | Europe/Paris — DST-aware via `zoneinfo` exclusively |

---

## Architecture

> Contrats complets + signatures : [docs/ALPHAEDGE_INTERFACES.md](docs/ALPHAEDGE_INTERFACES.md)
> Modules + responsabilités : [architecture/module_responsibilities.md](architecture/module_responsibilities.md)

`engine/` → `core/` → `config/` → `utils/` — top-down uniquement, aucun import circulaire.

```
alphaedge/
  config/      — constantes + loader YAML (toujours éditer constants.py, jamais hardcoder)
  core/        — détecteurs Cython (.pyx) + stubs Python (_stubs/) — ne jamais éditer sans instruction
  engine/      — orchestration live + backtest (exclu de la couverture tests)
  tests/       — pytest (602 tests, couverture ≥80% sur config/utils/core/)
.github/
  skills/      — workflows réutilisables (audit-workflow · cython-build · run-qa · run-backtest)
  prompts/     — templates tâches récurrentes (add-test · cython-build · new-util)
  specs/       — contrats comportement fonctions critiques (fcr · order · risk · backtest)
tasks/
  audits/      — prompts code/ et methode/ + resultats/ (rapports d'audit)
  corrections/ — plans d'action datés + prompts d'exécution (generate · execute)
  lessons.md   — leçons IA accumulées — LIRE EN PREMIER
agents/        — rôles spécialisés (#file:agents/<role>.md pour activer)
architecture/  — ADR + responsabilités modules
knowledge/     — contraintes IBKR + marché Forex
```

---

## Cython Edit Workflow

Après tout `.pyx` : **`make build` → `make qa`** — les deux doivent passer.
Les `.pyd`/`.so` sont le runtime — un `.pyx` sans `make build` est silencieusement cassé.

---

## Return Value Contracts

> Contrats complets + signatures : [docs/ALPHAEDGE_INTERFACES.md](docs/ALPHAEDGE_INTERFACES.md)

**Pipeline tout-ou-rien : un STOP à n'importe quelle étape annule le trade.**

| Function | Falsy return | Behavior |
|----------|-------------|----------|
| `detect_fcr(...)` | `None` | STOP — do not proceed |
| `detect_gap(...)` | `detected: False` | STOP — do not proceed |
| `detect_engulfing(...)` | `None` | STOP — no order |
| `calculate_position_size(...)` | `is_valid: False` | STOP — log WARNING |
| `check_daily_limit(...)` | `limit_breached: True` | STOP ALL — log CRITICAL |
| `create_bracket_order(...)` | `is_valid: False` | STOP — log rejection_reason |

---

## Timezone — Critical Note

- UTC en interne · dashboard : UTC + Europe/Paris
- NYSE open = **15:30 CET (hiver) / 14:30 CEST (été)** — gap DST EU/US ≈ 1 semaine/an
- `zoneinfo` exclusivement — jamais `pytz`, jamais offsets hardcodés
- **Jamais toucher `timezone.py` ou `session_manager.py`** sans relancer les tests DST

---

## QA Commands

```powershell
make qa      # lint + mypy + tests (baseline — doit toujours passer)
make build   # après modification .pyx uniquement
```

> Workflow complet : [.github/copilot-instructions.md](.github/copilot-instructions.md)

---

## Workflow Orchestration

- **Plan mode obligatoire** pour toute tâche ≥ 3 étapes — STOP et re-plan si ça dévie
- **Avant toute modification de code — 4 questions :**
  1. Ai-je lu tous les fichiers que je vais modifier ? (citer fichier:ligne avant d'agir)
  2. Ai-je un plan en N étapes validé avant d'agir ?
  3. Y a-t-il des informations manquantes ? (explorer d'abord, modifier ensuite)
  4. Comment vais-je valider le changement ? (`make qa` suffit ? test dédié requis ?)
- **Agents spécialisés disponibles :** invoquer via `#file:agents/<role>.md`
  (`code_auditor` · `dev_engineer` · `quant_researcher` · `risk_manager`)
- **Subagent `Explore`** pour toute exploration — garde le contexte principal propre
- **Après toute correction** : mettre à jour `tasks/lessons.md` — non-négociable
- **Bug report reçu** → corriger directement, sans demander de guidage
- **Jamais marquer terminé** sans `make qa` vert (574 tests)

---

## Task Management

1. **Plan First** — todo list avec items actionnables
2. **Track Progress** — marquer ✅ immédiatement après chaque item
3. **Explain Changes** — résumé haut niveau à chaque étape
4. **Capture Lessons** — `tasks/lessons.md` après toute correction

---

## Convention de fichiers `tasks/` — Règle absolue

Tout fichier créé dans `tasks/` doit commencer par ce frontmatter exact :

```yaml
---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: <nom_du_fichier_résultat>
derniere_revision: YYYY-MM-DD
creation: YYYY-MM-DD à HH:MM
---
```

Les prompts d'audit (`tasks/audits/code/`) doivent se terminer par un bloc `SORTIE OBLIGATOIRE` avec instruction de création du fichier résultat + confirmation chat. Modèle de référence : `tasks/audits/code/audit_trade_journal_prompt.md`.

**Ne jamais créer un fichier `tasks/` sans ce template.**

---

## Core Principles

- **Simplicity First** — impact minimal de code
- **No Laziness** — causes racines, pas de fix temporaires
- **Audit Before Modify** — lire + citer fichier:ligne avant toute modification
- **Git workflow :** committer dès qu'une correction passe `make qa` — ne pas attendre la fin du plan multi-étapes
  - Format : `fix(scope): description` · `feat(scope): description` · `cython: description`
  - Ex : `fix(journal): atomic CSV write`, `feat(backtest): add sl_pips column`
  - PRs focalisées : une correction / un audit par PR · squash merge

---

## Gitignored / Proprietary

| File | Reason |
|------|--------|
| `ALPHAEDGE_ACTION_PLAN.md` | Proprietary — do not regenerate |
| `.env` | IB credentials — use `.env.example` only |
| `alphaedge/logs/*.log` | Runtime logs — never committed |

---

## Current Project Health

| Document | Purpose |
|----------|---------|
| `docs/ALPHAEDGE_STRUCTURAL_ACTION_PLAN.md` | Open tasks, priorities |
| `docs/ALPHAEDGE_MASTER_AUDIT.md` | Last full technical audit |
| `tasks/lessons.md` | AI agent lessons (read every session) |

> Baseline : **574 tests — 100% pass · Coverage ≥80%** sur `config/`, `utils/`, `core/`
