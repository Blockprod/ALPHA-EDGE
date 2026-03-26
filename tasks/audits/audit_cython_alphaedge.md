---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: audit_cython_alphaedge.md
derniere_revision: 2026-03-25
creation: 2026-03-25 à 23:00
---

# Audit Cython — ALPHAEDGE
**Date :** 2026-03-25
**Périmètre :** `alphaedge/core/` — modules Momentum+Carry (momentum_detector, risk_manager, order_manager), stubs, __init__.py/.pyi, build system
**Exclusions :** logique stratégique FCR, engine/, sécurité credentials

---

## BLOC 1 — INVENTAIRE DES MODULES CYTHON

### Modules actifs (utilisés dans le pipeline Momentum+Carry)

| Module | .pyx | .pyd | .c | Stub _stubs/ | Nom stub correct |
|--------|------|------|----|--------------|-----------------|
| `momentum_detector` | ✅ | ✅ `momentum_detector.cp311-win_amd64.pyd` | ✅ | ✅ `momentum_detector.py` | ✅ |
| `risk_manager` | ✅ | ✅ `risk_manager.cp311-win_amd64.pyd` | ✅ | ✅ `risk_manager.py` | ✅ |
| `order_manager` | ✅ | ✅ `order_manager.cp311-win_amd64.pyd` | ✅ | ✅ `order_manager.py` | ✅ |

**Observation :** les fichiers `.c` (artefacts transpilation Cython) sont présents dans le dépôt — cohérent avec le workflow `build_ext --inplace`.

### Modules orphelins (compilés mais jamais importés)

| Module | .pyx | .pyd | .c | Stub _stubs/ | Import Python |
|--------|------|------|----|--------------|--------------|
| `fcr_detector` | ✅ | ✅ | ✅ | ❌ | ❌ aucun |
| `gap_detector` | ✅ | ✅ | ✅ | ❌ | ❌ aucun |
| `engulfing_detector` | ✅ | ✅ | ✅ | ❌ | ❌ aucun |

**Constat (→ C-02) :** Ces 3 modules sont listés dans `setup.py:35-46` et compilés à chaque `make build`, mais `strategy._import_core_modules()` (ligne 77) n'en importe aucun, aucun test n'en dépend, et ils ne sont pas exportés via `__init__.py`. Ce sont des artefacts de l'ancienne stratégie FCR — dette active.

---

## BLOC 2 — COHÉRENCE DES INTERFACES

### momentum_detector — `detect_momentum`

**Signature .pyx** (`momentum_detector.pyx:193-198`) :
```python
def detect_momentum(
    bars: list,
    fast_period: int,
    slow_period: int,
    adx_period: int,
    adx_threshold: float,
) -> dict | None:
```

**Signature stub** (`_stubs/momentum_detector.py:103-111`) :
```python
def detect_momentum(
    bars: list[dict[str, Any]],
    fast_period: int,
    slow_period: int,
    adx_period: int,
    adx_threshold: float,
) -> dict[str, Any] | None:
```

**Verdict : CONFORME ✅** — paramètres identiques, ordre identique. Le stub annote plus précisément (`list[dict[str, Any]]`) — acceptable et souhaitable.
Retour `None` documenté dans les deux fichiers ✅. Cas `None` couvert par `test_momentum_detector_insufficient.py` et `test_momentum_detector_no_trend.py` ✅.

---

### risk_manager — `calculate_position_size`

**Signature .pyx** (`risk_manager.pyx:122-131`) :
```
(account_equity, risk_pct, sl_pips, pair, pip_size, lot_type, min_lots, max_lots, exchange_rate=0.0)
```

**Signature stub** (`_stubs/risk_manager.py:8-17`) :
```
(account_equity, risk_pct, sl_pips, pair, pip_size, lot_type, min_lots, max_lots, exchange_rate=0.0)
```

**Verdict : CONFORME ✅** — identiques, y compris le paramètre optionnel `exchange_rate`.

---

### risk_manager — `check_daily_limit`

**Signature .pyx** (`risk_manager.pyx:202-207`) :
```
(starting_equity, current_equity, max_daily_loss_pct, trades_today, max_trades)
```

**Signature stub** (`_stubs/risk_manager.py:43-48`) :
```
(starting_equity, current_equity, max_daily_loss_pct, trades_today, max_trades)
```

**Verdict : CONFORME ✅** — signatures identiques.

