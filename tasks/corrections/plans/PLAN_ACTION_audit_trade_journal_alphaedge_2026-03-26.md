---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: PLAN_ACTION_audit_trade_journal_alphaedge_2026-03-26.md
derniere_revision: 2026-03-26
creation: 2026-03-26 à 14:30
---

# PLAN D'ACTION — ALPHAEDGE — 2026-03-26
Sources : `tasks/audits/resultats/audit_trade_journal_alphaedge.md`
Total : 🔴 2 · 🟠 5 · 🟡 1 · Effort estimé : 5h30

---

## PHASE 1 — CRITIQUES 🔴

---

### [C-01] Atomicité des écritures CSV live
Fichier : `alphaedge/engine/live_journal.py:58`
Problème : `open(path, "a", ...)` écrit directement dans le fichier de production. Un crash OS entre deux `write()` (header + ligne de données) laisse le fichier partiellement écrit. JSON/CSV parsers échouent ou produisent des KPIs faux. Données perdues définitivement.
Correction :
- Remplacer `open(path, "a")` par le pattern **read-all → write-tmp → `os.replace`**.
- Lire les lignes existantes en RAM (CSV complet, maximal quelques Ko par jour).
- Écrire header + existantes + nouvelle ligne dans un fichier `.tmp` dans le même répertoire NTFS (garantit atomicité sur Windows NTFS).
- `os.replace(tmp, dest)` — atomique : jamais de fichier partiellement écrit visible.
- Supprimer le `.tmp` en cas d'exception (`finally: os.unlink(tmp_path)`).
- Note : supprimer `import tempfile` si déjà présent, l'ajouter sinon.
Validation :
```powershell
make qa
# Attendu : 596+ tests pass · 0 Ruff · 0 Pyright
# Vérifier : test_live_journal*.py si existant
```
Dépend de : Aucune
Statut : ⏳

---

