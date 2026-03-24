# Référence — Types Cython ↔ Python 3.11

## Types scalaires

| Python 3.11 | Cython `cdef` | Notes |
|-------------|---------------|-------|
| `int` | `int` / `long` / `long long` | préférer `long long` pour éviter overflow |
| `float` | `double` | `float` = 32-bit en Cython, utiliser `double` |
| `bool` | `bint` | 0 = False, 1 = True |
| `str` | `str` / `unicode` | string Python — pas de gain Cython |
| `bytes` | `bytes` | OK en Cython |

## Types containers

| Python 3.11 | Cython | Notes |
|-------------|--------|-------|
| `list` | `list` | pas de typage fort des éléments |
| `dict` | `dict` | pas de typage fort des clés/valeurs |
| `tuple` | `tuple` | immuable, pas de cdef struct |
| `list[dict]` | `list` | pas de generic en Cython pré-3 |

## Déclarations Cython

```cython
# Variables locales typées (gain perf)
cdef double x = 1.0
cdef long long n = 100
cdef bint flag = True

# Fonctions C internes (non exposées à Python)
cdef double _internal_calc(double a, double b):
    return a * b

# Fonctions Python + C (exposées à Python)
cpdef double public_calc(double a, double b):
    return _internal_calc(a, b)

# Fonctions Python pures (exposition maximale)
def python_func(a: float, b: float) -> float:
    return _internal_calc(a, b)
```

## Annotations de type pour stubs (.pyi)

```python
# Dans le .pyi — utiliser les types Python natifs
def detect_fcr(
    candles_data: list[dict],    # pas list[dict[str, float]]
    min_range_pips: float,
    pip_size: float,
) -> dict | None: ...            # retour dict Python, pas cdef struct
```

## Types interdits dans ALPHAEDGE

| Type | Raison |
|------|--------|
| `Any` | Interdit — rustine mypy |
| `object` | Éviter — perd toute aide mypy |
| `# type: ignore` | Interdit — corriger la cause |
| `pytz.timezone` | Interdit — utiliser `zoneinfo` |

## Règle générale

> **Typer les variables internes Cython** (`cdef double`) pour la performance.
> **Garder les interfaces publiques en types Python** (`float`, `int`, `dict`) pour la compatibilité mypy/Pylance.
