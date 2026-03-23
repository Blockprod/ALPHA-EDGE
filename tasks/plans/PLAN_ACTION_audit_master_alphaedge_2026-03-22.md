# PLAN D'ACTION — ALPHAEDGE — 2026-03-22
Sources : tasks/audits/audit_master_alphaedge.md
Total : 🔴 0 · 🟠 3 · 🟡 4 · Effort estimé : 6 jours

## PHASE 1 — CRITIQUES 🔴

Aucune correction 🔴 ouverte dans l'audit master courant.

## PHASE 2 — MAJEURES 🟠

### [C-01] Renforcer le niveau de type-checking Pyright
Fichier : pyrightconfig.json:1
Problème : le projet repose encore sur `typeCheckingMode = "basic"`, ce qui laisse passer des dérives d'interface dans une base critique de trading.
Correction : durcir progressivement la configuration Pyright vers un niveau plus strict, corriger les erreurs réellement révélées, puis stabiliser la CI et les tests autour de ce nouveau niveau d'exigence.
Validation :
  make qa
  # Attendu : lint OK + pyright OK + pytest >= 80%
Dépend de : Aucune
Statut : ✅ 2026-03-22

### [C-02] Réduire l'angle mort de couverture sur le backend réellement testé
Fichier : pyproject.toml:50
Problème : la couverture exclut `engine/` et `core/_stubs/`, alors que la CI exécute les tests avec `ALPHAEDGE_CORE_BACKEND=stubs`.
Correction : réaligner le périmètre de couverture avec le backend effectivement exercé par la CI, ou documenter et tester explicitement le contrat entre stubs, `.pyi` et modules compilés pour éviter une confiance trompeuse dans la métrique globale.
Validation :
  make qa
  # Attendu : couverture >= 80% sur le périmètre réellement représentatif et CI inchangée ou durcie proprement
Dépend de : Aucune
Statut : ✅ 2026-03-22

### [C-03] Remplacer les `except Exception` critiques par une politique d'erreurs explicite
Fichier : alphaedge/engine/broker.py:176
Problème : le runtime critique protège bien le capital, mais une part importante de l'orchestration IB/feed/session absorbe les erreurs via `except Exception`, ce qui dégrade le diagnostic et la remédiation différenciée.
Correction : classifier les erreurs attendues par domaine (connexion IB, pacing, timeout historique, réconciliation, exécution ordre), introduire des branches d'erreurs explicites là où l'action corrective diffère réellement, et conserver les garde-fous fail-closed en dernier ressort.
Validation :
  make qa
  # Attendu : comportement fail-closed conservé, logs plus précis, tests ciblés sur les branches d'erreurs critiques
Dépend de : C-01
Statut : ✅ 2026-03-22

## PHASE 3 — MINEURES 🟡

### [C-04] Rendre visible l'absence d'artefact compilé hors mode `compiled`
Fichier : alphaedge/core/__init__.py:24
Problème : le fallback automatique compiled → stubs peut masquer un environnement partiellement ou totalement non compilé hors vérification explicite.
Correction : améliorer le signal runtime ou les logs de chargement pour indiquer clairement quel backend a été retenu et quand un fallback s'est produit, sans casser le mode CI fondé sur les stubs.
Validation :
  make qa
  # Attendu : backend chargé clairement identifiable en logs/tests, aucun changement de contrat public involontaire
Dépend de : Aucune
Statut : ✅ 2026-03-22

### [C-05] Réduire la taille des fonctions massives dans les zones critiques
Fichier : alphaedge/engine/data_feed.py:295
Problème : plusieurs fonctions dépassent 100 lignes et concentrent trop de responsabilités, ce qui ralentit l'audit et augmente le risque de régression.
Correction : extraire les sous-responsabilités évidentes dans `data_feed.py`, `backtest.py` et `walk_forward.py` sans changer le comportement métier, en privilégiant des extractions pures et testables.
Validation :
  make qa
  # Attendu : comportement inchangé, lisibilité meilleure, nouvelles fonctions couvertes par les tests existants ou ajustés
