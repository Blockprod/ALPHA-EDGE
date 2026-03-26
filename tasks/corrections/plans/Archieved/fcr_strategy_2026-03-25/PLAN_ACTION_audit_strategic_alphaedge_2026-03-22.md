# PLAN D'ACTION — ALPHAEDGE — 2026-03-22
**Créé le :** 2026-03-22 à 18:33
Sources : tasks/audits/audit_strategic_alphaedge.md
Total : 🔴 2 · 🟠 3 · 🟡 3 · Effort estimé : 5 jours

## PHASE 1 — CRITIQUES 🔴

### [C-01] Aligner la baseline gap live sur la pré-session M1
Fichier : alphaedge/engine/signal_pipeline.py:76
Problème : le live transmet `state.m5_candles` comme `pre_session_m1` au gap detector, alors que le backtest utilise la vraie pré-session M1. Le filtre gap ne mesure donc pas la même chose entre simulation et exécution réelle.
Correction : faire alimenter le pipeline live avec les bougies M1 pré-session réelles, ou adapter l'état/collecte de session pour exposer explicitement cette série au moment de l'appel à `detect_gap()`. Vérifier que la même sémantique de baseline est utilisée en live et en backtest.
Validation :
  make qa
  # Attendu : tests verts et aucun écart de type/lint
Dépend de : Aucune
Statut : ✅ 2026-03-22

### [C-02] Faire consommer au live les paramètres stratégiques configurés
Fichier : alphaedge/engine/signal_pipeline.py:54
Problème : le live force `DEFAULT_MIN_RANGE_PIPS`, `DEFAULT_MIN_ATR_RATIO`, `DEFAULT_VOLUME_PERIOD` et `DEFAULT_MIN_VOLUME_RATIO`, alors que le backtest consomme les valeurs de configuration et overrides par paire. Les réglages optimisés ne sont pas ceux réellement appliqués en live.
Correction : injecter dans `SignalPipeline` les paramètres issus de `AppConfig` pour FCR, gap et engulfing, y compris les overrides par paire lorsque prévus par le schéma de configuration. Centraliser le mapping pour éviter une nouvelle dérive live/backtest.
Validation :
  make qa
  # Attendu : tests verts et cohérence explicite entre config live et config backtest
Dépend de : Aucune
Statut : ✅ 2026-03-22

## PHASE 2 — MAJEURES 🟠

### [C-03] Rendre le pipeline live strictement all-or-nothing après absence de FCR
Fichier : alphaedge/engine/session_lifecycle.py:435
Problème : après `detect_fcr() -> None`, la session continue encore vers la logique gap sur les nouvelles M1. Aucun ordre n'est émis, mais le contrat all-or-nothing n'est pas respecté proprement.
Correction : court-circuiter explicitement le reste du pipeline pour le cycle courant tant qu'aucun FCR valide n'existe, avec un état clair côté session lifecycle pour éviter tout passage inutile par la détection gap.
Validation :
  make qa
  # Attendu : tests verts et ajout/ajustement de tests confirmant l'absence d'appel gap sans FCR
Dépend de : C-01
Statut : ✅ 2026-03-22

### [C-04] Réduire l'écart de validation exécution entre backtest et live
Fichier : alphaedge/engine/backtest.py:316
Problème : le backtest ne passe pas par `risk_manager` ni `order_manager`, contrairement au live. Une partie des rejets d'exécution réels n'est donc pas représentée dans l'historique.
Correction : intégrer dans le backtest une étape d'équivalent fonctionnel pour la validation de sizing et de bracket order, sans modifier la logique propriétaire `core/*.pyx`. Si l'alignement complet n'est pas souhaitable, documenter et tester explicitement le périmètre simulé.
Validation :
  make qa
  # Attendu : tests verts et invariants backtest/live clarifiés par tests ciblés
Dépend de : C-02
Statut : ✅ 2026-03-22

### [C-05] Clarifier et rapprocher le modèle de coûts backtest/live
Fichier : alphaedge/engine/backtest.py:316
Problème : le backtest applique un slippage variable, tandis que le live combine spread temps réel et buffer fixe. Les coûts d'exécution ne sont pas directement comparables.
Correction : définir un contrat commun de modélisation des coûts, puis aligner les hypothèses ou documenter précisément les différences résiduelles et leur impact attendu. Ajouter des tests ciblés sur la conversion de spread/slippage en risque/coût effectif.
Validation :
  make qa
  # Attendu : tests verts et modèle de coût explicite, stable et vérifiable
