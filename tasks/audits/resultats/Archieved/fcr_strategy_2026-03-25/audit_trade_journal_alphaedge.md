# Audit #12 — Journal de Trading Live · ALPHAEDGE

**Date :** 2026-03-24
**Auditeur :** GitHub Copilot (Claude Sonnet 4.6)
**Scope :** Traçabilité des trades en session live — de l'entrée ordre à la clôture position
**Verdict :** ❌ **NO-GO production** — score global **1/10**

---

## 1. État actuel — Traçabilité live

### 1.1 Données capturées à l'entrée

| Donnée | Disponible au runtime | Persistée |
|---|---|---|
| Paire (`pair`) | ✅ `state.pair` | ✅ `DailyState.open_pairs` (transitoire) |
| Direction | ✅ `signal["signal"]` | ❌ non |
| Prix demandé (`entry_price`) | ✅ `signal["entry_price"]` | ❌ log texte seul |
| SL prix | ✅ `bracket["stop_loss"]` | ❌ non |
| TP prix | ✅ `bracket["take_profit"]` | ❌ non |
| Taille de lot | ✅ `bracket["units"]` | ❌ non |
| Spread à l'entrée (`spread_pips`) | ✅ local dans `_execute_signal` | ❌ abandonné |
| Distance SL en pips | ✅ `signal["risk_pips"]` | ❌ non |
| Timestamp entrée | ✅ `now_utc()` disponible | ❌ **jamais capturé** |
| Fill price IB réel | ✅ dans objet `Trade` IB | ❌ **jamais lu** |

**Référence code :** [`session_lifecycle.py:167`](../../../alphaedge/engine/session_lifecycle.py) — `_record_fill()` incrémente `trades_today` et positionne `is_position_open`, mais **ne stocke aucun détail de trade**.

**Log texte produit :** `"ALPHAEDGE SIGNAL: {pair} BUY @ {entry_price}"` (ligne 497-499) — non structuré, non parsable fiablement.

### 1.2 Données capturées à la clôture

| Donnée | Disponible au runtime | Persistée |
|---|---|---|
| Exit timestamp | ✅ `now_utc()` disponible | ❌ **jamais capturé** |
| Exit price | ✅ `trade.orderStatus.avgFillPrice` (IB) | ❌ **jamais lu** |
| Outcome (SL/TP) | ✅ déductible du fill type | ❌ **jamais calculé** |
| PnL en pips | ✅ calculable (exit_price - entry_price) | ❌ **jamais calculé** |
| PnL en USD | ✅ calculable (lot_size × pnl_pips) | ❌ **jamais calculé** |
| Raison de clôture | ✅ déductible (SL child fill / TP child fill) | ❌ non |

**Référence code :** [`session_lifecycle.py:243-256`](../../../alphaedge/engine/session_lifecycle.py) — `_on_trade_closed()` reçoit uniquement `pair: str`, reset `is_position_open`, log "Position closed for {pair}", re-persiste `DailyState`.
Le callback est `trade_obj.filledEvent += lambda _t, _pair=state.pair: self._on_trade_closed(_pair)` — l'objet `trade` IB est disponible via `_t` mais **ignoré**.

### 1.3 DailyState — contenu persisté

**Fichier :** `alphaedge_daily_state.json` (racine workspace)
**Structure :**

```json
{
  "date": "2026-03-24",
  "starting_equity": 10000.0,
  "trades_today": 2,
  "shutdown_triggered": false,
  "open_pairs": [],
  "last_update_utc": "2026-03-24T15:42:00+00:00"
}
```

`trades_today` = compteur entier uniquement. Aucun détail par trade. À la clôture du bot, cette information est la seule trace structurée de l'activité du jour.

### 1.4 Logs texte — infrastructure

**Fichiers :** `alphaedge/logs/alphaedge_YYYY-MM-DD.log`
**Format :** `[ALPHAEDGE] {UTC} | {CET/CEST} | {LEVEL} | {module}:{func}:{line} | {message}`
**Rotation :** journalière (via loguru `LOG_ROTATION`, `LOG_RETENTION` — `constants.py`)

