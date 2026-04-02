---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/fix_errors/PLAN_result.md
derniere_revision: 2026-03-26
creation: 2026-03-26 à 00:00
---

# PLAN — Corrections AlphaEdge

**Source :** `tasks/audits/fix_errors/SCAN_result.md`
**Date :** 2026-03-26

---

## Analyse des dépendances

```
scripts/_cv_sweep.py
  └─► alphaedge.engine.backtest._backtest_pair  (import)
  └─► alphaedge.engine.backtest_stats.compute_stats  (import)
  → aucune dépendance interne avec le fichier tests/ à corriger
  → batch indépendant

alphaedge/tests/test_session_restart_blocked.py
  └─► alphaedge.engine.strategy  (import)
  → aucune dépendance avec scripts/
  → batch indépendant
```

**Conclusion :** les 2 fichiers sont totalement indépendants.
Ordre choisi : scripts/ en premier (🟠 Majeur) → tests/ ensuite (🟡 Mineur).

---

## PLAN

```python
PLAN = [
    {
        "batch": 1,
        "module": "scripts/",
        "files": ["scripts/_cv_sweep.py"],
        "error_types": ["typing"],
        "estimated_fixes": 2,
        "difficulty": "Facile",
        "pattern": "tuple non déstructuré assigné à list[TradeRecord]",
        "fix": (
            "Ligne 70 — déstructurer le retour de _backtest_pair :\n"
            "  avant : trades = _backtest_pair(pair, _bars[pair], cfg)\n"
            "  après : trades, _rejected = _backtest_pair(pair, _bars[pair], cfg)\n"
            "Les lignes 74 et 76 seront automatiquement résolues."
        ),
        "validation": "pyright scripts/_cv_sweep.py → 0 erreur",
        "risque": "Aucun — _rejected est un dict ignoré, aucun effet sur le sweep",
    },
    {
        "batch": 2,
        "module": "alphaedge/tests/",
        "files": ["alphaedge/tests/test_session_restart_blocked.py"],
        "error_types": ["ARG"],
        "estimated_fixes": 4,
        "difficulty": "Facile",
        "pattern": "ARG001 — paramètres de stub intentionnellement inutilisés",
        "fix": (
            "Lignes 108-111 — préfixer les 4 params avec `_` pour signaler l'intention :\n"
            "  starting_equity  → _starting_equity\n"
            "  live_equity      → _live_equity\n"
            "  persisted        → _persisted\n"
            "  session_start    → _session_start\n"
            "La signature reste compatible avec le monkey-patch (_init_session_pairs)."
        ),
        "validation": "ruff check --select ARG alphaedge/tests/test_session_restart_blocked.py → 0",
        "risque": "Aucun — stub internal, paramètres jamais utilisés dans le corps",
    },
]
```

---

## Résumé

```
total_batches    : 2
total_files      : 2
estimated_fixes  : 6  (2 lignes typing + 4 ARG001)
ordre_validation : batch 1 → pyright scripts/ | batch 2 → ruff --select ARG alphaedge/tests/
qa_final         : make qa (628 tests attendus · 0 Ruff · 0 Pyright)
```

---

## Checklist d'exécution P3

- [ ] **Batch 1** — `scripts/_cv_sweep.py` ligne 70 : `trades, _rejected = _backtest_pair(...)`
- [ ] **Batch 2** — `alphaedge/tests/test_session_restart_blocked.py` lignes 108-111 : préfixe `_`
- [ ] Validation batch 1 : `pyright scripts/_cv_sweep.py` → 0 erreur
- [ ] Validation batch 2 : `ruff check --select ARG alphaedge/tests/test_session_restart_blocked.py` → 0
- [ ] QA final : `make qa` → 628 tests · 0 Ruff
