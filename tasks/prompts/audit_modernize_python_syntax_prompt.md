---
modele: claude-sonnet-4.6
mode: agent
contexte: codebase
produit: corrections appliquées · ruff OK · pyright OK · 504 tests pass
derniere_revision: 2026-03-23
---

#codebase

Je suis le chef de projet ALPHAEDGE.

─────────────────────────────────────────────
OBJECTIF PRINCIPAL
─────────────────────────────────────────────
Corriger **tous les fichiers Python** du projet
(chaque dossier et sous-dossier) pour que :

1. Zéro erreur ruff (y compris paramètres orphelins ARG)
2. Zéro erreur Pyright
3. Tous les fichiers Python sont parfaitement alignés
   avec l'implémentation Cython correspondante
   (signatures, paramètres, types, clés de retour)
4. 504 tests passent · coverage ≥ 80%

L'alignement Cython est une contrainte transversale —
elle s'applique à TOUS les fichiers Python du projet,
pas uniquement aux stubs.

─────────────────────────────────────────────
RÈGLE D'ALIGNEMENT CYTHON (transversale)
─────────────────────────────────────────────
Pour tout fichier Python qui appelle, wrap, fallback
ou interagit avec un module Cython (`alphaedge/core/*.pyx`) :

- Les signatures de fonctions doivent correspondre
  exactement à la définition Cython (`cdef`, `cpdef`)
- L'ordre et les noms des paramètres doivent être identiques
- Les types des paramètres doivent être cohérents
  (Python type hints vs Cython types)
- Les clés des dicts retournés doivent être identiques
- Toute divergence dans un fichier Python = erreur critique

Corrige toujours le fichier Python, jamais le `.pyx`.
Pour vérifier une signature Cython :
→ Lis `alphaedge/core/<module>.pyx` directement.

─────────────────────────────────────────────
ÉTAPE 0 — AUDIT PRIORITAIRE DES STUBS CYTHON
─────────────────────────────────────────────
Les stubs (`alphaedge/core/_stubs/`) sont les fallbacks
Python purs des modules Cython. Ils sont traités
EN PREMIER car toute divergence stub↔Cython se propage
dans tout le projet.

### 0a — Ouverture des stubs dans l'éditeur

⛔ **BLOQUANT** — ouvre **chaque** fichier stub dans VSCode
via la commande PowerShell ci-dessous AVANT toute lecture
ou modification. Cette commande ouvre physiquement les
onglets dans la fenêtre VSCode active de l'utilisateur.

```powershell
$stubs = "c:\Users\averr\AlphaEdge\alphaedge\core\_stubs"
Get-ChildItem -Path $stubs -Filter "*.py" |
  Where-Object { $_.FullName -notmatch "__pycache__" } |
  Sort-Object Name |
  ForEach-Object { code --reuse-window $_.FullName }
```

⚠️ Attends la fin de l'exécution (les 6 onglets doivent
être visibles dans l'éditeur) avant de procéder à l'étape 0b.

### 0b — Vérification paramètres orphelins (ARG)
```powershell
python -m ruff check alphaedge/core/_stubs/ --select ARG 2>&1
```

Pour chaque violation `ARG001` / `ARG002` :
1. Lis le stub dans l'onglet ouvert
2. Lis la signature Cython correspondante dans
   `alphaedge/core/<module>.pyx`
3. Détermine si le paramètre est :
   - **nécessaire à la logique** → connecte-le à son usage
     naturel. Ne jamais supprimer.
   - **présent uniquement pour mirrorer la signature Cython**
     et intrinsèquement inutilisable en Python pur →
     renomme-le `_param` + commentaire inline :
     `# mirrors Cython signature — unused in Python fallback`
   - **totalement superflu** → signale au chef de projet
     avant toute suppression.

### 0c — Vérification alignement complet stub↔Cython
Pour chaque fonction publique de chaque stub :
- Nom de la fonction
- Ordre et noms des paramètres
- Types des paramètres
- Clés du dict retourné

Toute divergence = erreur critique → corrige le stub.

### 0d — Validation finale des stubs
```powershell
python -m ruff check alphaedge/core/_stubs/ --select ARG 2>&1
python -m ruff check alphaedge/core/_stubs/ 2>&1
get_errors ["c:\\Users\\averr\\AlphaEdge\\alphaedge\\core\\_stubs"]
```
→ Les trois doivent donner zéro violation.

Ferme tous les onglets ouverts :
```
① Charge l'outil (obligatoire pour les outils différés) :
   tool_search_tool_regex "run_vscode_command"

② Appelle l'outil récupéré :
   commandId : workbench.action.closeAllEditors
```

⚠️ Attends la confirmation de fermeture avant de continuer.