**⚠️ ÉCART DOCUMENTATION (→ C-01) :** La clé de retour documentée dans `CLAUDE.md:55` est `halt_trading: True`, mais l'implémentation réelle produit `limit_breached: True` et `can_trade: False` (visible dans `risk_manager.pyx:272-278` et `_stubs/risk_manager.py:61-68`). `copilot-instructions.md` est, lui, exact (`limit_breached`). Cette divergence entre les deux sources de vérité peut induire une erreur d'agent IA qui lirait CLAUDE.md en priorité.

---

### order_manager — `create_bracket_order`

**Signature .pyx** (`order_manager.pyx:142-154`) :
```
(direction, entry_price, stop_loss, take_profit, lot_size, pip_size, spread_pips, max_spread_pips, min_rr, min_lots, max_lots, adjust_for_spread)
```

**Signature stub** (`_stubs/order_manager.py:7-19`) :
```
idem + -> dict[str, Any]
```

**Verdict : CONFORME ✅** — 12 paramètres, ordre identique, flag `adjust_for_spread` (bint / bool) cohérent.

---

## BLOC 3 — `__init__.pyi` ET `__init__.py`

### Exports `__init__.py` (`alphaedge/core/__init__.py:149-151`)

```python
order_manager: ModuleType = _load_core_module("order_manager")
risk_manager: ModuleType = _load_core_module("risk_manager")
momentum_detector: ModuleType = _load_core_module("momentum_detector")
```

Les 3 modules actifs sont exportés. Les fonctions publiques (`get_backend_name`, `get_fallback_modules`, `reset_backend_tracking`, `load_core_module`) sont exposées. ✅

### `__init__.pyi` (`alphaedge/core/__init__.pyi`)

```python
from alphaedge.core._stubs import momentum_detector as momentum_detector
from alphaedge.core._stubs import order_manager as order_manager
from alphaedge.core._stubs import risk_manager as risk_manager

def get_backend_name() -> str: ...
def get_fallback_modules() -> tuple[str, ...]: ...
def reset_backend_tracking() -> None: ...
def load_core_module(name: str) -> ModuleType: ...
```

**Cohérence avec `__init__.py` :** ✅ Les 4 fonctions publiques déclarées correspondent.
**Re-exports typés :** ✅ Pyright résout les types via `_stubs/`, stratégie documentée en en-tête du `.pyi`.
**Fallback documenté :** ✅ Commentaire en tête du `.pyi` explique la raison.

**Observation :** `fcr_detector`, `gap_detector`, `engulfing_detector` sont absents du `.pyi` et du `.py` — cohérent avec leur statut orphelin (Bloc 1).

### Mécanisme fallback (`__init__.py:80-93`)

```python
try:
    module = importlib.import_module(f"alphaedge.core.{name}")
    _record_backend(name, "compiled")
    return module
except ImportError:
    _FALLBACK_MODULES.add(name)
    _record_backend(name, "stubs")
    if _is_production():
        raise ImportError(...)   # ✅ fail-fast en prod
    logger.warning(...)
    return importlib.import_module(f"alphaedge.core._stubs.{name}")
```

**Verdict :** ✅ Logique correcte — fallback silencieux en dev, `raise` en prod. Bien implémenté.

---

## BLOC 4 — BUILD ET REPRODUCTIBILITÉ

### `setup.py`

| Critère | Valeur | Statut |
|---------|--------|--------|
| Extensions listées (6) | fcr, gap, engulfing, order_manager, risk_manager, momentum_detector | ✅ |
| `language_level="3"` | `compiler_directives` ligne 64 | ✅ |
| `boundscheck=False` | `compiler_directives` | ✅ |
| `wraparound=False` | `compiler_directives` | ✅ |
| `cdivision=True` | `compiler_directives` | ✅ |
| `annotate` | Non défini → `False` (pas de `.html`) | ✅ |

### `Makefile`

| Critère | Commande | Statut |
|---------|---------|--------|
| `make build` produit les .pyd | `python setup.py build_ext --inplace` | ✅ |
| `make clean` supprime .pyd, .c, build/ | Lignes 70-76 | ✅ |
| `make clean` supprime `.html` | Non nécessaire (annotate=False) | ✅ |
| `build/` dans `.gitignore` | Ligne 21 | ✅ |
| `*.pyd` dans `.gitignore` | Ligne 13 | ✅ |

