---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: PLAN_ACTION_audit_strategic_alphaedge_2026-03-26.md
derniere_revision: 2026-03-26
creation: 2026-03-26 à 10:00
---

# PLAN D'ACTION — ALPHAEDGE — 2026-03-26
**Sources** : `tasks/audits/resultats/audit_strategic_alphaedge.md`
**Total** : 🔴 5 · 🟠 2 · 🟡 1 · **Effort estimé : 3–4 jours**

> ⚠️ Note de contexte : L'audit stratégique révèle un NO-GO fondamental lié à
> l'insuffisance de données (N=16). Les corrections S-01, S-03, S-04 ne sont pas
> des bugs code — ce sont des contraintes de maturité opérationnelle (accumulation
> de données réelles). Seules S-02 et S-06 sont des corrections immédiates de config.
> Les corrections S-05, S-07, S-08 améliorent la robustesse de mesure pour quand
> les données seront disponibles.

---

## PHASE 1 — CRITIQUES 🔴

---

### [S-02] Désactiver le SHORT — direction_filter: "LONG"

**Fichier** : `config.yaml:39`
**Problème** : `direction_filter: "ALL"` autorise les trades SHORT alors que
SHORT WR=0%, PF=0.00 sur N=4 dans le CSV. Les SHORT sont systématiquement
perdants (−29.60 pips, −$1052.59). Cette config destrucive de valeur est active
en production (live et backtest).
**Correction** : Modifier `direction_filter: "ALL"` → `direction_filter: "LONG"`
dans `config.yaml`. Mettre à jour le commentaire associé pour documenter la raison.
**Validation** :
```powershell
# No .pyx touched → no make build needed
python -m ruff check alphaedge/ ; python -m pytest alphaedge/tests/ -x -q 2>&1 | Select-Object -Last 5
# Attendu : 585 tests pass, 0 errors
```
**Dépend de** : Aucune
**Statut** : ⏳

---

### [S-01] Logger les motifs de rejet momentum dans le backtest

**Fichier** : `alphaedge/engine/signal_pipeline.py:87` + `alphaedge/engine/backtest.py:_backtest_pair`
**Problème** : Quand `detect_momentum()` retourne `None` (ADX < seuil), le pipeline
s'arrête silencieusement. Sur 17 mois et 82% de jours inactifs, les causes de silence
sont indiagnosticables. En production live, aucun log ne permet de distinguer :
« pas de signal valide » de « filtre trop restrictif » de « erreur données ».
**Correction** :
1. Dans `signal_pipeline.py:detect_momentum()`, si `result is None`, ajouter :
   `logger.debug("ALPHAEDGE MOMENTUM: %s — ADX below threshold (adx_threshold=%.1f)", state.pair, adx_t)`
2. Dans `backtest.py:_backtest_pair()`, la structure existante ne loggue pas les
   rejets signal. Ajouter un compteur de rejets et un log INFO à la fin du loop :
   `logger.info("ALPHAEDGE BACKTEST: %s — %d bars, %d signals, %d rejected (ADX gate)", pair, total, accepted, rejected)`
**Validation** :
```powershell
python -m ruff check alphaedge/ ; python -m pytest alphaedge/tests/ -x -q 2>&1 | Select-Object -Last 5
# Attendu : 585+ tests pass, 0 errors Ruff, 0 errors Pyright
```
**Dépend de** : Aucune
**Statut** : ⏳

---

### [S-04] Protéger contre l'effet jackpot — limiter trades par journée calendaire

**Fichier** : `alphaedge/engine/backtest.py:_backtest_pair` + `config.yaml`
**Problème** : 6 trades sur la seule journée 2025-04-11 représentent 98.3% du P&L net.
`max_trades_per_session=6` est un plafond global de session, non un plafond par journée
calendaire distincte. Des journées multi-sessions peuvent accumuler plus de 6 trades.
Le backtest n'enregistre pas une métrique de concentration P&L qui alerterait.
**Correction** :
1. Ajouter dans `backtest_stats.py:compute_stats()` une métrique `pnl_concentration_pct` :
   — Calculer la fraction du P&L total produite par la meilleure journée calendaire.
   — Logguer un WARNING si > 50%.
2. Ajouter dans `config.yaml` (section `trading`) un paramètre `max_trades_per_day: 3`
   et l'appliquer dans `_backtest_pair` en réinitialisant le compteur quotidien par
   `bar["datetime"].date()` (distinct de `max_trades_per_session`).
**Validation** :
```powershell
python -m ruff check alphaedge/ ; python -m pyright alphaedge/ 2>&1 | Select-String "0 errors|error" ; python -m pytest alphaedge/tests/ -x -q 2>&1 | Select-Object -Last 5
# Attendu : 0 Ruff, 0 Pyright, 585+ tests pass
```
**Dépend de** : Aucune
**Statut** : ⏳

---

### [S-03] Ajouter un script de diagnostic de silence — rapport de couverture signal

