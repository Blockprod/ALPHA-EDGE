---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: audit_trade_journal_alphaedge.md
derniere_revision: 2026-03-26
creation: 2026-03-26 à 14:00
---

# Audit — Journal de Trading ALPHAEDGE
**Date :** 2026-03-26 · **Baseline :** 596 tests · 0 Ruff · 0 Pyright

---

## 1. État actuel — Traçabilité live

### 1.1 Module `live_types.py` — Structure `LiveTradeRecord`

**Fichier :** `alphaedge/engine/live_types.py:17–38`

```python
@dataclass
class LiveTradeRecord:
    pair: str
    direction: int           # 1 = long, -1 = short
    entry_price: float       # prix demandé
    fill_price: float        # prix réel IB avgFillPrice
    stop_loss: float
    take_profit: float
    lot_size: float
    sl_pips: float           # signal["risk_pips"]
    spread_pips: float       # spread capturé à l'entrée
    exchange_rate: float     # mid-price pour conversion PnL
    entry_time: datetime     # now_utc() au moment du fill
    exit_price: float = 0.0
    exit_time: datetime | None = None
    pnl_pips: float = 0.0
    pnl_usd: float = 0.0
    outcome: str = ""        # 'win' | 'loss' | 'breakeven' | 'unknown'
    slippage_pips: float     # abs(fill - entry) / pip_size
```

**Évaluation :** Structure complète pour les données microstructure. Capture entry + slippage réel. Manquent : `exit_reason`, `adx_at_entry`, `strength_at_entry`, `pnl_eur`.

### 1.2 Point d'ancrage `_record_fill()` — Entrée

**Fichier :** `alphaedge/engine/session_lifecycle.py:176–229`

Appelé immédiatement après `placeOrder`. Capture :
- `fill_price` : `trade.orderStatus.avgFillPrice` — ✅ réel IB
- `slippage_pips` : `abs(fill_price - entry_price) / pip_size` — ✅ calculé correctement
- `spread_pips` : transmis depuis `_check_spread_and_execute` — ✅ (C-03 corrigé)
- `entry_time` : `now_utc()` — ✅ UTC ISO 8601

**Gap identifié :** Le signal contient `signal["adx"]` (ligne 661) et `signal["strength"]` (ligne 660), mais ces valeurs ne sont **pas** persistées dans `LiveTradeRecord`. Elles sont loggées (`TRADE_ENTRY`) mais non écrites en CSV.

### 1.3 Point d'ancrage `_on_trade_closed()` — Sortie

**Fichier :** `alphaedge/engine/session_lifecycle.py:331–413`

Déclenché via `filledEvent` sur chaque ordre bracket (SL ou TP). Capture :
- `exit_price` : `ib_trade.orderStatus.avgFillPrice` — ✅ réel IB
- `exit_time` : `now_utc()` — ✅ UTC
- `pnl_pips` : `(exit_price - entry_price) * direction / pip_size` — ✅
- `pnl_usd` : `pnl_pips * pip_size * lot_size * 100_000` — ✅
- `outcome` : `win / loss / breakeven / unknown` — ✅

**Gap critique :** La raison de sortie (`sl_hit` vs `tp_hit` vs `session_end`) est **totalement absente**. Le hook `filledEvent` ne distingue pas quel ordre bracket (enfant SL ou enfant TP) a déclenché le close. `outcome` est déduit du signe de `pnl_pips`, ce qui est fragile : un SL qui slip en positif serait codé `win`.

**Gap :** `pnl_usd` utilise `record.lot_size * 100_000` sans multiplier par `exchange_rate` (ligne 362). La formule est correcte uniquement pour les paires USD-quoted (EURUSD, GBPUSD). Pour USDJPY, elle est incorrecte.

### 1.4 Module `live_journal.py` — Persistance CSV

**Fichier :** `alphaedge/engine/live_journal.py`

**Colonnes CSV exports :**
```
pair, direction, entry_price, fill_price, exit_price, stop_loss, take_profit,
lot_size, sl_pips, spread_pips, slippage_pips, pnl_pips, pnl_usd,
outcome, entry_time, exit_time
```

**Rotation :** Quotidienne — `live_trades_{YYYY-MM-DD}.csv` — ✅ confirmé par `reports/live_trades_2026-03-{24,25,26}.csv`