Dépend de : C-04
Statut : ✅ 2026-03-22

## PHASE 3 — MINEURES 🟡

### [C-06] Élever le niveau de log sur dépassement daily loss
Fichier : alphaedge/engine/session_lifecycle.py:557
Problème : le kill-switch quotidien stoppe bien le trading, mais l'événement est logué en `warning` au lieu de `critical`.
Correction : passer ce log au niveau `critical` et vérifier que les alertes associées restent cohérentes avec la sévérité opérationnelle attendue.
Validation :
  make qa
  # Attendu : tests verts et logs/alertes conformes au contrat de sécurité
Dépend de : Aucune
Statut : ✅ 2026-03-22

### [C-07] Brancher ou supprimer le lookback FCR non utilisé
Fichier : alphaedge/config/constants.py:110
Problème : `DEFAULT_FCR_LOOKBACK` est défini mais n'a aucun effet observable dans le pipeline courant. Cela entretient une fausse configurabilité stratégique.
Correction : soit brancher réellement le lookback dans le flux FCR concerné, soit retirer la constante et la documentation associée si la stratégie ne doit pas l'exposer.
Validation :
  make qa
  # Attendu : tests verts et absence de paramètre mort côté stratégie
Dépend de : C-02
Statut : ✅ 2026-03-22

### [C-08] Traiter la dette technique du point d'entrée ML non intégré
Fichier : alphaedge/engine/ml_filter.py:8
Problème : `ml_filter.py` reste exposé comme module public alors qu'il n'est pas intégré au pipeline live. Cela brouille l'état réel des capacités ML.
Correction : soit intégrer explicitement ce composant avec contrat et tests, soit le déprécier/retirer du chemin public en gardant une compatibilité contrôlée si nécessaire.
Validation :
  make qa
  # Attendu : tests verts et statut ML explicite dans le code public
Dépend de : Aucune
Statut : ✅ 2026-03-22

## SÉQUENCE D'EXÉCUTION
1. C-01 — aligner la baseline gap live/backtest
2. C-02 — injecter les paramètres stratégiques configurés dans le live
3. C-03 — rendre le pipeline strict après absence de FCR
4. C-04 — rapprocher les validations backtest/live
5. C-05 — clarifier et rapprocher le modèle de coûts
6. C-06 — corriger la sévérité du log daily loss
7. C-07 — brancher ou retirer le lookback FCR mort
8. C-08 — traiter le point d'entrée ML orphelin

## CRITÈRES PASSAGE EN PRODUCTION
- [ ] Zéro 🔴 ouvert
- [ ] make qa : 100% pass (lint + mypy + pytest ≥80%)
- [ ] Zéro credential dans les logs loguru
- [ ] ALPHAEDGE_PAPER=true intact dans .env.example
- [ ] Bracket order is_valid vérifié avant envoi IB
- [ ] check_daily_limit() appelé chaque cycle
- [ ] Paper trading validé 5 sessions NYSE minimum

## TABLEAU DE SUIVI
| ID | Titre | Sévérité | Fichier | Effort | Statut | Date |
|----|-------|----------|---------|--------|--------|------|
| C-01 | Aligner la baseline gap live sur la pré-session M1 | 🔴 | alphaedge/engine/signal_pipeline.py | M | ✅ | 2026-03-22 |
| C-02 | Faire consommer au live les paramètres stratégiques configurés | 🔴 | alphaedge/engine/signal_pipeline.py | M | ✅ | 2026-03-22 |
| C-03 | Rendre le pipeline live strictement all-or-nothing après absence de FCR | 🟠 | alphaedge/engine/session_lifecycle.py | S | ✅ | 2026-03-22 |
| C-04 | Réduire l'écart de validation exécution entre backtest et live | 🟠 | alphaedge/engine/backtest.py | M | ✅ | 2026-03-22 |
| C-05 | Clarifier et rapprocher le modèle de coûts backtest/live | 🟠 | alphaedge/engine/backtest.py | S | ✅ | 2026-03-22 |
| C-06 | Élever le niveau de log sur dépassement daily loss | 🟡 | alphaedge/engine/session_lifecycle.py | XS | ✅ | 2026-03-22 |
| C-07 | Brancher ou supprimer le lookback FCR non utilisé | 🟡 | alphaedge/config/constants.py | S | ✅ | 2026-03-22 |
| C-08 | Traiter la dette technique du point d'entrée ML non intégré | 🟡 | alphaedge/engine/ml_filter.py | XS | ✅ | 2026-03-22 |