**Fichier** : `scripts/` (nouveau script) + `alphaedge/engine/backtest_stats.py`
**Problème** : 82% des jours sans trade (427 + 300 jours de silence). L'absence
de reporting structuré empêche de diagnostiquer si le silence vient du filtre ADX,
du news filter, du spread gate, ou de l'absence de données. Résoudre S-01 n'est
pas suffisant — il faut une vue agrégée par filtre.
**Correction** :
1. Dans `backtest_stats.py`, ajouter `BacktestStats.filter_rejection_counts: dict[str, int]`
   — champs : `adx_gate`, `news_blackout`, `spread_gate`, `direction_filter`, `carry_conflict`.
2. Dans `backtest.py:_collect_daily_trades()`, incrémenter les compteurs appropriés
   à chaque STOP de pipeline avant `return trades`.
3. Dans `backtest_stats.py:compute_stats()`, inclure ces compteurs dans le rapport.
**Validation** :
```powershell
python -m ruff check alphaedge/ ; python -m pyright alphaedge/ 2>&1 | Select-String "0 errors|error" ; python -m pytest alphaedge/tests/ -x -q 2>&1 | Select-Object -Last 5
# Attendu : 0 Ruff, 0 Pyright, tests ≥ baseline
```
**Dépend de** : S-01 (logging motifs — fournit la structure à comptabiliser)
**Statut** : ⏳

---

### [S-05] Activer le walk-forward et créer un test de validation minimum

**Fichier** : `config.yaml` + `alphaedge/engine/walk_forward.py` + `alphaedge/tests/`
**Problème** : `walk_forward_enabled: false` dans config.yaml. N_OOS=5 rend le split
IS/OOS statique non significatif. Le walk-forward est implémenté (`walk_forward.py`,
branché `backtest.py:147`) mais jamais validé en pratique.
**Correction** :
1. Ajouter `walk_forward_enabled: true` dans `config.yaml` (section `trading`) avec
   un commentaire indiquant que N minimum = 30 trades OOS pour interpréter les résultats.
2. Vérifier que `run_walk_forward()` dans `walk_forward.py` tolère des fenêtres avec
   N < 5 trade sans crash (tester le cas edge N_OOS=0 dans les fenêtres courtes).
3. Ajouter un test `alphaedge/tests/test_walk_forward_empty_window.py` :
   `run_walk_forward` avec jeu de données < lookback → retourne `WalkForwardReport` vide
   sans exception.
**Validation** :
```powershell
python -m ruff check alphaedge/ ; python -m pyright alphaedge/ 2>&1 | Select-String "0 errors|error" ; python -m pytest alphaedge/tests/ -x -q 2>&1 | Select-Object -Last 5
# Attendu : 0 Ruff, 0 Pyright, tests ≥ baseline + 1 nouveau test
```
**Dépend de** : Aucune
**Statut** : ⏳

---

## PHASE 2 — MAJEURES 🟠

---

### [S-06] Peupler carry_rates dans config.yaml pour activer le filtre carry

**Fichier** : `config.yaml:108−113`
**Problème** : `carry_enabled: true` mais `rates: {}` (commenté dans le YAML suite à
audit 7b P-04). `get_carry_bias()` retourne `CarrySignal(is_valid=False)` → filtre
carry silencieusement inactif depuis toujours. Le biais carry (Lustig 2011) n'a jamais
filtré le moindre trade du CSV.
**Correction** : Dépopuler la section `rates:` commentée en la rendant active avec
les taux 2026-Q1 (déjà présents en commentaire dans config.yaml depuis P-04) :
```yaml
carry:
  min_differential_pct: 0.5
  enabled: true
  rates:
    EUR: 3.65   # ECB deposit facility rate (2026-Q1)
    USD: 5.25   # Fed funds rate upper bound (2026-Q1)
    JPY: 0.10   # BOJ overnight rate (2026-Q1)
    GBP: 5.25   # BOE base rate (2026-Q1)
    AUD: 4.35   # RBA cash rate (2026-Q1)
    NZD: 5.50   # RBNZ official cash rate (2026-Q1)
    CAD: 5.00   # BOC overnight rate (2026-Q1)
    CHF: 1.50   # SNB policy rate (2026-Q1)
```
**Validation** :
```powershell
python -m ruff check alphaedge/ ; python -m pytest alphaedge/tests/ -x -q 2>&1 | Select-Object -Last 5
# Attendu : 585 tests pass + carry filter désormais actif sur backtest
# Vérifier manuellement sur le prochain backtest que carry_signal.direction != NEUTRAL
```
**Dépend de** : Aucune
**Statut** : ⏳

---

### [S-07] Ajouter une métrique de concentration P&L dans BacktestStats

**Fichier** : `alphaedge/engine/backtest_stats.py` + `alphaedge/engine/backtest_types.py`
**Problème** : `BacktestStats` ne contient aucune métrique de concentration P&L par
journée — l'effet jackpot (98.3% sur une journée) n'est visible qu'en inspectant le CSV
manuellement. Un système en production doit alerter automatiquement sur ce risque.
**Correction** :
1. Ajouter dans `BacktestStats` (`backtest_types.py`) deux champs :
   ```python
   best_day_pnl_pct: float = 0.0   # % du P&L net total généré par la meilleure journée
   best_day_date: str = ""          # date YYYY-MM-DD de ce pic
   ```
