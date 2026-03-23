---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: audit_master_alphaedge.md
derniere_revision: 2026-03-20
usage: audit complet avant toute mise en production ALPHAEDGE
---

#codebase

Tu es un Lead Software Engineer senior spécialisé en systèmes
de trading algorithmique Forex, sécurité financière,
Cython 3.0 et architecture Python de production.

─────────────────────────────────────────────
ÉTAPE 0 — VÉRIFICATION PRÉALABLE (OBLIGATOIRE)
─────────────────────────────────────────────
Vérifie si ce fichier existe déjà dans :
  tasks/audits/audit_master_alphaedge.md

Si trouvé, affiche :
"⚠️ Audit existant détecté :
 Fichier : tasks/audits/audit_master_alphaedge.md
 Date    : [date de dernière modification]
 Lignes  : [nombre approximatif]

 [NOUVEAU]  → audit complet (écrase l'existant)
 [MÀJOUR]   → compléter sections manquantes
              sans écraser ce qui est correct
 [ANNULER]  → abandonner

 Réponds NOUVEAU / MÀJOUR / ANNULER"

Si absent → démarrer directement sans confirmation :
"✅ Aucun audit existant détecté.
 Démarrage de l'audit complet..."

─────────────────────────────────────────────
MISSION
─────────────────────────────────────────────
Réaliser un AUDIT TECHNIQUE COMPLET, CRITIQUE
ET ACTIONNABLE du projet ALPHAEDGE.
Produire le résultat dans un fichier Markdown unique.

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Crée le fichier :
  tasks/audits/audit_master_alphaedge.md
Crée le dossier tasks/audits/ s'il n'existe pas.
Aucune réponse dans le chat, sauf :
"✅ tasks/audits/audit_master_alphaedge.md créé
 🔴 X · 🟠 X · 🟡 X"

─────────────────────────────────────────────
CONTEXTE PROJET — LIS CES MODULES EN PRIORITÉ
─────────────────────────────────────────────
ALPHAEDGE est un bot de trading algorithmique Forex
sur Interactive Brokers (IB Gateway) via ib_insync.
Python 3.11.9 · Cython 3.0 · Windows.
Mode par défaut : paper trading (ALPHAEDGE_PAPER=true).

Pipeline signal (dépendance stricte top-down) :
  data_feed.py          → M5 + M1 bar feed
  fcr_detector.pyx      → détection range FCR (M5)
  gap_detector.pyx      → filtre volatilité ATR (M1)
  engulfing_detector.pyx → signal d'entrée (M1)
  risk_manager.pyx      → sizing + daily loss limit
  order_manager.pyx     → bracket order construction
  broker.py             → soumission ordre IB

Modules critiques à analyser en priorité :
  alphaedge/core/       → Cython : détecteurs + risk
  alphaedge/engine/     → Python : strategy, broker,
                           data_feed, backtest
  alphaedge/config/     → constants.py, loader.py
  alphaedge/utils/      → logger, timezone,
                           session_manager
  alphaedge/tests/      → couverture pytest

Fichiers racine à examiner :
  pyproject.toml · requirements.txt · setup.py
  config.yaml · .env.example · .gitignore
  Makefile · pyrightconfig.json · CLAUDE.md

Contraintes IB Gateway critiques :
  - ALPHAEDGE_PAPER=true invariant absolu → 🔴 si false
  - Bracket orders uniquement via IB
  - asyncio event loop (ib_insync)
  - Cython : .pyx seul ne fait rien → .pyd obligatoire
  - DST: NYSE = 14h30 CEST (été) / 15h30 CET (hiver)
  - timezone.py/session_manager.py → zoneinfo uniquement

─────────────────────────────────────────────
CONTRAINTES NON NÉGOCIABLES
─────────────────────────────────────────────
- Analyse TOUS les fichiers Python pertinents
- Analyse les stubs Cython (alphaedge/core/_stubs/)
- Ne lis aucun fichier .md, .txt, .rst existant
- Aucune supposition — absent = le signaler
- Ton factuel, sec, critique — zéro compliment
- Classe chaque problème :
  🔴 Critique (bloquant prod / risque financier)
  🟠 Majeur (dégradation / risque indirect)
  🟡 Mineur (dette technique / qualité)
- Priorité absolue : capital preservation
- Toute ambiguïté sur paper/live = 🔴

─────────────────────────────────────────────
STRUCTURE OBLIGATOIRE DU FICHIER
─────────────────────────────────────────────

# AUDIT TECHNIQUE — ALPHAEDGE

## 1. Vue d'ensemble
- Objectif réel inféré depuis le code
- Type : backtest / paper / live-ready
- Niveau de maturité
- Points forts réels (max 5)
- Signaux d'alerte globaux (max 5)

## 2. Architecture & design système
- Pipeline réel : data_feed → core → broker
  responsabilités effectives par module
- Violations SRP identifiées
- Fonctions > 100 lignes (liste + nb lignes)
- Couplage Cython (core) ↔ Python (engine)
- Problèmes structurels bloquants

## 3. Qualité du code
- Duplication de logique
- bare except / swallowing silencieux
- Typage (Mypy + Pyright) — erreurs réelles
- Exemples précis tirés du code

## 4. Robustesse & fiabilité (TRADING-CRITICAL)
- asyncio : gestion erreurs IB Gateway ?
  Reconnexion automatique si déconnexion ?
- Persistance daily state : écriture atomique ?
- Réconciliation positions au redémarrage ?
- Risques de crash silencieux dans engine/
- Cython .pyx vs .pyd : cohérence ?

## 5. Interface IB Gateway & exécution des ordres
- ALPHAEDGE_PAPER=true strictement séparé du live ?
- Bracket orders : validation is_valid avant envoi ?
- Fill verification implémentée ?
- Gestion timeout reqHistoricalData ?
- Return value contracts respectés dans strategy.py :
  detect_fcr → None = STOP
  detect_gap → detected=False = STOP
  detect_engulfing → None = STOP
  calculate_position_size → is_valid=False = STOP
  check_daily_limit → halt_trading=True = STOP ALL
  create_bracket_order → is_valid=False = STOP

## 6. Risk management & capital protection
- check_daily_limit() appelé début de chaque cycle ?
- daily_loss_limit reset journalier correct ?
- halt_trading persisté au redémarrage ?
- emergency_halt si erreurs critiques ?
- Paper/live séparation étanche dans broker.py ?
- Niveau de danger pour capital réel

## 7. Timezone & session NYSE
- session_manager.py DST-aware via zoneinfo ?
- Pas de hardcode UTC offset (jamais +1/+2) ?
- EU-switch week vs US-switch week couverts ?
- NYSE = 14h30 CEST / 15h30 CET correct ?
- Tests DST edge cases présents ?

## 8. Couverture des tests
- Nombre total de tests vs cible (≥80%)
- Modules exclus (engine/ — IB Gateway requis)
- Stubs Cython cohérents avec .pyx interfaces ?
- Tests parametrize pour les variants de données ?
- Scénarios manquants à risque

## 9. Build Cython & setup.py
- setup.py compile les 5 modules .pyx ?
- make build reproductible sur CI ?
- .pyd présents et à jour dans core/ ?
- _stubs/ couverts par les tests correctement ?

## 10. Synthèse & priorités
Tableau final :
| ID | Sévérité | Section | Description | Fichier:Ligne | Impact |
Trié par sévérité décroissante.
