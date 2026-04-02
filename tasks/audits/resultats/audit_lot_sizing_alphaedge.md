---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: audit_lot_sizing_alphaedge.md
derniere_revision: 2026-04-01
creation: 2026-04-01 à 22:00
---

# AUDIT LOT SIZING — ALPHAEDGE — 2026-04-01

**Baseline verrouillé** : Sharpe=2.90 · OOS Sharpe=2.59 · MaxDD=9.00% · OOS MaxDD=15.50% · 579 trades
**Stack** : Python 3.11.9 · `alphaedge/core/_stubs/risk_manager.py` · `alphaedge/engine/backtest_stats.py`

---

## BLOC 1 — Implémentation actuelle (formule + flux + bugs)

### 1.1 Formule de sizing — stub Python

**Fichier** : `alphaedge/core/_stubs/risk_manager.py:8–42`

```
calculate_position_size(account_equity, risk_pct, sl_pips, pair, pip_size, lot_type, ...)
  pip_val = _compute_pip_value(pair, pip_size, lot_type, exchange_rate)
  risk_amount = account_equity × (risk_pct / 100)
  raw_lots = risk_amount / (sl_pips × pip_val)
  lot_size = floor(raw_lots × 100) / 100
  is_valid = min_lots ≤ lot_size ≤ max_lots
```

**`_compute_pip_value` (lignes 113–126)** :
```python
units = {"micro": 1000}  # lot_type micro
raw = units × pip_size
if exchange_rate > 0.0 and pip_size >= 0.001:
    return raw / exchange_rate   # JPY path (conversion USD)
return raw                       # non-JPY path (directement USD)
```

| Pair | pip_size | pip_val (exchange_rate=0) | pip_val correct (ex_rate=155) |
|---|---|---|---|
| EURUSD | 0.0001 | **$0.10/pip** ✓ | $0.10/pip |
| GBPUSD | 0.0001 | $0.10/pip (approx — devrait être ~$0.127) | ~$0.127/pip |
| USDJPY | 0.01 | **¥10/pip traitée comme $10** ✗ | ~$0.065/pip |

### 1.2 Flux complet — backtest

**Fichier** : `alphaedge/engine/backtest.py`

```
_collect_daily_trades()
  └─► _validate_backtest_signal()                    [backtest.py:365–405]
        calculate_position_size(
          account_equity = config.trading.starting_equity,  ← FIXE ($10k, jamais mis à jour)
          exchange_rate  = 0.0,                             ← HARDCODÉ (bug USDJPY)
        )
        → is_valid gate (lot_size ≥ min_lots=0.01)
        → lot_size RETOURNÉ MAIS IGNORÉ (TradeRecord n'a pas de champ lot_size)
  └─► _build_trade_record()                          [simulation: 1 micro lot implicite]
        pnl_pips = raw_pnl / pip_size - spread - carry
        pnl_usd  = pnl_pips × 1000 × pip_size        ← 1 micro lot, pas de FX (biais JPY)

── APRÈS TOUTES LES PAIRES ──
_apply_equity_sizing(all_trades, starting_equity, risk_pct)  [backtest.py:256]
  ← ÉCRASE pnl_usd avec la vraie formule compound :
  risk_usd = equity × risk_pct / 100
  t.pnl_usd = risk_usd × (pnl_pips / sl_pips)           ← pair-agnostique, correct
  equity += t.pnl_usd                                    ← compound trade par trade
```

**Flux live** (`position_manager.py:56`) :
```python
equity = state.current_equity or state.starting_equity   ← DYNAMIQUE ✓
exchange_rate = exchange_rate (paramètre du caller)       ← correctement propagé
```

### 1.3 Bugs et edge cases identifiés

**BUG-1 🟡 — `exchange_rate=0.0` hardcodé pour USDJPY** (`backtest.py:376`)
- Impact : lot_size USDJPY = 0.41 micro lots (devrait être ~64) → 155× sous-estimé
- Conséquence P&L : **AUCUNE** — `_apply_equity_sizing` écrase le pnl_usd avec la formule correcte
- Conséquence gate : 0.41 ≥ min_lots(0.01) → gate passe toujours → **aucun trade filtré à tort**
- Conséquence live : `position_manager.py` reçoit le vrai exchange_rate → divergence conceptuelle