**Atomicité :** ❌ — `open(path, "a")` direct — pas de `.tmp` → `os.replace`. En cas de crash OS pendant l'écriture, la ligne peut être partiellement écrite et corrompre le CSV.

**Mode append :** ✅ — les lignes existantes ne sont jamais réécrites.

**Header conditionnel :** ✅ — `write_header = not path.exists()` — correct.

### 1.5 Alertes et logs loguru

`TRADE_ENTRY` loggé à l'entrée — `session_lifecycle.py:208–219` — avec pair, direction, entry, fill, sl, tp, lots, sl_pips, spread, slippage.

`TRADE_CLOSE` loggé à la sortie — `session_lifecycle.py:382–393` — avec pair, exit, pnl_pips, pnl_usd, outcome, duration.

Les fichiers logs sont rotatifs par jour : `alphaedge/logs/alphaedge_{YYYY-MM-DD}.log` — rotation gérée par loguru.

---

## 2. État actuel — Traçabilité backtest

### 2.1 `TradeRecord` — Structure backtest

**Fichier :** `alphaedge/engine/backtest_types.py:25–46`

```python
@dataclass
class TradeRecord:
    pair: str
    direction: int
    entry_price: float
    stop_loss: float
    take_profit: float
    entry_time: datetime
    exit_price: float = 0.0
    exit_time: datetime | None = None
    pnl_pips: float = 0.0
    pnl_usd: float = 0.0
    outcome: str = ""        # 'win', 'loss', 'breakeven'
    spread_cost_pips: float  # coût spread simulé
    sl_pips: float           # distance SL
    sample_type: str = ""    # 'IS', 'OOS', ''
```

### 2.2 CSV backtest exporté

**Fichier :** `alphaedge/engine/backtest_export.py:53–74`
**Sortie :** `reports/ALPHAEDGE_backtest_results.csv`

**Colonnes :**
```
pair, direction, entry_price, exit_price, stop_loss, take_profit,
pnl_pips, pnl_usd, pnl_eur, outcome, entry_time, exit_time, sample_type
```

**Colonnes absentes vs `TradeRecord` :** `spread_cost_pips`, `sl_pips` — présents dans la dataclass mais non exportés. Ce sont pourtant les deux métriques clés pour valider les coûts de friction.

---

## 3. Données manquantes — Gaps critiques

### P0 — Bloquants pour passage en live

| ID | Donnée manquante | Localisation gap | Impact |
|----|---|---|---|
| G-01 | **Raison de sortie** (`sl_hit` / `tp_hit` / `session_end`) | `_on_trade_closed` ne sait pas quel ordre bracket a triggeré | Impossible de calculer le vrai win rate SL vs TP. Tout `outcome` déduit du signe de pnl est falsifiable par du slippage. |
| G-02 | **Atomicité CSV** (`tmp → os.replace`) | `live_journal.py:65` — `open(path, "a")` direct | Un crash pendant l'écriture corrompt le fichier. Une ligne partielle fausse toutes les stats ultérieures. |
| G-03 | **Formule PnL USD incorrecte pour non-USD-quoted** | `session_lifecycle.py:362` — ignore `exchange_rate` | `pnl_usd` faux pour USDJPY, USDCHF, etc. Reporting live erroné. `exchange_rate` est bien stocké dans `LiveTradeRecord` mais pas utilisé au calcul de sortie. |

### P1 — Importants pour réconciliation live/backtest

| ID | Donnée manquante | Localisation gap | Impact |
|----|---|---|---|
| G-04 | **Contexte signal non persisté** (`adx`, `strength`) | `_record_fill` ne copie pas `signal["adx"]` / `signal["strength"]` dans `LiveTradeRecord` | Impossible de corréler post-hoc la qualité du signal avec l'outcome. Besoin pour ML filter (Audit #7). |
| G-05 | **`spread_cost_pips` et `sl_pips` absents du CSV backtest** | `backtest_export.py:53–74` omet ces champs | Friction réelle non auditée dans le CSV de référence. Toute comparaison live vs backtest sur coûts est aveugle. |
| G-06 | **`duration_s` absent du CSV live** | `live_journal.py:26–40` — CSV_HEADERS ne contient pas `duration` | La durée moyenne des trades est une métrique clé de risque (position overnight / intraday gap). Loggée mais non persistée. |
| G-07 | **`pnl_eur` absent du CSV live** | `live_journal.py:26–40` — pas de conversion EUR | Le backtest exporte `pnl_eur` via un taux fixe (`eur_usd_rate=1.08`). Le live n'a pas d'équivalent. Réconciliation comptable impossible. |

