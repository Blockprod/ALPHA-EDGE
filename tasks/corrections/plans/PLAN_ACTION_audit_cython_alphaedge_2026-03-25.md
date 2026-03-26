---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: PLAN_ACTION_audit_cython_alphaedge_2026-03-25.md
derniere_revision: 2026-03-25
creation: 2026-03-25 à 23:15
---

# PLAN D'ACTION — ALPHAEDGE — Cython & Build — 2026-03-25

Sources : `tasks/audits/audit_cython_alphaedge.md`
Total : 🔴 0 · 🟠 1 · 🟡 3 · Effort estimé : 1.5 h

---

## PHASE 1 — CRITIQUES 🔴

Aucune.

---

## PHASE 2 — MAJEURES 🟠

### [C-01] Corriger `CLAUDE.md` — clé `halt_trading` → `limit_breached`

Fichier : `CLAUDE.md:54-55`
Problème : Le tableau Return Value Contracts de `CLAUDE.md` documente la clé de retour de `check_daily_limit()` comme `halt_trading: True`, alors que l'implémentation (`risk_manager.pyx:272-278`, `_stubs/risk_manager.py:61-68`) retourne `limit_breached: True` et `can_trade: False`. La source `.github/copilot-instructions.md` est, elle, exacte. Cette divergence est un risque agent IA : un agent qui lit `CLAUDE.md` en priorité peut vérifier la mauvaise clé et ne pas déclencher le STOP.
Correction : Remplacer dans `CLAUDE.md` la ligne `halt_trading: True` par `limit_breached: True` dans la colonne "Falsy return", alignée avec `copilot-instructions.md`.
Validation :
  # Aucun make qa requis — fichier documentation uniquement
  # Vérification manuelle : CLAUDE.md:54-55 doit afficher `limit_breached: True`
  # Vérifier cohérence avec copilot-instructions.md (déjà correct)
Dépend de : Aucune
Statut : ✅ 2026-03-25

---

## PHASE 3 — MINEURES 🟡

### [C-02] ✅ Retirer les 3 modules FCR orphelins de `setup.py`

Fichier : `setup.py:35-46`
Problème : `fcr_detector`, `gap_detector`, `engulfing_detector` sont listés dans `setup.py` et compilés à chaque `make build`. Aucun de ces modules n'est importé par le code Python (`strategy._import_core_modules`, `__init__.py`), aucun stub ne leur correspond dans `_stubs/`, aucun test ne les cible. Ce sont des reliquats de l'ancienne stratégie FCR — ils allongent le build inutilement (~15 s) et constituent une dette silencieuse.
Correction : Supprimer les 3 entrées `Extension(name="alphaedge.core.fcr_detector", ...)`, `Extension(name="alphaedge.core.gap_detector", ...)`, `Extension(name="alphaedge.core.engulfing_detector", ...)` de la liste `extensions` dans `setup.py`.
> ⚠️ Ne pas supprimer les fichiers `.pyx` eux-mêmes — ils peuvent être utiles lors d'une future migration ou d'un audit FCR. Supprimer uniquement les entrées dans `setup.py`.
> ⚠️ Les `.c` et `.pyd` correspondants seront supprimés par un `make clean` — ne pas les supprimer manuellement.
Validation :
  make qa
  # Attendu : 583 passed · 0 ruff · 0 pyright
  # Aucun make build requis (les .pyx ne sont pas modifiés — uniquement setup.py)
Dépend de : Aucune
Statut : ✅ 2026-03-25

---

### [C-03] ✅ Ajouter avertissement dans `Makefile` — `clean` supprime les `.c`

Fichier : `Makefile:71-73`
Problème : `make clean` supprime les fichiers `.c` (artefacts de transpilation Cython) sans prévenir l'utilisateur. Sur une machine où Cython n'est pas installé, `make build` échouera silencieusement après un `clean` car les `.c` sont nécessaires à la compilation C sans régénération Cython.
Correction : Ajouter un commentaire explicite avant la ligne de suppression des `.c` dans la cible `clean` du Makefile, indiquant que Cython est requis pour régénérer les `.c` par `make build`.
Validation :
  make qa
  # Attendu : 583 passed · 0 ruff · 0 pyright
  # Aucun make build requis
Dépend de : Aucune
Statut : ✅ 2026-03-25

---

### [C-04] ✅ Ajouter tests couverture backend compilé / fallback production

Fichier : `alphaedge/core/__init__.py:80-93` · `alphaedge/tests/conftest.py:21`
Problème : Tous les tests s'exécutent avec `ALPHAEDGE_CORE_BACKEND=stubs` (imposé par `conftest.py:21`). La cascade `auto` (import .pyd → ImportError → fallback stubs) et le raise en mode `ALPHAEDGE_ENV=production` de `_load_core_module()` ne sont jamais exercés. Un test `test_core_backend_visibility.py` existe mais ne couvre que le chemin mock, pas le vrai `ImportError`.
Correction : Créer `alphaedge/tests/test_core_backend_fallback.py` avec 2 tests :
  1. `test_backend_fallback_on_import_error` : patch `importlib.import_module` pour lever `ImportError` sur le chemin compilé → vérifier que le stub est retourné et que `get_fallback_modules()` contient le module.
  2. `test_backend_production_raises_on_missing_compiled` : même patch + `ALPHAEDGE_ENV=production` → vérifier que `ImportError` est bien propagé (pas de fallback silencieux).
Validation :
  make qa
  # Attendu : ≥585 passed (2 nouveaux tests) · 0 ruff · 0 pyright
Dépend de : Aucune
Statut : ✅ 2026-03-25

---

## SÉQUENCE D'EXÉCUTION

```
C-01 → C-03 → C-02 → C-04
```

- **C-01** en premier : correction documentaire pure, zéro risque, prend 1 min.
- **C-03** ensuite : commentaire Makefile, zéro risque.
- **C-02** : suppression des entrées `setup.py` (aucun `make build` requis).
- **C-04** en dernier : nouveaux tests, valide la baseline avec `make qa`.

> Aucune correction ne touche un `.pyx` — `make build` n'est pas requis dans ce plan.

---

## CRITÈRES PASSAGE EN PRODUCTION

- [ ] Zéro 🔴 ouvert
- [ ] `make qa` : 100% pass (lint + mypy + pytest ≥80%)
- [ ] Zéro credential dans les logs loguru
- [ ] `ALPHAEDGE_PAPER=true` intact dans `.env.example`
- [ ] Bracket order `is_valid` vérifié avant envoi IB
- [ ] `check_daily_limit()` appelé chaque cycle
- [ ] Paper trading validé 5 sessions NYSE minimum

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier | Effort | Statut | Date |
|----|-------|----------|---------|--------|--------|------|
| C-01 | Corriger `CLAUDE.md` clé `halt_trading` | 🟠 Majeur | `CLAUDE.md:79` | 5 min | ✅ | 2026-03-25 |
| C-02 | Retirer modules FCR orphelins de `setup.py` | 🟡 Mineur | `setup.py:35-46` | 15 min | ✅ | 2026-03-25 |
| C-03 | Avertissement `make clean` supprime `.c` | 🟡 Mineur | `Makefile:59-61` | 5 min | ✅ | 2026-03-25 |
| C-04 | Tests fallback backend compilé / prod | 🟡 Mineur | `__init__.py:80-93` | 45 min | ✅ | 2026-03-25 |
