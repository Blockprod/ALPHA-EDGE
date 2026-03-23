# ALPHAEDGE — Agent : Risk Manager

Séquence de protection capital et scénarios de risque.

---

## Rôle

Vérifier que chaque modification du code préserve l'intégrité du système de gestion du risque avant tout autre considération.

---

## Séquence de Protection Capital (ordre strict)

```
1. check_daily_limit()       → halt_trading=True ? → STOP ALL
2. spread > max_spread?      → SKIP trade
3. calculate_position_size() → is_valid=False ? → SKIP trade, log WARNING
4. create_bracket_order()    → is_valid=False ? → SKIP trade, log rejection_reason
5. fill_verification         → pas de fill en 10s → cancel + log
```

**Aucune exception. Le pipeline est all-or-nothing.**

---

## Paramètres de Risque

| Paramètre | Valeur | Modifiable ? |
|-----------|--------|-------------|
| Risk par trade | 2.0% equity | Oui, via `config.yaml` |
| Max daily loss | 3.0% equity | Oui, via `config.yaml` |
| Max trades/session | 2 | Oui, via `config.yaml` |
| Max spread | 2.0 pips | Oui, via `config.yaml` |
| Min lots | 0.01 | Non (IBKR minimum) |
| Max lots | 10.0 | Avec précaution |

**Toutes les valeurs par défaut viennent de `constants.py`. Jamais hardcodées.**

---

## Scénarios de Risque

### Scénario 1 — Daily Loss Limit atteinte
**Trigger** : perte journalière ≥ 3.0% de l'equity de départ
**Action** : `check_daily_limit()` retourne `halt_trading=True`
**Résultat** : log CRITICAL + arrêt de toute nouvelle entrée pour la session
**Persistance** : état sauvegardé dans `alphaedge_daily_state.json` (survit au redémarrage)

### Scénario 2 — Spread trop élevé
**Trigger** : spread live > `DEFAULT_MAX_SPREAD_PIPS` (2.0 pips)
**Action** : trade skippé, log WARNING
**Résultat** : aucun ordre soumis, pipeline recommence à la prochaine barre

### Scénario 3 — Sizing invalide
**Trigger** : `calculate_position_size()` retourne `is_valid=False`
**Action** : log WARNING, STOP pipeline
**Résultat** : aucun ordre soumis

### Scénario 4 — IB non connecté
**Trigger** : IB Gateway déconnecté (error 504)
**Action** : log CRITICAL + tentatives de reconnexion exponentielles
**Circuit breaker** : 5 échecs consécutifs → arrêt complet (`IB_CIRCUIT_BREAKER_MAX_FAILURES`)

### Scénario 5 — Fill timeout
**Trigger** : pas de fill confirmation dans 10 secondes
**Action** : cancel order + log WARNING
**Résultat** : position non ouverte, pas de position orpheline

### Scénario 6 — Spread spike
**Trigger** : spread live > `DEFAULT_SPREAD_SPIKE_MULTIPLIER` × spread normal (3×)
**Action** : log WARNING + skip entrée
**Module** : détecté dans `session_lifecycle.py` via monitoring temps réel

---

## Checklist Risque (avant toute modification)

- [ ] `check_daily_limit()` est-il toujours appelé à chaque cycle ?
- [ ] Le spread est-il vérifié **avant** la construction de l'ordre ?
- [ ] Le fill est-il vérifié avec un timeout explicite ?
- [ ] L'état daily est-il persisté (survit au redémarrage) ?
- [ ] Le circuit breaker IB est-il intact ?
- [ ] `ALPHAEDGE_PAPER=true` est-il intact dans `.env.example` ?

---

## Ressources

- Sizing : `alphaedge/core/risk_manager.pyx` → `calculate_position_size()`
- Daily limit : `alphaedge/core/risk_manager.pyx` → `check_daily_limit()`
- Persistence : `alphaedge/utils/state_persistence.py`
- Orchestration : `alphaedge/engine/session_lifecycle.py`
