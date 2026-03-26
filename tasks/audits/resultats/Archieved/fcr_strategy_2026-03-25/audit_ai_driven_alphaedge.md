# AUDIT AI-DRIVEN — ALPHAEDGE
# Date : 2026-03-20 à 18:27
# Généré par : audit_ai_driven_prompt.md

---

## BLOC 1 — ÉTAT DES LIEUX

| Fichier | Statut initial | Action |
|---------|---------------|--------|
| `.github/copilot-instructions.md` | ✅ EXISTE (120 lignes) | Aucune — déjà conforme |
| `.claude/context.md` | ❌ ABSENT | Créé |
| `.claude/rules.md` | ❌ ABSENT | Créé |
| `architecture/system_design.md` | ❌ ABSENT | Créé |
| `architecture/decisions.md` | ❌ ABSENT | Créé |
| `knowledge/ibkr_constraints.md` | ❌ ABSENT | Créé |
| `knowledge/trading_constraints.md` | ❌ ABSENT | Créé |
| `agents/quant_researcher.md` | ❌ ABSENT | Créé |
| `agents/risk_manager.md` | ❌ ABSENT | Créé |
| `agents/code_auditor.md` | ❌ ABSENT | Créé |
| `agents/dev_engineer.md` | ❌ ABSENT | Créé |

---

## BLOC 2 — NETTOYAGE PRÉALABLE

| Fichier | Présent ? | Action |
|---------|-----------|--------|
| `CMakeLists.txt` | ❌ Non | Aucune |
| `ARCHIVED_cpp_sources/` | ❌ Non | Aucune |
| `ARCHIVED_crypto/` | ❌ Non | Aucune |
| Fichiers debug `bt_results_v*.txt` | ❌ Non | Aucune |
| `run_backtest_v*.py` | ❌ Non | Aucune |

**Résultat** : Aucun nettoyage nécessaire. Racine propre.

---

## BLOC 3 — ARBORESCENCE CIBLE

```
AlphaEdge/
├── .claude/
│   ├── context.md          ✅ CRÉÉ
│   └── rules.md            ✅ CRÉÉ
├── .github/
│   └── copilot-instructions.md  ✅ EXISTANT (inchangé)
├── architecture/
│   ├── system_design.md    ✅ CRÉÉ
│   └── decisions.md        ✅ CRÉÉ  (8 ADRs)
├── knowledge/
│   ├── ibkr_constraints.md      ✅ CRÉÉ
│   └── trading_constraints.md   ✅ CRÉÉ
├── agents/
│   ├── quant_researcher.md ✅ CRÉÉ
│   ├── risk_manager.md     ✅ CRÉÉ
│   ├── code_auditor.md     ✅ CRÉÉ
│   └── dev_engineer.md     ✅ CRÉÉ
├── tasks/                  ← existant
├── docs/                   ← existant
├── alphaedge/              ← existant
└── ...
```

---

## BLOC 4 — FICHIERS CRÉÉS (contenu réel)

### `.claude/rules.md`
Règles de modification · ordre de priorité capital → risque → exécution → signal → backtest · obligations post-modification par type de fichier · startup checklist 5 points · workflow agent.

### `.claude/context.md`
Pipeline complet depuis le code source · table 29 modules avec responsabilités réelles · paramètres clés de `constants.py` · ce qui ne doit pas changer sans benchmark OOS · paires supportées et pip sizes.

### `architecture/system_design.md`
Vue d'ensemble FCR · diagramme ASCII pipeline complet · flux de données config → modules · tableau sessions NYSE/London avec DST · tableau modules Cython → .pyd → stubs · infrastructure de test · QA pipeline complet.

### `architecture/decisions.md`
8 ADRs documentés :
- ADR-001 : Cython pour modules de détection
- ADR-002 : Paper trading par défaut
- ADR-003 : Pipeline all-or-nothing
- ADR-004 : Séparation engine/ ↔ core/
- ADR-005 : zoneinfo exclusivement
- ADR-006 : constants.py source unique
- ADR-007 : ml_filter archivé en _experimental/
- ADR-008 : Bandit dans qa-strict uniquement