### P2 — Amélioration de la maturité

| ID | Donnée manquante | Localisation gap | Impact |
|----|---|---|---|
| G-08 | **Session ID / trade ID** | Aucun identifiant unique par trade ou par session | Réconciliation entre logs loguru, CSV live, et alerting est positionnelle, pas nominative. |
| G-09 | **État de la position à la fermeture de session** (`session_end` avec position ouverte) | `_handle_session_end` ferme gracieusement mais ne journalise pas l'outcome via `append_live_trade_csv` | Les trades fermés par fin de session sont absents du CSV live. |
| G-10 | **Métriques de qualité d'exécution** (temps entre signal et fill) | `entry_time = now_utc()` est pris après le fill, mais le timestamp de détection du signal n'est pas stocké | Impossible de mesurer le hot path réel (signal → ordre → fill). |

---

## 4. Risques

### R-01 — Corruption CSV (P0)
**Sévérité :** 🔴 Critique
**Fichier :** `live_journal.py:65`
**Scénario :** Crash OS / power loss pendant `f.write()` dans `open(path, "a")`. Python CSV écrit le header + la ligne dans deux `write()` séquentiels. Entre les deux, un crash laisse un fichier avec header sans donnée, ou une ligne tronquée. Tout parsing ultérieur du CSV échoue ou produit des KPIs faux.
**Impact :** Perte définitive du trade dans le journal. En cas de litige ALPHAEDGE vs IB, le journal ne fait pas foi.

### R-02 — PnL USD faux multi-paires (P0)
**Sévérité :** 🔴 Critique
**Fichier :** `session_lifecycle.py:362`
**Formule actuelle :** `pnl_pips * pip_size * record.lot_size * 100_000`
**Problème :** `exchange_rate` est capturé dans `LiveTradeRecord` (ligne 203) mais ignoré au calcul de sortie. Pour USDJPY : `pip_size = 0.01`, `100_000 lots` — le calcul est en JPY non converti. Le CSV live affiche un PnL en devise incorrecte.
**Impact :** Reporting live incorrect. Calcul de daily loss limit sur base fausse.

### R-03 — `outcome` falsifiable par slippage (P1)
**Sévérité :** 🟠 Majeur
**Fichier :** `session_lifecycle.py:368–375`
**Scénario :** Un SL avec fort slippage positif (gap de marché en sens favorable) donne `pnl_pips > 0` → codé `win`. Ce n'est pas une victoire stratégique.
**Impact :** Win rate live gonflé artificiellement. Impossible de distinguer les vrais TP des SL avec slippage favorable.

### R-04 — Trades session-end non journalisés (P1)
**Sévérité :** 🟠 Majeur
**Fichier :** `session_lifecycle.py:803–860` (`_handle_session_end`)
**Scénario :** Une position ouverte en fin de session est laissée avec bracket actif sur IB. Si elle ferme après la session ALPHAEDGE, `_on_trade_closed` ne se déclenche pas (feed désinscrit). Le CSV live ne contient jamais l'outcome de ce trade.
**Impact :** Journal lacunaire. Les statistiques live sous-comptent les trades réels.

### R-05 — Pas de checksum / intégrité CSV (P2)
**Sévérité :** 🟡 Mineur
**Scénario :** Un outil externe (éditeur, script) modifie `live_trades_YYYY-MM-DD.csv`. Aucun hash ou signature ne permet de détecter la modification.

---

## 5. Recommandations

### C-01 — Atomicité CSV `live_journal.py` [🔴 P0]

**Fichier cible :** `alphaedge/engine/live_journal.py:65`
**Pattern :** `.tmp → os.replace` — idempotent, atomique sur Windows NTFS et Linux ext4.

```python
import tempfile

def append_live_trade_csv(record: LiveTradeRecord) -> None:
    path = _journal_path(record.entry_time)
    os.makedirs(path.parent, exist_ok=True)

    # Lire les données existantes si le fichier existe
    existing_rows: list[dict] = []
    if path.exists():
        with open(path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            existing_rows = list(reader)

    # Écriture atomique dans tmp du même répertoire
    tmp_fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            writer.writeheader()
            writer.writerows(existing_rows)
            writer.writerow({...})  # nouvelle ligne
        os.replace(tmp_path, path)
    except Exception:
        os.unlink(tmp_path)
        raise
```

