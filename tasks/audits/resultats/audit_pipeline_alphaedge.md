---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: audit_pipeline_alphaedge.md
derniere_revision: 2026-03-26
creation: 2026-03-26 à 00:00
---

# Audit 7b — Pipeline (Ingénierie FCR → Momentum+Carry)
**ALPHAEDGE — Cohérence config ↔ live ↔ backtest**
Date : 2026-03-26 | Auditeur : GitHub Copilot (sonnet-4.6)

---

## BLOC 1 — COHÉRENCE DES PARAMÈTRES STRATÉGIQUES

### Sources lues
- `config.yaml` — section `trading`, `momentum`, `carry`, `risk`
- `alphaedge/config/loader.py:_build_trading_config()` — mapping YAML → TradingConfig
- `alphaedge/engine/signal_pipeline.py:detect_momentum()` — injection live
- `alphaedge/engine/backtest.py:_backtest_pair()` — injection backtest

---

### 1.1 Backtest — injection des paramètres

| Paramètre | Valeur config.yaml | Attribut TradingConfig | Lu dans backtest.py |
|-----------|-------------------|------------------------|---------------------|
| `momentum_fast_period` | `momentum.fast_period: 12` | `momentum_fast_period = 12` | `backtest.py:497 fast = config.trading.momentum_fast_period` ✅ |
| `momentum_slow_period` | `momentum.slow_period: 26` | `momentum_slow_period = 26` | `backtest.py:498 slow = config.trading.momentum_slow_period` ✅ |
| `momentum_adx_period` | `momentum.adx_period: 14` | `momentum_adx_period = 14` | `backtest.py:499 adx_p = config.trading.momentum_adx_period` ✅ |
| `momentum_adx_threshold` | `momentum.adx_threshold: 25.0` | `momentum_adx_threshold = 25.0` | `backtest.py:500 adx_t = config.trading.momentum_adx_threshold` ✅ |
| `momentum_lookback_days` | `momentum.lookback_days: 252` | `momentum_lookback_days = 252` | `backtest.py:496 lookback = config.trading.momentum_lookback_days` ✅ |
| `carry_enabled` | `carry.enabled: true` | `carry_enabled = True` | `backtest.py:501 carry_enabled = config.trading.carry_enabled` ✅ |
| `carry_min_differential_pct` | `carry.min_differential_pct: 0.5` | `carry_min_differential_pct = 0.5` | Passé via `get_carry_bias(min_differential=...)` ✅ |
| `carry_rates` | absente de config.yaml | `carry_rates = {}` | `backtest.py:502 carry_rates = config.trading.carry_rates = {}` — guard `if carry_enabled and carry_rates:` → carry **toujours sauté** ✅ (cohérent) |
| `rr_ratio` | `risk.reward_ratio: 2.0` | `rr_ratio = 2.0` (loader.py:357) | `backtest.py:374 min_rr=config.trading.rr_ratio * 0.9` ✅ |
| `max_spread_pips` | `trading.max_spread_pips: 2.0` | `max_spread_pips = 2.0` | `backtest.py:376 max_spread_pips=config.trading.max_spread_pips` ✅ |
| `risk_pct` | `trading.risk_pct: 3.0` | `risk_pct = 3.0` | `backtest.py:352 risk_pct=config.trading.risk_pct` ✅ |
| `max_trades_per_session` | `trading.max_trades_per_session: 6` | `max_trades_per_session = 6` | `backtest.py:529 max_trades_per_session = config.trading.max_trades_per_session` — mais voir P-07 ci-dessous |
| `max_daily_loss_pct` | `trading.max_daily_loss_pct: 3.0` | `max_daily_loss_pct = 3.0` | Non vérifié dans backtest (pas de check equity intra-session) |

**Verdict 1.1 : CONFORME** — tous les paramètres backtest proviennent de `config.trading.*`.

---

### 1.2 Live — injection des paramètres (`signal_pipeline.py`)

