---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: audit_migration_momentum_carry_alphaedge.md
derniere_revision: 2026-03-25
creation: 2026-03-25 à 11:00
---

# AUDIT — Migration Momentum + Carry FX
# ALPHAEDGE · Swing Trading · Daily/H4

> Stratégie cible : Time Series Momentum (Moskowitz 2012) + FX Carry (Lustig 2011) · Swing · IB Gateway
> Baseline : 1106 tests · coverage ≥80% sur config/, utils/, core/

---

## BLOC 1 — Inventaire : ce qui disparaît

### 1.1 Modules Cython FCR à désactiver

**`fcr_detector`** — `alphaedge/core/_stubs/fcr_detector.py`

Fonctions exportées :
- `detect_fcr(candles_data, min_range_pips, pip_size) → dict | None` — ligne 8
- `detect_fcr_scan(candles_data, min_range_pips, pip_size, lookback) → dict | None` — ligne 34

Modules qui l'importent :
- `alphaedge/engine/signal_pipeline.py:50` — `modules.fcr_detector.detect_fcr()`
- `alphaedge/engine/backtest.py:592,593,623` — `fcr_detector` passé comme argument, appelé en ligne 623
- `alphaedge/engine/strategy.py:68,89,90,109` — champ de `CoreModules`, instancié dans `_import_core_modules()`

Tests couvrant ce module :
- `alphaedge/tests/test_fcr_detector_detect.py:19` — import direct
- `alphaedge/tests/test_fcr_detector_jpy.py:18` — import direct
- `alphaedge/tests/test_fcr_detector_scan.py:18` — import direct

Verdict : **🔴 À SUPPRIMER** — aucune réutilisabilité dans la nouvelle stratégie.

---

**`gap_detector`** — `alphaedge/core/_stubs/gap_detector.py`

Fonctions exportées :
- `detect_gap(pre_session_m1, session_m1, pre_close, session_open, atr_period, min_atr_ratio) → dict` — ligne 8
- `is_in_gap_zone(price, gap_high, gap_low, tolerance_pips, pip_size) → bool` — ligne 59
- `_compute_atr(candles, period) → float` — ligne 71

Modules qui l'importent :
- `alphaedge/engine/signal_pipeline.py:74` — `modules.gap_detector.detect_gap()`
- `alphaedge/engine/backtest.py:470,478,594,635` — passé en argument et appelé
- `alphaedge/engine/strategy.py:69,89,91` — champ de `CoreModules`

Tests couvrant ce module :
- `alphaedge/tests/test_gap_detector_empty.py:18` — import direct
- `alphaedge/tests/test_gap_detector_spike.py:18` — import direct
- `alphaedge/tests/test_gap_detector_zone.py:16` — import direct

Verdict : **🔴 À SUPPRIMER** — détection de gap NYSE Open → sans objet pour un swing Daily.

---

**`engulfing_detector`** — `alphaedge/core/_stubs/engulfing_detector.py`

Fonctions exportées :
- `detect_engulfing(candles_data, fcr_high, fcr_low, rr_ratio, pip_size, volume_period, min_volume_ratio, min_body_ratio, max_wick_ratio) → dict | None` — ligne 8

Modules qui l'importent :
- `alphaedge/engine/signal_pipeline.py:108` — `modules.engulfing_detector.detect_engulfing()`
- `alphaedge/engine/backtest.py:495,519,592,651` — passé en argument et appelé
- `alphaedge/engine/strategy.py:70,89,90` — champ de `CoreModules`

Tests couvrant ce module :
- `alphaedge/tests/test_engulfing_detector_bullish.py:18` — import direct
- `alphaedge/tests/test_engulfing_detector_bearish.py:18` — import direct
- `alphaedge/tests/test_engulfing_detector_quality.py:18` — import direct
- `alphaedge/tests/test_engulfing_detector_volume.py:18` — import direct

Verdict : **🔴 À SUPPRIMER** — pattern M1 couplé à FCR → sans objet pour swing.

---

### 1.2 Paramètres FCR obsolètes dans `constants.py`

