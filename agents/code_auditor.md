# ALPHAEDGE — Agent : Code Auditor

Checklists de sécurité, qualité et intégrité du code.

---

## Rôle

Identifier les régressions, les violations de conventions, les problèmes de sécurité et les erreurs silencieuses avant merge.

---

## Checklist Sécurité

### Credentials & Secrets

- [ ] Aucun token, mot de passe ou clé dans le code source
- [ ] `.env` absent du repo (seul `.env.example` commité)
- [ ] `ALPHAEDGE_ACTION_PLAN.md` absent du tracking Git
- [ ] Aucun `*.log` commité
- [ ] Les credentials IB (host, port, clientId) viennent de `config.yaml` ou `.env`, jamais hardcodés

### IB Gateway

- [ ] Port paper (4002) par défaut — jamais port live (4001) par défaut
- [ ] `ALPHAEDGE_PAPER=true` dans `.env.example`
- [ ] Timeout explicite sur chaque `asyncio.wait_for` (fill verification = 10s)
- [ ] Circuit breaker intact (`IB_CIRCUIT_BREAKER_MAX_FAILURES = 5`)

### Web Dashboard (si modifié)

- [ ] Auth HMAC sur toutes les routes API
- [ ] URL webhook Discord/Telegram vient de la config, pas hardcodée
- [ ] `urlopen` sur URL de config uniquement (`# nosec B310` documenté)

---

## Checklist Qualité Code

### Imports & Types

- [ ] Aucun `# type: ignore` ou `# pyright: ignore` ajouté
- [ ] Aucun `Any` comme annotation de type
- [ ] Imports circulaires vérifiés (`pylint --disable=all --enable=cyclic-import`)
- [ ] Imports lazy documentés avec commentaire explicatif

### Conventions ALPHAEDGE

- [ ] Toute valeur numérique de trading → `constants.py` (jamais inline)
- [ ] Timezones → `zoneinfo` uniquement (`pytz` interdit)
- [ ] Pip sizes → `PIP_SIZES.get(pair, DEFAULT_PIP_SIZE)` (`DEFAULT_PIP_SIZE` défini dans `constants.py`)
- [ ] Logs → `get_logger()` de `utils/logger.py` uniquement (pas `logging.getLogger`)

### Cython

- [ ] Après modification `.pyx` : `make build` exécuté
- [ ] Stubs `_stubs/*.py` synchronisés avec les signatures `.pyx`
- [ ] Tests ne dépendent pas du `.pyd` compilé (utilisent les stubs)

---

## Checklist Gestion Erreurs Silencieuses

- [ ] Toute exception `except Exception` a un log explicite (pas de `pass` nu)
- [ ] Les retours `None` / `False` des fonctions Cython sont tous vérifiés
- [ ] Aucun état IB assumé sans vérification (`is_connected()` avant toute requête)
- [ ] Fill timeout traité (cancel + log WARNING si pas de fill en 10s)

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

## Checklist Avant Merge

1. `ruff check alphaedge/` → 0 erreur
2. `pyright alphaedge/` → 0 erreur, 0 warning
3. `pytest alphaedge/tests/ --tb=short` → 574 passed
4. `pytest --cov-fail-under=80` → ≥ 80% coverage
5. `bandit -r alphaedge/ -ll` → 0 Medium, 0 High (via `make qa-strict`)
6. `git diff .env.example` → `ALPHAEDGE_PAPER=true` intact
7. `git status` → aucun `.log`, `.env`, `ALPHAEDGE_ACTION_PLAN.md`

---

## Patterns Interdits

```python
# ❌ Interdit
from typing import Any
def func(x: Any) -> Any: ...

# ❌ Interdit
except Exception:
    pass

# ❌ Interdit
import pytz
tz = pytz.timezone("America/New_York")

# ❌ Interdit
PIP_SIZE = 0.0001  # hardcodé inline

# ❌ Interdit
# type: ignore

# ✅ Correct
from zoneinfo import ZoneInfo
tz = ZoneInfo("America/New_York")

# ✅ Correct
from alphaedge.config.constants import PIP_SIZES
pip_size = PIP_SIZES.get(pair, 0.0001)
```
