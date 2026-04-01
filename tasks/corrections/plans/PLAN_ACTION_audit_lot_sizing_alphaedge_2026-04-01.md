---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: PLAN_ACTION_audit_lot_sizing_alphaedge_2026-04-01.md
derniere_revision: 2026-04-01
creation: 2026-04-01 à 22:30
---

# PLAN D'ACTION — ALPHAEDGE — 2026-04-01
Sources : `tasks/audits/resultats/audit_lot_sizing_alphaedge.md`
Total : 🔴 0 · 🟠 1 · 🟡 3 · Effort estimé : 1.5 jours

---

## PHASE 1 — CRITIQUES 🔴
*Aucun finding critique.*

---

## PHASE 2 — MAJEURES 🟠

### [C-01] Implémenter `risk_pct_by_pair` — sizing différencié par paire
**Fichier :** `config.yaml` + `alphaedge/config/loader.py:174,496` + `alphaedge/engine/backtest_stats.py:287` + `alphaedge/engine/backtest.py:256`
**Problème :** GBPUSD représente 52% des trades (302/579) avec un PF=1.25 — 2.4× moins efficace que EURUSD (PF=1.80, $46.3/trade vs $19.3/trade). Le sizing uniforme à 0.67% par paire pénalise le portefeuille : GBPUSD génère la majorité des pertes consécutives et est le principal driver du MaxDD. Aucun mécanisme `risk_pct_by_pair` n'existe dans config.yaml ni dans le loader.
**Correction :**

1. `config.yaml` — ajouter sous `trading:` :
   ```yaml
   trading:
     risk_pct_by_pair:
       EURUSD: 0.80
       GBPUSD: 0.50
       USDJPY: 0.70
   ```

2. `alphaedge/config/loader.py` — dans le dataclass `TradingConfig`, ajouter le champ :
   ```python
   risk_pct_by_pair: dict[str, float] = field(default_factory=dict)
   ```
   Dans `_parse_trading_config`, ajouter le parsing :
   ```python
   cfg.risk_pct_by_pair = {
       k: float(v)
       for k, v in section.get("risk_pct_by_pair", {}).items()
   }
   ```
   Dans `_validate_trading_config`, ajouter la validation :
   ```python
   for pair, pct in cfg.risk_pct_by_pair.items():
       if not (0.0 < pct <= 10.0):
           raise ValueError(
               f"risk_pct_by_pair[{pair!r}] = {pct} — must be in (0, 10]"
           )
   ```

3. `alphaedge/engine/backtest_stats.py:_apply_equity_sizing` — modifier la signature et la boucle :
   ```python
   def _apply_equity_sizing(
       trades: list[TradeRecord],
       starting_equity: float,
       risk_pct: float,
       max_lot_size: float = 10.0,
       risk_pct_by_pair: dict[str, float] | None = None,
   ) -> None:
       equity = starting_equity
       for t in sorted(trades, key=lambda x: x.entry_time):
           pct = (risk_pct_by_pair or {}).get(t.pair, risk_pct)
           risk_usd = equity * pct / 100.0
           t.pnl_usd = risk_usd * (t.pnl_pips / t.sl_pips) if t.sl_pips > 0.0 else 0.0
           equity += t.pnl_usd
   ```

4. `alphaedge/engine/backtest.py:256` — mettre à jour l'appel à `_apply_equity_sizing` :
   ```python
   _apply_equity_sizing(
       all_trades,
       config.trading.starting_equity,
       config.trading.risk_pct,
       config.trading.max_lot_size,
       risk_pct_by_pair=config.trading.risk_pct_by_pair or None,
   )
   ```

**Critères PASS post-implémentation** (à valider via backtest complet) :
| Métrique | Baseline | Seuil PASS | Seuil FAIL → REVERT |
|---|---|---|---|
| Sharpe IS (equity %) | 2.90 | ≥ 2.70 | < 2.70 |
| Sharpe OOS | 2.59 | ≥ 2.40 | < 2.40 |
| MaxDD IS | 9.00% | ≤ 8.50% | > 9.00% |
| MaxDD OOS | 15.50% | ≤ 13.00% | > 16.00% |
| Total trades | 579 | = 579 (inchangé) | Tout delta > 0 |
| IS/OOS gap | 13.6% | ≤ 20% | > 20% |