| Constante | Ligne (≈) | Valeur | Action |
|-----------|-----------|--------|--------|
| `DEFAULT_MIN_RANGE_PIPS` | ~131 | `8.0` | 🔴 SUPPRIMER — seuil FCR |
| `DEFAULT_FCR_LOOKBACK` | ~133 | `6` | 🔴 SUPPRIMER — lookback FCR |
| `DEFAULT_MIN_ATR_RATIO` | ~112 | `2.0` | 🔴 SUPPRIMER — gate gap detector |
| `DEFAULT_GAP_TOLERANCE_PIPS` | ~114 | `5.0` | 🔴 SUPPRIMER — zone gap |
| `DEFAULT_MIN_BODY_RATIO` | ~139 | `0.3` | 🔴 SUPPRIMER — qualité engulfing |
| `DEFAULT_MAX_WICK_RATIO` | ~141 | `1.5` | 🔴 SUPPRIMER — qualité engulfing |
| `NYSE_OPEN_SLIPPAGE_MULTIPLIER` | ~165 | `2.0` | 🟡 ADAPTER — NYSE open non pertinent pour swing; garder pour coût monitoring |
| `NYSE_OPEN_SPREAD_PIPS` | ~167 | `1.5` | 🟡 ADAPTER — idem |
| `NYSE_OPEN_WINDOW_MINUTES` | ~178 | `5` | 🟡 ADAPTER — idem |
| `SESSION_START_HOUR/MINUTE` | ~35-38 | `9:30` | 🟡 ADAPTER — devient fenêtre de monitoring, plus signal |
| `LONDON_START_HOUR/MINUTE` | ~44-48 | `8:00` | 🟡 ADAPTER — idem |
| `DEFAULT_ATR_PERIOD` | ~111 | `14` | ✅ CONSERVER — utile pour momentum (ADX calcul) |
| `DEFAULT_VOLUME_PERIOD` | ~126 | `20` | ✅ CONSERVER — utile pour confirmation momentum |
| `DEFAULT_MIN_VOLUME_RATIO` | ~128 | `1.0` | ✅ CONSERVER — utile pour confirmation momentum |
| `TF_M1`, `TF_M5` | ~54-56 | strings | 🟡 ADAPTER — garder pour monitoring, ajouter `TF_H4`, `TF_D1` |
| `PIP_SIZES` | ~62-75 | dict | ✅ CONSERVER — générique, utile pour carry différentiel |

---

### 1.3 Paramètres FCR obsolètes dans `config.yaml`

| Clé YAML | Action |
|----------|--------|
| `structure.min_range_pips: 8.0` | 🔴 SUPPRIMER |
| `structure.lookback_candles: 6` | 🔴 SUPPRIMER |
| `structure.fcr_timeframe: "5 mins"` | 🔴 SUPPRIMER (remplacer par `signal_timeframe: "1 day"`) |
| `structure.entry_timeframe: "1 min"` | 🔴 SUPPRIMER (remplacer par `confirmation_timeframe: "4 hours"`) |
| `structure.fcr_range_cv_max: 0.5` | 🔴 SUPPRIMER |
| `volatility.min_atr_ratio: 1.7` | 🔴 SUPPRIMER (lié au gap detector) |
| `volatility.tolerance_pips: 5.0` | 🔴 SUPPRIMER |
| `volatility.min_atr_ratio_by_pair` | 🔴 SUPPRIMER |
| `engulfing.min_body_ratio: 0.3` | 🔴 SUPPRIMER |
| `engulfing.max_wick_ratio: 1.5` | 🔴 SUPPRIMER |
| `trading.london_open_enabled: false` | 🔴 SUPPRIMER (pertinence swing nulle) |
| `trading.session_start/end` | 🟡 ADAPTER — renommer en `monitoring_window_start/end` |
| `pattern.volume_period: 20` | 🟡 ADAPTER — renommer `momentum_lookback_fast: 12`, `momentum_lookback_slow: 26` |
| `pattern.min_volume_ratio: 1.0` | 🟡 ADAPTER → seuil ADX minimum (ex: `adx_threshold: 25.0`) |
| `pair_sessions` (bloc complet) | 🔴 SUPPRIMER — sessions intraday deviennent monitoring úniquement |

---

### 1.4 Logique FCR dans `engine/`