2. Dans `compute_stats()` (`backtest_stats.py`), regrouper les trades par date
   `entry_time.date()`, calculer `best_day_pnl_usd / total_pnl_usd * 100`.
3. Dans `_log_split_report()` ou équivalent, logguer un WARNING si `best_day_pnl_pct > 50%`.
**Validation** :
```powershell
python -m ruff check alphaedge/ ; python -m pyright alphaedge/ 2>&1 | Select-String "0 errors|error" ; python -m pytest alphaedge/tests/ -x -q 2>&1 | Select-Object -Last 5
# Attendu : 0 Ruff, 0 Pyright, tests ≥ baseline
```
**Dépend de** : Aucune (indépendant de S-04)
**Statut** : ⏳

---

## PHASE 3 — MINEURES 🟡

---

### [S-08] Activer walk_forward_enabled et documenter le seuil N minimum

**Fichier** : `config.yaml` (section `trading`) + `docs/ALPHAEDGE_STRUCTURAL_ACTION_PLAN.md`
**Problème** : `walk_forward_enabled` n'existe pas comme clé explicite dans `config.yaml` —
il est lu via `loader.py:402` avec fallback `False`. Aucune documentation utilisateur.
La combinaison S-05 active le WF techniquement ; S-08 documente le seuil.
**Correction** :
1. Ajouter explicitement dans `config.yaml` (section `trading`) :
   ```yaml
   # Walk-forward validation: activate after N >= 100 trades for meaningful OOS windows
   # Run via: python -m alphaedge.engine.backtest --walk-forward
   walk_forward_enabled: false  # LOCKED until N >= 100 live trades accumulated
   ```
2. Mettre à jour `docs/ALPHAEDGE_STRUCTURAL_ACTION_PLAN.md` pour noter le seuil N=100
   comme prérequis avant activation WF.
**Validation** :
```powershell
python -m pytest alphaedge/tests/ -x -q 2>&1 | Select-Object -Last 3
# Attendu : 585+ tests pass (modification config.yaml uniquement)
```
**Dépend de** : S-05
**Statut** : ⏳

---

## SÉQUENCE D'EXÉCUTION

```
S-02 (5 min)      ← direction_filter: "LONG" — correction config immédiate, aucune dépendance
S-06 (10 min)     ← carry_rates actifs — config uniquement, aucune dépendance
S-07 (2h)         ← BacktestStats.best_day_pnl_pct — code + tests, aucune dépendance
S-01 (1h)         ← Logging motifs de rejet momentum — code signal_pipeline + backtest
S-04 (3h)         ← max_trades_per_day + pnl_concentration backtest — dépend logiquement de S-01
S-03 (3h)         ← Compteurs filter_rejection — dépend de S-01 (structure logging)
S-05 (2h)         ← Walk-forward edge cases + test vide — indépendant mais après S-03
S-08 (15 min)     ← Documentation config walk_forward — après S-05
```

> Aucun fichier `.pyx` touché → `make build` non requis pour ce plan.

---

## CRITÈRES PASSAGE EN PRODUCTION

- [ ] Zéro 🔴 ouvert (S-01 à S-05 validés)
- [ ] `make qa` : 100% pass (lint + mypy + pytest ≥80%)
- [ ] Zéro credential dans les logs loguru
- [ ] `ALPHAEDGE_PAPER=true` intact dans `.env.example`
- [ ] `direction_filter: "LONG"` confirmé dans `config.yaml`
- [ ] `carry_rates` peuplé et carry filter actif (vérifié sur prochain backtest)
- [ ] Log de concentration P&L généré automatiquement à chaque backtest
- [ ] Paper trading validé **minimum 30 sessions NYSE** (≥ 30 trades) avant tout live
- [ ] N ≥ 100 trades accumulés avant activation walk-forward et décision statistique finale

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier | Effort | Statut | Date |
|----|-------|----------|---------|--------|--------|------|
| S-02 | direction_filter: "LONG" | 🔴 | config.yaml:39 | 5 min | ⏳ | — |
| S-01 | Logger motifs de rejet momentum | 🔴 | signal_pipeline.py:87 / backtest.py | 1h | ⏳ | — |
| S-04 | max_trades_per_day + pnl_concentration | 🔴 | backtest.py / config.yaml / backtest_stats.py | 3h | ⏳ | — |
| S-03 | Diagnostic silence — compteurs filtres | 🔴 | backtest_stats.py / backtest.py | 3h | ⏳ | — |
| S-05 | Walk-forward actif + test edge case | 🔴 | walk_forward.py / tests/ / config.yaml | 2h | ⏳ | — |
| S-06 | Peupler carry_rates config.yaml | 🟠 | config.yaml:108-113 | 10 min | ⏳ | — |
| S-07 | BacktestStats.best_day_pnl_pct | 🟠 | backtest_stats.py / backtest_types.py | 2h | ⏳ | — |
| S-08 | Documenter walk_forward_enabled config | 🟡 | config.yaml / docs/ | 15 min | ⏳ | — |