**BUG-2 🟡 — Backtest utilise `starting_equity` fixe pour le gate** (`backtest.py:366`)
- À equity=$26.7k final, le gate continue de vérifier la faisabilité sur $10k
- Si equity tombait sous $1.5k (lot_size < min_lots), le gate bloquerait les trades même si l'equity est suffisante pour la vraie formule
- Pas de scenario actuel : equity ne descend pas sous $10k en IS ni en OOS

**BUG-3 🟡 — `lot_size` calculé puis ignoré** (`backtest.py:405` → `_build_trade_record`)
- `lot_size` est retourné par `_validate_backtest_signal` mais non stocké dans `TradeRecord`
- Non transmis à la simulation (simulation toujours 1 micro lot)
- Commentaire explicite : `# lot_size: unused for pip calculation` (`backtest_simulation.py:164`)
- API trompeuse : calcul sans usage

**OBSERVATION-1 ✅ — `_apply_equity_sizing` est le vrai moteur**
- Formule `risk_usd × (pnl_pips / sl_pips)` = R-multiple pur, pair-agnostique
- Gère l'ensemble des 3 paires chronologiquement, equity compound
- Tous les résultats reportés (Sharpe=2.90, MaxDD=9%, total P&L) sont calculés sur cette base → **fiables**

**OBSERVATION-2 ✅ — Validation risk_pct au chargement** (`loader.py:496`)
- `0.0 < risk_pct ≤ 10.0` → intervalle correct
- `lot_type` validé parmi `standard/mini/micro` ✓
- Aucun support `risk_pct_by_pair` en config ni dans le loader

---

## BLOC 2 — Limites et asymétries identifiées

### 2.1 Effet du compounding sur le MaxDD

La formule `_apply_equity_sizing` compound trade par trade :

| Moment | Equity | risk_usd/trade | Perte 1R (SL hit) | Gain 2R (TP hit) |
|---|---|---|---|---|
| Début IS | $10,000 | $67 | -$67 | +$134 |
| Pic IS | ~$20,000 | $134 | -$134 | +$268 |
| Final ($26,783) | $26,783 | $179 | -$179 | +$358 |

**Impact MaxDD** : IS MaxDD = 9.00% mesuré au pic d'equity → correspondent à des pertes de ~$1,800 en dollars absolus. En fin de période (equity élevée), une même série de pertes représente +2.5× plus de dollars qu'au début.

**OOS MaxDD = 15.50%** : l'OOS démarre après le pic IS — les lots sont plus grands → les drawdowns OOS sont naturellement plus larges en %.

→ C'est le comportement attendu du fixed-fraction compounding. Ce n'est pas un bug.

### 2.2 Asymétrie GBPUSD — sur-représentation sans edge proportionnel

| Pair | N trades | WR | PF | P&L moyen/trade |
|---|---|---|---|---|
| EURUSD | 118 (20%) | 47.5% | 1.80 | **+$46.3/trade** |
| GBPUSD | **302 (52%)** | 43.7% | **1.25** | +$19.3/trade |
| USDJPY | 159 (27%) | 49.7% | 1.66 | +$34.5/trade |

GBPUSD génère **52% des trades** pour seulement **34.7% du P&L total** et **le PF le plus faible**.
L'efficience de GBPUSD (P&L/trade) est **2.4× inférieure** à EURUSD.

Coût caché : GBPUSD produit ~170 trades perdants vs 62 pour EURUSD → driver probable des séries de pertes consécutives (max consec. losses=9). GBPUSD est le principal contribuant au MaxDD.

### 2.3 SL fixe et bruit de marché

- SL = 16 pips = `rr_ratio(2.0) × min_range_pips(8.0)`
- avg_loss = **-18.2 pips** > SL 16 pips : cohérent avec spread variable (~1–2p) + slippage qui pousse le strike réel à ~17–18 pips
- SL/ATR par paire :