Annonce : **`_stubs/` ✅ — N erreurs corrigées.**
Demande `GO` pour passer à l'ÉTAPE 1.

─────────────────────────────────────────────
ÉTAPE 1 — TABLEAU DES DOSSIERS
─────────────────────────────────────────────
Scanne **l'ensemble du projet** (pas seulement `alphaedge/`)
et dresse un tableau de **tous les dossiers et sous-dossiers
contenant des fichiers `.py`**, en excluant :
`.venv/`, `__pycache__/`, `build/`, `.git/`.
```powershell
Get-ChildItem -Path "c:\Users\averr\AlphaEdge" `
  -Filter "*.py" -Recurse |
  Where-Object { $_.FullName -notmatch
    "(__pycache__|\.venv|\\build\\|\.git)" } |
  Select-Object DirectoryName |
  Sort-Object DirectoryName -Unique
```

Format du tableau :
```
DOSSIER                          | FICHIERS .py | STATUT
---------------------------------|--------------|--------
(racine)/                        |      1       | ⏳  ← setup.py
alphaedge/config/                |      3       | ⏳
alphaedge/core/_stubs/           |      6       | ✅
alphaedge/engine/                |     21       | ⏳
scripts/                         |      3       | ⏳
...
```

⚠️ La racine du projet (`setup.py`) et `scripts/`
(`param_sweep.py`, `_opt_run.py`, `_sl_sweep.py`)
font partie du périmètre d'audit — ne pas les oublier.

Affiche le tableau complet.
Demande `GO` pour démarrer le premier dossier.

─────────────────────────────────────────────
ÉTAPE 2 — TRAITEMENT DOSSIER PAR DOSSIER
─────────────────────────────────────────────
Pour chaque dossier dans l'ordre du tableau (sauf `_stubs/`
déjà traité), répète la séquence suivante.

**Ne passe jamais au dossier suivant tant que le dossier
courant n'est pas entièrement propre :
0 erreur ruff · 0 paramètre ARG · 0 erreur Pyright.**

### 2a — Ouvrir tous les fichiers dans l'éditeur VSCode

⛔ **BLOQUANT** — ouvre **chaque** fichier `.py` du dossier
courant dans VSCode via la commande PowerShell ci-dessous
AVANT toute lecture ou modification. Cette commande ouvre
physiquement les onglets dans la fenêtre VSCode active.

```powershell
$dossier = "c:\Users\averr\AlphaEdge\<chemin_dossier>"
Get-ChildItem -Path $dossier -Filter "*.py" |
  Where-Object { $_.FullName -notmatch "__pycache__" } |
  Sort-Object Name |
  ForEach-Object { code --reuse-window $_.FullName }
