# PLAN D'ACTION — ALPHAEDGE — 2026-03-22
**Créé le :** 2026-03-22 à 18:17
Sources : `tasks/audits/audit_cython_alphaedge.md`
Total : 🔴 0 · 🟠 4 · 🟡 2 · Effort estimé : 2 jours

## PHASE 1 — CRITIQUES 🔴

Aucun élément critique identifié dans cet audit.

## PHASE 2 — MAJEURES 🟠

### [C-01] Réaligner le contrat public de `is_in_gap_zone`
Fichier : CLAUDE.md:314
Problème : Le contrat public documente `is_in_gap_zone(price, gap_high, gap_low) -> bool`, alors que l'interface réellement exposée par `gap_detector.pyx` et son stub exige aussi `tolerance_pips` et `pip_size`.
Correction :
- Mettre à jour la documentation de contrat dans `CLAUDE.md` pour refléter la signature réellement supportée.
- Vérifier la cohérence du même contrat dans les autres documents d'instructions projet si la fonction y est rappelée.
- Conserver la signature runtime actuelle, déjà cohérente entre `.pyx`, `_stubs` et tests.
Validation :
  make qa
  # Attendu : documentation alignée avec le runtime, 100% pass
Dépend de : Aucune
Statut : ✅ 2026-03-22

### [C-02] Réaligner les contrats publics de `detect_engulfing`, `check_daily_limit` et `calculate_position_size`
Fichier : CLAUDE.md:327
Problème : Les valeurs de retour documentées ne correspondent plus au comportement réel validé par les tests. `detect_engulfing` est documenté avec des clés obsolètes, `check_daily_limit` aussi, et `calculate_position_size` omet le paramètre optionnel `exchange_rate`.
Correction :
- Mettre à jour dans `CLAUDE.md` les signatures et shapes de retour de `detect_engulfing`, `check_daily_limit` et `calculate_position_size` pour refléter l'API publique effective.
- Documenter explicitement les paramètres optionnels `min_body_ratio`, `max_wick_ratio` et `exchange_rate`.
- Vérifier que les noms de clés documentés correspondent aux assertions réellement utilisées dans les tests Cython.
Validation :
  make qa
  # Attendu : contrats publics alignés avec les tests et le runtime, 100% pass
Dépend de : Aucune
Statut : ✅ 2026-03-22

### [C-04] Faire builder les extensions Cython dans la CI avant Pytest
Fichier : .github/workflows/ci.yml:15
Problème : La CI installe les dépendances puis lance Ruff, Pyright et Pytest sans exécuter `make build`. Elle peut donc valider uniquement le chemin `_stubs` alors que les développeurs Windows exécutent les `.pyd` compilés.
Correction :
- Ajouter un step explicite `make build` ou `python setup.py build_ext --inplace` dans `.github/workflows/ci.yml` avant les tests.
- S'assurer que l'ordre CI devient : install → lint → typecheck → build Cython → tests.
- Vérifier que l'environnement CI dispose bien des prérequis pour compiler les extensions ciblées, ou échouer explicitement si ce n'est pas le cas.
Validation :
  make qa
  # Attendu : CI définie pour construire les extensions avant Pytest, QA locale inchangée
  # Si .pyx modifié : make build → make qa
Dépend de : Aucune
Statut : ✅ 2026-03-22

### [C-05] Rendre le mode de test Cython déterministe entre stubs et modules compilés
Fichier : alphaedge/tests/conftest.py:1
Problème : Les tests importent `alphaedge.core`, qui charge les modules compilés si présents. Comme `conftest.py` ne force aucun mode, le comportement dépend de l'état local du workspace.
Correction :
- Définir une stratégie de test explicite : soit forcer les stubs dans les tests unitaires Cython, soit séparer clairement tests stubs et tests runtime compilé.
- Implémenter dans `conftest.py` ou dans des helpers de test un mécanisme reproductible de sélection du backend Cython/stub.
- Documenter cette stratégie pour éviter que CI, dev Windows et dev Linux testent des surfaces différentes sans le savoir.
- Vérifier que les imports `from alphaedge.core import ...` restent compatibles avec la stratégie retenue.
Validation :
  make qa
  # Attendu : exécution des tests reproductible avec ou sans artefacts compilés locaux, 100% pass
  # Si .pyx modifié : make build → make qa