| Pair | ATR daily | SL (16p) / ATR | Intraday range 1h (~40% ATR) |
|---|---|---|---|
| EURUSD | ~80p | 20% | ~32p → SL ≈ 50% de 1h |
| GBPUSD | ~100p | 16% | ~40p → SL ≈ 40% de 1h |
| USDJPY | ~110p | 15% | ~44p → SL ≈ 36% de 1h |

Le SL à 16 pips représente 36–50% du range NYSE 1h typique → **raisonnable** pour un signal momentum intraday. Le risque de stop-out prématuré est réel mais accepté (avg_win=+30.9p couvre 170% du SL).

### 2.4 Quantization floor — non problématique

| Equity | raw_lots | lot_size (floor ×100/100) | Perte de précision |
|---|---|---|---|
| $10,000 | 41.875 | 41.87 | 0.005 lot = $0.008/pip = 1.2% de risk_usd |
| $5,000 | 20.94 | 20.94 | négligeable |
| $1,500 | 6.28 | 6.28 | négligeable |
| $150 | 0.628 | 0.62 | floor discrétise à 0.62 → OK (≥ min_lots) |
| $90 | 0.377 | 0.37 | OK |
| $24 | 0.10 | 0.10 | OK (min_lots=0.01) |

**La quantization n'est un problème que sous ~$240 d'equity** (lot_size < 0.10). Non pertinent pour ce compte.

---

## BLOC 3 — Évaluation des pistes d'amélioration

### Piste 3.1 — Sizing différencié par paire (`risk_pct_by_pair`)

**Concept** : Réduire l'exposition GBPUSD (PF=1.25) et augmenter EURUSD/USDJPY.
Exemple : EURUSD=0.80%, GBPUSD=0.50%, USDJPY=0.70% (global = 2.00%, inchangé)

**Mécanisme** : Modifier `_apply_equity_sizing` pour lire un dict par paire.
- Config actuelle : `risk_pct_by_pair` N'EXISTE PAS dans config.yaml ni loader.py
- Implémentation requiert : nouveau champ `TradingConfig`, parsing loader, modification `_apply_equity_sizing`

**Verdict** : 🟠 **PROMETTEUR**