| Fichier | Lignes | Nature de la dépendance | Action |
|---------|--------|------------------------|--------|
| `engine/signal_pipeline.py` | 37–120 | 3 méthodes FCR/gap/engulfing — classe entière est FCR | 🔴 RÉÉCRIRE entièrement |
| `engine/backtest.py` | 470,478,495,519,592-594,623,635,651 | `fcr_detector`/`gap_detector`/`engulfing_detector` passés comme args | 🟠 ADAPTER `_backtest_pair()` et `_detect_signal_at_bar()` |
| `engine/strategy.py` | 68-70,89-91,109 | `CoreModules` avec 3 champs FCR | 🟠 ADAPTER `CoreModules` + `_import_core_modules()` |
| `engine/strategy.py` | 225-258 | `_detect_fcr()`, `_detect_gap()`, `_detect_engulfing()` | 🔴 REMPLACER par `_detect_momentum()`, `_get_carry_bias()` |
| `engine/strategy.py` | 127 | Classe `FCRStrategy` — nom couplé à la stratégie | 🟡 RENOMMER en `SwingStrategy` |
| `engine/backtest_filters.py` | 55-57 | Fallback NYSE 9:30-10:30 quand `session_spec is None` | 🟡 ADAPTER — le fallback swing doit être Daily |
| `engine/backtest_simulation.py` | 28-35 | Imports NYSE open (slippage model) | 🟡 ADAPTER — carry overnight à intégrer |

---

## BLOC 2 — Inventaire : ce qui reste intact

### 2.1 Infrastructure d'exécution

**`broker.py`** — `alphaedge/engine/broker.py`
- `BrokerConnection`, `OrderExecutor`, `RequestThrottler`, `build_forex_contract()` — stratégie-agnostiques
- Aucun couplage FCR détecté
- Les types d'ordres (`MarketOrder`, `LimitOrder`, `StopOrder`) sont tous supportés pour swing
- Verdict : **✅ CONSERVÉ INTACT**

**`order_manager`** — `alphaedge/core/_stubs/order_manager.py`
- `create_bracket_order(direction, entry_price, stop_loss, take_profit, lot_size, ...)` — générique
- `direction` est `int` (1 ou -1) → compatible avec tout signal
- Validation SL/TP placement purement géométrique → compatible swing
- Verdict : **✅ CONSERVÉ INTACT**

**`position_manager.py`** — `alphaedge/engine/position_manager.py`
- `size_position()` — délègue à `risk_manager.calculate_position_size()` → générique
- Aucune référence à `session_end` ou `close_on_session_end` dans les méthodes vues (lignes 1-80)
- `config.yaml` : `session_end_action: "hold"` — supporte déjà les positions overnight sans modification
- Verdict : **✅ CONSERVÉ INTACT**

---

### 2.2 Infrastructure backtest

**`backtest.py` framework général** — `alphaedge/engine/backtest.py`
- Framework `run_backtest()`, `_fetch_pair_trades()`, `BarDiskCache`, exports CSV, equity curve → générique
- Couplage FCR localisé dans `_backtest_pair()` (lignes 470-700) et `_detect_signal_at_bar()` (lignes 333-357)
- `walk_forward`, `bayesian_optimizer`, `monte_carlo` : aucun couplage FCR détecté
- Verdict : **🟠 CONSERVÉ AVEC ADAPTATION** (supprimer les détecteurs FCR dans `_backtest_pair()`)

**`backtest_simulation.py`** — `alphaedge/engine/backtest_simulation.py`
- Modèle de coûts : `compute_variable_slippage()` — spread + slippage par contexte de marché
- Le carry overnight (swap points IB) **n'est pas modélisé** — manquant pour swing
- Point d'extension : ajouter `compute_overnight_carry(pair, direction, days_held, rates)` → nouveau point
- Verdict : **🟠 CONSERVÉ AVEC ADAPTATION** (carry overnight à ajouter)

**`backtest_stats.py`, `backtest_export.py`, `backtest_types.py`** :
- `TradeRecord`, `BacktestStats`, `BacktestReport` — structures de données génériques
- `compute_stats()`, `print_rich_summary()`, `export_results_csv()` — génériques
- Verdict : **✅ CONSERVÉ INTACT**

**`walk_forward.py`, `bayesian_optimizer.py`, `monte_carlo.py`** :
- Aucun couplage FCR visible dans les imports
- `run_walk_forward()` opère sur `entry_bars` / `fcr_bars` → renommer les paramètres uniquement
- Verdict : **✅ CONSERVÉ INTACT** (avec renommage mineur des paramètres)

---

### 2.3 Data pipeline

**`data_feed.py`** — `alphaedge/engine/data_feed.py`