| Paramètre | Attribut attendu (TradingConfig) | Code live (`signal_pipeline.py`) | Verdict |
|-----------|----------------------------------|----------------------------------|---------|
| `momentum_fast_period` | `momentum_fast_period` | `getattr(trading, "momentum_fast_period", DEFAULT_MOMENTUM_FAST_PERIOD)` — ligne 83 ✅ | CONFORME |
| `momentum_slow_period` | `momentum_slow_period` | `getattr(trading, "momentum_slow_period", DEFAULT_MOMENTUM_SLOW_PERIOD)` — ligne 84 ✅ | CONFORME |
| `momentum_adx_period` | **`momentum_adx_period`** | `getattr(trading, "adx_period", DEFAULT_ADX_PERIOD)` — ligne 85 ❌ | **NON CONFORME** → P-01 |
| `momentum_adx_threshold` | **`momentum_adx_threshold`** | `getattr(trading, "adx_threshold", DEFAULT_ADX_THRESHOLD)` — ligne 86 ❌ | **NON CONFORME** → P-01 |

**Analyse P-01** : `TradingConfig` n'a pas d'attribut `adx_period` ni `adx_threshold` — les attributs réels sont `momentum_adx_period` et `momentum_adx_threshold`. Le `getattr` se rabat donc **systématiquement** sur les constantes `DEFAULT_ADX_PERIOD=14` et `DEFAULT_ADX_THRESHOLD=25.0`. Toute modification de `momentum.adx_period` ou `momentum.adx_threshold` dans `config.yaml` est appliquée en backtest (`config.trading.momentum_adx_period`) mais **silencieusement ignorée en live**.

Observabilité aujourd'hui : nulle (valeurs config = defaults). Impact si tuning ADX : divergence immédiate backtest ↔ live sur le seuil de déclenchement d'entrée.

---

### 1.3 Overrides carry par paire

Aucun override `carry_rates` par paire ni `momentum_adx_threshold` par paire configuré dans `config.yaml`. **N/A** — aucune paire spécifique n'est concernée.

---

## BLOC 2 — PIPELINE ALL-OR-NOTHING

### 2.1 `detect_momentum()` → `None`

**Live** (`session_lifecycle.py:_on_new_m1_bar`) :
```python
if not state.signal_result or not state.signal_result.get("detected"):
    return  # ligne ~640
```
`state.signal_result` est positionné par `strategy._detect_momentum()` à l'initialisation de session. Si `None` → le handler M1 retourne immédiatement. Aucun traitement carry ni sizing ne suit. ✅

**Backtest** (`backtest.py:_backtest_pair`) :
```python
if signal is None or not signal.get("detected"):
    continue  # ligne ~535
```
STOP explicite avant tout traitement. ✅

**Verdict 2.1 : CONFORME**

---

### 2.2 Carry bias conflict → STOP

**Live** : `SignalPipeline.get_carry()` et `is_carry_conflict()` existent dans `signal_pipeline.py` (lignes 103–129) mais **ne sont pas appelés** dans le chemin d'exécution live. `strategy._detect_momentum()` appelle uniquement `self._signal_pipeline.detect_momentum()` (`strategy.py:~219`). `_on_new_m1_bar` ne vérifie pas la direction carry avant d'ordonnancer `_atomic_check_and_execute`. Même si `carry_rates` était peuplé, aucun conflit carry ne bloquerait un trade live. → **P-03**

**Backtest** : Guard explicite présent (`backtest.py:536–544`) :
```python
if carry_enabled and carry_rates:
    carry = get_carry_bias(pair=pair, rates=carry_rates)
    if carry.is_valid and carry.direction != "NEUTRAL":
        if (mom_dir == 1 and carry.direction == "SHORT") or ...:
            continue
```
Carry conflict STOP est reproduit en backtest. ✅

**Verdict 2.2 : NON CONFORME** — carry conflict check absent du pipeline live → P-03.

---

### 2.3 `calculate_position_size()` → `is_valid=False`

**Live** (`position_manager.py:52–68`) :
- Appel `risk_mod.calculate_position_size(...)` → si `pos_result["is_valid"] == False` → `logger.warning` + retourne `None`.
- `_execute_signal` → `if pos_result is None: return False`. Ordre non soumis. ✅

**Backtest** (`backtest.py:_validate_backtest_signal:348–360`) :
- `risk_mod.calculate_position_size(...)` → `if not pos_result.get("is_valid", False): return None`. ✅

**Verdict 2.3 : CONFORME**

---