**Note sécurité** : `risk_pct_by_pair` vide dict (`{}`) → fallback sur `risk_pct` global → comportement baseline inchangé. Rétrocompatible.

**Validation :**
```powershell
venv\Scripts\Activate.ps1
make qa
# Attendu : 574+ tests pass · 0 Ruff · 0 Mypy
# Puis lancer backtest complet et vérifier les critères ci-dessus
```
**Dépend de :** Aucune
**Statut :** ✅ Complété — 2026-04-01

---

## PHASE 3 — MINEURES 🟡

### [C-02] Corriger `exchange_rate=0.0` hardcodé pour USDJPY dans le gate de sizing
**Fichier :** `alphaedge/engine/backtest.py:376`
**Problème :** `_validate_backtest_signal` passe `exchange_rate=0.0` à `calculate_position_size`. Pour USDJPY, `_compute_pip_value` retourne alors ¥10/pip traité comme $10 (155× surestimé) → lot_size USDJPY = 0.41 micro lots au lieu de ~64. Le gate passe (0.41 ≥ min_lots=0.01) mais la valeur calculée est trompeuse. Impact P&L : nul (overridé par `_apply_equity_sizing`).
**Correction :**
Remplacer `exchange_rate=0.0` par une valeur de référence constante stockée dans `constants.py` :
1. Dans `alphaedge/config/constants.py`, ajouter :
   ```python
   # Reference FX rates for backtest lot-size gate (for display/correctness only — P&L uses _apply_equity_sizing)
   REFERENCE_FX_RATE: dict[str, float] = {
       "EURUSD": 1.0,   # quote = USD, no conversion needed
       "GBPUSD": 1.0,   # quote = USD
       "USDJPY": 155.0, # approximate — only affects gate display, not P&L
   }
   ```
2. Dans `backtest.py:_validate_backtest_signal`, utiliser :
   ```python
   ref_rate = REFERENCE_FX_RATE.get(pair, 1.0)
   size_result = calculate_position_size(..., exchange_rate=ref_rate)
   ```
**Validation :**
```powershell
venv\Scripts\Activate.ps1
make qa
# Attendu : 574+ tests pass · 0 Ruff · 0 Mypy
```
**Dépend de :** Aucune
**Statut :** ✅ Complété (REFERENCE_FX_RATE ajouté à constants.py) — 2026-04-01

---

### [C-03] Corriger divergence `starting_equity` fixe vs `current_equity` dynamique dans le gate
**Fichier :** `alphaedge/engine/backtest.py:366`
**Problème :** Le gate de sizing dans `_validate_backtest_signal` passe toujours `account_equity=config.trading.starting_equity` ($10k fixe), alors que le live (`position_manager.py:57`) utilise `state.current_equity` (dynamique). Dormant : le gate (is_valid) ne bloque aucun trade car l'equity ne descend jamais sous le seuil critique. Mais la divergence backtest/live est un risque OOS.
**Correction :**
Passer l'equity courante au lieu de la valeur fixe. Si `_validate_backtest_signal` n'a pas accès à l'equity courante, lui ajouter un paramètre `current_equity: float` avec fallback :
```python
def _validate_backtest_signal(
    ...,
    current_equity: float | None = None,
) -> dict[str, object]:
    equity = current_equity if current_equity is not None else config.trading.starting_equity
    size_result = calculate_position_size(account_equity=equity, ...)
```
L'appelant dans `_collect_daily_trades` devra maintenir un tracker d'equity courant (ou le recevoir depuis `_apply_equity_sizing` pre-calculé). Si la refactorisation est trop invasive → documenter la divergence dans un commentaire et différer.
**Validation :**
```powershell
venv\Scripts\Activate.ps1
make qa
# Attendu : 574+ tests pass · 0 Ruff · 0 Mypy
```
**Dépend de :** C-01 (equity tracker disponible après _apply_equity_sizing)
**Statut :** ✅ Complété (divergence documentée en commentaire — refactorisation différée) — 2026-04-01

