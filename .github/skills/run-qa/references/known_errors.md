# Erreurs QA connues — ALPHAEDGE

> Référence pour `run-qa`. Erreurs Ruff / Pyright réellement rencontrées sur ce projet.
> Mise à jour après chaque nouvelle erreur résolue.

---

## Erreurs Ruff

| Code | Description | Contexte ALPHAEDGE | Fix |
|------|-------------|-------------------|-----|
| `ARG001` | Paramètre de fonction non utilisé | Invisible avec `ruff check` seul — nécessite `ruff check --select ARG` | Connecter le paramètre à un usage naturel (`if not param: raise ValueError(...)`) ou préfixer `_` uniquement si privé |
| `E501` | Ligne trop longue (> 88 chars) | Fréquent dans les f-strings loguru | Découper sur plusieurs lignes avec `\` ou parenthèses |
| `S101` | `assert` dans du code de production | Détecté dans les modules `engine/` | Remplacer par `if … raise ValueError(...)` |
| `N803` | Argument en CamelCase (doit être lowercase) | Stubs Cython mal typés | Renommer en snake_case |
| `N806` | Variable en CamelCase dans une fonction | Idem | Renommer en snake_case |
| `UP007` | `Optional[X]` → `X \| None` (Python 3.10+) | Annotations legacy | Remplacer par `X \| None` |
| `UP006` | `List[X]` → `list[X]` (Python 3.9+) | Annotations legacy | Remplacer par `list[X]` |
| `B011` | `assert False` → `raise AssertionError` | Tests incorrects | Utiliser `pytest.fail()` ou `raise` |

## Erreurs Mypy / Pyright

| Code / Message | Cause | Fix |
|----------------|-------|-----|
| `Missing return type annotation` | Fonction publique sans annotation | Ajouter `: ReturnType` à la signature |
| `Incompatible return value type` | Type de retour diverge de l'annotation | Corriger le type retourné ou l'annotation |
| `Module "X" has no attribute "Y"` | Stub `.pyi` désynchronisé du `.pyx` | Synchroniser `_stubs/<module>.py` avec le `.pyx` |
| `Cannot find implementation` | `.pyx` non compilé | `make build` |
| `Argument 1 to "X" has incompatible type "int"; expected "float"` | Passage int où float attendu | `float(val)` ou corriger l'annotation |
| `"Any" not allowed` | `Any` utilisé comme annotation | Trouver le bon type union ou créer un Protocol |
| `# type: ignore` commentaire présent | Interdit dans ce projet | Corriger la cause racine, jamais silencer |

---

## Workflow de diagnostic

```powershell
# Étape 1 — Ruff standard
ruff check alphaedge/

# Étape 2 — Ruff ARG (orphan parameters — invisible à l'étape 1)
ruff check --select ARG alphaedge/

# Étape 3 — Pyright (mypy)
make qa   # inclut pyright via pyproject.toml

# Étape 4 — Coverage (si nouveau code)
# Vérifier que config/, utils/, core/ restent ≥ 80%
```

---

## Règle d'or ARG

Après toute correction impliquant des paramètres de fonctions :
1. Lancer `ruff check --select ARG alphaedge/`
2. Grepper manuellement les `def .*\b_[a-z]` pour vérifier que chaque paramètre `_prefixé` est utilisé dans le corps de la fonction
3. Pylance peut remonter `"_param" is not accessed` en WARNING — pas toujours visible via `get_errors`