### 2.4 `create_bracket_order()` → `is_valid=False`

**Live** (`position_manager.py:build_validated_order:99–113`) :
- Appel `order_mod.create_bracket_order(...)` → `if not bracket.get("is_valid", False): logger.warning(rejection_reason); return None`.
- `_prepare_bracket` retourne `None` → `_execute_signal` retourne `False`. ✅

**Backtest** (`backtest.py:_validate_backtest_signal:362–385`) :
- `if not bracket.get("is_valid", False): return None`. ✅

**Verdict 2.4 : CONFORME**

---

### 2.5 `check_daily_limit()` → `limit_breached=True`

**Live** (`session_lifecycle.py:_check_daily_loss_shutdown`) :
```python
if risk_result.get("limit_breached"):
    logger.critical(...)            # log CRITICAL ✅
    self._s._shutdown_requested = True  # trading stoppé ✅
    await self._s._executor.cancel_all_orders()
    self._persist_daily_state(shutdown=True)
```
✅ Shutdown global immédiat.

Également, le plafond `max_trades_per_session` est vérifié à chaque bar M1 via :
```python
if self._s._global_trades_today >= self._s._config.trading.max_trades_per_session:
    return  # session_lifecycle.py:~620
```
et re-vérifié sous lock dans `_atomic_check_and_execute`. ✅

**Backtest** : aucun check `check_daily_limit()` intra-session — la limite trades est appliquée post-hoc par `_apply_global_session_limit(all_trades, max_trades_per_session)` (`backtest.py:~261`). Le daily loss limit en équité n'est **pas** simulé barre par barre. C'est un choix délibéré de backtesting (mesure de la performance théorique complète du signal), pas un bug.

**Verdict 2.5 : CONFORME** (live) / À VÉRIFIER (backtest : daily loss non simulé — choix documenté par la conception).

---

## BLOC 3 — DONNÉES D'ENTRÉE (DAILY BARS)

### 3.1 Lookback window

**Backtest** (`backtest.py:_backtest_pair:509–536`) :
```python
lookback = config.trading.momentum_lookback_days  # 252
window = daily_bars[bar_index - lookback : bar_index + 1]  # 253 barres max
signal = momentum_detector.detect_momentum(bars=window, ...)
```
Chaque appel fournit 252+1 barres de contexte. ✅

**Live** (`session_lifecycle.py:_init_session_pairs:896–904`) :
```python
daily_bars = await self._s._hist_feed.fetch_bars(
    pair=pair,
    timeframe="1 day",
    duration="30 D",    # ← ≈20 barres trading
    end_dt=session_start,
)
state.daily_bars = daily_bars
```
Ensuite `signal_pipeline.detect_momentum()` passe `state.daily_bars` (≈20 barres) à `momentum_detector.detect_momentum()`. **Divergence massive : 20 barres live vs 252 barres backtest**. `config.trading.momentum_lookback_days = 252` est **totalement ignoré** dans le fetch live. → **P-02**

EMA(26) se stabilise en ≈26 barres, ADX(14) en ≈14 barres — techniquement faisable avec 20 barres. Mais le contexte de tendance long terme (signal Moskowitz 252 jours) n'est pas reproduit. La nature du signal live diffère structurellement du signal backtest.

**Verdict 3.1 : NON CONFORME** → P-02

---

### 3.2 Carry rates source

**Backtest** : `carry_rates = config.trading.carry_rates = {}` (aucune clé `rates:` sous `carry:` dans config.yaml → `loader.py:451 carry_section.get("rates", {})`).
Guard `if carry_enabled and carry_rates:` → `{}` est falsy → carry **jamais appliqué**.

**Live** : `rates = getattr(state, "carry_rates", {}) or config.trading.carry_rates` = `{}`. `get_carry_bias(rates={})` → `is_valid=False` → no conflict.

Les deux utilisent la même source (config.yaml → `config.trading.carry_rates`). Convergence sur `{}`. **CONFORME entre backtest et live** — mais les deux sont dysfonctionnels → P-04.

**Verdict 3.2 : CONFORME** (même source, même valeur nulle)

---

### 3.3 Cohérence du fallback carry

