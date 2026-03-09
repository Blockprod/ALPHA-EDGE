# ⚡ ALPHAEDGE — STRUCTURAL ACTION PLAN

> **Source**: Audit structurel du 2026-03-09 (6 dimensions : A→F)
> **Score de départ**: 5.2 / 10 — *Structurally noisy. Strong bones, poor hygiene.*
> **Objectif**: Amener le repo à un état **AI-ready, CI-complete, production-clean**
> **Méthode**: 4 sprints séquentiels — chaque sprint doit être **100% validé** avant de passer au suivant
> **Contrainte absolue**: Aucune modification de la logique métier `core/` ni de `engine/strategy.py`

---

## TABLE DES MATIÈRES

| Sprint | Priorité | Thème | Tâches |
|--------|----------|-------|--------|
| [Sprint 1](#sprint-1--p0--sécurité--bloquants-immédiats) | P0 | Sécurité & Bloquants immédiats | 3 |
| [Sprint 2](#sprint-2--p1--qa-pipeline--ai-readiness) | P1 | QA Pipeline & AI-Readiness | 4 |
| [Sprint 3](#sprint-3--p2--root-hygiene--documentation) | P2 | Root hygiene & Documentation | 5 |
| [Sprint 4](#sprint-4--p3--polish--build-unification) | P3 | Polish & Build unification | 3 |
| [Validation finale](#validation-finale) | — | Checklist globale | — |

**Total : 15 tâches**

---

# SPRINT 1 — P0 · Sécurité & Bloquants immédiats

> **Condition de sortie** : Aucun secret tracké, aucune config cassée, repo propre pour partage.

---

### P0-01 — Supprimer `ALPHAEDGE_ACTION_PLAN.md` du tracking Git

**Dimension** : [F] Sécurité
**Risque** : Contenu propriétaire (stratégie FCR) potentiellement exposé dans l'historique Git

**Problème** :
Le fichier `ALPHAEDGE_ACTION_PLAN.md` est listé dans `.gitignore` sous "Proprietary / Sensitive", mais ajouter un fichier à `.gitignore` après un premier commit **ne le retire pas de l'historique**. Il reste indexé et visible pour quiconque a accès au remote.

**Actions** :

- [ ] **1.** Vérifier si le fichier est actuellement tracké :
  ```powershell
  git ls-files ALPHAEDGE_ACTION_PLAN.md
  ```
  → Si la commande retourne `ALPHAEDGE_ACTION_PLAN.md`, il est tracké.

- [ ] **2.** Retirer du tracking sans supprimer le fichier local :
  ```powershell
  git rm --cached ALPHAEDGE_ACTION_PLAN.md
  git commit -m "chore: untrack proprietary ALPHAEDGE_ACTION_PLAN.md"
  ```

- [ ] **3.** Si le contenu a été commité dans des commits antérieurs (vérifier via `git log -- ALPHAEDGE_ACTION_PLAN.md`), effectuer un history rewrite :
  ```powershell
  git filter-branch --force --index-filter `
    "git rm --cached --ignore-unmatch ALPHAEDGE_ACTION_PLAN.md" `
    --prune-empty --tag-name-filter cat -- --all
  git push origin --force --all
  ```
  > ⚠️ ATTENTION : `--force` sur le remote. Coordonner si d'autres branches existent.

**Validation** :
- [ ] `git ls-files ALPHAEDGE_ACTION_PLAN.md` retourne vide
- [ ] `git log -- ALPHAEDGE_ACTION_PLAN.md` retourne vide (si rewrite effectué)
- [ ] Le fichier est toujours présent localement ✓

---

### P0-02 — Auditer `config.yaml` et l'ajouter au `.gitignore` si nécessaire

**Dimension** : [F] Sécurité
**Risque** : Exposition de credentials IB si des paramètres de connexion sont hardcodés dans `config.yaml`

**Problème** :
`config.yaml` est présent à la racine et **absent du `.gitignore`**. Si ce fichier contient des valeurs d'account IB, host, port non-defaults, ou des clés API, ils sont exposés dans le repo.

**Actions** :

- [ ] **1.** Lire le contenu de `config.yaml` et identifier toute valeur sensible :
  - Account ID (ex. `DU1234567`)
  - Host/port non-standard
  - Toute clé ou token

- [ ] **2a.** Si `config.yaml` contient des valeurs sensibles :
  - Remplacer les valeurs par des références aux variables d'environnement (ex. `${ALPHAEDGE_IB_ACCOUNT}`)
  - Créer `config.yaml.example` avec des valeurs fictives
  - Ajouter `config.yaml` au `.gitignore`
  - Retirer du tracking : `git rm --cached config.yaml`

- [ ] **2b.** Si `config.yaml` ne contient que des paramètres de trading non-sensibles (timeframes, paires, seuils) :
  - Le conserver tel quel, le laisser tracké

**Validation** :
- [ ] Aucune valeur sensible dans les fichiers trackés
- [ ] `.env` reste la seule source de vérité pour les credentials IB ✓

---

### P0-03 — Corriger la configuration Mypy cassée dans `launch.json`

**Dimension** : [C] VSCode Workspace
**Risque** : La config "ALPHAEDGE — Mypy Check" échoue silencieusement pour tous les utilisateurs

**Problème** :
`launch.json` ligne contenant `--config-file mypy.ini` référence un fichier **inexistant**. Il n'y a pas de `mypy.ini` dans le workspace. La configuration Mypy est donc non-fonctionnelle.

**Fichier** : `.vscode/launch.json`

**Action** : Modifier l'argument `--config-file` pour pointer vers `pyproject.toml` une fois que `[tool.mypy]` y sera ajouté (Sprint 2 – P1-01). En attendant, supprimer l'argument invalide :

- [ ] Dans `.vscode/launch.json`, remplacer la configuration "ALPHAEDGE — Mypy Check" :
  ```json
  // Avant (cassé) :
  "args": [
      "alphaedge/",
      "--config-file",
      "mypy.ini"
  ]

  // Après (fonctionnel) :
  "args": [
      "alphaedge/",
      "--ignore-missing-imports",
      "--no-strict-optional"
  ]
  ```
  > Cette config temporaire sera mise à jour après P1-01 (ajout de `[tool.mypy]` dans `pyproject.toml`).

**Validation** :
- [ ] La configuration "Mypy Check" dans VSCode s'exécute sans erreur de config file
- [ ] `python -m mypy alphaedge/ --ignore-missing-imports` tourne depuis le terminal ✓

---

# SPRINT 2 — P1 · QA Pipeline & AI-Readiness

> **Condition de sortie** : Mypy intégré au pipeline, cyclic imports résolus, AI entry point créé.

---

### P1-01 — Ajouter `[tool.mypy]` dans `pyproject.toml` et intégrer Mypy au Makefile et CI

**Dimension** : [D] QA Pipeline
**Risque** : Mypy run ad hoc sans config → résultats non reproductibles, erreurs ignorées

**Problème** :
- Aucune section `[tool.mypy]` dans `pyproject.toml`
- Mypy absent du `Makefile` (cible `qa`) et de `ci.yml`
- Le README annonce "Mypy (strict)" mais c'est faux — aucun mode strict configuré

**Fichiers** : `pyproject.toml`, `Makefile`, `.github/workflows/ci.yml`, `.vscode/launch.json`

**Actions** :

- [ ] **1.** Ajouter dans `pyproject.toml` (après `[tool.coverage.report]`) :
  ```toml
  # --- Mypy Configuration ---
  [tool.mypy]
  python_version = "3.11"
  warn_return_any = true
  warn_unused_configs = true
  ignore_missing_imports = true
  exclude = [
      "alphaedge/core/",
      "build/",
  ]
  ```
  > Note : `core/` exclu car les `.pyx` compilés n'ont pas de sources `.py` pour Mypy.

- [ ] **2.** Mettre à jour le `Makefile` — cible `qa` :
  ```makefile
  # Avant :
  qa: lint test

  # Après :
  typecheck:
  	python -m mypy alphaedge/ --config-file pyproject.toml

  qa: lint typecheck test
  ```

- [ ] **3.** Ajouter un step dans `ci.yml` après le step Ruff :
  ```yaml
  - name: Type checking (Mypy)
    run: |
      python -m mypy alphaedge/ --config-file pyproject.toml
  ```

- [ ] **4.** Mettre à jour `.vscode/launch.json` — config "ALPHAEDGE — Mypy Check" :
  ```json
  "args": [
      "alphaedge/",
      "--config-file",
      "pyproject.toml"
  ]
  ```

**Validation** :
- [ ] `python -m mypy alphaedge/ --config-file pyproject.toml` tourne sans crash de config
- [ ] `make qa` inclut Mypy dans la sortie
- [ ] CI passe avec le nouveau step ✓

---

### P1-02 — Résoudre les cyclic imports dans `utils/` et `engine/`

**Dimension** : [D] QA Pipeline
**Risque** : Import circulaire = crash runtime potentiel selon l'ordre d'import au démarrage

**Problème** (confirmé par `pylint_out.txt`) :
- Cycle 1 : `alphaedge.utils.logger → alphaedge.utils.timezone → alphaedge.utils.session_manager`
- Cycle 2 : `alphaedge.engine.backtest → alphaedge.engine.sensitivity`

**Actions** :

- [ ] **1.** Analyser le cycle dans `utils/` :
  ```powershell
  # Identifier les imports incriminés
  grep -n "import" alphaedge/utils/logger.py
  grep -n "import" alphaedge/utils/timezone.py
  grep -n "import" alphaedge/utils/session_manager.py
  ```

- [ ] **2.** Résoudre le cycle `utils/` — stratégies possibles (choisir selon le code) :
  - Déplacer l'import problématique dans le corps de la fonction qui en a besoin (lazy import)
  - Extraire les types partagés dans un module `utils/types.py` sans dépendances
  - Inverser la dépendance via injection de dépendance (passer l'objet en paramètre)

- [ ] **3.** Analyser et résoudre le cycle `engine/` :
  ```powershell
  grep -n "import" alphaedge/engine/backtest.py | grep sensitivity
  grep -n "import" alphaedge/engine/sensitivity.py | grep backtest
  ```
  → Extraire les types/constantes partagés dans `engine/backtest_types.py` (déjà présent ✓)

**Validation** :
- [ ] `python -m pylint alphaedge/ --disable=all --enable=cyclic-import` retourne 0 cyclic imports
- [ ] `python -c "import alphaedge"` s'exécute sans warning/erreur ✓

---

### P1-03 — Créer le fichier AI entry point `CLAUDE.md` / `copilot-instructions.md`

**Dimension** : [B] AI-Readiness
**Risque** : Chaque session AI repart de zéro — contexte architectural perdu, risque de modifications incohérentes

**Problème** :
Il n'existe aucun fichier d'entrée AI. Un LLM lisant le repo doit traverser 3 fichiers `.md` de 200+ lignes chacun pour comprendre l'architecture. Signal-to-noise ratio adversarial.

**Actions** :

- [ ] **1.** Créer `.github/copilot-instructions.md` (lu automatiquement par GitHub Copilot) avec :
  - Nom du projet, stack exact, version Python
  - Schéma d'architecture en 5 lignes (pipeline signal)
  - Règles absolues : "ne jamais modifier core/ sans recompiler", "ALPHAEDGE_PAPER=true par défaut"
  - Workflow QA : `make qa` avant tout commit
  - Pointeurs vers les fichiers clés : `config.yaml`, `.env.example`, `ALPHAEDGE_MASTER_AUDIT.md`
  - Score audit courant et P0s en cours

- [ ] **2.** Créer `CLAUDE.md` à la racine (lu par Claude / agents génériques) avec le même contenu
  + mention explicite des fichiers gitignorés (`ALPHAEDGE_ACTION_PLAN.md` = propriétaire, ne pas régénérer)

**Contenu minimal requis dans les deux fichiers** :
```markdown
## Project: ALPHAEDGE — FCR Forex Trading Bot
- Stack: Python 3.11.9 / Cython 3.0 / ib_insync / loguru / Rich / vectorbt
- Architecture: IB Gateway → data_feed → [fcr_detector/gap_detector/engulfing_detector].pyx
  → risk_manager.pyx → order_manager.pyx → broker.py
- Core rule: core/ modules are Cython (.pyx) — ALWAYS run `make build` after editing
- Safety rule: ALPHAEDGE_PAPER=true must remain default in .env.example
- QA: `make qa` (Ruff + Mypy + Pytest ≥80% cov) must pass before any commit
- Current audit score: 5.2/10 — see ALPHAEDGE_MASTER_AUDIT.md for details
```

**Validation** :
- [ ] `CLAUDE.md` présent à la racine
- [ ] `.github/copilot-instructions.md` présent
- [ ] Un LLM cold-started peut comprendre l'architecture en < 60 secondes depuis ces fichiers ✓

---

### P1-04 — Supprimer les 4 fichiers `.txt` de debug et les gitignorer

**Dimension** : [A] Root hygiene
**Risque** : Pollution visuelle + indexation par les outils AI → confusion sur l'état QA actuel

**Fichiers à supprimer** :
- `mypy_errors.txt`
- `mypy_errors2.txt`
- `pylint_out.txt`
- `pylint_output.txt`

**Actions** :

- [ ] **1.** Vérifier que les issues documentés dans ces fichiers sont tracés ailleurs (ils le sont dans `ALPHAEDGE_MASTER_AUDIT.md` ✓)

- [ ] **2.** Supprimer les fichiers :
  ```powershell
  git rm mypy_errors.txt mypy_errors2.txt pylint_out.txt pylint_output.txt
  git commit -m "chore: remove debug QA dump files from root"
  ```

- [ ] **3.** Ajouter au `.gitignore` pour éviter la réapparition :
  ```gitignore
  # --- QA Debug Dumps ---
  mypy_errors*.txt
  pylint_out*.txt
  pylint_output*.txt
  ruff_output*.txt
  ```

**Validation** :
- [ ] `git ls-files | grep -E "\.txt$"` ne retourne aucun fichier
- [ ] `.gitignore` contient les patterns `*.txt` de QA
- [ ] `ls` à la racine : propre ✓

---

# SPRINT 3 — P2 · Root Hygiene & Documentation

> **Condition de sortie** : Racine lisible en 30 secondes, documentation consolidée, VSCode propre.

---

### P2-01 — Consolider les deux plans d'action post-audit en un seul `ROADMAP.md`

**Dimension** : [E] Documentation
**Risque** : Deux fichiers conflictuels → ambiguïté sur les priorités actives → travail en double ou oublié

**Problème** :
`ALPHAEDGE_PLAN_ACTION_AUDIT.md` et `ALPHAEDGE_POST_AUDIT_ACTION_PLAN.md` couvrent les mêmes P0 (asyncio.Lock, spread return 0.0) avec des numérotations différentes (P0-01/P0-02 vs TÂCHE 1.1/1.2).

**Actions** :

- [ ] **1.** Lire les deux fichiers en entier et identifier les tâches DISTINCTES dans chacun
- [ ] **2.** Créer `ROADMAP.md` avec :
  - Source unique de vérité pour toutes les tâches code (P0 → P3)
  - Statut de chaque tâche (`[ ]` / `[x]` / `[~]` en cours)
  - Référence vers `ALPHAEDGE_MASTER_AUDIT.md` pour la justification
- [ ] **3.** Supprimer (ou archiver dans `docs/`) les deux fichiers remplacés :
  ```powershell
  git rm ALPHAEDGE_PLAN_ACTION_AUDIT.md ALPHAEDGE_POST_AUDIT_ACTION_PLAN.md
  git commit -m "docs: consolidate post-audit plans into ROADMAP.md"
  ```

**Validation** :
- [ ] Un seul fichier fait autorité sur les tâches en cours
- [ ] Toutes les tâches P0/P1 des deux anciens fichiers sont présentes dans `ROADMAP.md` ✓

---

### P2-02 — Compléter le `Makefile` : ajouter `typecheck` et `pylint`

**Dimension** : [D] QA Pipeline
**Risque** : Le pipeline QA complet n'est pas exécutable en une seule commande

**Fichier** : `Makefile`

**Actions** :

- [ ] Ajouter les cibles manquantes :
  ```makefile
  # Type checking
  typecheck:
  	python -m mypy alphaedge/ --config-file pyproject.toml

  # Pylint
  pylint:
  	python -m pylint alphaedge/ --rcfile=pyproject.toml

  # Full QA (lint + typecheck + pylint + test)
  qa: lint typecheck test

  # QA strict (inclut pylint)
  qa-strict: lint typecheck pylint test
  ```

- [ ] Mettre à jour `.PHONY` :
  ```makefile
  .PHONY: lint format typecheck pylint test qa qa-strict build all clean
  ```

**Validation** :
- [ ] `make qa` passe entièrement
- [ ] `make qa-strict` liste tous les outils QA ✓

---

### P2-03 — Supprimer `ms-python.black-formatter` de `extensions.json`

**Dimension** : [C] VSCode Workspace
**Risque** : Conflit de formatter (Black vs Ruff) → format-on-save imprévisible

**Fichier** : `.vscode/extensions.json`

**Action** :

- [ ] Retirer `"ms-python.black-formatter"` de la liste `recommendations`
- [ ] Vérifier que `settings.json` confirme déjà Ruff comme `defaultFormatter` ✓ (c'est le cas)

**Validation** :
- [ ] `extensions.json` ne contient plus `black-formatter`
- [ ] Aucun conflit fmt à l'ouverture d'un `.py` dans VSCode ✓

---

### P2-04 — Créer `tasks.json` pour exposer les targets Makefile comme tâches VSCode

**Dimension** : [C] VSCode Workspace
**Risque** : Workflow QA inaccessible depuis l'UI VSCode → adoption réduite

**Fichier à créer** : `.vscode/tasks.json`

**Action** :

- [ ] Créer `.vscode/tasks.json` avec les tâches suivantes :
  ```json
  {
      "version": "2.0.0",
      "tasks": [
          {
              "label": "ALPHAEDGE — QA (lint + mypy + test)",
              "type": "shell",
              "command": "make qa",
              "group": { "kind": "test", "isDefault": true },
              "presentation": { "panel": "shared", "reveal": "always" },
              "problemMatcher": ["$mypy", "$pylint"]
          },
          {
              "label": "ALPHAEDGE — Build Cython",
              "type": "shell",
              "command": "make build",
              "group": "build",
              "presentation": { "panel": "shared" }
          },
          {
              "label": "ALPHAEDGE — Clean artifacts",
              "type": "shell",
              "command": "make clean",
              "presentation": { "panel": "shared" }
          },
          {
              "label": "ALPHAEDGE — Tests only",
              "type": "shell",
              "command": "make test",
              "group": "test",
              "presentation": { "panel": "shared", "reveal": "always" }
          }
      ]
  }
  ```

**Validation** :
- [ ] `Ctrl+Shift+P` → "Run Task" liste les 4 tâches ALPHAEDGE
- [ ] `make qa` s'exécute via la tâche VSCode ✓

---

### P2-05 — Documenter la limitation de couverture dans `README.md`

**Dimension** : [E] Documentation
**Risque** : Claim "≥80% coverage" trompeur — `engine/` entièrement exclu du calcul

**Fichier** : `README.md`

**Action** :

- [ ] Dans la section "QA Toolchain" du README, ajouter une note explicite :
  ```markdown
  > **Note coverage** : Le seuil ≥80% s'applique à `config/`, `utils/` et `core/` (stubs).
  > Les modules `engine/` (strategy, broker, data_feed, backtest) sont exclus car ils
  > nécessitent une connexion IB Gateway active. Voir `pyproject.toml [tool.coverage.run]`.
  ```

**Validation** :
- [ ] La section QA du README mentionne explicitement la portée de la couverture ✓

---

# SPRINT 4 — P3 · Polish & Build Unification

> **Condition de sortie** : Repo sans redondances de config, CI avec secret scanning.

---

### P3-01 — Supprimer `pyrightconfig.json` (redondant avec `settings.json`)

**Dimension** : [D] QA Pipeline / [A] Root hygiene
**Risque** : 3 endroits déclarent `typeCheckingMode` — incohérence garantie lors des mises à jour

**Fichier** : `pyrightconfig.json` (5 lignes, `typeCheckingMode: "basic"`)

**Action** :

- [ ] Vérifier que `settings.json` couvre déjà `python.analysis.typeCheckingMode: "basic"` ✓
- [ ] Supprimer `pyrightconfig.json` :
  ```powershell
  git rm pyrightconfig.json
  git commit -m "chore: remove redundant pyrightconfig.json (superseded by settings.json)"
  ```

**Validation** :
- [ ] Pylance fonctionne toujours correctement (il lit `settings.json` en priorité)
- [ ] `pyrightconfig.json` absent du repo ✓

---

### P3-02 — Ajouter le secret scanning dans `ci.yml`

**Dimension** : [F] Sécurité
**Risque** : Aucune protection contre un commit accidentel de credentials dans une PR future

**Fichier** : `.github/workflows/ci.yml`

**Action** :

- [ ] Ajouter un step de secret scanning avec `trufflesecurity/trufflehog` :
  ```yaml
  - name: Secret scanning (TruffleHog)
    uses: trufflesecurity/trufflehog@main
    with:
      path: ./
      base: ${{ github.event.repository.default_branch }}
      head: HEAD
      extra_args: --only-verified
  ```

**Validation** :
- [ ] Le workflow CI inclut le step secret scanning
- [ ] Un test avec une fausse clé API dans un fichier déclenche le scan ✓

---

### P3-03 — Unifier la configuration du build : migrer `setup.py` vers PEP 517 pur

**Dimension** : [D] QA Pipeline
**Risque** : `setup.py` + `pyproject.toml [build-system]` = deux sources de vérité pour la build Cython

**Contexte** :
`pyproject.toml` déclare `setuptools.build_meta` comme backend, mais `setup.py` contient l'intégralité de la logique Cython (extensions, `cythonize()`, vérification de version Python). Cette dualité est courante mais dépréciée depuis setuptools 61+.

**Actions** :

- [ ] **Option A (recommandée — migration complète)** :
  - Déplacer toute la configuration Cython dans `pyproject.toml` via `[tool.setuptools]` + script `build_ext`
  - Utiliser `[project.optional-dependencies]` pour les dépendances Cython
  - Supprimer `setup.py`
  - ⚠️ Tester avec `python -m build` et vérifier que les `.pyd` sont bien générés

- [ ] **Option B (conservatrice — acceptable)** :
  - Garder `setup.py` comme entry point Cython
  - Retirer `[build-system]` de `pyproject.toml` (ou le conserver mais documenter que `setup.py` est le build actif)
  - Ajouter un commentaire dans les deux fichiers indiquant lequel est actif

**Validation** :
- [ ] `make build` produit les `.pyd` sans warning de deprecation setup.py
- [ ] `make clean && make build` cycle complet fonctionne ✓

---

# VALIDATION FINALE

> À utiliser comme checklist finale avant de considérer le repo "production-clean".

## Checklist globale

### Sécurité
- [ ] `ALPHAEDGE_ACTION_PLAN.md` non tracké par Git et absent de l'historique
- [ ] `config.yaml` audité — aucune valeur sensible committée
- [ ] `.env` absent du repo (seul `.env.example` présent)
- [ ] Secret scanning actif dans CI

### QA Pipeline
- [ ] `[tool.mypy]` présent dans `pyproject.toml`
- [ ] Mypy présent dans `Makefile` cible `qa`
- [ ] Mypy présent dans `ci.yml`
- [ ] `make qa` passe sans erreur (Ruff + Mypy + Pytest)
- [ ] Zéro cyclic import détecté par Pylint
- [ ] Aucun fichier `.txt` de dump QA à la racine

### VSCode
- [ ] `launch.json` Mypy pointe vers `pyproject.toml`
- [ ] `extensions.json` sans `ms-python.black-formatter`
- [ ] `tasks.json` présent avec les 4 tâches Make
- [ ] `pyrightconfig.json` supprimé

### Documentation
- [ ] `CLAUDE.md` présent à la racine
- [ ] `.github/copilot-instructions.md` présent
- [ ] `ROADMAP.md` remplace les deux plans conflictuels
- [ ] `README.md` documente la limitation de couverture engine/

### Root hygiene
- [ ] `ls` à la racine : ≤ 12 fichiers visibles (hors dossiers)
- [ ] Aucun artifact de build (`build/`, `.coverage`, `.mypy_cache/`) visible dans VSCode Explorer

---

## Commande de vérification finale

```powershell
# Vérification complète en une commande
make qa

# Vérification Git propre
git status --short
git ls-files | Select-String "\.txt$"

# Vérification imports
python -m pylint alphaedge/ --disable=all --enable=cyclic-import

# Vérification AI entry point
Test-Path CLAUDE.md
Test-Path .github/copilot-instructions.md
```

---

## Scoring cible post-sprint

| Dimension | Score actuel | Score cible |
|-----------|-------------|-------------|
| A — Root hygiene | 4/10 | 8/10 |
| B — AI-readiness | 3/10 | 8/10 |
| C — VSCode workspace | 7/10 | 9/10 |
| D — QA pipeline | 5/10 | 8/10 |
| E — Documentation | 5/10 | 8/10 |
| F — Security | 7/10 | 9/10 |
| **Total** | **5.2/10** | **8.3/10** |