Points clés :
- `BarDiskCache` : clé = `(pair, timeframe)` → cache `"1 day"` supporté sans modification (ligne 58-72)
- `_bar_to_dict()` (ligne 80-110) : gère déjà `date` objects (pas uniquement `datetime`) → compatible Daily bars nativement
- `_chunk_days_for_timeframe()` (ligne 239) : renvoie `365` pour tout timeframe non reconnu → **Daily fetch fonctionnel dès maintenant** sans modification
- Fetch via chaîne IB standard (`reqHistoricalData`) → compatible `"1 day"` comme durée IB
- Verdict : **🟡 CONSERVÉ AVEC ADAPTATION MINEURE** — ajouter `"1 day"` et `"4 hours"` dans `_chunk_days_for_timeframe()` pour clarté

---

### 2.4 Risk management

**`risk_manager`** — `alphaedge/core/_stubs/risk_manager.py`
- `calculate_position_size(account_equity, risk_pct, sl_pips, pair, pip_size, lot_type, min_lots, max_lots)` → générique
- Le SL swing (50–150 pips) est plus large qu'en intraday → la formule reste identique, seul `sl_pips` change
- `check_daily_limit()` → générique, applicable en swing
- `check_pair_limit()` → générique
- Verdict : **✅ CONSERVÉ INTACT**

---

## BLOC 3 — Regime filter : état actuel

### 3.1 Ce qui est déjà implémenté

**`alphaedge/engine/regime_filter.py`** — classe `DailyRegimeFilter`

Fonctions publiques :
- `fit(m5_bars_history, pair="") → None` — entraîne un KMeans 2-clusters sur l'historique M5 (ligne 96)
- `predict(session_date, pre_session_m5) → str` — retourne `"high_vol"` | `"low_vol"` | `"unknown"` (ligne 177)
- `needs_recalibration(reference_date=None) → bool` — seuil = 30 jours (ligne 225)

Paramètres de détection (ligne 63-67) :
- Features : `atr_daily` (std des ranges M5), `intraday_range` (max_high − min_low), `momentum` (last_close − first_close)
- Algorithme : KMeans 2-clusters + StandardScaler
- Identification high_vol : cluster avec ATR moyen le plus élevé

Timeframe : **M5 bars pré-session** — couplage explicite à l'intraday (`pre_session_m5`, ligne 185)

Importé dans :
- `alphaedge/engine/strategy.py:29` — import
- `alphaedge/engine/strategy.py:181` — instancié dans `FCRStrategy.__init__()`
- `alphaedge/engine/strategy.py:234-237` — appelé dans `_detect_fcr()` en **OBSERVATION ONLY**

Non importé dans `backtest.py` — absent du pipeline backtest.

---

### 3.2 Réutilisabilité pour Momentum + Carry

**Couplage M5** : `_extract_daily_features()` (ligne 43) attend des barres M5. Incompatible direct avec Daily.

**Adaptation nécessaire** : changer l'input de M5 à Daily bars. Les 3 features (`atr_daily`, `intraday_range`, `momentum`) restent pertinentes sur Daily — elles mesurent exactement les conditions de régime qui conditionnent le momentum swing.

**Rôle dans la nouvelle architecture** :
- Couche 2 (gate optionnel) après `momentum_detector`
- Entrée : barres Daily des 20 derniers jours de trading
- Utilisation : bloquer les entrées momentum en régime `"low_vol"` (marché en range sans tendance)
- Delta Sharpe attendu à mesurer : activer seulement si improvement démontrable

Verdict : **🟡 RÉUTILISABLE AVEC ADAPTATION** — modifier uniquement `_extract_daily_features()` pour accepter des barres Daily, pas `predict()` ni `fit()`.

---

## BLOC 4 — Modules à créer

### 4.1 `momentum_detector.pyx` — `alphaedge/core/momentum_detector.pyx`

**Justification Cython** : chemin critique du signal — appelé pour chaque barre Daily de chaque paire.

