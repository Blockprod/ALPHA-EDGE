---
modele: sonnet-4.6
mode: agent
contexte: codebase
derniere_revision: 2026-03-20
---

#codebase

Tu es un Software Architect spécialisé en
AI-Driven Repository Engineering.
Analyse EDGECORE et génère le plan de
restructuration File Engineering complet.

─────────────────────────────────────────────
CONTRAINTES
─────────────────────────────────────────────
- Génère le contenu RÉEL basé sur le code source
- Pas de templates génériques
- Chaque fichier prêt à copier-coller
- [À COMPLÉTER MANUELLEMENT] si info absente du code
- Ne jamais écraser un fichier existant sans
  afficher son contenu actuel et demander GO

─────────────────────────────────────────────
ÉTAPE 0 — ÉTAT DES LIEUX (OBLIGATOIRE)
─────────────────────────────────────────────
Avant toute action, scanne le workspace et
vérifie l'existence de chaque fichier AI-Driven.

Affiche le rapport d'état complet :

┌─────────────────────────────────────────────────┐
│ ÉTAT DES LIEUX — FICHIERS AI-DRIVEN             │
├──────────────────────────────────────────────────┤
│ .github/copilot-instructions.md  ✅ EXISTE       │
│ .claude/context.md               ❌ ABSENT       │
│ .claude/rules.md                 ⚠️ PARTIEL      │
│ architecture/system_design.md    ❌ ABSENT       │
│ architecture/decisions.md        ❌ ABSENT       │
│ knowledge/ibkr_constraints.md    ❌ ABSENT       │
│ knowledge/trading_constraints.md ❌ ABSENT       │
│ agents/quant_researcher.md       ✅ EXISTE       │
│ agents/risk_manager.md           ❌ ABSENT       │
│ agents/code_auditor.md           ❌ ABSENT       │
│ agents/dev_engineer.md           ❌ ABSENT       │
└──────────────────────────────────────────────────┘

Légende :
  ✅ EXISTE    → fichier présent et non vide
  ⚠️ PARTIEL  → fichier présent mais incomplet
                 (moins de 20 lignes ou sections
                 manquantes par rapport au standard)
  ❌ ABSENT   → fichier à créer

Pour chaque fichier ✅ EXISTE ou ⚠️ PARTIEL :
  - Affiche le contenu actuel
  - Identifie ce qui est déjà correct
  - Identifie ce qui manque ou est obsolète

Puis affiche le résumé :
"📋 État des lieux terminé.
 ✅ [X] fichiers existants
 ⚠️ [X] fichiers partiels à compléter
 ❌ [X] fichiers absents à créer
 Réponds GO pour démarrer la restructuration
 ou LISTE pour voir l'ordre de création proposé."

─────────────────────────────────────────────
ÉTAPE 1 — NETTOYAGE PRÉALABLE
─────────────────────────────────────────────
Vérifie la présence de chaque fichier avant
de recommander une action :

- CMakeLists.txt : présent ? → supprimer ?
- ARCHIVED_cpp_sources/ : référencé depuis prod ?
- ARCHIVED_crypto/ : référencé depuis prod ?
- Fichiers debug racine (bt_results_v*.txt,
  bt_errors_*.txt, debug_*.txt, bt_out*.txt) :
  présents ? → archiver dans docs/archived/ ?
- run_backtest_v17d.py, run_backtest_v18.py :
  actifs ou résidus ? → déplacer vers scripts/ ?
- setup.py vs pyproject.toml :
  les deux présents ? → lequel conserver ?

Pour chaque action recommandée :
afficher GO [action] pour confirmer ou SKIP.

─────────────────────────────────────────────
ÉTAPE 2 — ARBORESCENCE CIBLE
─────────────────────────────────────────────
Propose l'arborescence complète restructurée
en distinguant ce qui existe déjà de ce qui
sera créé :

EDGECORE/
├── .claude/
│   ├── context.md          ✅/⚠️/❌
│   └── rules.md            ✅/⚠️/❌
├── .github/
│   └── copilot-instructions.md  ✅/⚠️/❌
├── architecture/
│   ├── system_design.md    ✅/⚠️/❌
│   └── decisions.md        ✅/⚠️/❌
├── knowledge/
│   ├── ibkr_constraints.md      ✅/⚠️/❌
│   └── trading_constraints.md   ✅/⚠️/❌
├── agents/
│   ├── quant_researcher.md ✅/⚠️/❌
│   ├── risk_manager.md     ✅/⚠️/❌
│   ├── code_auditor.md     ✅/⚠️/❌
│   └── dev_engineer.md     ✅/⚠️/❌
├── tasks/               ← existant
├── backtests/           ← existant
├── execution/           ← existant
├── models/              ← existant
└── tests/               ← existant

