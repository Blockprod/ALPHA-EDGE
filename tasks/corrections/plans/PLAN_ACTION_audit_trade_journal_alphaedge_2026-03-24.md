# PLAN D'ACTION — ALPHAEDGE — 2026-03-24
Sources : `tasks/audits/resultats/audit_trade_journal_alphaedge.md`
Total : 🔴 5 · 🟠 1 · 🟡 1 · Effort estimé : 1.5 jours

---

## PHASE 1 — CRITIQUES 🔴

---

### [C-01] Créer `LiveTradeRecord` — structure de données live

Fichier : `alphaedge/engine/live_types.py` *(nouveau fichier)*
Problème : Aucune structure de données n'existe pour un trade live. Seul `TradeRecord` existe, dans le sous-système backtest. La traçabilité live est structurellement impossible sans cette dataclass.
Correction : Créer `alphaedge/engine/live_types.py` avec la dataclass `LiveTradeRecord` :

```python
# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/engine/live_types.py
# DESCRIPTION  : Live trade record type — journal de trading live
# PYTHON       : 3.11.9
# ============================================================
"""ALPHAEDGE — Live trade data type for session journal."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class LiveTradeRecord:
    """Stores a single live trade — populated at fill then updated at close."""

    pair: str
    direction: int            # 1 = long, -1 = short
    entry_price: float        # prix demandé (bracket["entry_price"])
    fill_price: float         # prix réel IB (trade.orderStatus.avgFillPrice)
    stop_loss: float
    take_profit: float
    lot_size: float
    sl_pips: float            # distance SL en pips (signal["risk_pips"])
    spread_pips: float        # spread capturé à l'entrée
    exchange_rate: float      # taux EUR/USD ou JPY/USD pour PnL (1.0 si USD-quoted)
    entry_time: datetime      # now_utc() au moment du fill
    exit_price: float = 0.0
    exit_time: datetime | None = None
    pnl_pips: float = 0.0
    pnl_usd: float = 0.0
    outcome: str = ""         # 'win' | 'loss' | 'breakeven' | 'unknown'
    slippage_pips: float = 0.0  # abs(fill_price - entry_price) / pip_size
```

Validation :
```
make qa
# Attendu : green — nouveau fichier sans imports externes
```
Dépend de : Aucune
Statut : ✅ 2026-03-24

---

### [C-02] Ajouter `live_record` à `StrategyState`

Fichier : `alphaedge/engine/strategy.py:42`
Problème : `StrategyState` ne possède pas de champ pour stocker le trade en cours entre l'entrée (`_record_fill`) et la sortie (`_on_trade_closed`). Sans ce champ, le `LiveTradeRecord` créé à l'entrée est perdu avant la clôture.
Correction : Ajouter le champ `live_record` à la dataclass `StrategyState` :

```python
# Après la ligne : max_candles: int = 200
live_record: LiveTradeRecord | None = None
```

Et ajouter l'import en tête de `strategy.py` :

```python
from alphaedge.engine.live_types import LiveTradeRecord
```

Validation :
```
make qa
# Attendu : green — ajout d'un champ None-defaulted, aucun test cassé
```
Dépend de : C-01
Statut : ✅ 2026-03-24

---

### [C-03] Créer `live_journal.py` — export CSV live

Fichier : `alphaedge/engine/live_journal.py` *(nouveau fichier)*
Problème : Aucune fonction d'écriture structurée n'existe pour les trades live. L'export CSV backtest (`backtest_export.py`) ne peut pas être réutilisé — il opère sur une liste complète en fin de session, alors qu'il faut ici un **append atomique par trade**, en rotation journalière.
Correction : Créer `alphaedge/engine/live_journal.py` :