Les logs contiennent des fragments utiles mais :
- Format texte libre — pas de délimiteur stable ni de champs numérotés
- `entry_price` apparaît dans le message du signal mais pas l'exit_price
- Aucune ligne de type `TRADE_CLOSED | pair | exit_price | pnl`
- Reconstruction manuelle requise — fragile, non auditée

---

## 2. État actuel — Traçabilité backtest

### 2.1 TradeRecord (`backtest_types.py:26`)

```python
@dataclass
class TradeRecord:
    pair: str
    direction: int          # 1 = long, -1 = short
    entry_price: float
    stop_loss: float
    take_profit: float
    entry_time: datetime
    exit_price: float = 0.0
    exit_time: datetime | None = None
    pnl_pips: float = 0.0
    pnl_usd: float = 0.0
    outcome: str = ""       # 'win', 'loss', 'breakeven'
    spread_cost_pips: float = 0.0
    sl_pips: float = 0.0
    sample_type: str = ""   # 'IS', 'OOS', ''
```

**Complétude : 14/14 champs critiques couverts.**

### 2.2 Export backtest

**Fichier :** `reports/ALPHAEDGE_backtest_results.csv`
**En-têtes :** `pair, direction, entry_price, exit_price, stop_loss, take_profit, pnl_pips, pnl_usd, pnl_eur, outcome, entry_time, exit_time, sample_type`
**Référence :** [`backtest_export.py:37-75`](../../../alphaedge/engine/backtest_export.py)

Chaque trade est intégralement tracé. La réconciliation IS/OOS est possible.

### 2.3 Asymétrie critique

| Composante | Backtest | Live |
|---|---|---|
| Structure de données par trade | ✅ `TradeRecord` | ❌ inexistante |
| Entry_time | ✅ | ❌ |
| Exit_price | ✅ | ❌ |
| PnL calculé | ✅ | ❌ |
| Export CSV | ✅ | ❌ |
| Traçabilité audit | ✅ complète | ❌ absente |

---

## 3. Gaps critiques

### P0 — Bloquants (données absentes en totalité)

| ID | Gap | Impact | Fichier concerné |
|---|---|---|---|
| G-01 | Aucune `LiveTradeRecord` — structure inexistante | Si crash bot → 0 trace du trade | — à créer |
| G-02 | `entry_time` jamais capturé lors du fill | Impossible de calculer durée/slippage | `session_lifecycle.py:167` |
| G-03 | `fill_price` IB ignoré (`_t` dans lambda callback) | Slippage totalement invisible | `session_lifecycle.py:175` |
| G-04 | `exit_price` jamais capturé à la clôture | PnL réel inconnu | `session_lifecycle.py:243` |
| G-05 | `exit_time` jamais capturé | Durée de trade inconnue | `session_lifecycle.py:243` |
| G-06 | PnL pips/USD jamais calculé en live | Performance réelle non supervisée | — |
| G-07 | `outcome` (SL/TP) non déterminé | Distribution réelle win/loss inconnue | `session_lifecycle.py:243` |

### P1 — Importants (données disponibles mais non persistées)

| ID | Gap | Donnée disponible | Fichier concerné |
|---|---|---|---|
| G-08 | `spread_pips` à l'entrée non persisté | Variable locale `_execute_signal` | `session_lifecycle.py:215` |
| G-09 | `lot_size` non persisté | `bracket["units"]` | `session_lifecycle.py:167` |
| G-10 | `sl_pips` non persisté | `signal["risk_pips"]` | `session_lifecycle.py:167` |
| G-11 | Direction non persistée | `bracket["direction"]` | `session_lifecycle.py:167` |
| G-12 | `entry_price` demandé vs fill réel (slippage=G-03+G-02) | `bracket["entry_price"]` + `trade.orderStatus.avgFillPrice` | `session_lifecycle.py:167,175` |

### P2 — Souhaitables (contexte signal enrichi)

| ID | Gap | Impact |
|---|---|---|
| G-13 | FCR zone (high/low) non enregistrée avec le trade | Impossible d'analyser la qualité du range ex-post |
| G-14 | ATR ratio gap non enregistré | Corrélation signal/volatilité non traçable |
| G-15 | Volatility regime non enregistré | Filtrage ML non évaluable en live |
| G-16 | `exchange_rate` (JPY) non persisté | Vérification PnL USD impossible |

