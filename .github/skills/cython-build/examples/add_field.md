# Exemple — Ajouter un champ `cdef` dans un module .pyx existant

## Contexte

Quand ajouter un champ `cdef` à une struct ou une classe Cython existante
dans `alphaedge/core/` (ex: ajouter un nouveau paramètre de calcul au `risk_manager`).

## Workflow complet

### 1. Lire le stub avant de toucher au .pyx

```python
# alphaedge/core/_stubs/risk_manager.py  ← lire d'abord
def calculate_position_size(...) -> dict: ...
```

### 2. Modifier le .pyx

```cython
# alphaedge/core/risk_manager.pyx
# AVANT
cdef double _compute_pip_value(double lot_size, double pip_size):
    return lot_size * pip_size * 100000

# APRÈS — ajout d'un multiplicateur configurable
cdef double _compute_pip_value(double lot_size, double pip_size, double multiplier):
    return lot_size * pip_size * multiplier
```

### 3. Mettre à jour la signature dans le stub Python

```python
# alphaedge/core/_stubs/risk_manager.py
def _compute_pip_value(lot_size: float, pip_size: float, multiplier: float) -> float: ...
```

### 4. Mettre à jour les appelants (si signature publique changée)

```python
# Chercher tous les appels dans alphaedge/
grep_search("_compute_pip_value", isRegexp=False)
```

### 5. Rebuild + QA

```powershell
make build   # recompile
make qa      # lint + mypy + tests
```

### 6. Commit

```
cython: add multiplier param to _compute_pip_value in risk_manager
```

## Pièges courants

- Oublier de rebuilder après la modification `.pyx` → l'ancien `.pyd` est chargé silencieusement
- Modifier la signature publique sans mettre à jour `_stubs/` → mypy échoue
- Ne pas chercher les appelants avant de changer une signature → RuntimeError en test
