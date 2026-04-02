# ALPHAEDGE — Claude Rules
# Règles de modification pour agents Claude

---

## ⛔ INTERDICTIONS ABSOLUES


- **Never** modify `alphaedge/core/*.pyx` without explicit instruction from the user
- **Never** commit `.env`, `*.log`, or `ALPHAEDGE_ACTION_PLAN.md`
- **Never** run `make build` unless a `.pyx` file was intentionally modified
- **Never** use `# type: ignore` or `# pyright: ignore` — fix the root cause
- **Never** use `Any` as a type annotation — it is a shortcut, not a solution
- **Never** hardcode pip values, RR ratios, session times, or risk parameters outside `alphaedge/config/constants.py`
- **Never** touch `alphaedge/utils/timezone.py` or `session_manager.py` without re-running DST edge case tests
- **Never** mark a task complete without running `make qa` (574 tests, ≥80% coverage)
- **Never** push a `.pyx` edit without running `make build` followed by `make qa`

---

## ORDRE DE PRIORITÉ DES MODIFICATIONS

```
1. Sécurité capital    → risk_manager.pyx · session_lifecycle.py
2. Gestion du risque   → constants.py · loader.py
3. Exécution ordres    → order_manager.pyx · broker.py
4. Signal de trading   → momentum_detector.pyx · gap_detector.pyx · engulfing_detector.pyx
5. Backtest / analyse  → backtest*.py
6. Dashboard / logs    → dashboard.py · web_dashboard.py · logger.py
```

---

## OBLIGATIONS POST-MODIFICATION

| Type de fichier modifié | Action obligatoire |
|-------------------------|-------------------|
| Tout `.pyx` | `make build` → `make qa` |
| `constants.py` | `make qa` complet |
| `loader.py` | `make qa` + vérifier tests de session |
| `timezone.py` ou `session_manager.py` | `make qa` + tests DST edge cases |
| N'importe quel autre | `make qa` |

---

## STARTUP CHECKLIST (OBLIGATOIRE)

Avant de toucher un seul fichier :

1. Lire `tasks/lessons.md` — pas d'exceptions
2. Lire `docs/ALPHAEDGE_STRUCTURAL_ACTION_PLAN.md`
3. Confirmer que `make qa` est vert (574 tests)
4. Vérifier que `.env.example` contient `ALPHAEDGE_PAPER=true`
5. Identifier l'ensemble minimal de fichiers impactés

---

## WORKFLOW AGENT

- Plan mode obligatoire pour toute tâche ≥ 3 étapes
- **Avant toute modification — 4 questions :**
  1. Ai-je lu tous les fichiers que je vais modifier ? (citer fichier:ligne avant d'agir)
  2. Ai-je un plan en N étapes validé avant d'agir ?
  3. Y a-t-il des informations manquantes ? (explorer d'abord, modifier ensuite)
  4. Comment vais-je valider le changement ? (`make qa` suffit ? test dédié requis ?)
- Stop immédiat + re-plan si quelque chose déraille
- Never mark complete without proof: `make qa` doit passer
- Après toute correction utilisateur : mettre à jour `tasks/lessons.md`
- Bug report → fixer directement, pas de questions inutiles