| Critère | Évaluation |
|---|---|
| Impact MaxDD | Modéré ↓ — GBPUSD réduit de 25% → ~7.8 DD théorique |
| Impact Sharpe | Légère ↑ EURUSD compensant, stable global |
| Risque IS overfitting | **ÉLEVÉ** si différence agressive (PF calculé sur IS 3 ans) |
| Complexité | M (3 fichiers : loader, backtest_stats, config.yaml) |
| Sans toucher core/*.pyx | ✅ oui |
| Implémentation | Modifier `_apply_equity_sizing(t.pair, risk_pct_dict)` |

**Seuil recommandé** : différence max ±25% de 0.67% (soit 0.50–0.84%). Au-delà → surfit IS.

---

### Piste 3.2 — Drawdown-scaled sizing

**Concept** : `lot_size × max(0.5, 1 − rolling_DD / max_DD_config)` — réduire en période de stress.

**Verdict** : 🟡 **FAIBLEMENT PROMETTEUR**

| Critère | Évaluation |
|---|---|
| Impact MaxDD | Théoriquement ↓ mais arrive APRÈS la DD (réactif, pas préventif) |
| Impact Sharpe | ↓ car réduit aussi l'exposition sur les rebonds |
| Implémentation | Complexe : rolling equity tracker dans `_apply_equity_sizing` |
| Risque régression | Moyen — comportement non-linéaire difficile à anticiper |
| Testabilité backtest | ✅ oui (modifier `_apply_equity_sizing`) |

→ **À tester en second si 3.1 déçoit**

---

### Piste 3.3 — ATR-scaling du `risk_pct` (volatility-adjusted sizing)

**Concept** : `risk_pct_effective = risk_pct × (ATR_ref / ATR_current)`.
- SL et TP restent inchangés (R:R toujours 2.0 — pas le problème du sl_atr_multiplier rejeté)
- C'est le MONTANT RISQUÉ qui diminue quand ATR augmente

**Verdict** : 🟠 **PROMETTEUR — mais complexe**

| Critère | Évaluation |
|---|---|
| Impact MaxDD | ↓ sur les sessions à forte volatilité (ATR élevé → lots réduits) |
| Impact Win rate | Neutre (SL/TP inchangés) |
| Implémentation | L — nécessite stockage ATR dans TradeRecord + modification `_apply_equity_sizing` |
| Risque régression | Faible (formule monotone) |
| vs sl_atr_multiplier | Différent et non-rejeté : ici R:R reste 2.0, seul le montant exposé change |

→ **À implémenter après 3.1** — plus d'impact que 3.1 sur OOS DD

---

### Piste 3.4 — Half-Kelly comme borne supérieure

**Kelly estimé** sur métriques agrégées :
- b = AvgWin/AvgLoss = 30.9/18.2 = **1.698**
- p = WR = 0.461, q = 0.539
- K = (p × b − q) / b = (0.461 × 1.698 − 0.539) / 1.698 = 0.244 / 1.698 = **14.4%**
- Half-Kelly = **7.2%** par paire

**Conclusion** : `risk_pct atual = 0.67%` est à **9.3% du Kelly** → très conservateur.
La stratégie est loin d'être sur-risquée. Kelly ne donne pas de levier pour réduire le MaxDD.

**Verdict** : 🔴 **À REJETER** — dans le mauvais sens (augmenter risk_pct augmente MaxDD)

---

### Piste 3.5 — Cap de lot absolu par session

**Concept** : Limiter la somme des lots ouverts simultanément (ex : 0.15 lot total = 3×0.05).

**Analyse** : Le risque multi-paires est DÉJÀ contrôlé par le design :
- 3 paires × 0.67% risk_pct = 2.0% d'exposition globale maximale par session
- `max_lots=10.0` est une borne de sécurité, jamais atteinte à l'equity actuel
- Un cap supplémentaire serait redondant avec le sizing existant

**Verdict** : 🔴 **À REJETER** — protection déjà en place

---

## BLOC 4 — Plan de test priorisé

### Priorité 1 — Piste 3.1 : `risk_pct_by_pair`

**Objectif** : Réduire GBPUSD de 0.67% → 0.50%, compenser EURUSD à 0.80%, USDJPY à 0.70%.
Total global = 2.00% (inchangé).

**Fichiers à toucher** (3 fichiers, pas de core/*.pyx) :

1. `config.yaml` — ajouter :
   ```yaml
   trading:
     risk_pct_by_pair:
       EURUSD: 0.80
       GBPUSD: 0.50
       USDJPY: 0.70
   ```

2. `alphaedge/config/loader.py` — ajouter dans `TradingConfig` :
   ```python
   risk_pct_by_pair: dict[str, float] = field(default_factory=dict)
   ```
   Et parsing :
   ```python
   cfg.risk_pct_by_pair = {k: float(v) for k, v in section.get("risk_pct_by_pair", {}).items()}
   ```

3. `alphaedge/engine/backtest_stats.py:_apply_equity_sizing` — modifier :
   ```python
   def _apply_equity_sizing(trades, starting_equity, risk_pct, _max_lot_size=10.0,
                            risk_pct_by_pair: dict[str, float] | None = None) -> None:
       ...
       for t in trades:
           pct = (risk_pct_by_pair or {}).get(t.pair, risk_pct)  # fallback au global
           risk_usd = equity * pct / 100.0
           t.pnl_usd = risk_usd * (t.pnl_pips / t.sl_pips) if t.sl_pips > 0 else 0.0
           equity += t.pnl_usd
   ```

**Valeurs de test** :
| Scénario | EURUSD | GBPUSD | USDJPY | Global |
|---|---|---|---|---|
| Baseline | 0.67% | 0.67% | 0.67% | 2.00% |
| Test A | 0.80% | 0.50% | 0.70% | 2.00% |
| Test B | 0.75% | 0.55% | 0.70% | 2.00% |
| Test C | 0.70% | 0.60% | 0.70% | 2.00% |

**Critères PASS** vs baseline :
| Métrique | Baseline | Seuil PASS | Seuil FAIL |
|---|---|---|---|
| Sharpe (equity %) | 2.90 | ≥ 2.70 | < 2.70 |
| OOS Sharpe | 2.59 | ≥ 2.40 | < 2.40 |
| Max drawdown IS | 9.00% | ≤ 8.50% | > 9.00% |
| OOS Max drawdown | 15.50% | ≤ 13.00% | > 16.00% |
| Total trades | 579 | ± 20 trades | Tout changement trade count |
| Win rate | 46.1% | ≥ 44% | < 43% |

**Note sur trade count** : `risk_pct_by_pair` ne change que le `pnl_usd` post-hoc (via `_apply_equity_sizing`). Il ne modifie pas le filtre `is_valid` donc **aucun trade ne sera ajouté ou retiré**.

---

### Priorité 2 — Piste 3.3 : ATR-scaling du `risk_pct`

À implémenter SI ET SEULEMENT SI la Piste 3.1 est insuffisante sur OOS MaxDD.

**Modification structurelle requise** :
- Stocker `atr_pips` dans `TradeRecord` (nouveau champ)
- Modifier `_apply_equity_sizing` pour une référence ATR par paire
- Définir `atr_ref_pips: dict[str, float]` dans config.yaml (ATR de référence par paire)

---

### Séquençage recommandé

```
Test 3.1.A → Test 3.1.B → Test 3.1.C
      ↓ (si OOS MaxDD > 13%)
Test 3.3 (ATR-scaling)
      ↓ (si Sharpe dégradé < 2.70)
REVERT → Baseline (sl_atr_multiplier=0.0, risk_pct=0.67% uniforme)
```

**Règle d'or** : une seule variable modifiée à la fois. Pas de 3.1 + 3.3 simultanément.

---

## SYNTHÈSE

| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact | Effort |
|---|---|---|---|---|---|---|
| BUG-1 | 1 | `exchange_rate=0.0` hardcodé USDJPY → lot_size gate 155× sous-estimé | backtest.py:376 | 🟡 Mineur | Nul (P&L non affecté par `_apply_equity_sizing`) | XS |
| BUG-2 | 1 | Backtest gate utilise `starting_equity` fixe vs live `current_equity` | backtest.py:366 | 🟡 Mineur | Dormant (equity ne descend pas sous starting) | S |
| BUG-3 | 1 | `lot_size` calculé puis ignoré — API trompeuse | backtest.py:405 → simulation:164 | 🟡 Mineur | Aucun P&L | Documentation |
| OBS-1 | 1 | `_apply_equity_sizing` est le vrai moteur sizing — pair-agnostique, compound | backtest_stats.py:287 | ✅ | Métriques fiables | — |
| LIM-1 | 2 | GBPUSD 52% des trades, PF=1.25 → 2.4× moins efficace que EURUSD | — | 🟠 Majeur | MaxDD GBPUSD dominant | — |
| LIM-2 | 2 | Compounding amplifie MaxDD au pic : IS → OOS MaxDD 9% → 15.5% | backtest_stats.py:273 | 🟠 Majeur | OOS performance | Structural |
| LIM-3 | 2 | SL=16p = 15–20% ATR daily — tight mais adapté session NYSE 1h | constants.py:71 | 🟡 Mineur | avg_loss=-18.2p cohérent | — |
| P3.1 | 3 | `risk_pct_by_pair` PROMETTEUR — cible MaxDD ≤ 8.5% | loader.py:174 | 🟠 | MaxDD ↓, Sharpe stable | M |
| P3.3 | 3 | ATR-scaling `risk_pct` PROMETTEUR mais complexe | backtest_stats.py:287 | 🟠 | OOS MaxDD ↓↓ | L |
| P3.4 | 3 | Half-Kelly → risk_pct actuel = 9.3% Kelly : sizing conservateur | — | 🟡 | Augmenter = plus MaxDD | À rejeter |