Dépend de : C-03
Statut : ✅ 2026-03-22

### [C-06] Taper explicitement les handlers de déconnexion IB
Fichier : alphaedge/engine/broker.py:102
Problème : les callbacks de déconnexion restent typés en `Any`, ce qui affaiblit les contrats d'intégration et la détection statique des erreurs.
Correction : remplacer `Any` par un type callable explicite adapté au modèle d'événement utilisé par `ib_insync` et aligner les tests/stubs sur ce contrat.
Validation :
  make qa
  # Attendu : pyright plus précis et aucun faux positif sur les tests de reconnect
Dépend de : C-01
Statut : ✅ 2026-03-22

### [C-07] Ajouter un test e2e unique de cycle live mocké
Fichier : alphaedge/tests/test_fill_verification.py:118
Problème : le comportement global est validé par fragments, sans scénario unique couvrant la chaîne complète depuis l'initialisation de session jusqu'au fill/close.
Correction : créer un test d'intégration mocké unique couvrant pré-session, FCR, gap, engulfing, sizing, bracket, fill puis fermeture de position, afin de verrouiller l'invariant système principal.
Validation :
  make qa
  # Attendu : nouveau scénario e2e vert et couverture utile accrue sur l'orchestration live
Dépend de : C-03
Statut : ✅ 2026-03-22

## SÉQUENCE D'EXÉCUTION
1. C-01 — renforcer Pyright
2. C-02 — réaligner la couverture avec le backend réellement testé
3. C-03 — expliciter la politique d'erreurs critiques
4. C-04 — rendre le fallback compiled → stubs plus visible
5. C-06 — typer les handlers de déconnexion IB
6. C-05 — réduire la taille des fonctions massives
7. C-07 — ajouter un scénario e2e live mocké

## CRITÈRES PASSAGE EN PRODUCTION
- [ ] Zéro 🔴 ouvert
- [x] make qa : 100% pass (lint + mypy + pytest ≥80%)
- [ ] Zéro credential dans les logs loguru
- [ ] ALPHAEDGE_PAPER=true intact dans .env.example
- [ ] Bracket order is_valid vérifié avant envoi IB
- [ ] check_daily_limit() appelé chaque cycle
- [ ] Paper trading validé 5 sessions NYSE minimum

## TABLEAU DE SUIVI
| ID | Titre | Sévérité | Fichier | Effort | Statut | Date |
|----|-------|----------|---------|--------|--------|------|
| C-01 | Renforcer le niveau de type-checking Pyright | 🟠 | pyrightconfig.json | M | ✅ | 2026-03-22 |
| C-02 | Réduire l'angle mort de couverture sur le backend réellement testé | 🟠 | pyproject.toml | M | ✅ | 2026-03-22 |
| C-03 | Remplacer les `except Exception` critiques par une politique d'erreurs explicite | 🟠 | alphaedge/engine/broker.py | L | ✅ | 2026-03-22 |
| C-04 | Rendre visible l'absence d'artefact compilé hors mode `compiled` | 🟡 | alphaedge/core/__init__.py | S | ✅ | 2026-03-22 |
| C-05 | Réduire la taille des fonctions massives dans les zones critiques | 🟡 | alphaedge/engine/data_feed.py | L | ✅ | 2026-03-22 |
| C-06 | Taper explicitement les handlers de déconnexion IB | 🟡 | alphaedge/engine/broker.py | XS | ✅ | 2026-03-22 |
| C-07 | Ajouter un test e2e unique de cycle live mocké | 🟡 | alphaedge/tests/test_fill_verification.py | M | ✅ | 2026-03-22 |

## VALIDATION 2026-03-22
- Ruff : OK
- Pyright : 0 erreur, 0 warning
- Pytest : 553 passed
- Coverage : 89% sur le périmètre CI représentatif