---

## 4. Risques

### R1 — Opacité totale de la performance live *(Critique)*
Sans `exit_price` ni PnL calculé, il est impossible de savoir si la stratégie est profitable en production. Un backtest à 40% winrate peut cacher un live à 15% — silencieusement. La seule "vérité" disponible est le solde IB, non réconcilié avec les trades FCR.

### R2 — Perte de données en cas de crash *(Critique)*
Si le bot crash entre `_record_fill()` et la persistance des détails du trade, toute trace du trade actif disparaît. `DailyState` confirme `trades_today=N` mais aucun détail. Le log texte peut manquer si le buffer loguru n'est pas flushed.

### R3 — Slippage invisible *(Élevé)*
`DEFAULT_MARKET_SLIPPAGE_PIPS` dans `constants.py` est le seul paramètre de slippage — une valeur fixée a priori, jamais mesurée sur données réelles. Sans `fill_price` vs `entry_price`, l'hypothèse modèle ne peut pas être validée.

### R4 — Impossibilité de réconciliation live/backtest *(Élevé)*
Sans `LiveTradeRecord` avec les mêmes champs que `TradeRecord`, toute comparaison live/backtest est manuelle, subjective, et non automatisable. Le ROADMAP mentionne un dashboard de réconciliation (`engine/web_dashboard.py`) — il ne peut pas fonctionner sans données live structurées.

### R5 — Non-conformité audit externe *(Modéré)*
Un audit de risque ou un broker review exigerait un journal de trades daté et signé. Les logs texte loguru ne constituent pas une preuve suffisante.

---

## 5. Recommandations

### R1 — Créer `LiveTradeRecord` *(P0 — bloquant)*

**Fichier :** `alphaedge/engine/backtest_types.py` (ajouter à la suite) ou nouveau `alphaedge/engine/live_types.py`

```python
@dataclass
class LiveTradeRecord:
    pair: str
    direction: int          # 1 = long, -1 = short
    entry_price: float      # prix demandé (bracket["entry_price"])
    fill_price: float       # prix réel IB (trade.orderStatus.avgFillPrice)
    stop_loss: float
    take_profit: float
    lot_size: float
    sl_pips: float
    spread_pips: float      # spread capturé à l'entrée
    entry_time: datetime    # now_utc() dans _record_fill
    exit_price: float = 0.0
    exit_time: datetime | None = None
    pnl_pips: float = 0.0
    pnl_usd: float = 0.0
    outcome: str = ""       # 'win', 'loss', 'breakeven', 'unknown'
    slippage_pips: float = 0.0  # fill_price - entry_price (en pips)
```

### R2 — Modifier `_record_fill()` pour capturer les données d'entrée *(P0)*

**Fichier :** [`session_lifecycle.py:167`](../../../alphaedge/engine/session_lifecycle.py)

Actuellement :
```python
def _record_fill(self, state, trades_placed) -> None:
    for trade_obj in trades_placed:
        trade_obj.filledEvent += lambda _t, _pair=state.pair: self._on_trade_closed(_pair)
    state.trades_today += 1
    ...
```

Après correction :
```python
def _record_fill(self, state, trades_placed, bracket, signal, spread_pips) -> None:
    entry_time = now_utc()
    fill_price = trades_placed[0].orderStatus.avgFillPrice
    record = LiveTradeRecord(
        pair=state.pair,
        direction=bracket["direction"],
        entry_price=bracket["entry_price"],
        fill_price=fill_price,
        stop_loss=bracket["stop_loss"],
        take_profit=bracket["take_profit"],
        lot_size=bracket["units"],
        sl_pips=signal["risk_pips"],
        spread_pips=spread_pips,
        entry_time=entry_time,
        slippage_pips=abs(fill_price - bracket["entry_price"]) / state.pip_size,
    )
    state.live_record = record  # stocker sur StrategyState
    for trade_obj in trades_placed:
        trade_obj.filledEvent += lambda _t, _pair=state.pair: self._on_trade_closed(_pair)
    ...
```

### R3 — Modifier `_on_trade_closed()` pour capturer les données de sortie *(P0)*

**Fichier :** [`session_lifecycle.py:243`](../../../alphaedge/engine/session_lifecycle.py)

