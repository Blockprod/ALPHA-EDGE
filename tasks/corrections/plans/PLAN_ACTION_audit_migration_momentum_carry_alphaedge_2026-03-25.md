---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: PLAN_ACTION_audit_migration_momentum_carry_alphaedge_2026-03-25.md
derniere_revision: 2026-03-25
creation: 2026-03-25 à 14:00
---

# PLAN D'ACTION — ALPHAEDGE — 2026-03-25

**Sources :** `tasks/audits/resultats/audit_migration_momentum_carry_alphaedge.md`
**Total :** 🔴 6 Critiques · 🟠 6 Majeurs · 🟡 3 Mineurs · **Effort estimé : 3–4 jours**

> Pipeline tout-ou-rien. Ordre d'exécution impératif : Phase 1 → 2 → 3 → 4 → 5 → 6.
> Ne jamais passer d'une phase à la suivante si `make qa` ne passe pas.

---

## PHASE 1 — CRITIQUES 🔴

---

### [C-01] Désactiver fcr_detector dans core/__init__.py + supprimer le stub

**Fichiers :**
- `alphaedge/core/__init__.py` — Supprimer l'export de `fcr_detector`
- `alphaedge/core/_stubs/fcr_detector.py` — Supprimer le fichier (stub Python)

**Problème :** `fcr_detector` est un module FCR sans réutilisabilité dans la nouvelle stratégie Momentum+Carry. Son export dans `__init__.py` rend l'import valide, ce qui maintient des tests obsolètes en vie.

**Correction :**
1. Dans `alphaedge/core/__init__.py` : retirer l'import/export de `fcr_detector`
2. Supprimer `alphaedge/core/_stubs/fcr_detector.py`
3. Conserver les sources Cython `fcr_detector.pyx` et `fcr_detector.c` en archive (ne pas supprimer — référence historique)

**Validation :** `make qa` (tests directs fcr_detector doivent être supprimés en C-13 avant)
**Dépend de :** C-13 (suppression des 11 tests directs, à exécuter en même temps)
**Statut :** ⏳

---

### [C-02] Désactiver gap_detector dans core/__init__.py + supprimer le stub

**Fichiers :**
- `alphaedge/core/__init__.py` — Supprimer l'export de `gap_detector`
- `alphaedge/core/_stubs/gap_detector.py` — Supprimer le fichier

**Problème :** `gap_detector` est couplé à la détection de gap NYSE Open (intraday M1). Sans objet pour un swing Daily.

**Correction :**
1. Dans `alphaedge/core/__init__.py` : retirer l'import/export de `gap_detector`
2. Supprimer `alphaedge/core/_stubs/gap_detector.py`
3. Conserver `gap_detector.pyx` et `gap_detector.c` en archive

**Validation :** `make qa`
**Dépend de :** C-13
**Statut :** ⏳

---

### [C-03] Désactiver engulfing_detector dans core/__init__.py + supprimer le stub

**Fichiers :**
- `alphaedge/core/__init__.py` — Supprimer l'export de `engulfing_detector`
- `alphaedge/core/_stubs/engulfing_detector.py` — Supprimer le fichier