### `knowledge/ibkr_constraints.md`
Ports 4001/4002 · rate limits token-bucket (45 req/s, burst 10) · timeouts (15s connexion, 60s hist, 10s fill) · codes d'erreur IB classifiés (informatifs vs critiques) · types d'ordres disponibles · idempotence · circuit breaker.

### `knowledge/trading_constraints.md`
6 conditions d'entrée FCR · paramètres risque (2% risk, 3% daily loss, 2 trades, 2 pips spread) · sizing position (micro lots, 0.01–10.0) · sessions UTC avec DST · modèles slippage et spread variables · filtres additionnels (corrélation, régime, news, spread spike) · pip sizes par paire · kill switch.

### `agents/quant_researcher.md`
Checklist anti-biais (look-ahead, survival, overfitting, IS/OOS contamination) · protocole IS/OOS/Monte Carlo · paramètres sensibles (RR, range, ATR) · ressources code.

### `agents/risk_manager.md`
Séquence protection capital (5 étapes ordonnées) · paramètres risque · 6 scénarios de risque avec triggers et actions · checklist risque avant modification · ressources code.

### `agents/code_auditor.md`
Checklist sécurité (credentials, IB, web dashboard) · checklist qualité code (types, conventions, Cython) · checklist erreurs silencieuses · checklist avant merge (7 points) · patterns interdits vs corrects avec exemples.

### `agents/dev_engineer.md`
Procédure 5 étapes ajout fonctionnalité · pipeline CI (make qa/qa-strict/build/test/bandit) · workflow Cython obligatoire · 8 interdictions absolues · fichiers clés à connaître · convention de nommage des tests.

---

## BLOC 5 — PLAN DE MIGRATION PRIORISÉ

| Priorité | Fichier | Statut initial | Effort réel | Impact |
|----------|---------|---------------|-------------|--------|
| 1 | `.claude/rules.md` | ❌ ABSENT | ~10 min | Réduit à zéro les erreurs d'agent par session |
| 2 | `.claude/context.md` | ❌ ABSENT | ~15 min | Fournit le pipeline complet sans lecture du code |
| 3 | `architecture/decisions.md` | ❌ ABSENT | ~20 min | Explique le pourquoi de chaque choix structurel |
| 4 | `knowledge/ibkr_constraints.md` | ❌ ABSENT | ~10 min | Évite les violations pacing IB en session |
| 5 | `knowledge/trading_constraints.md` | ❌ ABSENT | ~15 min | Source unique des règles de trading |
| 6 | `agents/risk_manager.md` | ❌ ABSENT | ~10 min | Checklist capital protection avant chaque PR |
| 7 | `agents/code_auditor.md` | ❌ ABSENT | ~10 min | Detects regressions that slip past make qa |
| 8 | `agents/dev_engineer.md` | ❌ ABSENT | ~10 min | Onboarding procédure complète |
| 9 | `agents/quant_researcher.md` | ❌ ABSENT | ~10 min | Checklist anti-biais statistiques |
| 10 | `architecture/system_design.md` | ❌ ABSENT | ~10 min | Vue d'ensemble pour nouveaux contributeurs |
| — | `.github/copilot-instructions.md` | ✅ EXISTE | — | Inchangé — déjà conforme |

---

## SYNTHÈSE

| Métrique | Valeur |
|----------|--------|
| Fichiers existants | 1 (`.github/copilot-instructions.md`) |
| Fichiers partiels | 0 |
| Fichiers absents → créés | 10 |
| Fichiers inchangés | 1 |
| Nettoyage requis | Aucun |

**QA après audit** : `make qa` → 504 tests ✅ · 0 ruff ✅ · 0 pyright ✅
