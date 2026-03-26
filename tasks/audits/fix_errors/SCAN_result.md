---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/fix_errors/SCAN_result.md
derniere_revision: 2026-03-26
creation: 2026-03-26 à 00:00
---

# SCAN — Résultat des erreurs AlphaEdge

**Date :** 2026-03-26
**Baseline :** 628 tests · 0 Ruff général · 0 Pyright

---

## Résumé exécutif

| Outil | Résultat |
|-------|----------|
| Ruff général | ✅ 0 erreur |
| Ruff ARG | 🟡 4 erreurs (ARG001) — 1 fichier |
| Pyright (config/ utils/ core/ engine/ tests/) | ✅ 0 erreur |
| IDE get_errors (PROBLEMS) | 🟠 2 erreurs typing — 1 fichier `scripts/` |

---

## FILES_TO_FIX

```python
FILES_TO_FIX = [
    {
        "file": "alphaedge/tests/test_session_restart_blocked.py",
        "errors": ["ARG"],
        "count": 4,
        "lines": [108, 109, 110, 111],
        "detail": (
            "ARG001 — 4 paramètres inutilisés dans le stub interne `_stop_early` "
            "(starting_equity, live_equity, persisted, session_start). "
            "Fix : préfixer chaque param avec `_` pour signaler l'intention."
        ),
        "priority": "P2",  # tests/ — dans le périmètre QA
    },
    {
        "file": "scripts/_cv_sweep.py",
        "errors": ["typing"],
        "count": 2,
        "lines": [74, 76],
        "detail": (
            "`_backtest_pair` retourne `tuple[list[TradeRecord], dict[str, int]]` "
            "mais le script assigne le résultat directement à `trades` utilisé ensuite "
            "comme `list[TradeRecord]`. "
            "Fix : déstructurer → `trades, _filters = _backtest_pair(...)`."
        ),
        "priority": "P1",  # scripts/ — hors périmètre pytest mais cassé fonctionnellement
    },
]
```

---

## Détail par fichier

### 1 · `alphaedge/tests/test_session_restart_blocked.py` — ARG001

**Outil :** Ruff `--select ARG`
**Scope :** dans le périmètre QA (tests/)

```
ARG001  ligne 108  starting_equity: float   — unused
ARG001  ligne 109  live_equity: float        — unused
ARG001  ligne 110  persisted: object         — unused
ARG001  ligne 111  session_start: object     — unused
```

**Contexte :** `_stop_early` est un stub interne (monkey-patch sur `_init_session_pairs`)
qui doit avoir la même signature que la méthode originale mais ne fait que `return []`.
Les 4 params sont intentionnellement inutilisés.

**Fix minimal :**
```python
async def _stop_early(
    _starting_equity: float,
    _live_equity: float,
    _persisted: object,
    _session_start: object,
) -> list[str]:
    return []
```

---

### 2 · `scripts/_cv_sweep.py` — typing

**Outil :** IDE get_errors (Pyright PROBLEMS)
**Scope :** hors périmètre alphaedge/ mais script de production utilisé pour les sweeps CV

```
ligne 74  Argument of type "tuple[list[TradeRecord], dict[str, int]]"
          cannot be assigned to parameter "trades" of type "list[TradeRecord]"
          in function "_apply_equity_sizing"

ligne 76  Argument of type "tuple[list[TradeRecord], dict[str, int]]"
          cannot be assigned to parameter "trades" of type "list[TradeRecord]"
          in function "compute_stats"
```

**Contexte :** `_backtest_pair` a été mis à jour pour retourner
`tuple[list[TradeRecord], dict[str, int]]` (trades + filtres rejetés).
`_cv_sweep.py` utilise encore l'ancienne signature sans déstructurer le tuple.

**Fix minimal :**
```python
# ligne 70 — avant
trades = _backtest_pair(pair, _bars[pair], cfg)
# après
trades, _rejected = _backtest_pair(pair, _bars[pair], cfg)
```

---

## Fichiers hors périmètre — aucune erreur détectée

| Dossier | Pyright | Ruff général |
|---------|---------|--------------|
| `alphaedge/config/` | 0 | 0 |
| `alphaedge/utils/` | 0 | 0 |
| `alphaedge/core/` | 0 | 0 |
| `alphaedge/engine/` | 0 | 0 |
| `alphaedge/tests/` | 0 | 4 ARG001 |

---

## Ordonnancement des corrections

| # | Fichier | Type | Priorité | Effort |
|---|---------|------|----------|--------|
| 1 | `scripts/_cv_sweep.py` | typing | 🟠 Majeur | ~2 min |
| 2 | `alphaedge/tests/test_session_restart_blocked.py` | ARG | 🟡 Mineur | ~2 min |

**Total : 2 fichiers · 6 erreurs · ~5 min**
