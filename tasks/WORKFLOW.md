---
type: guide
projet: ALPHAEDGE
broker: Interactive Brokers (IB Gateway)
stack: Python 3.11.9 · Cython 3.0 · ib_insync · Windows
derniere_revision: 2026-03-26
creation: 2026-03-20 à 15:29
---

# WORKFLOW — Audit → Plan → Corrections
# ALPHAEDGE — Momentum+Carry Forex Trading Bot (IB Gateway)

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
| 2 | [Cython & Build](#2--cython--build) | Intégrité .pyx ↔ .pyd · Stubs · reproductibilité build | Ask |
| 3 | [Technique & Sécurité](#3--technique--sécurité) | Credentials IB · paper/live · robustesse asyncio | Ask |
| 4 | [AI-Driven](#4--ai-driven-file-engineering) | Fichiers agents · architecture/ · knowledge/ · copilot-instructions | Agent |
| 5 | [Email & Alertes](#5--email--alertes) | Couverture notifications · tempêtes · sécurité contenu | Agent |
| 6 | [Latence Institutionnel](#6--latence-institutionnel) | Chemin critique · Cython vs stubs · Latence IBKR · asyncio · I/O synchrones | Agent |
| 7 | [IA / ML](#7--ia--ml) | ML sur signal FCR · Régime de marché · Sizing adaptatif | Ask |
| 8 | [Pipeline (Ingénierie FCR)](#8--pipeline-ingénierie-fcr) | Cohérence config ↔ live ↔ backtest · Pipeline all-or-nothing · Coûts · Multi-paires | Ask |
| 9 | [Stratégique (FCR)](#9--stratégique-fcr) | Intégrité signal · Walk-forward · RR ratio · DST | Ask |
| 10 | [Journal de Trading](#10--journal-de-trading) | Traçabilité live · LiveTradeRecord · réconciliation live/backtest · persistance | Agent |
| 11 | [Best Practices AI](#11--best-practices-ai) | Claude · Copilot Pro+ · VSCode · fichiers contexte · patterns prompts | Agent |
| 12 | [Master](#12--master) | Audit complet toutes dimensions | Agent |
| 13 | [Migration Momentum + Carry](#13--migration-momentum--carry) | Inventaire FCR à supprimer · modules à créer · compatibilité backtest engine · plan phases | Agent |
| 14 | [Modernisation Python](#14--modernisation-python-syntax) | Ruff · Pyright · syntaxe 3.11.9 · annotations | Agent |
| 15 | [AI Best Practices](#15--ai-best-practices) | Hooks · Commands · MCP · Memory · Latency · Feature store | Agent |
| 16 | [Fix Errors](#16--fix-errors) | Correction erreurs Ruff · Mypy · Pytest — pipeline P1 → P5 | Agent |
| 17 | [Taille de Lot (Sizing)](#17--taille-de-lot-sizing) | Formule lot size · Compounding · Asymétrie paires · Pistes ATR-scaling · Kelly | Agent |

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

## `2 · CYTHON & BUILD`

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

---

## `3 · TECHNIQUE & SÉCURITÉ`

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

## `4 · AI-DRIVEN (FILE ENGINEERING)`

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

## `5 · EMAIL & ALERTES`

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

## `6 · LATENCE INSTITUTIONNEL`

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

## `7 · IA / ML`

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

## `8 · PIPELINE (INGÉNIERIE FCR)`

> Cohérence des paramètres config ↔ live ↔ backtest · Pipeline all-or-nothing · Données M1/M5 · Coûts · Multi-paires
> **Complément de l'audit 9** — vérifie que le câblage correspond aux hypothèses statistiques

**Produit A** : `tasks/audits/resultats/audit_pipeline_alphaedge.md`

**A — Audit**
```
#file:tasks/audits/code/audit_pipeline_prompt.md
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

## `9 · STRATÉGIQUE (FCR)`

> Validité statistique de l'edge · Performance par paire/régime · IS/OOS · Calibration filtres · Coûts · Kelly
> **Source principale : reports/ALPHAEDGE_backtest_results.csv** — métriques réelles uniquement

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

## `10 · JOURNAL DE TRADING`

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

## `12 · MASTER`

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

## `13 · MIGRATION MOMENTUM + CARRY`

> Inventaire FCR à supprimer · modules à conserver · modules à créer (momentum_detector, carry_signal) · compatibilité backtest engine Daily/H4 · plan de migration 6 phases
> **Stratégie cible : Time Series Momentum + FX Carry (swing, Daily/H4)**

**Produit A** : `tasks/audits/resultats/audit_migration_momentum_carry_alphaedge.md`

**A — Audit**
```
#file:tasks/audits/code/audit_migration_momentum_carry_prompt.md
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

## `14 · MODERNISATION PYTHON SYNTAX`

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

## `15 · AI BEST PRACTICES`

> Hooks système · Slash commands · Profil utilisateur · MCP · Memory queryable · Latency benchmark · Feature store · Regime classifier contrat · SessionEnd auto-lessons

**Produit A** : `tasks/audits/resultats/audit_ai_best_practices_alphaedge.md`
**Produit B** : `tasks/corrections/plans/PLAN_ACTION_audit_ai_best_practices_alphaedge_2026-03-26.md`

**A — Audit** *(déjà réalisé — 2026-03-26)*
```
#file:tasks/audits/resultats/audit_ai_best_practices_alphaedge.md
```
🔴 3 · 🟠 3 · 🟡 3

**B — Plan d'action** *(déjà généré — 2026-03-26)*
```
#file:tasks/corrections/plans/PLAN_ACTION_audit_ai_best_practices_alphaedge_2026-03-26.md
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `16 · FIX ERRORS`

> Correction des erreurs Ruff · Mypy · Pytest en 5 étapes séquentielles (SCAN → PLAN → FIX → VERIFY → FINAL QA)

**Pipeline P1 → P5** — pas d'audit A ni de plan B : les corrections sont appliquées directement.

**P1 — SCAN**
```
#file:tasks/audits/fix_errors/P1- SCAN_prompt_alphaedge.md
Lance le scan des erreurs sur le workspace.
```

**P2 — PLAN**
```
#file:tasks/audits/fix_errors/P2- PLAN_prompt_alphaedge.md
Génère le plan de correction depuis le scan.
```

**P3 — FIX**
```
#file:tasks/audits/fix_errors/P3- FIX_core_prompt_alphaedge.md
Applique les corrections dans l'ordre défini au P2.
```

**P4 — VERIFY**
```
#file:tasks/audits/fix_errors/P4- VERIFY_prompt_alphaedge.md
Vérifie que chaque correction est complète.
```

**P5 — FINAL QA**
```
#file:tasks/audits/fix_errors/P5- FINAL QA_prompt_alphaedge.md
Run final make qa · vérification ALPHAEDGE_PAPER=true · résumé final.
```

---

## `17 · TAILLE DE LOT (SIZING)`

> Formule lot size · Compounding sur equity · Asymétrie paires (GBPUSD PF=1.25 vs EURUSD PF=1.80) · Exchange rate USDJPY · Pistes : sizing différencié · ATR-scaling du risk_pct · Half-Kelly · Drawdown-scaled sizing
> **Baseline verrouillé** : Sharpe=2.90 · OOS=2.59 · MaxDD=9.00% · 579 trades

**Produit A** : `tasks/audits/resultats/audit_lot_sizing_alphaedge.md`

**A — Audit**
```
#file:tasks/audits/methode/audit_lot_sizing_prompt.md
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
