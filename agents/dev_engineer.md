# ALPHAEDGE — Agent : Dev Engineer

Procédure d'ajout de fonctionnalité et pipeline CI.

---

## Rôle

Implémenter des modifications du code en respectant les conventions ALPHAEDGE et sans introduire de régressions.

---

## Procédure — Ajout d'une Fonctionnalité

### 1. Avant de commencer

```powershell
# Activer le venv
.\.venv\Scripts\Activate.ps1

# Confirmer que la baseline est verte
python -m pytest alphaedge/tests/ -q  # doit afficher "574 passed"
python -m ruff check alphaedge/       # doit afficher "All checks passed!"
python -m pyright alphaedge/          # doit afficher "0 errors"
```

Lire `tasks/lessons.md` — sans exception.

### 2. Identifier le périmètre

- Lister les fichiers à modifier (minimum nécessaire)
- Vérifier les dépendances dans `architecture/system_design.md`
- Si modification d'un `.pyx` → prévoir `make build`

### 3. Implémenter

- Toute valeur numérique → `constants.py`
- Toute timezone → `zoneinfo` uniquement
- Toute annotation de type → précise (pas `Any`)
- Toute exception catchée → log explicite

### 4. Tests

- Ajouter un test dans `alphaedge/tests/`
- Nommage : `test_<module>_<scenario>.py`
- Un scénario par fichier, `pytest.mark.parametrize` pour les variantes

### 5. Validation finale

```powershell
# Si .pyx modifié :
python setup.py build_ext --inplace   # make build

# QA complète
python -m ruff check alphaedge/
python -m pyright alphaedge/
python -m pytest alphaedge/tests/ --cov=alphaedge --cov-fail-under=80 -q
```

**574 tests doivent passer. 0 erreur lint. 0 erreur type. ≥ 80% coverage.**

---

## Pipeline CI (make qa)

```
make qa          = ruff + pyright + pytest (--cov-fail-under=80)
make qa-strict   = make qa + pylint + bandit
make build       = Cython compilation (après .pyx uniquement)
make test        = pytest seul (sans lint/type)
make bandit      = sécurité Medium+ uniquement
```

---

## Workflow Cython (obligatoire si .pyx modifié)

```
1. Éditer le .pyx
2. python setup.py build_ext --inplace   ← make build
3. python -m pytest alphaedge/tests/     ← make qa
```

**Un .pyx édité sans `make build` = silencieusement cassé au runtime.**

---

## Règle Anti-Hallucination

```xml
<investigate_before_answering>
Never speculate about code or files you have not opened. Read relevant files
before answering questions about the codebase. If the user references a prompt
or result file, read it first to detect any changes before assuming its current
state matches a previous version.
</investigate_before_answering>
```

---

## Interdictions Absolues


- ❌ Modifier `core/*.pyx` sans instruction explicite de l'utilisateur
- ❌ Committer `.env`, `*.log`, `ALPHAEDGE_ACTION_PLAN.md`
- ❌ `# type: ignore` ou `# pyright: ignore`
- ❌ `Any` comme type annotation
- ❌ Valeurs numériques de trading inline (toujours `constants.py`)
- ❌ `pytz` ou offsets UTC hardcodés
- ❌ Marquer une tâche terminée sans `make qa` passant

---

## Fichiers Clés à Connaître

| Fichier | Rôle |
|---------|------|
| `alphaedge/config/constants.py` | Source unique de tous les paramètres numériques |
| `alphaedge/config/loader.py` | YAML → AppConfig typé |
| `alphaedge/engine/session_lifecycle.py` | Boucle async principale |
| `alphaedge/engine/signal_pipeline.py` | Orchestrateur du pipeline signal |
| `alphaedge/core/_stubs/` | Stubs Python purs pour les tests |
| `tasks/lessons.md` | Leçons passées — lire avant chaque session |
| `.claude/context.md` | Architecture complète |
| `architecture/decisions.md` | ADRs |

---

## Convention de Nommage des Tests

| Type | Pattern | Exemple |
|------|---------|---------|
| Happy path | `test_<module>_<feature>.py` | `test_fcr_detector_detect.py` |
| Edge case | `test_<module>_<scenario>.py` | `test_risk_manager_daily.py` |
| Validation | `test_<module>_validation.py` | `test_order_manager_validation.py` |