**Effort :** 30 min · Aucun impact sur les tests existants.

### C-02 — Correction formule PnL USD multi-paires [🔴 P0]

**Fichier cible :** `alphaedge/engine/session_lifecycle.py:362`

```python
# AVANT (incorrect pour non-USD-quoted)
pnl_usd = pnl_pips * pip_size * record.lot_size * 100_000

# APRÈS (correct)
raw_pnl = pnl_pips * pip_size * record.lot_size * 100_000
pnl_usd = raw_pnl / record.exchange_rate if record.exchange_rate > 0 else raw_pnl
```

**Note :** `exchange_rate` est le mid-price de la paire quote/USD au moment de l'entrée. Pour EURUSD, `exchange_rate ≈ 1.0` (déjà en USD) → division par 1,0 → aucun changement. Pour USDJPY, `exchange_rate ≈ 150` → `raw_pnl / 150` → conversion correcte.
**Effort :** 15 min · Un test paramétré à ajouter.

### C-03 — Raison de sortie `exit_reason` [🟠 P1]

**Approche :** Identifier quel ordre bracket (SL ou TP) a fermé via `ib_trade.order.orderId`.

**Fichier cible :** `alphaedge/engine/live_types.py` + `session_lifecycle.py`

```python
# live_types.py — ajouter champ
exit_reason: str = ""  # 'sl_hit' | 'tp_hit' | 'session_end' | 'manual' | 'unknown'

# session_lifecycle.py — dans _on_trade_closed
# Comparer l'orderId du trade fermé avec les IDs des ordres bracket
if ib_trade is not None:
    order_id = getattr(ib_trade, "order", None)
    if order_id and hasattr(state, "_tp_order_id"):
        if order_id.orderId == state._tp_order_id:
            record.exit_reason = "tp_hit"
        elif order_id.orderId == state._sl_order_id:
            record.exit_reason = "sl_hit"
        else:
            record.exit_reason = "unknown"
```

**Point d'ancrage :** `_record_fill` doit stocker `tp_order_id` et `sl_order_id` dans `StrategyState`. Nécessite une extension de `StrategyState`.
**Effort :** 2h · Tests existants à mettre à jour.

### C-04 — Persistance contexte signal (`adx`, `strength`) [🟠 P1]

**Fichier cible :** `alphaedge/engine/live_types.py` + `session_lifecycle.py:201`

```python
# live_types.py — ajouter champs
adx_at_entry: float = 0.0
strength_at_entry: float = 0.0

# session_lifecycle.py — dans _record_fill (ligne ~201)
state.live_record = LiveTradeRecord(
    ...
    adx_at_entry=signal.get("adx", 0.0),
    strength_at_entry=signal.get("strength", 0.0),
)
```

CSV_HEADERS dans `live_journal.py` à compléter avec ces deux colonnes.
**Effort :** 30 min · Impact minimal.

### C-05 — Ajouter `duration_s` et `pnl_eur` au CSV live [🟠 P1]

**Fichier cible :** `alphaedge/engine/live_journal.py`

```python
CSV_HEADERS = [
    ...,
    "duration_s",   # exit_time - entry_time en secondes
    "pnl_eur",      # pnl_usd / eur_usd_rate (lire depuis constants)
]
```

`pnl_eur` doit utiliser le taux de change live du moment de la sortie, pas un taux fixe.
**Effort :** 30 min.

### C-06 — Journaliser les trades session-end [🟠 P1]

**Fichier cible :** `alphaedge/engine/session_lifecycle.py:803–860`

Dans `_handle_session_end`, si une position est ouverte et qu'un `live_record` existe : forcer `exit_reason = "session_end"`, `exit_time = now_utc()`, `outcome = "open_at_end"` et appeler `append_live_trade_csv`.
**Effort :** 1h.

### C-07 — Écriture atomique backtest export [🟡 P2]

Même pattern que C-01 pour `backtest_export.py:74` (`df.to_csv` direct).
**Effort :** 20 min.

### C-08 — Ajouter `spread_cost_pips` et `sl_pips` au CSV backtest [🟡 P2]