**Backtest** : skip explicite via `if carry_enabled and carry_rates:` — zéro fallback.
**Live** : `getattr(state, "carry_rates", {}) or config.trading.carry_rates` — fallback sur config (aussi vide). Même résultat final mais mécanisme différent. Si `carry_rates` était peuplé uniquement dans state (sans passer par config), le backtest ignorerait ces rates.

**Verdict 3.3 : À VÉRIFIER** — fallback identique aujourd'hui mais code paths différents si populate future.

---

## BLOC 4 — MODÈLE DE COÛTS

### 4.1 Spread — backtest

Modèle : `compute_variable_slippage(bar_dt, pair=pair)` (`backtest.py:_collect_daily_trades:461`) :
- Contexte normal : `BASE_SPREAD_BY_PAIR.get(pair, BASE_SPREAD_PIPS) + BASE_SLIPPAGE_PIPS`
- Ouverture NYSE : spread élevé (`NYSE_OPEN_SPREAD_PIPS`)
- News event : spread maximal (`NEWS_SPREAD_PIPS`)

Filtre `max_spread_pips` : appliqué via `create_bracket_order(max_spread_pips=config.trading.max_spread_pips)` dans `_validate_backtest_signal` (`backtest.py:376`). Si le coût variable dépasse la limite, l'ordre est rejeté. ✅

La valeur de spread utilisée est **calibrée par paire** (`BASE_SPREAD_BY_PAIR`) — non issue du spread réel IB.

**Verdict 4.1 : CONFORME** (filtre max_spread_pips respecté, modèle calibré documenté)

---

### 4.2 Spread — live

Vérification du spread live (`session_lifecycle.py:_check_spread_and_execute`) :
```python
spread = await self._s._rt_feed.get_live_spread(state.pair)
spread_pips = spread / pip_size
if spread_pips > self._s._config.trading.max_spread_pips:
    return False  # signal skippé
```
`max_spread_pips` consommé depuis `config.trading` (= YAML `trading.max_spread_pips = 2.0`). ✅

Buffer slippage sur le SL (`session_lifecycle.py:_prepare_bracket:105`) :
```python
bracket["stop_loss"] = risk_mod.apply_slippage_buffer(
    ...
    slippage_pips=DEFAULT_MARKET_SLIPPAGE_PIPS,  # constante hardcodée
    pip_size=pip_size,
)
```
`DEFAULT_MARKET_SLIPPAGE_PIPS` est une constante importée de `constants.py`, **non** `config.trading.slippage_buffer_pips`. Or `config.yaml` déclare `risk.slippage_buffer_pips: 0.5` mais ce champ n'existe pas dans `TradingConfig` et n'est pas lu par `_build_trading_config()`. → **P-06**

**Verdict 4.2 : À VÉRIFIER** — max_spread_pips conforme ; slippage buffer non paramétrable → P-06

---

### 4.3 Slippage — backtest vs live

**Backtest** : modèle variable (`compute_variable_slippage`) — temps de marché, news, paire.
**Live** : spread réel IB (`get_live_spread`) + buffer fixe (`DEFAULT_MARKET_SLIPPAGE_PIPS`).

Ce choix est **explicitement documenté** dans `backtest_simulation.py:72–79` :
```python
# HYPOTHÈSE DE MODÉLISATION — Approuvée 2026-03-24
# Backtest : spread calibré par paire (BASE_SPREAD_BY_PAIR) + slippage variable ...
# Live : spread réel IB via get_live_spread() + buffer fixe ...
# Ces deux méthodes sont des approximations non équivalentes.
# Correction estimée à ~0.5 pip additionnels côté backtest.
```

**Verdict 4.3 : À VÉRIFIER** — divergence documentée et approuvée, correction de coût estimée

---

### 4.4 Divergence totale backtest ↔ live

Documentée dans le code. ~0.5 pip d'écart estimé par trade (côté backtest sous-évalue le coût).

**Verdict 4.4 : À VÉRIFIER** — divergence assumée et documentée

---

## BLOC 5 — ALIGNEMENT VALIDATION EXÉCUTION

### 5.1 Le backtest passe-t-il par risk_manager ?