**Cython version :** `Cython==3.0.10` pincé dans `requirements.txt`. ✅
**Language level par fichier :** chaque `.pyx` commence par `# cython: language_level=3, ...` — redondant avec `setup.py` mais non problématique, cohérent. ✅

**CI/CD :** Aucun workflow GitHub Actions détecté dans le workspace (`.github/workflows/` absent). La reproductibilité du build n'est pas vérifiée en CI automatisé — risque de régression silencieuse si le build casse entre sessions.

**(→ C-03) `make clean` supprime les `.c`** (`Makefile:73`) : sans Cython disponible, `make build` échouera après un `make clean` car Cython est requis pour régénérer les `.c`. Pas de message d'avertissement dans le Makefile.

---

## BLOC 5 — UTILISATION DES STUBS DANS LES TESTS

### Backend imposé

`conftest.py:21` :
```python
os.environ.setdefault("ALPHAEDGE_CORE_BACKEND", "stubs")
```

100% des tests s'exécutent avec les stubs pure-Python. Le backend `compiled` n'est jamais exercé en CI. ✅ pour la reproductibilité cross-env ; ⚠️ pour la couverture du chemin compilé (→ C-04).

### Couverture des modules actifs

| Module | Fichiers de tests | Cas `None`/invalide couvert |
|--------|------------------|-----------------------------|
| `momentum_detector` | `test_momentum_detector_bull_trend.py`, `test_momentum_detector_bear_trend.py`, `test_momentum_detector_no_trend.py`, `test_momentum_detector_insufficient.py` | ✅ (`None` via ADX bas, via bars insuffisants) |
| `risk_manager` | `test_risk_manager_daily.py`, `test_risk_manager_sizing.py`, `test_risk_manager_pair_limit.py`, `test_risk_manager_slippage.py` | ✅ (`is_valid: False`, `limit_breached: True`) |
| `order_manager` | `test_order_manager_validation.py`, `test_order_manager_bracket.py`, `test_order_manager_lots.py` | ✅ (`is_valid: False`, `rejection_reason`) |

**Convention de nommage `test_<module>_<scenario>.py` :** ✅ respectée pour tous les fichiers cités.

### Fallback `_load_core_module` — non testé (→ C-04)

`test_core_backend_visibility.py` teste `load_core_module("fcr_detector")` via mock, mais **aucun test ne valide la cascade réelle** :
1. `ALPHAEDGE_CORE_BACKEND=compiled` → import depuis `.pyd` réussi
2. `ALPHAEDGE_CORE_BACKEND=compiled` → `.pyd` absent → `ImportError` puis fallback stubs vérifié
3. `ALPHAEDGE_CORE_BACKEND=compiled` + `ALPHAEDGE_ENV=production` → `raise` confirmé

---

## SYNTHÈSE

| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact | Effort |
|----|------|-------------|---------------|----------|--------|--------|
| C-01 | 2 | `CLAUDE.md` documente `halt_trading: True` comme retour de `check_daily_limit()`, mais l'implémentation retourne `limit_breached` / `can_trade` — divergence source de vérité IA | `CLAUDE.md:55` · `risk_manager.pyx:272` · `_stubs/risk_manager.py:61` | 🟠 Majeur | Agent IA peut vérifier la mauvaise clé → STOP incorrect ou absent | Très faible |
| C-02 | 1/4 | 3 modules orphelins (`fcr_detector`, `gap_detector`, `engulfing_detector`) listés dans `setup.py:35-46` et compilés à chaque `make build` — jamais importés par aucun code Python, aucun stub, aucun test dédié | `setup.py:35-46` · `strategy.py:77` | 🟡 Mineur | Build overhead ~15 s inutile, dette silencieuse | Moyen |
| C-03 | 4 | `make clean` supprime les `.c` (`Makefile:73`) sans avertir : sans Cython disponible, `make build` échouera sans message clair | `Makefile:73` | 🟡 Mineur | Rebuilt cassé sur machine sans Cython après clean | Très faible |
| C-04 | 5 | Aucun test ne couvre `ALPHAEDGE_CORE_BACKEND=compiled` ni la cascade `ImportError→fallback` ni le `raise` en mode production dans `_load_core_module()` | `__init__.py:80-93` · `conftest.py:21` | 🟡 Mineur | Les .pyd compilés ne sont pas vérifiés automatiquement | Moyen |
