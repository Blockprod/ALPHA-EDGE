# PLAN D'ACTION — ALPHAEDGE — 2026-03-20

Sources : `tasks/audits/audit_ai_driven_alphaedge.md`
Total : 🔴 0 · 🟠 3 · 🟡 7 · Effort estimé : ~2h

> **✅ ALL 10 CORRECTIONS COMPLETED — 2026-03-20**
> Tous les fichiers AI-Driven ont été créés en session.
> `make qa` : 504 tests pass, 89% coverage, 0 lint errors, 0 pyright errors.

---

## PHASE 1 — CRITIQUES 🔴

> Aucun point critique identifié dans cet audit. ✅

---

## PHASE 2 — MAJEURES 🟠

> Priorités 1–3 : fichiers structurant le contexte agent pour chaque session.

---

### [C-01] Créer `.claude/rules.md`

Fichier : `.claude/rules.md`
Problème : Fichier absent. Sans lui, l'agent devait re-dériver les règles de modification à chaque session depuis CLAUDE.md et copilot-instructions.md — risque d'oubli de règles critiques (no `Any`, no `# type: ignore`, no `ALPHAEDGE_PAPER=false`).
Correction : Créer `.claude/rules.md` avec :
  - Interdictions absolues (8 règles hard-stop)
  - Ordre de priorité des modifications (capital → risque → exécution → signal → backtest)
  - Obligations post-modification par type de fichier (.pyx, .py, .yaml, .md)
  - Startup checklist 5 points
  - Workflow agent complet
Validation :
  ```powershell
  Test-Path .claude/rules.md
  make qa
  # Attendu : True + 504 tests passing (fichier doc uniquement)
  ```
Dépend de : Aucune
Statut : ✅ 2026-03-20

---

### [C-02] Créer `.claude/context.md`

Fichier : `.claude/context.md`
Problème : Fichier absent. L'agent naviguait le pipeline depuis les commentaires du code source — lent et incomplet. Aucune table centralisée des 29 modules ni des paramètres clés de `constants.py`.
Correction : Créer `.claude/context.md` avec :
  - Pipeline complet tracé depuis le code source (data_feed → fcr → gap → engulfing → risk → order → broker)
  - Table 29 modules avec responsabilités réelles
  - Paramètres clés de `constants.py` (RR=2.5, risk=2%, daily_loss=3%, pip_sizes, IB rates)
  - Ce qui ne doit pas changer sans benchmark OOS
  - Paires supportées et pip sizes par paire
Validation :
  ```powershell
  Test-Path .claude/context.md
  make qa
  # Attendu : True + 504 tests passing
  ```
Dépend de : Aucune
Statut : ✅ 2026-03-20

---

### [C-03] Créer `architecture/decisions.md`