Dépend de : C-04
Statut : ✅ 2026-03-22

## PHASE 3 — MINEURES 🟡

### [C-03] Compléter `make clean` pour supprimer les `.c` générés
Fichier : Makefile:57
Problème : `make clean` supprime les binaires, caches et dossiers de build, mais laisse les fichiers `.c` générés par Cython dans le workspace.
Correction :
- Étendre la cible `clean` du `Makefile` pour supprimer aussi les `alphaedge/core/*.c` générés.
- Limiter le nettoyage aux artefacts de transpilation attendus, sans toucher aux `.pyx` ni aux fichiers source suivis.
- Vérifier que la cible reste cross-platform et sûre sur Windows.
Validation :
  make qa
  # Attendu : `make clean` supprime aussi les `.c` générés, puis `make build` régénère proprement les artefacts
  # Si .pyx modifié : make build → make qa
Dépend de : Aucune
Statut : ✅ 2026-03-22

### [C-06] Ajouter un test unitaire direct pour `check_pair_limit`
Fichier : alphaedge/tests/test_race_condition_multi_pair.py:54
Problème : `check_pair_limit` est une API publique exposée par `risk_manager`, mais elle n'est pas testée directement. Le test multi-pair la remplace par un mock local, ce qui ne couvre pas son implémentation réelle.
Correction :
- Créer un test unitaire dédié pour `risk_manager.check_pair_limit` couvrant au minimum les cas autorisé et rejeté.
- Faire porter ce test sur l'interface publique `alphaedge.core.risk_manager`, en cohérence avec la stratégie retenue en C-05.
- Vérifier le shape complet du retour (`allowed`, `reason`, `open_count`, `max_allowed`, `open_pairs`).
Validation :
  make qa
  # Attendu : couverture directe de `check_pair_limit`, 100% pass
Dépend de : C-05
Statut : ✅ 2026-03-22

## SÉQUENCE D'EXÉCUTION
1. C-01 — réaligner la signature documentée de `is_in_gap_zone`
2. C-02 — réaligner les contrats documentés de `detect_engulfing`, `check_daily_limit` et `calculate_position_size`
3. C-04 — ajouter le build Cython explicite dans la CI
4. C-05 — rendre le backend de test Cython déterministe
5. C-06 — ajouter le test direct de `check_pair_limit`
6. C-03 — compléter `make clean` pour supprimer les `.c`

Toujours `make build` avant `make qa` si `.pyx` touché.
Ce plan ne cible pas de modification `.pyx` à ce stade.

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
| C-01 | Réaligner le contrat de `is_in_gap_zone` | 🟠 | CLAUDE.md | 0.25 jour | ✅ | 2026-03-22 |
| C-02 | Réaligner les contrats publics documentés restants | 🟠 | CLAUDE.md | 0.5 jour | ✅ | 2026-03-22 |
| C-04 | Builder les extensions Cython dans la CI | 🟠 | .github/workflows/ci.yml | 0.25 jour | ✅ | 2026-03-22 |
| C-05 | Rendre les tests Cython déterministes | 🟠 | alphaedge/tests/conftest.py ; alphaedge/tests/test_* | 0.5 jour | ✅ | 2026-03-22 |
| C-03 | Nettoyer aussi les `.c` générés | 🟡 | Makefile | 0.25 jour | ✅ | 2026-03-22 |
| C-06 | Tester directement `check_pair_limit` | 🟡 | alphaedge/tests/test_risk_manager_pair_limit.py | 0.25 jour | ✅ | 2026-03-22 |
