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

- **Never** set `ALPHAEDGE_PAPER=false` in any file, ever
- **Never** modify `core/*.pyx` without explicit user instruction
- **Never** commit `.env`, `*.log`, or proprietary action plan files
- **Never** run `make build` unless a `.pyx` file was intentionally modified
- **Never** use `# type: ignore` / `# pyright: ignore` — fix the root cause
- **Never** use `Any` as a type annotation — it is a rustine
- **Never** hardcode pip values, RR ratios, session times, or risk parameters outside `alphaedge/config/constants.py`
- **Never** touch `timezone.py` or `session_manager.py` without re-running DST edge case tests (CET / CEST / EU-switch / US-switch)
- **Never** mark a task complete without `make qa` green (504 tests)
- **Never** push a `.pyx` edit without `make build` followed by `make qa`

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

> Pipeline complet + modules : [.github/copilot-instructions.md](.github/copilot-instructions.md)
> Tableau des modules : [architecture/module_responsibilities.md](architecture/module_responsibilities.md)

`engine/` → `core/` → `config/` → `utils/` — top-down uniquement, aucun import circulaire.

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
| `check_daily_limit(...)` | `halt_trading: True` | STOP ALL — log CRITICAL |
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
- **Subagent `Explore`** pour toute exploration — garde le contexte principal propre
- **Après toute correction** : mettre à jour `tasks/lessons.md` — non-négociable
- **Bug report reçu** → corriger directement, sans demander de guidage
- **Jamais marquer terminé** sans `make qa` vert (504 tests)

---

## Task Management

1. **Plan First** — todo list avec items actionnables
2. **Track Progress** — marquer ✅ immédiatement après chaque item
3. **Explain Changes** — résumé haut niveau à chaque étape
4. **Capture Lessons** — `tasks/lessons.md` après toute correction

---

## Core Principles

- **Simplicity First** — impact minimal de code
- **No Laziness** — causes racines, pas de fix temporaires
- **Audit Before Modify** — lire + citer fichier:ligne avant toute modification

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

> Baseline : **504 tests — 100% pass · Coverage ≥80%** sur `config/`, `utils/`, `core/`
