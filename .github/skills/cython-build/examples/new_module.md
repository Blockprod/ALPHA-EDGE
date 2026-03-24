# Exemple — Créer un nouveau module .pyx

## Contexte

Quand ajouter un nouveau module Cython complet dans `alphaedge/core/`
(ex: un nouveau détecteur ou filtre de signal).

## Fichiers à créer (4 fichiers)

```
alphaedge/core/my_detector.pyx       ← logique Cython
alphaedge/core/my_detector.pyi       ← type hints (Pylance)
alphaedge/core/_stubs/my_detector.py ← stub Python (tests + mypy)
alphaedge/tests/test_my_detector_<scenario>.py
```

## Étapes

### 1. Écrire le .pyx

```cython
# alphaedge/core/my_detector.pyx
# cython: language_level=3

def detect_my_signal(
    list candles_data,
    double threshold,
    double pip_size
):
    """
    Returns dict | None — STOP pipeline si None.
    """
    if not candles_data or len(candles_data) < 2:
        return None

    # ... logique propriétaire ...

    return {
        "detected": True,
        "value": threshold,
    }
```

### 2. Écrire le stub .pyi

```python
# alphaedge/core/my_detector.pyi
def detect_my_signal(
    candles_data: list[dict],
    threshold: float,
    pip_size: float,
) -> dict | None: ...
```

### 3. Écrire le stub Python pour les tests

```python
# alphaedge/core/_stubs/my_detector.py
def detect_my_signal(
    candles_data: list[dict],
    threshold: float,
    pip_size: float,
) -> dict | None:
    if not candles_data or len(candles_data) < 2:
        return None
    return {"detected": True, "value": threshold}
```

### 4. Déclarer dans setup.py

```python
# setup.py — ajouter à la liste des extensions
Extension("alphaedge.core.my_detector", ["alphaedge/core/my_detector.pyx"]),
```

### 5. Exposer dans core/__init__.py si nécessaire

```python
# alphaedge/core/__init__.py
try:
    from alphaedge.core.my_detector import detect_my_signal
except ImportError:
    from alphaedge.core._stubs.my_detector import detect_my_signal  # type: ignore[no-redef]
```

### 6. Rebuild + QA

```powershell
make build
make qa
```

### 7. Commit

```
cython: add my_detector module with detect_my_signal
```

## Checklist

- [ ] `.pyx` créé avec `# cython: language_level=3`
- [ ] `.pyi` stub créé avec signature exacte
- [ ] `_stubs/my_detector.py` créé pour tests offline
- [ ] `setup.py` mis à jour
- [ ] `core/__init__.py` mis à jour avec fallback stub
- [ ] Au moins un test créé dans `tests/test_my_detector_<scenario>.py`
- [ ] `make build` → `make qa` passent