```python
# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/engine/live_journal.py
# DESCRIPTION  : Live trade journal — CSV append journalier
# PYTHON       : 3.11.9
# ============================================================
"""ALPHAEDGE — Live trade journal: append one trade per close."""

from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path

from alphaedge.engine.live_types import LiveTradeRecord
from alphaedge.utils.logger import get_logger
from alphaedge.utils.timezone import now_utc

logger = get_logger()

LIVE_JOURNAL_DIR = "reports"

CSV_HEADERS = [
    "pair", "direction", "entry_price", "fill_price", "exit_price",
    "stop_loss", "take_profit", "lot_size", "sl_pips", "spread_pips",
    "slippage_pips", "pnl_pips", "pnl_usd", "outcome",
    "entry_time", "exit_time",
]


def _journal_path(trade_date: datetime | None = None) -> Path:
    """Return the CSV path for the given date (today if None)."""
    d = (trade_date or now_utc()).strftime("%Y-%m-%d")
    return Path(LIVE_JOURNAL_DIR) / f"live_trades_{d}.csv"


def append_live_trade_csv(record: LiveTradeRecord) -> None:
    """
    Append one completed trade to today's live journal CSV.

    Creates the file with headers if it does not exist.
    Uses append mode — never rewrites existing rows.
    """
    path = _journal_path(record.entry_time)
    os.makedirs(path.parent, exist_ok=True)
    write_header = not path.exists()
    try:
        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            if write_header:
                writer.writeheader()
            writer.writerow({
                "pair": record.pair,
                "direction": "LONG" if record.direction == 1 else "SHORT",
                "entry_price": record.entry_price,
                "fill_price": record.fill_price,
                "exit_price": record.exit_price,
                "stop_loss": record.stop_loss,
                "take_profit": record.take_profit,
                "lot_size": record.lot_size,
                "sl_pips": round(record.sl_pips, 2),
                "spread_pips": round(record.spread_pips, 2),
                "slippage_pips": round(record.slippage_pips, 4),
                "pnl_pips": round(record.pnl_pips, 2),
                "pnl_usd": round(record.pnl_usd, 2),
                "outcome": record.outcome,
                "entry_time": record.entry_time.isoformat() if record.entry_time else "",
                "exit_time": record.exit_time.isoformat() if record.exit_time else "",
            })
        logger.info(
            "TRADE_JOURNAL: {} {} — pnl_pips={:+.1f} — outcome={} — {}",
            record.pair,
            "LONG" if record.direction == 1 else "SHORT",
            record.pnl_pips,
            record.outcome,
            path.name,
        )
    except OSError:
        logger.exception("TRADE_JOURNAL: Failed to write live trade CSV — {}", path)
```

Validation :
```
make qa
# Attendu : green — nouveau fichier, aucun import circulaire
```
Dépend de : C-01
Statut : ✅ 2026-03-24

---

### [C-04] Modifier `_record_fill()` — capturer les données d'entrée

Fichier : `alphaedge/engine/session_lifecycle.py:167`
Problème : `_record_fill()` incrémente uniquement `trades_today` et pose `is_position_open = True`. Le `fill_price` IB réel, `entry_time`, `spread_pips`, `bracket`, `lot_size`, `sl_pips` et `direction` sont tous disponibles à cet instant mais ne sont pas capturés. Le `LiveTradeRecord` n'est jamais créé.

Correction : Étendre la signature de `_record_fill` et créer le `LiveTradeRecord` sur `state` :

1. **Modifier la signature** pour accepter `bracket`, `signal`, `spread_pips`, `pip_size`, `exchange_rate` :
   ```python
   def _record_fill(
       self,
       state: StrategyState,
       trades_placed: list,
       bracket: dict[str, Any],
       signal: dict[str, Any],
       spread_pips: float,
       pip_size: float,
       exchange_rate: float,
   ) -> None:
   ```

2. **Capturer le fill_price** depuis le premier trade IB et **créer le `LiveTradeRecord`** :
   ```python
   from alphaedge.engine.live_types import LiveTradeRecord  # en tête du fichier
   from alphaedge.utils.timezone import now_utc              # déjà importé

   entry_time = now_utc()
   parent = trades_placed[0]
   raw_fill = getattr(getattr(parent, "orderStatus", None), "avgFillPrice", None)
   fill_price = float(raw_fill) if raw_fill else bracket["entry_price"]
   slippage = abs(fill_price - bracket["entry_price"]) / pip_size

   state.live_record = LiveTradeRecord(
       pair=state.pair,
       direction=bracket["direction"],
       entry_price=bracket["entry_price"],
       fill_price=fill_price,
       stop_loss=bracket["stop_loss"],
       take_profit=bracket["take_profit"],
       lot_size=bracket["units"],
       sl_pips=signal["risk_pips"],
       spread_pips=spread_pips,
       exchange_rate=exchange_rate,
       entry_time=entry_time,
       slippage_pips=slippage,
   )
   ```

3. **Mettre à jour le site d'appel** dans `_execute_signal()` :
   ```python
   self._record_fill(state, trades_placed, bracket, signal, spread_pips, pip_size, exchange_rate)
   ```