Le callback lambda `lambda _t, _pair=state.pair: self._on_trade_closed(_pair)` ignore `_t` (l'objet Trade IB). Modifier pour passer le trade :

```python
trade_obj.filledEvent += lambda _t, _pair=state.pair: self._on_trade_closed(_pair, _t)
```

Puis dans `_on_trade_closed(pair, ib_trade)` :
```python
exit_price = ib_trade.orderStatus.avgFillPrice
exit_time = now_utc()
record = state.live_record
if record:
    record.exit_price = exit_price
    record.exit_time = exit_time
    pip_size = PIP_SIZES.get(pair, 0.0001)
    record.pnl_pips = (exit_price - record.entry_price) * record.direction / pip_size
    record.pnl_usd = record.pnl_pips * pip_size * record.lot_size * 100_000
    record.outcome = "win" if record.pnl_pips > 0 else "loss"
    _append_live_csv(record)  # R4
```

### R4 — Écrire un CSV live en rotation journalière *(P0)*

**Fichier cible :** `reports/live_trades_YYYY-MM-DD.csv`
**En-têtes :** `pair, direction, entry_price, fill_price, exit_price, stop_loss, take_profit, lot_size, sl_pips, spread_pips, slippage_pips, pnl_pips, pnl_usd, outcome, entry_time, exit_time`

Fonction `_append_live_csv(record: LiveTradeRecord) -> None` — append atomique (une ligne par call, pas de rechargement du fichier entier).

### R5 — Ajouter des lignes log structurées *(P1)*

Compléter les logs texte avec des lignes JSON-like parsables :

```python
logger.info(
    "TRADE_ENTRY | pair={} | dir={} | entry={} | fill={} | sl={} | tp={} | lots={} | spread_pips={:.1f} | slippage_pips={:.1f}",
    pair, direction, entry_price, fill_price, sl, tp, lots, spread_pips, slippage_pips
)
logger.info(
    "TRADE_CLOSE | pair={} | exit={} | pnl_pips={:+.1f} | pnl_usd={:+.2f} | outcome={} | duration={}s",
    pair, exit_price, pnl_pips, pnl_usd, outcome, duration_s
)
```

### R6 — Script de réconciliation live/backtest *(P2)*

Nouveau script `scripts/reconcile_live_backtest.py` — compare `reports/live_trades_YYYY-MM-DD.csv` vs `reports/ALPHAEDGE_backtest_results.csv` sur winrate/avg_pnl/spread par paire.

---

## 6. Synthèse

### Scorecard traçabilité live

| Composante | Score | Détail |
|---|---|---|
| Données d'entrée capturées | 1/10 | Log texte entry_price seul |
| Données de sortie capturées | 0/10 | Rien — position closed = seul log |
| PnL live calculé | 0/10 | Jamais calculé |
| Persistance structurée | 0/10 | DailyState = compteur seul |
| Réconciliation live/backtest | 0/10 | Impossible sans données |
| Infrastructure log | 3/10 | Logs texte complets mais non parsables |
| **Global** | **1/10** | |

### Verdict

> ❌ **NO-GO production**

La traçabilité live est insuffisante pour toute supervision sérieuse du trading algorithmi que. Un sinistre (crash bot, désync IB, rotation log) efface toute trace des trades du jour. La mesure du slippage — paramètre clé justifiant `DEFAULT_MARKET_SLIPPAGE_PIPS` dans le modèle de risque — est structurellement impossible.

### Ordre de traitement recommandé

| Priorité | Recommandation | Effort | Impact |
|---|---|---|---|
| P0 | R1 — Créer `LiveTradeRecord` | Faible (dataclass) | Critique |
| P0 | R2 — Modifier `_record_fill()` | Moyen | Critique |
| P0 | R3 — Modifier `_on_trade_closed()` | Moyen | Critique |
| P0 | R4 — CSV live journalier | Faible | Critique |
| P1 | R5 — Log structuré TRADE_ENTRY/TRADE_CLOSE | Faible | Élevé |
| P2 | R6 — Script réconciliation | Élevé | Moyen |

**La correction P0 complète (R1 → R4) est un prérequis stratégique avant tout déploiement live. Sans elle, ALPHAEDGE est un "black box" en production.**
