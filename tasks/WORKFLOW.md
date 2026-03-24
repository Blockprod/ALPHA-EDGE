---
type: guide
projet: ALPHAEDGE
broker: Interactive Brokers (IB Gateway)
stack: Python 3.11.9 · Cython 3.0 · ib_insync · Windows
derniere_revision: 2026-03-22
creation: 2026-03-20 à 15:29
---

# WORKFLOW — Audit → Plan → Corrections
# ALPHAEDGE — FCR Forex Trading Bot (IB Gateway)

Chaque audit suit le même pipeline en **3 étapes** :

| Étape | Prompt | Mode | Produit |
|:---:|---|:---:|---|
| **A** | `audit_<type>_prompt.md` | Ask / Agent | `tasks/audits/resultats/audit_<type>_alphaedge.md` |
| **B** | `generate_action_plan_prompt.md` | Agent | `tasks/corrections/plans/PLAN_ACTION_<type>_[DATE].md` |
| **C** | `execute_corrections_prompt.md` | Agent | corrections appliquées · ⏳ → ✅ |

> Toujours exécuter **A → B → C** dans l'ordre strict.
> Ne jamais lancer B sans avoir l'audit A complet.

---

## AUDITS DISPONIBLES

| # | Audit | Dimension | Mode A |
|:---:|---|---|:---:|
| 1 | [Structurel](#1--structurel) | Pipeline FCR · SRP · Couplage modules · Cython ↔ Python | Ask |
| 2 | [AI-Driven](#2--ai-driven-file-engineering) | Fichiers agents · architecture/ · knowledge/ · copilot-instructions | Agent |
| 3 | [Email & Alertes](#3--email--alertes) | Couverture notifications · tempêtes · sécurité contenu | Agent |
| 4 | [IA / ML](#4--ia--ml) | ML sur signal FCR · Régime de marché · Sizing adaptatif | Ask |
| 5 | [Technique & Sécurité](#5--technique--sécurité) | Credentials IB · paper/live · robustesse asyncio | Ask |
| 6 | [Cython & Build](#6--cython--build) | Intégrité .pyx ↔ .pyd · Stubs · reproductibilité build | Ask |
| 7 | [Stratégique (FCR)](#7--stratégique-fcr) | Intégrité signal · Walk-forward · RR ratio · DST | Ask |
| 8 | [Master](#8--master) | Audit complet toutes dimensions | Agent |
| 9 | [Modernisation Python](#9--modernisation-python-syntax) | Ruff · Pyright · syntaxe 3.11.9 · annotations | Agent |
| 10 | [Latence Institutionnel](#10--latence-institutionnel) | Chemin critique · Cython vs stubs · Latence IBKR · asyncio · I/O synchrones | Agent |
| 11 | [Best Practices AI](#11--best-practices-ai) | Claude · Copilot Pro+ · VSCode · fichiers contexte · patterns prompts | Agent |
| 12 | [Journal de Trading](#12--journal-de-trading) | Traçabilité live · LiveTradeRecord · réconciliation live/backtest · persistance | Agent |

---

## `1 · STRUCTUREL`

> Pipeline FCR · Couplage modules · SRP · Dépendances Cython ↔ Python

**Produit A** : `tasks/audits/resultats/audit_structural_alphaedge.md`

**A — Audit**
```
#file:tasks/audits/code/audit_structural_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `2 · AI-DRIVEN (FILE ENGINEERING)`

> État des fichiers AI-Driven · copilot-instructions · CLAUDE.md · agents/ · architecture/ · knowledge/ · Plan de migration

**Produit A** : `tasks/audits/resultats/audit_ai_driven_alphaedge.md`

**A — Audit & restructuration**
```
#file:tasks/audits/methode/audit_ai_driven_prompt.md
Lance cet audit et cette restructuration sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `3 · EMAIL & ALERTES`

> Système d'envoi (email · Telegram · Discord) · couverture des événements · protection contre les tempêtes · sécurité du contenu

**Produit A** : `tasks/audits/resultats/audit_email_alerts_alphaedge.md`

**A — Audit**
```
#file:tasks/audits/code/audit_email_alerts_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `4 · IA / ML`

> Pertinence ML sur signal FCR · Régime de marché · Sizing adaptatif · Agents IB · SHAP backtest

**Produit A** : `tasks/audits/resultats/audit_ia_ml_alphaedge.md`

**A — Audit**
```
#file:tasks/audits/methode/audit_ia_ml_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `5 · TECHNIQUE & SÉCURITÉ`

> Sécurité credentials IB · Séparation paper/live · Robustesse IB Gateway · Gestion erreurs asyncio

**Produit A** : `tasks/audits/resultats/audit_technical_alphaedge.md`

**A — Audit**
```
#file:tasks/audits/code/audit_technical_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `6 · CYTHON & BUILD`

> Intégrité .pyx ↔ .pyd · Stubs · Reproductibilité build · setup.py

**Produit A** : `tasks/audits/resultats/audit_cython_alphaedge.md`

**A — Audit**
```
#file:tasks/audits/code/audit_cython_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

## `7 · STRATÉGIQUE (FCR)`

> Intégrité signal FCR · Walk-forward · Cohérence backtest ↔ live · RR ratio · Gestion risque DST

**Produit A** : `tasks/audits/resultats/audit_strategic_alphaedge.md`

**A — Audit**
```
#file:tasks/audits/code/audit_strategic_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `8 · MASTER`

> Audit complet couvrant toutes les dimensions du projet en une seule passe

**Produit A** : `tasks/audits/resultats/audit_master_alphaedge.md`

**A — Audit**
```
#file:tasks/audits/code/audit_master_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `9 · MODERNISATION PYTHON SYNTAX`

> Ruff auto-fix · Pyright erreurs résiduelles · syntaxe Python 3.11.9 · annotations de type · dossier par dossier

**Produit** : corrections appliquées directement · `make qa` vert

**A — Audit & corrections**
```
#file:tasks/audits/code/audit_modernize_python_syntax_prompt.md
Lance cet audit sur le workspace.
```



> ⚠️ Cet audit intègre les étapes B et C directement —
> il corrige et valide en une seule passe. Aucun plan intermédiaire requis.

---

## `10 · LATENCE INSTITUTIONNEL`

> Chemin critique signal→ordre · Cython vs stubs · Latence IBKR · Event loop asyncio · I/O synchrones · Fraîcheur données · Résilience

**Produit A** : `tasks/audits/resultats/audit_latence_alphaedge.md`

**A — Audit**
```
#file:tasks/audits/code/audit_latence_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `11 · BEST PRACTICES AI`

> Best practices Claude · Copilot Pro+ · VSCode · fichiers contexte AI-Driven · patterns prompts réutilisables

**Produit A** : `tasks/audits/resultats/audit_best_practices_alphaedge.md`

**A — Audit**
```
#file:tasks/audits/methode/best practices_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `12 · JOURNAL DE TRADING`

> Traçabilité live · LiveTradeRecord · hook `_on_trade_closed` · rotation CSV · réconciliation live/backtest · maturité journal

**Produit A** : `tasks/audits/resultats/audit_trade_journal_alphaedge.md`

**A — Audit**
```
#file:tasks/audits/code/audit_trade_journal_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```