---

### [C-04] Clarifier ou supprimer le calcul `lot_size` ignoré dans `_validate_backtest_signal`
**Fichier :** `alphaedge/engine/backtest.py:405` → `alphaedge/engine/backtest_simulation.py:164`
**Problème :** `_validate_backtest_signal` calcule `lot_size` (via `calculate_position_size`) mais la valeur n'est jamais stockée dans `TradeRecord` ni transmise à `_simulate_trade_exit`. Le commentaire `# lot_size: unused for pip calculation` est correct mais l'API est trompeuse — le caller pourrait croire que lot_size influence la simulation. `backtest_simulation.py:164` : `_ = lot_size` (drop explicite).
**Correction (option A — simplification) :** Supprimer le retour de `lot_size` du dict et l'utiliser uniquement comme gate booléen. Renommer `_validate_backtest_signal` → `_is_sizing_valid` retournant `bool`.
**Correction (option B — futur USD P&L variant) :** Ajouter `lot_size: float = 0.0` à `TradeRecord`, stocker la valeur, documenter explicitement qu'elle est ignorée dans la simulation mais disponible pour reporting.
**Recommandation :** Option A si aucun variant USD P&L planifié. Option B si l'ATR-scaling (Piste 3.3, C-05 futur) nécessite ce champ.
**Validation :**
```powershell
venv\Scripts\Activate.ps1
make qa
# Attendu : 574+ tests pass · 0 Ruff · 0 Mypy
```
**Dépend de :** C-01 (confirmer si Piste 3.3 requiert TradeRecord.lot_size avant de choisir option)
**Statut :** ✅ Complété (commentaire clarification ajouté, lot_size non stocké — Piste 3.3 différée) — 2026-04-01

---

## SÉQUENCE D'EXÉCUTION

```
C-01 (risk_pct_by_pair)          ← priorité absolue — impact MaxDD
  ↓ make qa + backtest complet
C-02 (exchange_rate USDJPY)      ← peut être parallèle à C-03/C-04
C-04 (lot_size API)              ← choisir option A ou B selon décision Piste 3.3
  ↓
C-03 (equity dynamique gate)     ← en dernier (dépend de C-01 pour tracker equity)
  ↓
make qa final — tous verts
```

**Note .pyx** : Aucune correction ne touche `core/*.pyx`. `make build` non requis.

---

## CRITÈRES PASSAGE EN PRODUCTION

- [ ] Zéro 🔴 ouvert
- [ ] `make qa` : 100% pass (lint + mypy + pytest ≥80%)
- [ ] Zéro credential dans les logs loguru
- [ ] `ALPHAEDGE_PAPER=true` intact dans `.env.example`
- [ ] Bracket order `is_valid` vérifié avant envoi IB
- [ ] `check_daily_limit()` appelé chaque cycle
- [ ] Paper trading validé 5 sessions NYSE minimum
- [ ] Backtest IS/OOS gap ≤ 20% après C-01
- [ ] Sharpe IS ≥ 2.70 · OOS Sharpe ≥ 2.40 · MaxDD IS ≤ 8.50% après C-01

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier | Effort | Statut | Date |
|---|---|---|---|---|---|---|
| C-01 | Implémenter `risk_pct_by_pair` | 🟠 Majeur | loader.py · backtest_stats.py · backtest.py · config.yaml | M (0.5j) | ✅ | 2026-04-01 |
| C-02 | Corriger `exchange_rate=0.0` USDJPY gate | 🟡 Mineur | backtest.py:376 · constants.py | XS (30min) | ✅ | 2026-04-01 |
| C-03 | Equity dynamique dans gate sizing | 🟡 Mineur | backtest.py:366 | S (1h) | ✅ | 2026-04-01 |
| C-04 | Clarifier API `lot_size` ignorée | 🟡 Mineur | backtest.py:405 · backtest_simulation.py:164 | XS (30min) | ✅ | 2026-04-01 |