4. **Modifier le callback filledEvent** pour passer l'objet Trade IB à `_on_trade_closed` (prépare C-05) :
   ```python
   for trade_obj in trades_placed:
       trade_obj.filledEvent += lambda _t, _pair=state.pair: self._on_trade_closed(_pair, _t)
   ```

Validation :
```
make qa
# Attendu : green — signature change + appel mis à jour
```
Dépend de : C-01, C-02
Statut : ✅ 2026-03-24

---

### [C-05] Modifier `_on_trade_closed()` — capturer EXIT + calculer PnL + écrire CSV

Fichier : `alphaedge/engine/session_lifecycle.py:243`
Problème : `_on_trade_closed(pair: str)` ignore l'objet Trade IB (`_t`). À la clôture, aucune donnée n'est capturée : ni `exit_price`, ni `exit_time`, ni PnL, ni `outcome`. C'est le gap le plus critique — toute la performance live est perdue.

Correction :

1. **Étendre la signature** pour recevoir l'objet Trade IB :
   ```python
   def _on_trade_closed(self, pair: str, ib_trade: Any = None) -> None:
   ```

2. **Dans `_reset_position()`** — extraire `exit_price`, calculer PnL, finaliser `LiveTradeRecord`, écrire CSV :
   ```python
   from alphaedge.engine.live_journal import append_live_trade_csv  # en tête du fichier

   async def _reset_position() -> None:
       async with self._s._trade_lock:
           state = self._s._states.get(pair)
           if state:
               state.is_position_open = False
               logger.info(f"ALPHAEDGE: Position closed for {pair}")

               # Capture exit data and finalise live record
               if state.live_record is not None:
                   record = state.live_record
                   exit_time = now_utc()
                   pip_size = PIP_SIZES.get(pair, 0.0001)

                   raw_exit = None
                   if ib_trade is not None:
                       raw_exit = getattr(
                           getattr(ib_trade, "orderStatus", None),
                           "avgFillPrice", None
                       )
                   exit_price = float(raw_exit) if raw_exit else 0.0

                   pnl_pips = (
                       (exit_price - record.entry_price) * record.direction / pip_size
                       if exit_price else 0.0
                   )
                   # USD PnL: for USD-quoted pairs (EUR/USD), factor = 1.0
                   # For USD-base pairs (USD/JPY), factor = exchange_rate (JPY/USD ≈ 1/mid)
                   pnl_usd = pnl_pips * pip_size * record.lot_size * 100_000

                   record.exit_price = exit_price
                   record.exit_time = exit_time
                   record.pnl_pips = round(pnl_pips, 2)
                   record.pnl_usd = round(pnl_usd, 2)
                   record.outcome = (
                       "win" if pnl_pips > 0
                       else ("breakeven" if pnl_pips == 0.0 else "loss")
                   )
                   if not exit_price:
                       record.outcome = "unknown"

                   append_live_trade_csv(record)
                   state.live_record = None  # Clear after write

               self._persist_daily_state()
   ```

Validation :
```
make qa
# Attendu : green — _on_trade_closed signature backward-compatible (default ib_trade=None)
```
Dépend de : C-01, C-02, C-03, C-04
Statut : ✅ 2026-03-24

---

## PHASE 2 — MAJEURES 🟠

---

### [C-06] Ajouter logs structurés TRADE_ENTRY / TRADE_CLOSE

Fichier : `alphaedge/engine/session_lifecycle.py:167,243`
Problème : Les seules lignes de log liées aux trades sont `"ALPHAEDGE SIGNAL: {pair} BUY @ {entry_price}"` et `"ALPHAEDGE: Position closed for {pair}"` — format libre, non parsable de manière fiable. En cas de crash, impossible d'extraire les données d'un log partiel.
Correction : Après création du `LiveTradeRecord` dans `_record_fill()`, ajouter :

```python
logger.info(
    "TRADE_ENTRY | pair={} | dir={} | entry={} | fill={} | sl={} | tp={} | lots={} | sl_pips={:.1f} | spread={:.1f} | slip={:.2f}",
    record.pair,
    "LONG" if record.direction == 1 else "SHORT",
    record.entry_price,
    record.fill_price,
    record.stop_loss,
    record.take_profit,
    record.lot_size,
    record.sl_pips,
    record.spread_pips,
    record.slippage_pips,
)
```

Après `append_live_trade_csv(record)` dans `_on_trade_closed()` :

```python
logger.info(
    "TRADE_CLOSE | pair={} | exit={} | pnl_pips={:+.1f} | pnl_usd={:+.2f} | outcome={} | duration={}s",
    record.pair,
    record.exit_price,
    record.pnl_pips,
    record.pnl_usd,
    record.outcome,
    int((record.exit_time - record.entry_time).total_seconds())
    if record.exit_time and record.entry_time else "?",
)
```