─────────────────────────────────────────────
ÉTAPE 3 — CRÉATION ET MISE À JOUR DES FICHIERS
─────────────────────────────────────────────
Traite chaque fichier dans l'ordre de priorité :
  1. Fichiers ❌ ABSENTS → créer entièrement
  2. Fichiers ⚠️ PARTIELS → compléter les sections
     manquantes sans écraser ce qui est correct
  3. Fichiers ✅ EXISTANTS → vérifier si mise
     à jour nécessaire (contenu obsolète ?)

Pour chaque fichier, avant d'agir :
  - Affiche : "── [nom fichier] ──────────────"
  - Indique : CRÉATION / COMPLÉTION / MISE À JOUR
  - Pour COMPLÉTION : montre uniquement les
    sections à ajouter (pas le fichier entier)
  - Pour MISE À JOUR : montre le diff précis
  - Attends GO avant d'appliquer

Contenu à générer basé sur le code réel :

1. .github/copilot-instructions.md
   Stack · modules clés · conventions critiques
   (rate limiting IBKR, risk tiers, datetime UTC,
   types d'ordres) · interdictions absolues ·
   commandes de validation

2. .claude/rules.md
   Règles de modification · ordre de priorité
   (capital > risk > exécution > backtest) ·
   obligations post-modification · interdictions

3. .claude/context.md
   Pipeline complet depuis le code ·
   table des modules avec responsabilité réelle ·
   contraintes IBKR extraites du code ·
   paramètres clés (z-score, drawdown, risk tiers) ·
   ce qui ne doit pas changer sans benchmark

4. architecture/decisions.md
   ADR pour : séparation modules publics/internes ·
   triple-gate coïntégration · Kalman vs hedge fixe ·
   z-score adaptatif · kill-switch 6 conditions ·
   migration C++ → Python · Docker · risk tiers T1/T2/T3

5. knowledge/ibkr_constraints.md
   Types d'ordres IBKR disponibles ·
   rate limits (50 req/s, burst 10) ·
   ports TWS/Gateway (7496/7497) ·
   erreurs informatives (2104, 2106, 2158) ·
   erreurs données historiques (162, 200, 354) ·
   idempotence client order IDs

6. agents/quant_researcher.md
   Checklist anti-biais spécifique EDGECORE
   (expanding window, Kalman causal, Bonferroni,
   OOS gates, IS/OOS contamination)

7. agents/risk_manager.md
   Séquence protection capital EDGECORE ·
   risk tiers T1/T2/T3 · scénarios de risque

8. agents/code_auditor.md
   Checklist doublons (execution/ vs execution_engine/) ·
   checklist sécurité IBKR ·
   checklist gestion erreurs silencieuses

9. agents/dev_engineer.md
   Procédure ajout fonctionnalité · pipeline CI ·
   commandes de validation ·
   interdictions absolues rappelées

─────────────────────────────────────────────
ÉTAPE 4 — PLAN DE MIGRATION PRIORISÉ
─────────────────────────────────────────────
Tableau final tenant compte de l'état des lieux :

| Priorité | Fichier | Statut | Effort | % Auto | Impact session |
|----------|---------|--------|--------|--------|----------------|
| 1 | .github/copilot-instructions.md | ❌/⚠️/✅ | Xmin | X% | [impact] |
| 2 | .claude/rules.md | ❌/⚠️/✅ | Xmin | X% | [impact] |
...

Affiche en conclusion :
"✅ File Engineering terminé.
 Créés : [X] · Complétés : [X] · Mis à jour : [X]
 Inchangés : [X] (déjà conformes)"

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Crée le fichier :
  tasks/audits/audit_ai_driven_alphaedge.md
Crée le dossier tasks/audits/ s'il n'existe pas.

Structure du fichier :
## BLOC 1 — ÉTAT DES LIEUX (fichiers présents / partiels / absents)
## BLOC 2 — NETTOYAGE PRÉALABLE (fichiers à supprimer ou archiver)
## BLOC 3 — ARBORESCENCE CIBLE
## BLOC 4 — FICHIERS CRÉÉS OU MIS À JOUR (contenu réel généré)
## BLOC 5 — PLAN DE MIGRATION PRIORISÉ
## SYNTHÈSE

Tableau synthèse :
| Priorité | Fichier | Statut | Effort | % Auto | Impact |

Statuts : ✅ EXISTE · ⚠️ PARTIEL · ❌ ABSENT.

Confirme dans le chat uniquement :
"✅ tasks/audits/audit_ai_driven_alphaedge.md créé
 ✅ [X] · ⚠️ [X] · ❌ [X]"