Fichier : `architecture/decisions.md`
Problème : Fichier absent. Les décisions architecturales (Cython pour signal, paper-default, zoneinfo exclusif, all-or-nothing pipeline) n'étaient pas documentées — risque de réverser une décision intentionnelle sans en comprendre les raisons.
Correction : Créer `architecture/decisions.md` avec 8 ADRs :
  - ADR-001 : Cython pour modules de détection (performance + sécurité logique propriétaire)
  - ADR-002 : Paper trading par défaut (`ALPHAEDGE_PAPER=true`)
  - ADR-003 : Pipeline all-or-nothing (STOP à la première étape falsy)
  - ADR-004 : Séparation engine/ ↔ core/ (flux de dépendance unidirectionnel)
  - ADR-005 : `zoneinfo` exclusivement (pas de `pytz`, pas d'offset hardcodé)
  - ADR-006 : `constants.py` source unique de vérité
  - ADR-007 : `ml_filter.py` archivé en `_experimental/`
  - ADR-008 : Bandit dans `qa-strict` uniquement
Validation :
  ```powershell
  Test-Path architecture/decisions.md
  make qa
  # Attendu : True + 504 tests passing
  ```
Dépend de : Aucune
Statut : ✅ 2026-03-20

---

## PHASE 3 — MINEURES 🟡

> Priorités 4–10 : knowledge base domaine + guides agents spécialisés.

---

### [C-04] Créer `knowledge/ibkr_constraints.md`

Fichier : `knowledge/ibkr_constraints.md`
Problème : Contraintes IBKR non documentées (ports, rate limits, codes d'erreur). En session, un agent risquait d'ignorer les pacing violations ou de ne pas reconnaître les codes d'erreur critiques (1100-1102 = déconnexion, 2100 = annulation d'ordre).
Correction : Créer avec :
  - Ports (4002 paper / 4001 live), architecture
  - Rate limiting token-bucket (45 req/s, burst 10)
  - Timeouts (15s connexion, 60s hist, 10s fill)
  - Codes d'erreur IB classifiés (informatifs vs critiques)
  - Types d'ordres disponibles (LMT, MKT, STP)
  - Circuit breaker et idempotence
Validation :
  ```powershell
  Test-Path knowledge/ibkr_constraints.md
  make qa
  # Attendu : True + 504 tests passing
  ```
Dépend de : Aucune
Statut : ✅ 2026-03-20

---

### [C-05] Créer `knowledge/trading_constraints.md`

Fichier : `knowledge/trading_constraints.md`
Problème : Règles de trading FCR non centralisées dans un document agent-lisible. Un agent pouvait mal interpréter les 6 conditions d'entrée ou les paramètres de risk/sizing.
Correction : Créer avec :
  - Stratégie FCR (6 conditions d'entrée exhaustives)
  - Paramètres risque (2% risk, 3% daily loss, 2 trades, 2 pips spread max)
  - Sizing position (micro lots, 0.01–10.0)
  - Sessions UTC avec DST (NYSE/London)
  - Modèles slippage et spread variables
  - Filtres additionnels (corrélation, régime, news, spread spike)
  - Pip sizes par paire · kill switch
Validation :
  ```powershell
  Test-Path knowledge/trading_constraints.md
  make qa
  # Attendu : True + 504 tests passing
  ```
Dépend de : Aucune
Statut : ✅ 2026-03-20

---

### [C-06] Créer `agents/risk_manager.md`

Fichier : `agents/risk_manager.md`
Problème : Aucun guide dédié à la protection du capital pour l'agent. En cas de modification du pipeline, l'agent pouvait ignorer l'ordre de vérification des protections.
Correction : Créer avec :
  - Séquence protection capital (5 étapes ordonnées : daily_limit → position_size → spread → slippage → bracket_valid)
  - Paramètres risque
  - 6 scénarios de risque avec triggers et actions concrètes
  - Checklist risque avant toute modification
Validation :
  ```powershell
  Test-Path agents/risk_manager.md
  make qa
  # Attendu : True + 504 tests passing
  ```
Dépend de : Aucune
Statut : ✅ 2026-03-20

---

### [C-07] Créer `agents/code_auditor.md`

Fichier : `agents/code_auditor.md`
Problème : Checklist de révision code non documentée pour agents. Risque de laisser passer des patterns interdits (credentials, `Any`, `# type: ignore`, imports circulaires).
Correction : Créer avec :
  - Checklist sécurité (credentials, IB, web dashboard)
  - Checklist qualité (imports/types, conventions, Cython)
  - Checklist erreurs silencieuses
  - Checklist avant merge (7 points)
  - Patterns interdits vs corrects (avec exemples)
Validation :
  ```powershell
  Test-Path agents/code_auditor.md
  make qa
  # Attendu : True + 504 tests passing
  ```
Dépend de : Aucune
Statut : ✅ 2026-03-20

---

### [C-08] Créer `agents/dev_engineer.md`

Fichier : `agents/dev_engineer.md`
Problème : Procédure d'ajout de fonctionnalités non documentée. Un agent pouvait ajouter du code sans respecter le workflow Cython obligatoire ou la convention de nommage des tests.
Correction : Créer avec :
  - Procédure 5 étapes ajout fonctionnalité
  - Pipeline CI (make qa/qa-strict/build/test/bandit)
  - Workflow Cython obligatoire (edit → make build → make qa)
  - 8 interdictions absolues
  - Convention nommage tests : `test_<module>_<scenario>.py`
Validation :
  ```powershell
  Test-Path agents/dev_engineer.md
  make qa
  # Attendu : True + 504 tests passing
  ```
Dépend de : Aucune
Statut : ✅ 2026-03-20

---

### [C-09] Créer `agents/quant_researcher.md`

Fichier : `agents/quant_researcher.md`
Problème : Checklist anti-biais statistiques absente. Un agent en mode recherche pouvait introduire du look-ahead bias ou ne pas respecter le protocole IS/OOS/Monte Carlo.
Correction : Créer avec :
  - Checklist anti-biais (look-ahead, survival, overfitting, contamination IS/OOS)
  - Protocole IS/OOS/Monte Carlo obligatoire
  - Paramètres sensibles (RR, range, ATR)
  - Ressources code (backtest.py, monte_carlo.py, walk_forward.py)
Validation :
  ```powershell
  Test-Path agents/quant_researcher.md
  make qa
  # Attendu : True + 504 tests passing
  ```
Dépend de : Aucune
Statut : ✅ 2026-03-20

---

### [C-10] Créer `architecture/system_design.md`

Fichier : `architecture/system_design.md`
Problème : Vue d'ensemble système absente pour nouveaux contributeurs et pour l'agent en début de session. Pipeline, flux de données, sessions, infrastructure de test non documentés dans un seul fichier.
Correction : Créer avec :
  - Vue d'ensemble FCR
  - Diagramme ASCII pipeline complet
  - Flux de données config → modules
  - Sessions NYSE/London avec DST
  - Modules Cython → .pyd → stubs
  - Infrastructure de test
  - QA pipeline complet
Validation :
  ```powershell
  Test-Path architecture/system_design.md
  make qa
  # Attendu : True + 504 tests passing
  ```
Dépend de : Aucune
Statut : ✅ 2026-03-20

---

## SÉQUENCE D'EXÉCUTION

```
Étape 1  →  C-01  (.claude/rules.md — 10 min)
Étape 2  →  C-02  (.claude/context.md — 15 min)
Étape 3  →  C-03  (architecture/decisions.md — 20 min)
Étape 4  →  C-04  (knowledge/ibkr_constraints.md — 10 min)
Étape 5  →  C-05  (knowledge/trading_constraints.md — 15 min)
Étape 6  →  C-06  (agents/risk_manager.md — 10 min)
Étape 7  →  C-07  (agents/code_auditor.md — 10 min)
Étape 8  →  C-08  (agents/dev_engineer.md — 10 min)
Étape 9  →  C-09  (agents/quant_researcher.md — 10 min)
Étape 10 →  C-10  (architecture/system_design.md — 10 min)
          ── make qa ── [vérification baseline QA inchangé] ──
```

> ⚠️ Aucun fichier `.py` ou `.pyx` modifié dans ce plan → `make build` NON requis.
> Ces corrections ne touchent que des fichiers `.md` de documentation agent.
> L'impact sur `make qa` est nul — les 504 tests restent identiques.

---

## CRITÈRES PASSAGE EN PRODUCTION

- [x] Zéro 🔴 ouvert
- [x] `make qa` : 100% pass (lint + pyright + pytest ≥80%)
- [x] `ALPHAEDGE_PAPER=true` intact dans `.env.example`
- [ ] Zéro credential dans les logs loguru *(hors scope de cet audit)*
- [ ] Bracket order `is_valid` vérifié avant envoi IB *(hors scope de cet audit)*
- [ ] `check_daily_limit()` appelé chaque cycle *(hors scope de cet audit)*
- [ ] Paper trading validé 5 sessions NYSE minimum *(hors scope de cet audit)*

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier | Effort | Statut | Date |
|----|-------|----------|---------|--------|--------|------|
| C-01 | Créer `.claude/rules.md` | 🟠 P1 | `.claude/rules.md` | ~10min | ✅ 2026-03-20 | 2026-03-20 |
| C-02 | Créer `.claude/context.md` | 🟠 P2 | `.claude/context.md` | ~15min | ✅ 2026-03-20 | 2026-03-20 |
| C-03 | Créer `architecture/decisions.md` | 🟠 P3 | `architecture/decisions.md` | ~20min | ✅ 2026-03-20 | 2026-03-20 |
| C-04 | Créer `knowledge/ibkr_constraints.md` | 🟡 P4 | `knowledge/ibkr_constraints.md` | ~10min | ✅ 2026-03-20 | 2026-03-20 |
| C-05 | Créer `knowledge/trading_constraints.md` | 🟡 P5 | `knowledge/trading_constraints.md` | ~15min | ✅ 2026-03-20 | 2026-03-20 |
| C-06 | Créer `agents/risk_manager.md` | 🟡 P6 | `agents/risk_manager.md` | ~10min | ✅ 2026-03-20 | 2026-03-20 |
| C-07 | Créer `agents/code_auditor.md` | 🟡 P7 | `agents/code_auditor.md` | ~10min | ✅ 2026-03-20 | 2026-03-20 |
| C-08 | Créer `agents/dev_engineer.md` | 🟡 P8 | `agents/dev_engineer.md` | ~10min | ✅ 2026-03-20 | 2026-03-20 |
| C-09 | Créer `agents/quant_researcher.md` | 🟡 P9 | `agents/quant_researcher.md` | ~10min | ✅ 2026-03-20 | 2026-03-20 |
| C-10 | Créer `architecture/system_design.md` | 🟡 P10 | `architecture/system_design.md` | ~10min | ✅ 2026-03-20 | 2026-03-20 |