### [C-02] Corriger la formule PnL USD multi-paires
Fichier : `alphaedge/engine/session_lifecycle.py:362`
Problème : `pnl_usd = pnl_pips * pip_size * record.lot_size * 100_000` — ignore `record.exchange_rate` (pourtant capturé à l'entrée, ligne ~203). Pour USDJPY (`pip_size=0.01`, `exchange_rate≈150`), le résultat est en JPY non converti. Le daily loss limit est calculé sur une base fausse.
Correction :
```python
# AVANT (ligne 362)
pnl_usd = pnl_pips * pip_size * record.lot_size * 100_000

# APRÈS
raw_pnl = pnl_pips * pip_size * record.lot_size * 100_000
pnl_usd = raw_pnl / record.exchange_rate if record.exchange_rate > 0.0 else raw_pnl
```
- Sémantique : `exchange_rate` = mid-price quote_currency/USD au moment de l'entrée.
  - EURUSD : `exchange_rate ≈ 1.0` → division par 1.0 → aucun changement.
  - USDJPY : `exchange_rate ≈ 150` → `raw_pnl / 150` → conversion JPY→USD correcte.
  - GBPUSD : `exchange_rate ≈ 1.0` → aucun changement.
- Ajouter un test paramétré (`pytest.mark.parametrize`) couvrant EURUSD + USDJPY.
Validation :
```powershell
make qa
# Attendu : tests EURUSD inchangés · test USDJPY nouveau passe
```
Dépend de : Aucune
Statut : ⏳

---

## PHASE 2 — MAJEURES 🟠

---

### [C-03] Ajouter `exit_reason` — distinguer SL/TP/session_end
Fichier : `alphaedge/engine/live_types.py:35` + `alphaedge/engine/session_lifecycle.py:331`
Problème : `_on_trade_closed` ne distingue pas quel ordre bracket (SL enfant vs TP enfant) a déclenché le close. `outcome` est déduit du signe de `pnl_pips` — falsifiable par du slippage favorable sur un SL. Impossible d'auditer le vrai win rate TP vs SL hit.
Correction :
**1. `live_types.py` — ajouter champ après ligne 35 (`outcome`) :**
```python
exit_reason: str = ""  # 'sl_hit' | 'tp_hit' | 'session_end' | 'manual' | 'unknown'
```

**2. `session_lifecycle.py` — étendre `StrategyState` pour stocker les order IDs bracket :**
- Dans `_record_fill` (après `placeOrder`) : lire `bracket_orders[1].order.orderId` (TP) et `bracket_orders[2].order.orderId` (SL), les stocker dans `state._tp_order_id` et `state._sl_order_id`.
- Note : identifier la structure exacte de `bracket_orders` retournée par `ib_insync.placeOrder`.

**3. `session_lifecycle.py` — dans `_on_trade_closed` (ligne 331) :**
```python
if ib_trade is not None and hasattr(state, "_tp_order_id"):
    filled_id = getattr(getattr(ib_trade, "order", None), "orderId", None)
    if filled_id == state._tp_order_id:
        record.exit_reason = "tp_hit"
    elif filled_id == state._sl_order_id:
        record.exit_reason = "sl_hit"
    else:
        record.exit_reason = "unknown"
else:
    record.exit_reason = "unknown"
```

**4. `live_journal.py` — ajouter `"exit_reason"` dans `CSV_HEADERS` (ligne 27) :**
```python
CSV_HEADERS = [
    ...,
    "exit_reason",   # après "outcome"
    ...
]
```
Et écrire `"exit_reason": record.exit_reason` dans le row dict.

Validation :
```powershell
make qa
# Attendu : tests existants passent (exit_reason="" par défaut)
# Ajouter test : mock ib_trade avec orderId == tp_order_id → exit_reason == "tp_hit"
```
Dépend de : C-01 (CSV modifié — atomicité d'abord)
Statut : ⏳

---

### [C-04] Persister contexte signal — `adx_at_entry` + `strength_at_entry`
Fichier : `alphaedge/engine/live_types.py:36` + `alphaedge/engine/session_lifecycle.py:176`
Problème : `signal["adx"]` et `signal["strength"]` sont utilisés dans le pipeline (signal_pipeline.py lignes 660–661) mais ne sont pas copiés dans `LiveTradeRecord` dans `_record_fill`. Impossible de corréler post-hoc qualité du signal ↔ outcome. Bloquant pour Audit #7 (ML filter).
Correction :
**1. `live_types.py` — ajouter champs après `slippage_pips` (ligne 36) :**
```python
adx_at_entry: float = 0.0
strength_at_entry: float = 0.0
```

**2. `session_lifecycle.py` — dans `_record_fill` (ligne ~201) :**
```python
state.live_record = LiveTradeRecord(
    ...
    adx_at_entry=float(signal.get("adx", 0.0)),
    strength_at_entry=float(signal.get("strength", 0.0)),
)
```
Vérifier que `signal` est accessible dans `_record_fill` (passer en paramètre si nécessaire).

**3. `live_journal.py` — ajouter colonnes dans `CSV_HEADERS` :**
```python
"adx_at_entry",
"strength_at_entry",
```
Et écrire les valeurs correspondantes dans le row dict.

Validation :
```powershell
make qa
# Vérifier que les tests mock de _record_fill incluent adx et strength dans le signal dict
```
Dépend de : C-03 (LiveTradeRecord déjà modifié dans C-03 — appliquer les deux en séquence)
Statut : ⏳

---

### [C-05] Ajouter `duration_s` et `pnl_eur` au CSV live
Fichier : `alphaedge/engine/live_journal.py:27`
Problème : `duration_s` est loggé dans TRADE_CLOSE mais absent du CSV — durée moyenne des trades non mesurable. `pnl_eur` présent dans le CSV backtest (`backtest_export.py:54`) mais absent du live — réconciliation comptable EUR impossible.
Correction :
**1. `live_types.py` — ajouter champ `pnl_eur` (calculé à la sortie) :**
```python
pnl_eur: float = 0.0
```

**2. `session_lifecycle.py` — calculer dans `_on_trade_closed` :**
```python
from alphaedge.config.constants import EUR_USD_RATE  # ou lire live si disponible
record.pnl_eur = round(record.pnl_usd / EUR_USD_RATE, 2)
duration_s = (
    (record.exit_time - record.entry_time).total_seconds()
    if record.exit_time and record.entry_time
    else 0.0
)
```

**3. `live_journal.py` — ajouter colonnes dans `CSV_HEADERS` :**
```python
"duration_s",
"pnl_eur",
```
Et écrire les valeurs dans le row dict.

**Note :** `EUR_USD_RATE` est à lire depuis `constants.py` (pas de hardcode). Si un taux live est disponible via broker, préférer celui-ci pour le live.

Validation :
```powershell
make qa
# Vérifier que les trades de test ont duration_s calculé correctement (exit_time - entry_time)
```
Dépend de : C-04 (LiveTradeRecord modifié)
Statut : ⏳

---

### [C-06] Journaliser les trades fermés à la fin de session
Fichier : `alphaedge/engine/session_lifecycle.py:803`
Problème : `_handle_session_end` ferme les positions ouvertes mais ne journalise pas le trade via `append_live_trade_csv`. Ces trades sont absents du CSV live (journal lacunaire). Les statistiques live sous-comptent les trades réels.
Correction :
- Dans `_handle_session_end` (ligne 803), si `state.live_record` est non None et qu'une position est fermée gracieusement :
  1. Récupérer le prix de fermeture réel (ou utiliser mid-price comme estimation).
  2. Calculer `pnl_pips`, `pnl_usd`, `pnl_eur`, `duration_s`.
  3. Définir `record.exit_reason = "session_end"`.
  4. Définir `record.exit_time = now_utc()`.
  5. Appeler `append_live_trade_csv(state.live_record)`.
  6. Reset `state.live_record = None`.
- Gérer le cas où le prix de fermeture n'est pas disponible immédiatement (trade non encore exécuté côté IB) — utiliser mid-price avec commentaire.
Validation :
```powershell
make qa
# Ajouter test : simuler _handle_session_end avec live_record non None
# → append_live_trade_csv appelé avec exit_reason == "session_end"
```
Dépend de : C-03 (exit_reason requis) · C-05 (pnl_eur + duration_s)
Statut : ⏳

---

## PHASE 3 — MINEURES 🟡

---

### [C-07] Atomicité du CSV backtest export
Fichier : `alphaedge/engine/backtest_export.py:45`
Problème : `df.to_csv(path, ...)` ou `open(path, "w")` direct — risque de corruption lors d'un crash pendant l'export backtest. Moins critique que le live (données reproductibles), mais cohérence de pratique.
Correction :
- Même pattern que C-01 : écrire dans `.tmp` → `os.replace`.
- Ou utiliser `df.to_csv(tmp_path)` puis `os.replace(tmp_path, final_path)`.
Validation :
```powershell
make qa
# Vérifier que le CSV backtest est bien écrit après correction
```
Dépend de : Aucune
Statut : ⏳

---

### [C-08] Ajouter `sl_pips` et `spread_cost_pips` au CSV backtest
Fichier : `alphaedge/engine/backtest_export.py:45`
Problème : `TradeRecord.sl_pips` (ligne 36) et `TradeRecord.spread_cost_pips` (ligne 35) existent dans la dataclass mais ne sont pas exportés dans le CSV de backtest. La friction (spread simulé) n'est pas auditée dans le CSV de référence.
Correction :
- Ajouter dans le dict de chaque ligne exportée :
```python
"sl_pips": round(t.sl_pips, 2),
"spread_cost_pips": round(t.spread_cost_pips, 2),
```
Validation :
```powershell
make qa
# Vérifier colonnes CSV backtest avec head du fichier résultat
```
Dépend de : C-07 (même fichier — appliquer après C-07 ou dans la même passe)
Statut : ⏳

---

## SÉQUENCE D'EXÉCUTION

```
C-01  Atomicité live_journal.py           [🔴 P0 · 30min] → make qa
C-02  PnL USD multi-paires                [🔴 P0 · 20min] → make qa
C-03  exit_reason SL/TP                   [🟠 P1 · 2h00]  → make qa  ← dépend C-01
C-04  adx_at_entry / strength_at_entry    [🟠 P1 · 30min] → make qa  ← dépend C-03
C-05  duration_s + pnl_eur csv live       [🟠 P1 · 30min] → make qa  ← dépend C-04
C-06  trades session-end journalisés      [🟠 P1 · 1h00]  → make qa  ← dépend C-03 + C-05
C-07  Atomicité backtest_export.py        [🟡 P2 · 20min] → make qa
C-08  sl_pips + spread_cost_pips backtest [🟡 P2 · 15min] → make qa  ← dépend C-07 (même fichier)
```

**Total estimé : ~5h25**

**Règle critique :** aucun `.pyx` modifié dans ce plan → `make build` NON requis.

---

## CRITÈRES PASSAGE EN PRODUCTION

- [ ] Zéro 🔴 ouvert (C-01 + C-02 complétés et QA vert)
- [ ] `make qa` : 100% pass (lint + mypy + pytest ≥80%)
- [ ] Zéro credential dans les logs loguru
- [ ] `ALPHAEDGE_PAPER=true` intact dans `.env.example`
- [ ] Bracket order `is_valid` vérifié avant envoi IB
- [ ] `check_daily_limit()` appelé chaque cycle
- [ ] `exit_reason` présent dans tous les trades closés (SL, TP, session_end)
- [ ] PnL USD vérifié pour EURUSD + USDJPY (test paramétré)
- [ ] CSV live non-corruptible (test atomicité C-01)
- [ ] Paper trading validé 5 sessions NYSE minimum

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier | Effort | Statut | Date |
|----|-------|----------|---------|--------|--------|------|
| C-01 | Atomicité CSV live | 🔴 Critique | `live_journal.py:58` | 30 min | ⏳ | — |
| C-02 | PnL USD multi-paires | 🔴 Critique | `session_lifecycle.py:362` | 20 min | ⏳ | — |
| C-03 | exit_reason SL/TP/session_end | 🟠 Majeur | `live_types.py:35` + `session_lifecycle.py:331` | 2h00 | ⏳ | — |
| C-04 | adx_at_entry + strength_at_entry | 🟠 Majeur | `live_types.py:36` + `session_lifecycle.py:176` | 30 min | ⏳ | — |
| C-05 | duration_s + pnl_eur CSV live | 🟠 Majeur | `live_journal.py:27` | 30 min | ⏳ | — |
| C-06 | Trades session-end journalisés | 🟠 Majeur | `session_lifecycle.py:803` | 1h00 | ⏳ | — |
| C-07 | Atomicité backtest export | 🟡 Mineur | `backtest_export.py:45` | 20 min | ⏳ | — |
| C-08 | sl_pips + spread_cost_pips backtest | 🟡 Mineur | `backtest_export.py:45` | 15 min | ⏳ | — |