**Fichier cible :** `alphaedge/engine/backtest_export.py:53`
Ces champs existent dans `TradeRecord` mais sont omis à l'export.
**Effort :** 10 min.

---

## 6. Synthèse

### Score de maturité du journal

| Dimension | Score | Commentaire |
|---|:---:|---|
| Capture entrée (fill réel, slippage, spread) | 8/10 | Bon. Manque contexte signal. |
| Capture sortie (exit_price, pnl, outcome) | 6/10 | Raison de sortie absente. Formule PnL incorrecte multi-paires. |
| Rotation et nommage fichiers | 9/10 | Quotidien, nommage ISO. |
| Atomicité écriture | 2/10 | `open(path, "a")` direct — risque de corruption réel. |
| Réconciliation live/backtest | 4/10 | Colonnes communes minimales. Friction, durée, raison sortie absentes des deux. |
| Complétude colonnes | 5/10 | 15 colonnes live vs 13 backtest. Gaps symétriques importants. |
| Auditabilité (trace pour litige) | 4/10 | Pas d'ID unique, pas d'atomicité, trades session-end perdus. |

**Score global : 5.4 / 10**

### Verdict Go / No-Go trading live

**⛔ NO-GO** pour passage en trading live avec capitaux réels.

**Bloquants absolus :**
1. **G-02 / C-01** — Atomicité CSV : risque de corruption sur crash.
2. **G-03 / C-02** — Formule PnL incorrecte pour paires non-USD-quoted (USDJPY, USDCHF) — daily loss limit calculé sur base fausse.
3. **G-01 / C-03** — Absence de `exit_reason` : impossible de distinguer SL du TP — win rate non auditables.

**Séquence recommandée :**

```
C-01 (atomicité CSV)      → 30 min → make qa
C-02 (PnL USD multi-pair) → 15 min → make qa
C-03 (exit_reason)        → 2h     → make qa
C-04 (adx/strength)       → 30 min → make qa
C-05 (duration/pnl_eur)   → 30 min → make qa
C-06 (session-end trades) → 1h     → make qa
C-07 (atomicité backtest) → 20 min
C-08 (sl_pips backtest)   → 10 min → make qa final
```

Total estimé : **~5h** pour passer de 5.4/10 → 8.5/10 et atteindre le seuil go-live.

---

## Tableau synthèse

| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact | Effort |
|----|------|-------------|---------------|----------|--------|--------|
| G-01 | Sortie | `exit_reason` absent — SL vs TP indistinguables | `session_lifecycle.py:331` | 🟠 Majeur | Win rate non auditable | 2h |
| G-02 | Persistance | Écriture CSV non atomique — corruption sur crash | `live_journal.py:65` | 🔴 Critique | Perte de trades, données corrompues | 30min |
| G-03 | Calcul | Formule PnL USD ignore `exchange_rate` | `session_lifecycle.py:362` | 🔴 Critique | PnL faux multi-paires, daily-loss-limit incorrect | 15min |
| G-04 | Entrée | `adx` et `strength` non persistés en CSV | `session_lifecycle.py:200` | 🟠 Majeur | Impossible corrélation signal↔outcome | 30min |
| G-05 | Backtest | `spread_cost_pips`, `sl_pips` absents CSV backtest | `backtest_export.py:53` | 🟠 Majeur | Friction non auditée, réconciliation aveugle | 10min |
| G-06 | CSV live | `duration_s` absent du CSV live | `live_journal.py:26` | 🟠 Majeur | Risque overnight/intraday gap non mesurable | 30min |
| G-07 | CSV live | `pnl_eur` absent du CSV live | `live_journal.py:26` | 🟠 Majeur | Réconciliation comptable EUR impossible | 30min |
| G-08 | Identifiant | Pas de session_id / trade_id | modules live | 🟡 Mineur | Réconciliation positionnelle uniquement | 1h |
| G-09 | Session | Trades session-end non journalisés | `session_lifecycle.py:803` | 🟠 Majeur | Journal lacunaire — trades réels non comptés | 1h |
| G-10 | Latence | Timestamp détection signal absent | `session_lifecycle.py:176` | 🟡 Mineur | Hot path non mesurable | 45min |

**Sévérité : 🔴 Critique × 2 · 🟠 Majeur × 6 · 🟡 Mineur × 2**