Interface publique :
```python
def detect_momentum(
    bars: list[dict[str, Any]],       # barres Daily ou H4, triées par timestamp
    fast_period: int,                  # ex: 12 (EMA rapide)
    slow_period: int,                  # ex: 26 (EMA lente)
    adx_period: int,                   # ex: 14 (période ADX)
    adx_threshold: float,              # ex: 25.0 (gate minimum)
) -> dict[str, Any] | None:
    # Retourne:
    # {
    #   "detected": True,
    #   "direction": 1 | -1,          # LONG ou SHORT
    #   "strength": float,             # ADX normalisé 0-1 (pour sizing)
    #   "ema_fast": float,             # EMA fast (dernier)
    #   "ema_slow": float,             # EMA slow (dernier)
    #   "adx": float,                  # valeur ADX brute
    #   "timestamp": int,              # timestamp de la dernière barre
    # }
    # Retourne None si ADX < adx_threshold → STOP pipeline
```

Point d'ancrage : `alphaedge/engine/signal_pipeline.py` ligne 37 — remplace `detect_fcr()`

Stub Python à créer : `alphaedge/core/_stubs/momentum_detector.py`

Dépendances : `numpy` (déjà dans requirements)

Complexité : **Modérée** (EMA + ADX = formules iteratives; Cython strict)

---

### 4.2 `carry_signal.py` — `alphaedge/engine/carry_signal.py`

**Justification Python** : dépend d'une API externe (taux IB) — pas de hot path Cython nécessaire.

Interface publique :
```python
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class CarrySignal:
    differential: float        # base_rate - quote_rate (annualisé, %)
    direction: Literal["LONG", "SHORT", "NEUTRAL"]
    daily_carry_pips: float    # carry estimé par jour calendaire
    is_valid: bool

def get_carry_bias(
    pair: str,                 # ex: "AUDJPY", "EURUSD"
    rates: dict[str, float],  # ex: {"AUD": 4.35, "JPY": 0.10, "EUR": 3.65}
) -> CarrySignal:
    # - Calcule differential = rates[base] - rates[quote]
    # - direction = LONG si differential > 0, SHORT si differential < 0
    # - NEUTRAL si abs(differential) < 0.5% (carry négligeable)
    # - daily_carry_pips = (differential / 100) × pip_size_factor / 365
    # - is_valid = True si pair reconnu et taux disponibles
```

Paires prioritaires :
- `AUDJPY` : carry principal (~4.25% différentiel RBA vs BoJ)
- `EURUSD` : carry secondaire (~0.7% BCE vs Fed, variable)
- `GBPUSD` : momentum pur (carry faible, souvent NEUTRAL)

Point d'ancrage : `alphaedge/engine/signal_pipeline.py`, après `detect_momentum()` — biais directionnel confirmatoire.

Dépendances : aucune nouvelle bibliothèque, uniquement `alphaedge/config/constants.py` (PIP_SIZES).

Complexité : **Simple**

---

### 4.3 Adaptation `signal_pipeline.py` — réécriture

Nouveau pipeline séquencé à implémenter dans `alphaedge/engine/signal_pipeline.py` :

```
Étape 1 → momentum_detector.detect_momentum(daily_bars)
              → MomentumSignal | None
              → STOP si None (ADX < threshold)

Étape 2 → carry_signal.get_carry_bias(pair, rates)
              → CarrySignal
              → STOP si direction LONG et carry SHORT (signal contradictoire)
              → OU continuer avec note de divergence

Étape 3 → regime_filter.predict(today, daily_bars[-20:])  [OPTIONNEL]
              → "high_vol" | "low_vol" | "unknown"
              → STOP si "low_vol" (gate activé — à mesurer)

Étape 4 → risk_manager.calculate_position_size()          [CONSERVÉ INTACT]
              → sizing basé sur sl_pips swing (50–150 pips typiques)

Étape 5 → order_manager.create_bracket_order()           [CONSERVÉ INTACT]
              → bracket avec SL/TP swing
```

Lignes cibles à modifier dans `signal_pipeline.py` : **1-120** (réécriture complète de la classe)

---

## BLOC 5 — Risques de régression QA

### 5.1 Tests à SUPPRIMER (import direct des modules FCR)