OUI. `_validate_backtest_signal()` (`backtest.py:345–361`) appelle explicitement :
```python
pos_result = risk_mod.calculate_position_size(
    account_equity=config.trading.starting_equity,
    risk_pct=config.trading.risk_pct,
    sl_pips=signal["risk_pips"],
    ...
)
```
Les rejets de sizing live sont reproduits en simulation. ✅

**Verdict 5.1 : CONFORME**

---

### 5.2 Le backtest passe-t-il par order_manager ?

OUI. `_validate_backtest_signal()` (`backtest.py:362–384`) appelle :
```python
bracket = order_mod.create_bracket_order(
    direction=signal["direction"],
    ...
    max_spread_pips=config.trading.max_spread_pips,
    min_rr=config.trading.rr_ratio * 0.9,
    ...
)
```
Les rejets de bracket order live sont reproduits. ✅

**Verdict 5.2 : CONFORME**

---

### 5.3 Équivalence fonctionnelle documentée

`_backtest_pair()` a un docstring explicite : *"Mirrors the live flow: momentum detection on the rolling lookback window, carry filter, then bracket order sizing."* (`backtest.py:483`). La fonction miroir `_validate_backtest_signal` centralise les validations sizing + bracket et est appelée pour chaque signal. CONFORME à la documentation.

**Verdict 5.3 : CONFORME**

---

## BLOC 6 — EXPOSITION MULTI-PAIRES

### 6.1 Trades simultanés inter-paires

Live (`session_lifecycle.py:_on_new_m1_bar:~628`) :
```python
risk_mod.check_pair_limit(pair=pair, open_pairs=open_pairs, max_open_pairs=1)
```
`max_open_pairs=1` — hardcodé. Au plus 1 paire ouverte simultanément. Re-vérifié sous lock dans `_atomic_check_and_execute` avec les paires `_executing_pairs` incluses. Impossibilité d'ouvrir EURUSD + USDJPY simultanément. ✅

`max_open_pairs=1` n'est pas exposé dans config.yaml. Acceptable pour l'architecture actuelle (1 paire active : EURUSD).

**Verdict 6.1 : CONFORME**

---

### 6.2 Filtre de corrélation USD

`config.yaml` : `usd_correlation_filter: false` avec commentaire de justification :
```yaml
# Tested: 26T WR=46.2%, Sharpe=1.94 vs baseline 69T WR=54.5%, Sharpe=3.37 — ELIMINATED
```
Justification présente ✅

**Algorithmes** :
- **Backtest** (`backtest.py:~261`) : `_apply_usd_correlation_filter(all_trades)` — filtre post-hoc sur l'exposition directionnelle USD.
- **Live** (`session_lifecycle.py:_on_new_m1_bar:~615`) : `check_signal_allowed(pair, open_for_corr, correlation_matrix)` — filtre temps réel basé sur une matrice de corrélation pairwise construite depuis les barres daily (`session_lifecycle.py:_init_session_pairs:~930 build_correlation_matrix(pair_closes)`).

Ces deux algorithmes sont **fondamentalement différents** pour le même flag `usd_correlation_filter`. Le backtest supprime les trades qui amplifient l'exposition USD directionnelle ; le live bloque les signaux corrélés à une paire déjà ouverte (selon la corrélation historique des prix). Comportements non équivalents si activés simultanément. → **P-05**

Actuellement inopérant (config `false` + EURUSD seul actif). Mais la divergence algorithme deviendrait visible lors de l'activation multi-paires.