```

⚠️ Remplace `<chemin_dossier>` par le chemin réel du
dossier courant à chaque itération.
⚠️ Attends la fin de l'exécution (tous les onglets doivent
être visibles dans l'éditeur) avant de passer à l'étape 2c.

✅ Dès que les onglets sont visibles, VSCode/Pylance analyse
automatiquement les fichiers ouverts et alimente le panneau
**PROBLEMS** (onglet en bas de l'éditeur). Passe directement
à l'étape 2c pour lire ce panneau et corriger chaque erreur
avant toute autre vérification.

### 2b — Vérifier l'alignement Cython
Pour chaque fichier du dossier qui appelle, wrap ou
interagit avec un module `alphaedge/core/*.pyx` :

1. Lis le fichier Python dans l'onglet ouvert
2. Lis le fichier `.pyx` correspondant
3. Compare signatures, paramètres, types, clés de retour
4. Corrige toute divergence dans le fichier Python

Cette vérification est obligatoire même si aucune
erreur ruff ou Pyright n'est remontée.

### 2c — Lire et vider le panneau PROBLEMS de VSCode

⛔ **BLOQUANT** — accède immédiatement au panneau PROBLEMS
de VSCode (onglet en bas de l'éditeur). Il affiche tous les
diagnostics Pylance/Pyright des fichiers ouverts. Lis-le via :
```
get_errors ["c:\\Users\\averr\\AlphaEdge\\<chemin_dossier>"]
```
C'est la source de vérité — identique au contenu visible dans
l'onglet PROBLEMS de l'éditeur VSCode.

Dresse la liste complète de toutes les erreurs remontées.

**Boucle de correction — une erreur à la fois :**
1. Prends la première erreur de la liste
2. Lis le fichier concerné dans l'onglet ouvert
3. Comprends le contexte — ne corrige jamais à l'aveugle
4. Applique la correction selon les règles de l'étape 2f
5. Relance `get_errors ["c:\\Users\\averr\\AlphaEdge\\<chemin_dossier>"]`
6. Vérifie que l'erreur est résolue et qu'aucune nouvelle
   erreur n'est apparue
7. Répète jusqu'à ce que le panneau PROBLEMS retourne **0 erreurs**

⚠️ Ne passe jamais à 2d tant que `get_errors` retourne
des erreurs. Les fichiers doivent rester ouverts pendant
toute cette phase.

### 2d — Corriger les erreurs ruff (auto-fix)
```powershell
python -m ruff check <chemin_dossier>/ --fix 2>&1
python -m ruff check <chemin_dossier>/ --fix --unsafe-fixes 2>&1
```
Si des erreurs restent après l'auto-fix → lis le fichier
dans l'onglet ouvert, comprends le contexte, corrige
manuellement via `replace_string_in_file` ou
`multi_replace_string_in_file`.
Relance jusqu'à `All checks passed!`

### 2e — Vérifier les paramètres orphelins (ARG)
⚠️ Obligatoire — ruff standard ne détecte pas ARG.
```powershell
python -m ruff check <chemin_dossier>/ --select ARG 2>&1
```

Pour chaque violation :
1. Lis le fichier dans l'onglet ouvert
2. Connecte le paramètre à son usage naturel si possible
3. Si structurellement inutilisable → renomme `_param`
   avec commentaire justificatif inline
4. Vérifie l'impact sur les call sites :
```powershell
grep_search "<nom_parametre>" alphaedge/
```
5. Ne jamais supprimer sans validation chef de projet

### 2e.bis — Audit des paramètres `_`-préfixés (angle mort de ruff)

⚠️ **CRITIQUE** — `ruff --select ARG` ignore silencieusement les
paramètres préfixés `_param` car la convention Python signifie
"intentionnellement inutilisé". Or la règle d'or du projet est
**zéro paramètre déclaré sans usage**. Ce step comble cet angle mort.

```powershell
# Trouve tous les paramètres _-préfixés dans les signatures de fonctions
Select-String -Path "<chemin_dossier>\*.py" `
  -Pattern "def .*\b_[a-z][a-z0-9_]*\s*[=:,)]" -Recurse
```

Pour chaque occurrence trouvée :
1. Lis la fonction entière dans l'onglet ouvert (de la `def` jusqu'à
   la fin du corps — **ligne par ligne sans exception**)
2. Vérifie si `_param` apparaît dans le corps de la fonction
3. **S'il n'apparaît pas → c'est un orphelin caché** :
   - Renomme `_param` → `param`
   - Identifie l'usage naturel (validation, condition, calcul, log)
   - Connecte-le à cet usage
   - ``if not param: raise ValueError(...)`` est souvent le
     connecteur naturel minimal pour les paramètres `str`
4. Ne jamais laisser un paramètre `_`-préfixé non utilisé —
   Pylance le signale comme `"_param" is not accessed` même
   si ruff ne le voit pas

### 2f — Règles de correction par type d'erreur

Référence pour la boucle de la section 2c.
Pour chaque erreur rencontrée dans le panneau PROBLEMS :

**Import non utilisé** → supprimer l'import.

**Type incompatible** → corriger l'annotation ou le code.

**Variable, paramètre ou fonction non utilisé(e)**
(`"X" is not accessed` / `"_x" is not accessed`) →
**Règle d'or — zéro orphelin** :
toute variable, tout paramètre et toute fonction présents
dans le code doivent être utilisés avec cohérence et pertinence.
Cela inclut les paramètres `_`-préfixés — le préfixe `_` ne
dispense PAS d'une connexion à un usage naturel.
Marche à suivre :
1. Lis le fichier **ligne par ligne** dans l'onglet ouvert
   (de la ligne 1 à la dernière — aucune ligne ne doit être sautée)
2. Identifie où l'identifiant devrait logiquement être utilisé
   (validation, logging, assertion, condition, valeur de retour…)
3. Connecte-le à son usage naturel
4. Ne le supprime pas
5. **Exception unique** : index de boucle sans usage
   possible → renomme `_i` + commentaire inline
6. Si inutile après analyse → signale au chef de projet
   avant toute suppression

**Divergence avec Cython** → applique la règle
d'alignement Cython définie en haut du prompt.

**Toute autre erreur** → lire, comprendre, corriger.

→ Reprends à l'étape 2c (boucle) après chaque correction.

### 2g — Vérification finale du dossier
```powershell
python -m ruff check <chemin_dossier>/ 2>&1 |
  Select-Object -Last 3
python -m ruff check <chemin_dossier>/ --select ARG 2>&1 |
  Select-Object -Last 3
```
→ Les deux : `All checks passed!`
```
get_errors ["c:\\Users\\averr\\AlphaEdge\\<chemin_dossier>"]
```
→ `No errors found.`

### 2h — Fermer les fichiers et annoncer

⛔ **CONDITION PRÉALABLE** — ne ferme les fichiers que lorsque
les trois conditions suivantes sont simultanément réunies :
- `get_errors` retourne **0 erreurs** (panneau PROBLEMS vide)
- `python -m ruff check <chemin_dossier>/ --select ARG` → 0 violation
- `python -m ruff check <chemin_dossier>/` → `All checks passed!`

Ferme tous les onglets ouverts :
```
① Charge l'outil (obligatoire pour les outils différés) :
   tool_search_tool_regex "run_vscode_command"

② Appelle l'outil récupéré :
   commandId : workbench.action.closeAllEditors
```

⚠️ **BLOQUANT** — attends la confirmation de fermeture
avant d'ouvrir les fichiers du dossier suivant (2a).

Annonce :
**`<dossier>/` ✅ — ruff: N · ARG: N · Pyright: N ·
Alignement Cython: N divergences corrigées.**

Met à jour le tableau :
```
DOSSIER                          | FICHIERS .py | STATUT
---------------------------------|--------------|--------
alphaedge/config/                |      3       | ✅
alphaedge/core/_stubs/           |      5       | ✅
alphaedge/engine/                |     21       | ✅ ← vient de finir
alphaedge/signals/               |      8       | ⏳ ← suivant
...
```

Demande `GO` pour passer au dossier suivant.

─────────────────────────────────────────────
CONTRAINTES DU PROJET ALPHAEDGE
─────────────────────────────────────────────
- ❌ Ne jamais utiliser `# type: ignore` ou
  `# pyright: ignore`
- ❌ Ne jamais utiliser `Any` comme raccourci de type
- ❌ Ne jamais utiliser `datetime.utcnow()` →
  utiliser `datetime.now(timezone.utc)`
- ❌ Ne jamais toucher `alphaedge/core/*.pyx`
- ❌ Ne jamais modifier `alphaedge/utils/timezone.py`
  ou `session_manager.py` sans relancer les tests
  DST edge cases
- ❌ Ne jamais hardcoder de valeurs numériques
  (pips, RR, risk%) → tout passe par
  `alphaedge/config/constants.py`
- ❌ **RÈGLE D'OR — zéro orphelin** : toute variable,
  fonction ET paramètre présent dans le code doit être
  utilisé. Couvre :
  - Variables locales (Pyright `"X" is not accessed`)
  - Fonctions non appelées (Pyright)
  - Paramètres non référencés dans le corps
    (`ruff --select ARG` uniquement)
  Ne jamais supprimer ou masquer sans comprendre
  l'intention et avoir connecté à l'usage naturel.
- ❌ **RÈGLE ALIGNEMENT CYTHON** : tout fichier Python
  interagissant avec `alphaedge/core/*.pyx` doit être
  parfaitement aligné (signatures, paramètres, types,
  clés de retour). Corrige toujours le Python, jamais
  le `.pyx`.
- ✅ Python 3.11.9 strictement
- ✅ Grouper les corrections avec
  `multi_replace_string_in_file` quand possible
- ✅ Toujours ouvrir les fichiers via PowerShell
  `code --reuse-window <chemin>` avant toute modification.
  Cette commande ouvre les onglets dans la fenêtre VSCode
  active de l'utilisateur. Attendre la fin de l'exécution.

─────────────────────────────────────────────
ÉTAPE 3 — VÉRIFICATION GLOBALE FINALE
─────────────────────────────────────────────
Après tous les dossiers :
```powershell
python -m ruff check alphaedge/ --select ARG 2>&1
make qa
```

→ Premier : `All checks passed!`
  (zéro ARG orphelin sur tout le projet)
→ Second : 0 ruff · 0 pyright · 504 tests ✅ · coverage ≥ 80%

─────────────────────────────────────────────
SORTIE FINALE
─────────────────────────────────────────────
```
✅ Correction complète terminée — ALPHAEDGE
   Dossiers traités                  : X
   Fichiers Python corrigés          : X
   Erreurs ruff corrigées            : X
   Paramètres orphelins (ARG)        : X
   Erreurs Pyright corrigées         : X
   Divergences Python↔Cython         : X
   make qa :
     504 tests  ✅
     0 ruff     ✅
     0 pyright  ✅
     coverage   X% ✅
```

─────────────────────────────────────────────
DÉMARRAGE
─────────────────────────────────────────────
Commence maintenant par l'**ÉTAPE 0**.

Exécute d'abord la commande PowerShell d'ouverture
des stubs dans VSCode, audite l'alignement Cython,
corrige, valide, puis demande `GO` pour l'ÉTAPE 1.