| Fichier test | Ligne | Import | Action |
|--------------|-------|--------|--------|
| `test_fcr_detector_detect.py` | 19 | `from alphaedge.core import fcr_detector` | 🔴 SUPPRIMER |
| `test_fcr_detector_jpy.py` | 18 | `from alphaedge.core import fcr_detector` | 🔴 SUPPRIMER |
| `test_fcr_detector_scan.py` | 18 | `from alphaedge.core import fcr_detector` | 🔴 SUPPRIMER |
| `test_gap_detector_empty.py` | 18 | `from alphaedge.core import gap_detector` | 🔴 SUPPRIMER |
| `test_gap_detector_spike.py` | 18 | `from alphaedge.core import gap_detector` | 🔴 SUPPRIMER |
| `test_gap_detector_zone.py` | 16 | `from alphaedge.core import gap_detector` | 🔴 SUPPRIMER |
| `test_engulfing_detector_bullish.py` | 18 | `from alphaedge.core import engulfing_detector` | 🔴 SUPPRIMER |
| `test_engulfing_detector_bearish.py` | 18 | `from alphaedge.core import engulfing_detector` | 🔴 SUPPRIMER |
| `test_engulfing_detector_quality.py` | 18 | `from alphaedge.core import engulfing_detector` | 🔴 SUPPRIMER |
| `test_engulfing_detector_volume.py` | 18 | `from alphaedge.core import engulfing_detector` | 🔴 SUPPRIMER |
| `test_signal_pipeline.py` | 34-36,61,89,107,113,149,166,186,202 | Teste FCR/gap/engulfing pipeline | 🔴 SUPPRIMER → RÉÉCRIRE (nouveaux scenarios momentum/carry) |

**Total tests à supprimer : 11 fichiers**

---

### 5.2 Tests à ADAPTER (MagicMock de `CoreModules`)

Ces tests utilisent les champs `fcr_detector`, `gap_detector`, `engulfing_detector` de `CoreModules` via `MagicMock` — ils testent d'autres comportements (shutdown, fills, spread, reconnect) mais doivent être mis à jour quand `CoreModules` change.

| Fichier test | Lignes | Action |
|--------------|--------|--------|
| `test_daily_state_persistence.py` | 54-56 | 🟠 ADAPTER mock CoreModules |
| `test_daily_loss_logging.py` | 33-35 | 🟠 ADAPTER mock CoreModules |
| `test_dependency_injection.py` | 27-29 | 🟠 ADAPTER mock CoreModules |
| `test_fill_verification.py` | 105-107, 296, 301, 305 | 🟠 ADAPTER mock CoreModules + signals momentum |
| `test_graceful_shutdown.py` | 47-49 | 🟠 ADAPTER mock CoreModules |
| `test_race_condition_multi_pair.py` | 64-66 | 🟠 ADAPTER mock CoreModules |
| `test_risk_check_interval.py` | 48-50 | 🟠 ADAPTER mock CoreModules |
| `test_spread_error_blocks_trade.py` | 67-69 | 🟠 ADAPTER mock CoreModules |
| `test_reconnect.py` | 55-57, 84-86 | 🟠 ADAPTER mock CoreModules |
| `test_slippage_integration.py` | 48-50 | 🟠 ADAPTER mock CoreModules |
| `test_spread_monitor.py` | 47-49 | 🟠 ADAPTER mock CoreModules |
| `test_strategy_p2_04.py` | 180, 222, 271, 313, 319, 346 | 🟠 ADAPTER mock CoreModules |
| `test_strategy_p2_05.py` | 45-47, 165, 204 | 🟠 ADAPTER mock CoreModules |
| `test_backtest_news_filter.py` | 109-111, 122-124 | 🟠 ADAPTER mock CoreModules |
| `test_core_backend_visibility.py` | 69-71 | 🟠 ADAPTER — remplacer `fcr_detector` par `momentum_detector` |

**Total tests à adapter : 15 fichiers**

---

### 5.3 Couverture à maintenir

- Coverage threshold actuelle : ≥80% sur `config/`, `utils/`, `core/`
- Après migration : `core/` ne contiendra plus `fcr_detector`, `gap_detector`, `engulfing_detector` → plus de tests à maintenir pour eux
- `momentum_detector.pyx` : couverture via `_stubs/momentum_detector.py` — objectif ≥80%
- `carry_signal.py` : dans `engine/` (exclu du threshold) — tests recommandés quand même

Nouveaux scénarios de tests à créer (prioritaires) :
```
test_momentum_detector_bull_trend.py    — ADX ≥ 25, EMA fast > slow → signal LONG
test_momentum_detector_bear_trend.py   — ADX ≥ 25, EMA fast < slow → signal SHORT
test_momentum_detector_no_trend.py     — ADX < 25 → None (STOP)
test_momentum_detector_insufficient.py — moins de bars que slow_period → None
test_carry_signal_audjpy.py           — AUD 4.35%, JPY 0.10% → LONG carry
test_carry_signal_neutral.py          — différentiel < 0.5% → NEUTRAL
test_carry_signal_unknown_pair.py     — paire non reconnue → is_valid=False
```