Validation :
```
make qa
# Attendu : green
```
Dépend de : C-04, C-05
Statut : ✅ 2026-03-24

---

## PHASE 3 — MINEURES 🟡

---

### [C-07] Script de réconciliation live/backtest

Fichier : `scripts/reconcile_live_backtest.py` *(nouveau fichier)*
Problème : Il est impossible de comparer automatiquement les performances live vs backtest. Sans réconciliation, une divergence de winrate entre simulation et production reste invisible.
Correction : Créer `scripts/reconcile_live_backtest.py` — script CLI qui :
- Charge `reports/live_trades_YYYY-MM-DD.csv` (ou toute la plage `reports/live_trades_*.csv`)
- Charge `reports/ALPHAEDGE_backtest_results.csv`
- Calcule par paire : winrate, avg_pnl_pips, avg_spread, avg_slippage
- Affiche un tableau comparatif dans le terminal (Rich `Table`)
- Retourne exit code 1 si `abs(live_winrate - backtest_winrate) > 0.15`

Validation :
```
# Aucun make qa requis — script autonome hors alphaedge/
python scripts/reconcile_live_backtest.py --help
# Attendu : aide CLI affichée sans erreur
```
Dépend de : C-03 (format CSV live)
Statut : ✅ 2026-03-24

---

## SÉQUENCE D'EXÉCUTION

```
C-01  →  C-02
C-01  →  C-03
C-01, C-02  →  C-04  →  C-05  →  C-06
C-03  →  C-07
```

Ordre optimal (sans blocage) :
1. **C-01** — `live_types.py` (aucune dépendance)
2. **C-02** — `StrategyState.live_record` (dépend C-01)
3. **C-03** — `live_journal.py` (dépend C-01, parallélisable avec C-02)
4. **C-04** — `_record_fill()` (dépend C-01, C-02)
5. **C-05** — `_on_trade_closed()` (dépend C-01, C-02, C-03, C-04)
6. **C-06** — logs structurés (dépend C-04, C-05)
7. **C-07** — script réconciliation (dépend C-03, indépendant des autres)

> ⚠️ Aucun fichier `.pyx` n'est modifié — `make build` non requis.

---

## CRITÈRES PASSAGE EN PRODUCTION

- [ ] Zéro 🔴 ouvert
- [ ] `make qa` : 100% pass (lint + mypy + pytest ≥80%)
- [ ] `reports/live_trades_YYYY-MM-DD.csv` créé après une session paper avec ≥1 trade
- [ ] Champs `exit_price`, `pnl_pips`, `outcome` non vides dans le CSV
- [ ] `slippage_pips` calculé et cohérent (< 3 pips en paper)
- [ ] Log `TRADE_ENTRY` et `TRADE_CLOSE` présents dans `alphaedge/logs/alphaedge_YYYY-MM-DD.log`
- [ ] Script `reconcile_live_backtest.py` exécutable sans erreur
- [ ] `ALPHAEDGE_PAPER=true` intact dans `.env.example`
- [ ] Paper trading validé 5 sessions NYSE minimum avec journal non vide

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier | Effort | Statut | Date |
|---|---|---|---|---|---|---|
| C-01 | Créer `LiveTradeRecord` | 🔴 | `engine/live_types.py` (nouveau) | 30 min | ✅ | 2026-03-24 |
| C-02 | `live_record` sur `StrategyState` | 🔴 | `engine/strategy.py:42` | 15 min | ✅ | 2026-03-24 |
| C-03 | Créer `live_journal.py` CSV append | 🔴 | `engine/live_journal.py` (nouveau) | 45 min | ✅ | 2026-03-24 |
| C-04 | Modifier `_record_fill()` | 🔴 | `engine/session_lifecycle.py:167` | 1 h | ✅ | 2026-03-24 |
| C-05 | Modifier `_on_trade_closed()` | 🔴 | `engine/session_lifecycle.py:243` | 1 h | ✅ | 2026-03-24 |
| C-06 | Logs structurés TRADE_ENTRY/CLOSE | 🟠 | `engine/session_lifecycle.py:167,243` | 30 min | ✅ | 2026-03-24 |
| C-07 | Script réconciliation live/backtest | 🟡 | `scripts/reconcile_live_backtest.py` | 2 h | ✅ | 2026-03-24 |