**Problème :** `engulfing_detector` est un pattern M1 (barre d'entrée FCR). Sans objet pour swing Daily.

**Correction :**
1. Dans `alphaedge/core/__init__.py` : retirer l'import/export de `engulfing_detector`
2. Supprimer `alphaedge/core/_stubs/engulfing_detector.py`
3. Conserver `engulfing_detector.pyx` et `engulfing_detector.c` en archive

**Validation :** `make qa`
**Dépend de :** C-13
**Statut :** ⏳

---

### [C-13] Supprimer 11 fichiers test FCR/gap/engulfing (imports directs)

**Fichiers à supprimer :**
```
alphaedge/tests/test_fcr_detector_detect.py
alphaedge/tests/test_fcr_detector_jpy.py
alphaedge/tests/test_fcr_detector_scan.py
alphaedge/tests/test_gap_detector_empty.py
alphaedge/tests/test_gap_detector_spike.py
alphaedge/tests/test_gap_detector_zone.py
alphaedge/tests/test_engulfing_detector_bullish.py
alphaedge/tests/test_engulfing_detector_bearish.py
alphaedge/tests/test_engulfing_detector_quality.py
alphaedge/tests/test_engulfing_detector_volume.py
alphaedge/tests/test_signal_pipeline.py
```

**Problème :** Ces 11 fichiers importent directement les modules FCR/gap/engulfing. Après suppression des stubs (C-01, C-02, C-03), ils provoqueront des `ImportError` fatals. `test_signal_pipeline.py` doit également être supprimé — il sera réécrit en C-06 avec les nouveaux scenarios momentum/carry.

**Correction :**
1. Supprimer les 11 fichiers listés ci-dessus
2. Note : `test_signal_pipeline.py` sera recréé depuis zéro dans C-06

**Validation :** `make qa` — le compte de tests doit baisser de ~N (tests supprimés)
**Dépend de :** Aucune (à exécuter EN MÊME TEMPS que C-01, C-02, C-03)
**Statut :** ⏳

---

### [C-06] Réécrire signal_pipeline.py — nouveau pipeline Momentum + Carry

**Fichier :** `alphaedge/engine/signal_pipeline.py:1-120`

**Problème :** La classe `SignalPipeline` actuelle (120 lignes) est entièrement structurée autour de 3 méthodes FCR/gap/engulfing. Elle doit être réécrite pour le nouveau pipeline séquencé.

**Correction :** Réécrire `signal_pipeline.py` avec le pipeline suivant :
```
Étape 1 → momentum_detector.detect_momentum(daily_bars)
              → dict | None — STOP si None (ADX < threshold)

Étape 2 → carry_signal.get_carry_bias(pair, rates)
              → CarrySignal — STOP si contradiction momentum/carry

Étape 3 → regime_filter.predict(today, daily_bars[-20:])  [OPTIONNEL]
              → "high_vol" | "low_vol" — STOP si "low_vol"

Étape 4 → risk_manager.calculate_position_size()          [CONSERVÉ]
Étape 5 → order_manager.create_bracket_order()            [CONSERVÉ]
```

Puis réécrire `test_signal_pipeline.py` avec les scenarios :
- `test_momentum_stop_adx_below_threshold` — ADX < 25 → None → pipeline STOP
- `test_carry_contradiction_blocks_entry` — momentum LONG / carry SHORT → STOP
- `test_full_pipeline_long_signal` — ADX ≥ 25 + carry LONG → ordre créé
- `test_full_pipeline_short_signal` — ADX ≥ 25 + carry SHORT → ordre créé

**Validation :** `make qa`
**Dépend de :** C-01, C-02, C-03, C-13, C-11 (momentum_detector), C-12 (carry_signal)
**Statut :** ⏳

---

### [C-07] Adapter CoreModules + strategy.py — remplacer les 3 détecteurs FCR

**Fichier :** `alphaedge/engine/strategy.py:68-70, 89-91, 109, 127, 225-258`

**Problème :** `CoreModules` (dataclass ou namedtuple, ligne ~68) contient les champs `fcr_detector`, `gap_detector`, `engulfing_detector`. `_import_core_modules()` importe ces 3 modules. Les méthodes `_detect_fcr()`, `_detect_gap()`, `_detect_engulfing()` (lignes 225-258) orchestrent le pipeline FCR. La classe s'appelle `FCRStrategy` (ligne 127).

**Correction :**
1. `CoreModules` : remplacer `fcr_detector`, `gap_detector`, `engulfing_detector` par `momentum_detector`
2. `_import_core_modules()` : importer uniquement `momentum_detector` depuis `alphaedge.core`
3. Remplacer `_detect_fcr()`, `_detect_gap()`, `_detect_engulfing()` par `_detect_momentum()`, `_get_carry_bias()`
4. Renommer `FCRStrategy` → `SwingStrategy`
5. `strategy.py:234-237` : adapter l'appel `regime_filter.predict()` pour barres Daily (après C-10)

**Validation :** `make qa`
**Dépend de :** C-01, C-02, C-03, C-11, C-12, C-14 (mocks à adapter)
**Statut :** ⏳

---

### [C-11] Créer momentum_detector.pyx + stub Python + 4 tests

> ⚠️ `make build` requis après création de ce module

**Fichiers à créer :**
- `alphaedge/core/momentum_detector.pyx`
- `alphaedge/core/_stubs/momentum_detector.py`
- `alphaedge/tests/test_momentum_detector_bull_trend.py`
- `alphaedge/tests/test_momentum_detector_bear_trend.py`
- `alphaedge/tests/test_momentum_detector_no_trend.py`
- `alphaedge/tests/test_momentum_detector_insufficient.py`

**Fichiers à modifier :**
- `alphaedge/core/__init__.py` — exporter `momentum_detector`
- `setup.py` — enregistrer l'Extension Cython

**Problème :** Le signal principal de la nouvelle stratégie est absent. Sans `momentum_detector`, le pipeline ne peut pas fonctionner.

**Interface publique :**
```python
def detect_momentum(
    bars: list[dict[str, Any]],  # barres Daily ou H4, ordre chronologique
    fast_period: int,             # ex: 12
    slow_period: int,             # ex: 26
    adx_period: int,              # ex: 14
    adx_threshold: float,         # ex: 25.0
) -> dict[str, Any] | None:
    # Retourne None si ADX < adx_threshold (→ STOP pipeline)
    # Sinon: {"detected": True, "direction": 1|-1, "strength": float,
    #          "ema_fast": float, "ema_slow": float, "adx": float, "timestamp": int}
```

**Scénarios de test :**
- `test_momentum_detector_bull_trend.py` : ADX ≥ 25, EMA fast > slow → `direction == 1`
- `test_momentum_detector_bear_trend.py` : ADX ≥ 25, EMA fast < slow → `direction == -1`
- `test_momentum_detector_no_trend.py` : ADX < 25 → `None`
- `test_momentum_detector_insufficient.py` : `len(bars) < slow_period` → `None`

**Validation :** `make build` → `make qa` — coverage `core/momentum_detector` ≥ 80%
**Dépend de :** C-08 (TF_D1 dans constants — fournit le nom du timeframe)
**Statut :** ⏳

---

## PHASE 2 — MAJEURES 🟠

---

### [C-04] Nettoyer 6 constantes FCR obsolètes dans constants.py

**Fichier :** `alphaedge/config/constants.py:~111-141`

**Problème :** 6 constantes FCR polluent `constants.py` et seront des références mortes après migration.

**Constantes à supprimer :**
| Constante | Ligne (≈) | Raison |
|-----------|-----------|--------|
| `DEFAULT_MIN_RANGE_PIPS` | ~131 | Seuil FCR range — sans objet |
| `DEFAULT_FCR_LOOKBACK` | ~133 | Lookback FCR — sans objet |
| `DEFAULT_MIN_ATR_RATIO` | ~112 | Gate gap detector — sans objet |
| `DEFAULT_GAP_TOLERANCE_PIPS` | ~114 | Zone gap — sans objet |
| `DEFAULT_MIN_BODY_RATIO` | ~139 | Qualité engulfing — sans objet |
| `DEFAULT_MAX_WICK_RATIO` | ~141 | Qualité engulfing — sans objet |

**Nouvelles constantes à ajouter :**
```python
DEFAULT_MOMENTUM_FAST_PERIOD: int = 12     # EMA rapide (Moskowitz 2012)
DEFAULT_MOMENTUM_SLOW_PERIOD: int = 26     # EMA lente
DEFAULT_ADX_PERIOD: int = 14               # Période ADX
DEFAULT_ADX_THRESHOLD: float = 25.0        # Gate minimum tendance
DEFAULT_CARRY_MIN_DIFFERENTIAL: float = 0.5  # Différentiel carry minimum (%)
DEFAULT_MOMENTUM_LOOKBACK_DAYS: int = 252   # Fenêtre historique (1 an)
```

**Validation :** `make qa`
**Dépend de :** C-01, C-02, C-03 (modules supprimés avant de nettoyer leurs constantes)
**Statut :** ⏳

---

### [C-05] Nettoyer 12 clés YAML FCR dans config.yaml

**Fichier :** `config.yaml`

**Problème :** 12 clés YAML référencent des paramètres FCR/gap/engulfing devenus obsolètes. Des clés doivent être renommées pour la nouvelle stratégie.

**Clés à supprimer :**
```yaml
structure.min_range_pips
structure.lookback_candles
structure.fcr_timeframe
structure.entry_timeframe
structure.fcr_range_cv_max
volatility.min_atr_ratio
volatility.tolerance_pips
volatility.min_atr_ratio_by_pair
engulfing.min_body_ratio
engulfing.max_wick_ratio
trading.london_open_enabled
pair_sessions  # bloc complet
```

**Nouvelles clés à ajouter :**
```yaml
signal_timeframe: "1 day"
confirmation_timeframe: "4 hours"
momentum:
  fast_period: 12
  slow_period: 26
  adx_period: 14
  adx_threshold: 25.0
  lookback_days: 252
carry:
  min_differential_pct: 0.5
  enabled: true
monitoring_window_start: "08:00"
monitoring_window_end: "18:00"
```

**Validation :** `make qa`
**Dépend de :** C-04
**Statut :** ⏳

---

### [C-09] Ajouter compute_overnight_carry() dans backtest_simulation.py

**Fichier :** `alphaedge/engine/backtest_simulation.py`

**Problème :** Le modèle de coûts actuel ne prend pas en compte le carry overnight (swap points IB). Pour un swing Daily, les positions sont maintenues plusieurs jours — omettre le carry introduit un biais systématique sur les performances backtest.

**Correction :** Ajouter la fonction suivante :
```python
def compute_overnight_carry(
    pair: str,
    direction: int,          # 1 = LONG, -1 = SHORT
    days_held: int,
    rates: dict[str, float], # taux annualisés par devise {currency: rate_pct}
    lot_size: float,
    pip_size: float,
) -> float:
    """Retourne le carry total en pips sur la période (positif = gain, négatif = coût)."""
    ...
```

Intégrer l'appel dans `_simulate_trade()` ou l'équivalent — additionner `compute_overnight_carry()` au P&L de chaque trade.

**Validation :** `make qa`
**Dépend de :** C-05 (config carry chargé depuis config.yaml)
**Statut :** ⏳

---

### [C-12] Créer carry_signal.py + 3 tests

**Fichiers à créer :**
- `alphaedge/engine/carry_signal.py`
- `alphaedge/tests/test_carry_signal_audjpy.py`
- `alphaedge/tests/test_carry_signal_neutral.py`
- `alphaedge/tests/test_carry_signal_unknown_pair.py`

**Problème :** Le biais directionnel Carry (Lustig 2011) est absent. Sans lui, le signal momentum n'a pas de filtre confirmatoire.

**Interface publique :**
```python
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class CarrySignal:
    differential: float                          # base_rate - quote_rate (annualisé, %)
    direction: Literal["LONG", "SHORT", "NEUTRAL"]
    daily_carry_pips: float                      # carry estimé par jour calendaire
    is_valid: bool

def get_carry_bias(
    pair: str,
    rates: dict[str, float],  # {"AUD": 4.35, "JPY": 0.10, "EUR": 3.65, ...}
) -> CarrySignal:
    ...
```

**Logique :**
- `direction = "LONG"` si `differential > DEFAULT_CARRY_MIN_DIFFERENTIAL`
- `direction = "SHORT"` si `differential < -DEFAULT_CARRY_MIN_DIFFERENTIAL`
- `direction = "NEUTRAL"` sinon
- `is_valid = False` si la paire n'est pas reconnue ou si un taux manque

**Scénarios de test :**
- `test_carry_signal_audjpy.py` : AUD 4.35%, JPY 0.10% → `direction="LONG"`, `differential≈4.25`
- `test_carry_signal_neutral.py` : différentiel < 0.5% → `direction="NEUTRAL"`
- `test_carry_signal_unknown_pair.py` : paire non dans `rates` → `is_valid=False`

**Validation :** `make qa`
**Dépend de :** C-04 (DEFAULT_CARRY_MIN_DIFFERENTIAL dans constants.py)
**Statut :** ⏳

---

### [C-14] Adapter 15 fichiers test — mock CoreModules

**Fichiers à modifier :**
```
alphaedge/tests/test_daily_state_persistence.py      lignes 54-56
alphaedge/tests/test_daily_loss_logging.py           lignes 33-35
alphaedge/tests/test_dependency_injection.py         lignes 27-29
alphaedge/tests/test_fill_verification.py            lignes 105-107, 296, 301, 305
alphaedge/tests/test_graceful_shutdown.py            lignes 47-49
alphaedge/tests/test_race_condition_multi_pair.py    lignes 64-66
alphaedge/tests/test_risk_check_interval.py          lignes 48-50
alphaedge/tests/test_spread_error_blocks_trade.py    lignes 67-69
alphaedge/tests/test_reconnect.py                    lignes 55-57, 84-86
alphaedge/tests/test_slippage_integration.py         lignes 48-50
alphaedge/tests/test_spread_monitor.py               lignes 47-49
alphaedge/tests/test_strategy_p2_04.py               lignes 180, 222, 271, 313, 319, 346
alphaedge/tests/test_strategy_p2_05.py               lignes 45-47, 165, 204
alphaedge/tests/test_backtest_news_filter.py         lignes 109-111, 122-124
alphaedge/tests/test_core_backend_visibility.py      lignes 69-71
```

**Problème :** Ces 15 fichiers construisent un `MagicMock` de `CoreModules` avec les champs `fcr_detector`, `gap_detector`, `engulfing_detector`. Après C-07 (`CoreModules` reconfiguré), ces mocks ne correspondront plus à la structure réelle.

**Correction :** Dans chaque fichier, remplacer :
```python
# Avant (pattern typique)
modules = MagicMock()
modules.fcr_detector = MagicMock()
modules.gap_detector = MagicMock()
modules.engulfing_detector = MagicMock()
```
par :
```python
# Après
modules = MagicMock()
modules.momentum_detector = MagicMock()
```

Adapter aussi les assertions qui référencent `.detect_fcr()`, `.detect_gap()`, `.detect_engulfing()` → `.detect_momentum()`.

**Validation :** `make qa`
**Dépend de :** C-07 (CoreModules adapté)
**Statut :** ⏳

---

### [C-15] Créer 7 nouveaux tests momentum/carry (coverage core/)

**Fichiers à créer :**
```
alphaedge/tests/test_momentum_detector_bull_trend.py      [voir C-11]
alphaedge/tests/test_momentum_detector_bear_trend.py      [voir C-11]
alphaedge/tests/test_momentum_detector_no_trend.py        [voir C-11]
alphaedge/tests/test_momentum_detector_insufficient.py    [voir C-11]
alphaedge/tests/test_carry_signal_audjpy.py               [voir C-12]
alphaedge/tests/test_carry_signal_neutral.py              [voir C-12]
alphaedge/tests/test_carry_signal_unknown_pair.py         [voir C-12]
```

**Note :** Ces 7 fichiers sont déjà spécifiés dans C-11 (4 tests momentum) et C-12 (3 tests carry). Cette correction consolide le suivi de la couverture `core/`.

**Objectif coverage :**
- `core/momentum_detector` (via stub) : ≥ 80%
- `engine/carry_signal.py` : ≥ 70% (dans `engine/`, exclu du threshold officiel mais recommandé)

**Validation :** `make qa` — vérifier le rapport coverage
**Dépend de :** C-11, C-12
**Statut :** ⏳

---

## PHASE 3 — MINEURES 🟡

---

### [C-08] Ajouter TF_H4 et TF_D1 dans constants.py + _chunk_days_for_timeframe

**Fichiers :**
- `alphaedge/config/constants.py:~54-56` — Ajouter `TF_H4` et `TF_D1`
- `alphaedge/engine/data_feed.py:239` — Documenter `"1 day"` dans `_chunk_days_for_timeframe()`

**Problème :** Les timeframes Daily et H4 existent implicitement (`_chunk_days_for_timeframe` retourne 365 pour tout timeframe inconnu), mais ne sont pas documentés comme constantes nommées. Référencer `"1 day"` en dur dans le code est fragile.

**Correction :**
```python
# Dans constants.py, après TF_M5
TF_M1: str = "1 min"    # existant
TF_M5: str = "5 mins"   # existant
TF_H4: str = "4 hours"  # NOUVEAU
TF_D1: str = "1 day"    # NOUVEAU
```

Dans `_chunk_days_for_timeframe()` (data_feed.py:239) : ajouter les cas explicites pour `TF_H4` (30 jours) et `TF_D1` (365 jours) au lieu du fallback implicite.

**Validation :** `make qa`
**Dépend de :** Aucune
**Statut :** ⏳

---

### [C-10] Adapter regime_filter.py pour barres Daily

**Fichier :** `alphaedge/engine/regime_filter.py:43`

**Problème :** `_extract_daily_features()` (ligne 43) attend des barres M5 (`pre_session_m5`). Incompatible avec le pipeline swing qui fournit des barres Daily.

**Correction :** Modifier uniquement `_extract_daily_features()` pour accepter des barres Daily en input. Les 3 features (`atr_daily`, `intraday_range`, `momentum`) restent les mêmes — elles sont pertinentes sur Daily. Ne pas modifier `predict()` ni `fit()`.

Adapter aussi `fit()` ligne 96 : le paramètre `m5_bars_history` → `daily_bars_history` (renommage + docstring).

Mettre à jour `strategy.py:234-237` : l'appel `regime_filter.predict()` doit passer des barres Daily (`daily_bars[-20:]`) au lieu de `pre_session_m5`.

**Validation :** `make qa` — Relancer les tests DST edge case si `session_manager.py` est impacté (attention : règle projet — ne pas toucher `session_manager.py` sans relancer les tests DST)
**Dépend de :** C-07 (strategy.py adapté)
**Statut :** ⏳

---

## SÉQUENCE D'EXÉCUTION

```
PHASE 1 (Nettoyage FCR) — à exécuter en bloc atomique :
  C-13 → C-01 + C-02 + C-03    [supprimer tests, puis stubs]
  make qa  ← baseline réduite (N − 11 tests)

PHASE 2 (Data constants) :
  C-08                           [TF_H4 / TF_D1 — sans dépendance]
  make qa

PHASE 3 (Nouveau signal Cython) :
  C-11                           [momentum_detector.pyx + stub + 4 tests]
  make build → make qa           ← ⚠️ make build requis

PHASE 4 (Carry + config) :
  C-04 → C-12                   [constants.py, puis carry_signal.py + 3 tests]
  C-05                           [config.yaml — après C-04]
  make qa

PHASE 5 (Pipeline + orchestration + QA) :
  C-06 → C-07 → C-14 → C-15    [signal_pipeline, strategy, mocks, coverage]
  C-09                           [backtest_simulation carry overnight]
  C-10                           [regime_filter Daily — après C-07]
  make qa  ← baseline complète (N + 7 − 11 tests)

PHASE 6 (Backtest validation) :
  Adapter _backtest_pair() dans backtest.py (hors plan — validation terrain)
  Adapter backtest_filters.py:55-57 (fallback swing)
  Lancer walk-forward Daily
  Seuil GO : Sharpe OOS ≥ 0.8, N ≥ 50 trades
```

---

## CRITÈRES PASSAGE EN PRODUCTION

| Critère | Seuil | Instrument de vérification |
|---------|-------|---------------------------|
| Zéro correction 🔴 ouverte | 0 | Tableau de suivi ci-dessous |
| `make qa` — lint + mypy | 0 erreur | `make qa` |
| `make qa` — pytest | 100% pass | `make qa` |
| Coverage `config/`, `utils/`, `core/` | ≥ 80% | `make qa` coverage report |
| `ALPHAEDGE_PAPER=true` intact | Obligatoire | `.env.example` + `make qa` |
| Paper trading validé | ≥ 5 sessions | Journal de trading |
| Walk-forward OOS Sharpe | ≥ 0.8 | `run_walk_forward()` |
| Walk-forward N trades OOS | ≥ 50 | `BacktestStats.n_trades` |

---

## TABLEAU DE SUIVI

| ID | Phase | Sévérité | Description courte | Dépend de | Statut |
|----|-------|----------|--------------------|-----------|--------|
| C-01 | 1 | 🔴 | Désactiver fcr_detector core | C-13 | ✅ |
| C-02 | 1 | 🔴 | Désactiver gap_detector core | C-13 | ✅ |
| C-03 | 1 | 🔴 | Désactiver engulfing_detector core | C-13 | ✅ |
| C-04 | 2 | 🟠 | Nettoyer constants.py FCR | C-01, C-02, C-03 | ✅ |
| C-05 | 2 | 🟠 | Nettoyer config.yaml FCR | C-04 | ✅ |
| C-06 | 1 | 🔴 | Réécrire signal_pipeline.py | C-01…C-03, C-11, C-12 | ✅ |
| C-07 | 1 | 🔴 | Adapter CoreModules + strategy.py | C-01…C-03, C-11, C-12, C-14 | ✅ |
| C-08 | 3 | 🟡 | Ajouter TF_H4/TF_D1 | Aucune | ✅ |
| C-09 | 2 | 🟠 | carry overnight backtest_simulation | C-05 | ✅ |
| C-10 | 3 | 🟡 | Adapter regime_filter Daily | C-07 | ✅ |
| C-11 | 1 | 🔴 | Créer momentum_detector.pyx | C-08 | ✅ |
| C-12 | 2 | 🟠 | Créer carry_signal.py | C-04 | ✅ |
| C-13 | 1 | 🔴 | Supprimer 11 tests FCR directs | Aucune | ✅ |
| C-14 | 2 | 🟠 | Adapter 15 mocks CoreModules | C-07 | ✅ |
| C-15 | 2 | 🟠 | Créer 7 tests momentum/carry | C-11, C-12 | ✅ |