---

## BLOC 6 — Plan de migration séquencé

### Phase 1 — Nettoyage FCR (pré-requis)

Opérations :
1. Désactiver les 3 modules FCR dans `alphaedge/core/__init__.py` (ne pas supprimer les `.pyx` — conserver en archive)
2. Supprimer les 11 fichiers test FCR/gap/engulfing directs
3. Supprimer les paramètres FCR dans `constants.py` (6 constantes — cf 1.2)
4. Nettoyer `config.yaml` (12 clés FCR — cf 1.3)
5. Adapter le mock `CoreModules` dans `conftest.py` si centralisé

Critère de sortie : `make qa` passe avec **N tests réduits** (N = baseline − 11 supprimés)
Risque de régression : **Élevé** (11 suppressions + 15 adaptations mock)
Durée estimée : **Complexe (> 4h)**

---

### Phase 2 — Data pipeline Daily/H4

Opérations :
1. Ajouter `TF_H4 = "4 hours"` et `TF_D1 = "1 day"` dans `constants.py`
2. Ajouter `"1 day"` et `"4 hours"` dans `_chunk_days_for_timeframe()` (`data_feed.py:239`)
3. Valider le fetch manuel : `HistoricalDataFeed.fetch_bars_chunked(pair="EURUSD", timeframe="1 day", ...)`

Script de validation suggéré :
```python
# scripts/validate_daily_fetch.py
import asyncio
from alphaedge.engine.broker import BrokerConnection
from alphaedge.engine.data_feed import HistoricalDataFeed
from alphaedge.config.loader import load_config
# fetch 1 an de Daily bars EURUSD → valider N barres ≈ 252/an
```

Critère de sortie : fetch Daily retourne ≥ 240 barres / an, cache `pkl` créé
Risque de régression : **Faible** (modification mineure `_chunk_days_for_timeframe`)
Durée estimée : **Simple (< 1h)**

---

### Phase 3 — `momentum_detector.pyx`

Opérations :
1. Créer `alphaedge/core/momentum_detector.pyx` (interface BLOC 4.1)
2. Créer `alphaedge/core/_stubs/momentum_detector.py` (fallback Python pur)
3. Enregistrer dans `setup.py` (Extension Cython)
4. Mettre à jour `alphaedge/core/__init__.py` — exporter `momentum_detector`
5. `make build` → `make qa`
6. Créer les 4 fichiers test (cf 5.3)

Critère de sortie : `make qa` vert, coverage `core/momentum_detector` ≥ 80%
Risque de régression : **Moyen** (nouveau module Cython, recompilation)
Durée estimée : **Complexe (> 4h)**

> **⚠️ Règle projet** : `make build` obligatoire après tout `.pyx` — runtime = `.pyd`/`.so`, pas `.pyx`

---

### Phase 4 — `carry_signal.py`

Opérations :
1. Créer `alphaedge/engine/carry_signal.py` (interface BLOC 4.2)
2. Créer les 3 fichiers test (cf 5.3)
3. `make qa` → vérifier tests pass

Critère de sortie : `make qa` vert, tests carry pass
Risque de régression : **Faible** (nouveau module Python pur, pas de Cython)
Durée estimée : **Simple (< 1h)**

---

### Phase 5 — `signal_pipeline.py` rewrite + `strategy.py` adaptation

Opérations :
1. Réécrire `signal_pipeline.py` (nouveau pipeline BLOC 4.3)
2. Adapter `CoreModules` dans `strategy.py:68-70` — remplacer `fcr_detector`, `gap_detector`, `engulfing_detector` par `momentum_detector`
3. Réécrire `_import_core_modules()` — importer `momentum_detector`
4. Remplacer `_detect_fcr()`, `_detect_gap()`, `_detect_engulfing()` par `_detect_momentum()`, `_get_carry_bias()`
5. Renommer `FCRStrategy` → `SwingStrategy`
6. Adapter les 15 tests mock (cf 5.2)
7. Réécrire `test_signal_pipeline.py` (scenarios momentum/carry)
8. `make qa` vert