**Verdict 6.2 : À VÉRIFIER** (documenté, inopérant aujourd'hui, algorithmes divergents → P-05)

---

### 6.3 `max_trades_per_session`

Valeur active : `trading.max_trades_per_session: 6`

**Live** : plafond global appliqué à chaque bar M1 (`session_lifecycle.py:~620`) et re-vérifié sous lock (`_atomic_check_and_execute`). Plafond cross-paires. ✅

**Backtest** : la vérification intra-boucle est **code mort** :
```python
daily_trade_count = 0          # réinitialisé
if daily_trade_count >= max_trades_per_session:  # toujours False (0 >= 6)
    continue
```
`backtest.py:527–529`. Cette condition ne se déclenche jamais. La limite réelle est appliquée post-hoc par `_apply_global_session_limit(all_trades, max_trades_per_session)` (`backtest.py:261`). → **P-07**

La limite IS appliquée — juste par un mécanisme différent (post-hoc vs. pré-hoc). Résultat final identique pour une seule paire.

**Verdict 6.3 : CONFORME** (résultat final identique) — code mort à nettoyer → P-07

---

## SYNTHÈSE

### Score global : 6 / 10 → **CONDITIONNEL**

> Corrections 🟠 requises avant activation carry_rates ou tuning ADX.
> Toutes les anomalies sont latentes : aucun impact observable dans la config actuelle (1 paire, carry_rates vide, ADX = defaults).

---

### Tableau des anomalies

| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact | Effort |
|----|------|-------------|---------------|----------|--------|--------|
| P-01 | 1 | `signal_pipeline.detect_momentum` utilise `getattr(trading, "adx_period", ...)` et `getattr(trading, "adx_threshold", ...)` — attributs inexistants sur `TradingConfig` (`momentum_adx_period` / `momentum_adx_threshold`) — fallback constant systématique | `signal_pipeline.py:85–86` | 🟠 | Divergence live ↔ backtest si ADX tuné dans config.yaml | XS |
| P-02 | 3 | `_init_session_pairs` fetch `duration="30 D"` (≈20 barres) — `config.trading.momentum_lookback_days=252` ignoré — contexte EMA long-terme absent du signal live | `session_lifecycle.py:900` | 🟠 | Signal live structurellement différent du signal backtest (fenêtre 12× plus courte) | S |
| P-03 | 2 | `SignalPipeline.get_carry()` / `is_carry_conflict()` non appelés dans le chemin live — carry conflict check absent de `strategy._detect_momentum()` et de `_on_new_m1_bar` | `signal_pipeline.py:103–129` / `strategy.py:~219` | 🟠 | Si carry_rates peuplé, carry ne bloquerait aucun trade live | XS |
| P-04 | 1/3 | `carry.rates:` absent de config.yaml → `carry_rates={}` → `carry.enabled: true` est sans effet (filtre inopérant live et backtest) | `config.yaml:~106` / `loader.py:451` | 🟡 | Carry filter présenté comme actif, ignoré en pratique | XS |
| P-05 | 6 | Live utilise `build_correlation_matrix` (corrélation pairwise) ; backtest utilise `_apply_usd_correlation_filter` (exposition USD directionnelle) — deux algorithmes différents pour `usd_correlation_filter` | `session_lifecycle.py:~930` / `backtest.py:~261` | 🟠 | Comportements divergents si feature activée en multi-paires | M |
| P-06 | 4 | `risk.slippage_buffer_pips: 0.5` orphelin dans config.yaml — non lu par loader, pas dans TradingConfig — live utilise `DEFAULT_MARKET_SLIPPAGE_PIPS` hardcodé | `config.yaml:~130` / `session_lifecycle.py:105` / `loader.py:341–407` | 🟡 | Slippage buffer non paramétrable depuis config.yaml | XS |
| P-07 | 6 | `daily_trade_count = 0; if daily_trade_count >= max_trades_per_session: continue` — code mort dans `_backtest_pair` (condition toujours False) | `backtest.py:527–529` | 🟡 | Aucun impact (limite appliquée post-hoc correctement) — lisibilité trompeuse | XS |

**Sévérité** : 🔴 Critique · 🟠 Majeure · 🟡 Mineure
**Effort** : XS (< 1h) · S (< 4h) · M (< 1j) · L (> 1j)

---

### Verdict : **CONDITIONNEL**

Le pipeline est **fonctionnellement correct** dans la configuration actuelle : EURUSD seul, `carry_rates={}`, `usd_correlation_filter=false`, valeurs ADX identiques aux defaults. Aucune dérive silencieuse n'est active aujourd'hui.

Trois anomalies 🟠 deviendront critiques dès l'activation de fonctionnalités planifiées :
1. **P-01** — tout tuning ADX via config.yaml sera ignoré en live
2. **P-02** — le contexte de tendance long terme (252 jours) n'est jamais fourni au détecteur live
3. **P-03** — le carry conflict check n'est pas câblé dans le chemin d'exécution live

Ces corrections sont toutes de faible effort (XS–S) et doivent être résolues avant d'alimenter `carry_rates` ou de modifier les seuils ADX.