Critère de sortie : `make qa` vert, baseline tests ≥ N − 11 (phases 1-4)
Risque de régression : **Élevé** (cœur du pipeline, 15 mocks à adapter)
Durée estimée : **Complexe (> 4h)**

---

### Phase 6 — Backtest walk-forward swing

Opérations :
1. Adapter `_backtest_pair()` dans `backtest.py` — remplacer détecteurs FCR par `momentum_detector`
2. Ajouter `compute_overnight_carry()` dans `backtest_simulation.py`
3. Adapter `backtest_filters.py:55-57` — fallback non-NYSE pour swing
4. Configurer `config.yaml` : `walk_forward_enabled: true`, paires cibles, `backtest_years: 5`
5. Lancer backtest walk-forward avec barres Daily

Seuil GO : Sharpe OOS ≥ 0.8, N ≥ 50
Seuil NO-GO : toute autre configuration → retour Phase 2 (recalibration paramètres)

Critère de sortie : walk-forward OOS Sharpe ≥ 0.8 sur ≥ 50 trades
Risque de régression : **Moyen** (adaptation backtest engine, nouveau timeframe)
Durée estimée : **Complexe (> 4h)**

---

## SYNTHÈSE

| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact | Effort |
|----|------|-------------|---------------|----------|--------|--------|
| M-01 | 1.1 | Supprimer fcr_detector + 3 tests | core/_stubs/fcr_detector.py, tests/test_fcr_*.py | 🔴 Critique | Bloque migration Phase 1 | Moyen |
| M-02 | 1.1 | Supprimer gap_detector + 3 tests | core/_stubs/gap_detector.py, tests/test_gap_*.py | 🔴 Critique | Bloque migration Phase 1 | Moyen |
| M-03 | 1.1 | Supprimer engulfing_detector + 4 tests | core/_stubs/engulfing_detector.py, tests/test_engulfing_*.py | 🔴 Critique | Bloque migration Phase 1 | Moyen |
| M-04 | 1.2 | Nettoyer 6 constantes FCR obsolètes | config/constants.py:~111-141 | 🟠 Majeur | Divergence config/code | Faible |
| M-05 | 1.3 | Nettoyer 12 clés YAML FCR | config.yaml:structure,volatility,engulfing | 🟠 Majeur | Divergence config/code | Faible |
| M-06 | 1.4 | Réécrire signal_pipeline.py entièrement | engine/signal_pipeline.py:1-120 | 🔴 Critique | Cœur du pipeline | Élevé |
| M-07 | 1.4 | Adapter CoreModules + strategy.py | engine/strategy.py:68-70,225-258 | 🔴 Critique | Orchestrateur live | Élevé |
| M-08 | 2.3 | Ajouter TF_H4/TF_D1 dans data_feed | engine/data_feed.py:239 | 🟡 Mineur | Daily fetch non documenté | Faible |
| M-09 | 2.2 | Ajouter carry overnight dans backtest_simulation | engine/backtest_simulation.py | 🟠 Majeur | Biais coûts backtest | Modéré |
| M-10 | 3.2 | Adapter regime_filter pour barres Daily | engine/regime_filter.py:43 | 🟡 Mineur | Gate optionnel Phase 6 | Faible |
| M-11 | 4.1 | Créer momentum_detector.pyx | core/momentum_detector.pyx (à créer) | 🔴 Critique | Signal principal manquant | Élevé |
| M-12 | 4.2 | Créer carry_signal.py | engine/carry_signal.py (à créer) | 🟠 Majeur | Biais directionnel manquant | Modéré |
| M-13 | 5.1 | Supprimer 11 fichiers test FCR directs | tests/test_fcr_*.py, test_gap_*.py, test_engulfing_*.py | 🔴 Critique | QA coverage invalide post-migration | Moyen |
| M-14 | 5.2 | Adapter 15 fichiers test mock CoreModules | tests/test_daily_*.py, test_fill_*.py, etc. | 🟠 Majeur | Régressions QA | Élevé |
| M-15 | 5.3 | Créer 7 nouveaux tests momentum/carry | tests/test_momentum_*.py, test_carry_*.py | 🟠 Majeur | Coverage nouveau core | Modéré |

**Total :** 🔴 6 Critiques · 🟠 6 Majeurs · 🟡 3 Mineurs

**Ordre d'exécution impératif :** Phase 1 → Phase 2 → Phase 3 (`make build`) → Phase 4 → Phase 5 → Phase 6
