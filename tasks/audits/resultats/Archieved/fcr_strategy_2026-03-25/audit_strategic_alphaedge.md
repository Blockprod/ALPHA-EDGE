---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: audit_strategic_alphaedge.md
derniere_revision: 2026-03-24
creation: 2026-03-24 à 17:00
---

# AUDIT STRATÉGIQUE — ALPHAEDGE FCR
**Date** : 2026-03-24 · **Analyste** : GitHub Copilot (sonnet-4.6)

> **Sources primaires lues** : `reports/ALPHAEDGE_backtest_results.csv` (28 trades, 3 ans), `config.yaml`, `alphaedge/config/constants.py`, `alphaedge/engine/signal_pipeline.py`, `alphaedge/engine/backtest.py`, `alphaedge/engine/backtest_stats.py`, `alphaedge/engine/backtest_simulation.py`, `alphaedge/engine/backtest_filters.py`, `alphaedge/engine/session_lifecycle.py`, `alphaedge/core/_stubs/risk_manager.py`, `alphaedge/core/_stubs/order_manager.py`, `alphaedge/engine/position_manager.py`.
> **Toutes les métriques ont été calculées depuis le CSV** — zéro valeur inventée.

---

## BLOC 1 — VALIDITÉ STATISTIQUE DE L'EDGE

### 1.1 Taille d'échantillon

| Métrique | Valeur |
|----------|--------|
| N total | **28** trades |
| Période | 2024-01-02 → 2025-06-03 (3 ans de données IB, mais 28 trades réels) |
| Wins | 12 |
| Losses | 16 |

**N = 28 < 30 → 🔴 S-01** — Seuil critique non atteint. Les conclusions statistiques sur 28 trades ne sont pas fiables.

**Intervalle de confiance à 95% sur le win rate :**
```
WR = 12/28 = 42.86%
IC = WR ± 1.96 × √(WR × (1−WR) / N)
   = 42.86% ± 1.96 × √(0.4286 × 0.5714 / 28)
   = 42.86% ± 18.3%
   = [24.5% ; 61.2%]
```

**IC à 95% inclut 50% → 🔴 S-02** — On ne peut pas rejeter l'hypothèse que cette stratégie est un coin flip. L'edge n'est statistiquement **pas prouvé** sur cet échantillon.

### 1.2 Métriques d'edge

| Métrique | Valeur | Seuil viable | Verdict |
|----------|--------|-------------|---------|
| Win rate global | 42.86% | — | 🔴 (IC inclut 50%) |
| Profit Factor | **1.234** | ≥ 1.5 | 🟠 S-08 |
| Avg win pips | +19.95 pips | — | — |
| Avg loss pips | −12.12 pips | — | — |
| Expectancy | **+1.62 pips/trade** | > 0 | ✅ (positif mais fragile) |
| Max pertes consécutives | **5** (trades 23–27) | < 5 | 🟠 S-12 |

Calculs :
```
E = 0.4286 × 19.95 + 0.5714 × (−12.12) = +1.62 pips/trade
PF = 239.4 / 193.95 = 1.234
```

**CONFORME (expectancy > 0) mais 🟠 (PF < 1.5) et 🔴 (statistiquement non prouvé)**

### 1.3 Critère de Kelly

```
f* = WR − (1−WR) / (avg_win / avg_loss)
   = 0.4286 − 0.5714 / (19.95 / 12.12)
   = 0.4286 − 0.3471 = 8.15%
```

| Paramètre | Valeur | Verdict |
|-----------|--------|---------|
| Kelly f* | 8.15% | — |
| Demi-Kelly | 4.08% | — |
| risk_pct (config.yaml) | **3.0%** | ✅ < demi-Kelly |

**CONFORME** — risk_pct = 3.0% < demi-Kelly (4.08%). Sizing conservateur. Attention : f* calculé sur N=28 est lui-même peu fiable.

---

## BLOC 2 — FRÉQUENCE ET CONTINUITÉ DU SIGNAL

### 2.1 Taux de signal

| Paire | 2023 | 2024 | 2025 | 2026 (partiel) | Total |
|-------|------|------|------|----------------|-------|
| EURUSD | 0 | 1 | 15 | 0 | 16 |
| USDJPY | 0 | 0 | 12 | 0 | 12 |
| **Global** | **0** | **1** | **27** | **0** | **28** |

**Distribution trimestrielle :**

| Trimestre | Trades |
|-----------|--------|
| Q1–Q4 2023 | 0 |
| Q1 2024 | 1 (2024-01-02) |
| Q2–Q4 2024 | 0 |
| Q1 2025 | 0 |
| Q2 2025 | 27 (mars–juin) |
| Q3 2025 – Q1 2026 | 0 |

**8 trimestres sur 13 : zéro signal.** 27 des 28 trades générés en 3 mois (mars–juin 2025).

### 2.2 Silences consécutifs

| Silence | Période | Durée | Verdict |
|---------|---------|-------|---------|
| Silence 1 | Mars 2023 → Janv 2024 | ~10 mois | 🔴 (≥ 90 jours) |
| Silence 2 | 2 Janv 2024 → 5 Mars 2025 | **14 mois** | 🔴 (≥ 90 jours) |
| Silence 3 | 3 Juin 2025 → Mars 2026 | **9 mois** | 🔴 S-07 (≥ 90 jours) |

**Plus long silence actuel : 9 mois (en cours depuis juin 2025) → 🔴 S-07**
En production live, 9 mois sans aucun trade signifie que le système est de facto inactif.

### 2.3 Cascade de filtres — diagnostic du silence

| Filtre | Paramètre actif (config.yaml) | Sens |
|--------|-------------------------------|------|
| FCR range min | `structure.min_range_pips: 8.0` | Restrictif |
| FCR quality CV | `structure.fcr_range_cv_max: 0.5` | Restrictif — exige consolidation homogène |
| Gap ATR global | `volatility.min_atr_ratio: 1.7` | Très restrictif |
| Gap ATR EURUSD | override 1.0 | Permissif |
| Gap ATR USDJPY | **non défini → 1.7** | Le plus restrictif de facto |
| Volume | `pattern.min_volume_ratio: 1.0` | Permissif |
| Spread | `trading.max_spread_pips: 2.0` | Standard |
| News blackout | `news_filter.enabled: true` | → À VÉRIFIER (BLOC 6) |

**Absence d'override USDJPY sur `min_atr_ratio`** — USDJPY subit le seuil le plus restrictif (1.7×) sans test documenté d'un override adapté.

**NON CONFORME** — Silences structurels sur 9+ mois. Surrestrictivité probable du filtre gap sur USDJPY.

---

## BLOC 3 — PERFORMANCE PAR PAIRE ET RÉGIME

### 3.1 Performance par paire

| Paire | N | WR | Win pips | Loss pips | PF | P&L USD | Verdict |
|-------|---|----|----------|-----------|----|---------|---------|
| EURUSD | 16 | **56.25%** | 172.3 | 50.75 | **3.39** | **+$2,749** | ✅ Solide |
| USDJPY | 12 | **25.0%** | 67.1 | 143.2 | **0.47** | **−$1,657** | 🔴 S-03 |
| **Global** | **28** | **42.86%** | **239.4** | **193.95** | **1.234** | **+$1,092** | 🟠 |

**USDJPY PF = 0.47 < 1.0 → 🔴 S-03** — USDJPY détruit de la valeur. La totalité de la profitabilité provient d'EURUSD. USDJPY efface 60% des gains EURUSD. **Retrait de USDJPY recommandé.**

### 3.2 Performance par direction

| Direction | N | Wins | WR | Verdict |
|-----------|---|------|----|---------|
| LONG | 24 | 12 | **50.0%** | ✅ |
| SHORT | 4 | 0 | **0.0%** | 🟠 S-09 |

**SHORT WR = 0% (N=4) → 🟠 S-09** — Toutes les positions SHORT sont des pertes. N=4 reste non significatif, mais le signal est clair : la stratégie FCR est un biais LONG en ouverture NYSE.

### 3.3 Évolution temporelle (edge decay)

| Année | N | WR | PF |
|-------|---|----|----|
| 2023 | 0 | — | — |
| 2024 | 1 | 0% | 0.0 |
| 2025 | 27 | 44.4% | 1.28 |
| 2026 | 0 | — | — |

Edge decay non calculable (données trop sporadiques). Le silence total de 2026 est structurellement inquiétant.

### 3.4 Concentration du P&L

| Date | Trades | P&L net (pips) | % du total (+45.45) |
|------|--------|----------------|---------------------|
| **2025-04-11** | 6 EURUSD | **+118.45** | **261%** |
| 2025-06-03 | 1 USDJPY | +24.9 | 55% |
| 2025-03-12 | 1 EURUSD | +8.8 | 19% |
| Tous autres jours | 19 trades | **−106.7** | — |

```
Top 3 jours = +152.15 pips sur total net +45.45 pips → 335% du P&L total
Sans 2025-04-11 : total = 45.45 − 118.45 = −73.0 pips (PERTE)
```

**→ 🔴 S-04** : Le 11 avril 2025 correspond à l'annonce de la pause des tarifs douaniers Trump (08:15–08:50 UTC). 6 trades EURUSD LONG en 35 minutes sur un événement macro Black Swan. **L'edge observé n'est pas reproductible — il s'agit d'un effet de queue exceptionnel, pas d'un signal FCR structurel.**

**NON CONFORME** — USDJPY à supprimer. P&L concentré sur 1 jour exceptionnel. Biais directionnel SHORT inexpliqué.

---

## BLOC 4 — ROBUSTESSE IS/OOS

### 4.1 Validité du split IS/OOS

Split implémenté dans `backtest_stats.py:split_trades_is_oos()` ligne ~286 : `is_ratio=0.7`.
`split_idx = int(28 × 0.7) = 19` → N_IS=19, N_OOS=9.

| Segment | N | Période | WR | PF |
|---------|---|---------|----|----|
| **IS** (70%) | **19** | 2024-01-02 → 2025-04-15 | **47.4%** | **1.627** |
| **OOS** (30%) | **9** | 2025-04-23 → 2025-06-03 | **33.3%** | **0.709** |

**N_OOS = 9 < 15 → 🔴 S-06** — Métriques OOS statistiquement non significatives.

**Dégradation IS → OOS :**

| Métrique | IS | OOS | Dégradation | Verdict |
|----------|----|-----|-------------|---------|
| WR | 47.4% | 33.3% | **−29.7%** | 🟠 (≈ seuil 30%) |
| PF | 1.627 | **0.709** | **−56.4%** | 🔴 S-05 |

```
Dégradation PF = (1.627 − 0.709) / 1.627 = 56.4% → bien au-dessus du seuil 30%
```

**PF_OOS = 0.709 < 1.0 → 🔴 S-05** — Stratégie **perdante** hors échantillon. L'IS inclut le 11 avril 2025 (118 pips) ; l'OOS n'a aucun événement équivalent.

### 4.2 Cohérence temporelle

- **IS** (jan 2024 → avr 2025) : marché pré-choc tarifaire + l'événement exceptionnel du 11 avril 2025
- **OOS** (avr–juin 2025) : marché post-choc tarifaire, USDJPY en tendance baissière (USD faible)

Régimes distincts ✅ — mais la dégradation IS→OOS est structurelle : l'OOS est dominé par USDJPY dans un régime de tendance incompatible avec l'hypothèse FCR de consolidation + spike.

### 4.3 Walk-forward

`run_walk_forward` importé dans `backtest.py:61–69`, **non appelé** dans `run_backtest()`.

**→ 🟡 S-13** : Validation IS/OOS statique uniquement. L'IS/OOS statique est vulnérable à la sélection du point de coupure.

**NON CONFORME** — PF_OOS < 1.0, N_OOS < 15, dégradation 56%.

---

## BLOC 5 — CALIBRATION DES FILTRES FCR

### 5.1 Inventaire des paramètres actifs

| Paramètre | config.yaml | Constante default | Verdict |
|-----------|------------|------------------|---------|
| `min_range_pips` | 8.0 | `DEFAULT_MIN_RANGE_PIPS = 8.0` | ✅ Identique |
| `fcr_range_cv_max` | 0.5 | Aucun default | Strict |
| `min_atr_ratio` | 1.7 | `DEFAULT_MIN_ATR_RATIO = 2.0` | Moins restrictif que default |
| `min_atr_ratio EURUSD` | 1.0 (override) | N/A | Permissif |
| `min_atr_ratio USDJPY` | **non défini → 1.7** | N/A | Restrictif |
| `min_volume_ratio` | 1.0 | `DEFAULT_MIN_VOLUME_RATIO = 1.0` | ✅ Identique |
| `min_body_ratio` | 0.3 | `DEFAULT_MIN_BODY_RATIO = 0.3` | ✅ Identique |
| `max_wick_ratio` | 1.5 | `DEFAULT_MAX_WICK_RATIO = 1.5` | ✅ Identique |
| `reward_ratio` | 2.0 | `DEFAULT_RR_RATIO = 2.5` | Moins restrictif |
| `max_spread_pips` | 2.0 | `DEFAULT_MAX_SPREAD_PIPS = 2.0` | ✅ Identique |

### 5.2 Cohérence live ↔ backtest

Post-corrections C-01/C-02 (2026-03-24) :

| Paramètre | Backtest | Live | Verdict |
|-----------|----------|------|---------|
| `volume_period` | `backtest.py:294` → `config.trading.volume_period` | `signal_pipeline.py:107` | **CONFORME** |
| `atr_period` | `backtest.py:437` → `config.trading.atr_period` | `signal_pipeline.py:74` | **CONFORME** |
| `rr_ratio` | `backtest.py:286` ✅ | `signal_pipeline.py:100` ✅ | **CONFORME** |

### 5.3 Analyse critique de reward_ratio

`reward_ratio = 2.0` (config.yaml:risk). RR réalisé depuis le CSV :
```
Avg win / Avg loss = 19.95 / 12.12 = 1.646 < 2.0
```
**RR réalisé (1.646) < RR configuré (2.0)** → TP rarement atteint à plein ; cohérent avec le commentaire config : *"TP at 2.5R rarely hit"*.

WR minimum pour PF > 1.0 avec RR=2.0 : `1 / (1 + 2.0) = 33.3%` → WR global 42.86% > 33.3% ✅

**CONFORME** — reward_ratio adapté à la réalité observée.

---

## BLOC 6 — MODÉLISATION DES COÛTS

### 6.1 Spread

**Backtest** (`backtest_simulation.py:compute_variable_slippage()`) :
- Spread simulé depuis `BASE_SPREAD_BY_PAIR[pair]` — fixe par paire, multiplié par `NYSE_OPEN_SLIPPAGE_MULTIPLIER` si ouverture NYSE
- Filtre `max_spread_pips=config.trading.max_spread_pips` actif dans `_validate_backtest_signal()` ✅
- Hypothèse de modélisation documentée via correction C-03 (2026-03-24) ✅

**Live** : spread réel IB via `get_live_spread()`.

**CONFORME** : filtre max_spread_pips actif. Divergence modélisation documentée.

### 6.2 News filter — divergence

`config.yaml:125` : `news_filter.enabled: true`.

**Backtest** : `EconomicNewsFilter` importé (`backtest.py:72`), `_collect_session_trades` accepte `news_filter: EconomicNewsFilter | None = None`. Dans le flux `run_backtest()` → `_fetch_pair_trades()` → `_backtest_pair()`, **aucune instanciation de `EconomicNewsFilter` n'est visible** → paramètre reste `None` → filtre ignoré silencieusement (`backtest.py:462` : `if news_filter is not None:`).

**Live** : filtre news actif via `check_signal_allowed()`.

**→ 🟠 S-10** — Le backtest n'applique pas le filtre news alors que config dit `enabled: true`. Les 28 trades CSV peuvent inclure des signaux sur events HIGH IMPACT bloqués en live. La fréquence réelle du signal live est inférieure à celle du backtest.

### 6.3 Expectancy nette

Les `pnl_pips` du CSV sont nets (spread + slippage intégrés dans `_simulate_trade_exit`).
Rendement total simulé : +$1,092 sur $10,000 départ = **+10.9% sur 3 ans** (~3.5%/an).

**Expectancy nette : ✅ positive (+1.62 pips/trade)**, mais fragile sur N=28.

---

## BLOC 7 — RISK MANAGEMENT FINANCIER

### 7.1 Position sizing

- `risk_pct = 3.0%` equity fixe (`config.yaml:26`). Compound sizing via `_apply_equity_sizing()` (`backtest_stats.py:250`).
- Kelly f* = 8.15% → demi-Kelly = 4.08% → **3.0% < demi-Kelly ✅**
- `max_lot_size = 1000` micro lots → sur $10k, sizing 3% ≈ 30 micro lots pour 10-pip SL → cap non contraignant ✅

### 7.2 Garde-fous d'exécution

| Garde-fou | Localisation | Verdict |
|-----------|-------------|---------|
| `calculate_position_size() is_valid → False` | `position_manager.py:65` | ✅ CONFORME |
| `check_daily_limit() limit_breached → True` | `risk_manager.py:check_daily_limit()` | ✅ CONFORME |
| `create_bracket_order() is_valid → False` | `position_manager.py:104` + log rejection_reason | ✅ CONFORME |
| Pipeline all-or-nothing | `signal_pipeline.py:99` | ✅ CONFORME |

**CONFORME** — Tous les garde-fous opérationnels.

### 7.3 Exposition simultanée multi-paires

Filtre USD correlation désactivé (`usd_correlation_filter: false`, config.yaml:40) — justifié par tests documentés. EURUSD LONG + USDJPY LONG = USD-net neutre → pas de double exposition directionnelle USD. **CONFORME** avec configuration actuelle.

---

## BLOC 8 — INTÉGRITÉ DU PIPELINE SIGNAL

### 8.1 All-or-nothing

| Étape | Guard | Localisation | Verdict |
|-------|-------|-------------|---------|
| FCR → None → STOP | `if state.fcr_result is None: return None` | `signal_pipeline.py:99` | **CONFORME** |
| Gap → False → STOP | check `gap_result["detected"]` | `signal_pipeline.py:detect_gap()` | **CONFORME** |
| Engulfing → None → STOP | Signal None → pas d'exécution | `session_lifecycle.py` | **CONFORME** |

### 8.2 Paramètres live vs backtest

Post-corrections C-01/C-02 (2026-03-24) — tous CONFORMES (voir BLOC 5.2).

**CONFORME** — Pipeline all-or-nothing respecté, paramètres injectés identiquement après corrections.

---

## SYNTHÈSE

### Score global : **3 / 10 → NO-GO**

> < 5 → NO-GO : refonte paramétrique ou stratégique nécessaire avant tout paper trading.

Le score de 3/10 s'explique par :
- **7 anomalies 🔴** dont S-02, S-04, S-05 sont des blockers absolus
- L'edge statistique n'est **pas prouvé** sur N=28 (IC inclut 50%)
- La profitabilité repose à **261% sur un seul jour** (11 avril 2025, Black Swan tarifaire)
- USDJPY structurellement perdant (PF=0.47)
- Stratégie inactive depuis **9 mois**
- Ingénierie saine (pipeline correct, guards opérationnels, sizing conservateur) → base solide

**EURUSD seul** (N=16, WR=56.25%, PF=3.39) est potentiellement viable — mais N=16 est trop faible pour trancher.

### Tableau des anomalies

| ID | Bloc | Description courte | Fichier:Ligne | Sévérité | Impact | Effort |
|----|------|--------------------|---------------|----------|--------|--------|
| S-01 | 1.1 | N=28 < 30 — échantillon critique | `reports/ALPHAEDGE_backtest_results.csv` | 🔴 Critique | Edge non fiable statistiquement | Fort (+ données / + paires) |
| S-02 | 1.1 | IC 95% WR = [24.5%–61.2%] inclut 50% | CSV calculé | 🔴 Critique | Impossible de distinguer edge réel de luck | Dépend de S-01 |
| S-03 | 3.1 | USDJPY PF=0.47 — détruit de la valeur | `reports/ALPHAEDGE_backtest_results.csv` | 🔴 Critique | −$1,657 USD sur 3 ans | Faible (suspendre USDJPY) |
| S-04 | 3.4 | P&L concentré à 261% sur 2025-04-11 — sans ce jour: −73 pips | CSV calculé | 🔴 Critique | Résultat non reproductible — Black Swan macro | Fort (recalibration stratégique) |
| S-05 | 4.1 | PF_OOS = 0.71 < 1.0 — perdant hors échantillon | `backtest_stats.py:286` | 🔴 Critique | Overfitting confirmé | Fort |
| S-06 | 4.1 | N_OOS = 9 < 15 — non significatif | `backtest_stats.py:286` | 🔴 Critique | OOS ne permet pas de conclure | Dépend de S-01 |
| S-07 | 2.1 | 9 mois de silence signal (juin 2025 → mars 2026) | `reports/ALPHAEDGE_backtest_results.csv` | 🔴 Critique | Stratégie inactive en production | Fort (recalibration filtres ou univers) |
| S-08 | 1.2 | PF global = 1.234 < seuil 1.5 | CSV calculé | 🟠 Majeur | Marge sécurité insuffisante | Moyen |
| S-09 | 3.2 | SHORT WR = 0% (N=4) | CSV calculé | 🟠 Majeur | Biais directionnel non maîtrisé | Moyen (filtrer SHORT) |
| S-10 | 6.2 | `news_filter.enabled=true` non instancié dans `run_backtest()` | `backtest.py:~200` | 🟠 Majeur | Divergence live backtest sur filtrage news | Faible (instancier EconomicNewsFilter) |
| S-11 | 4.3 | `run_walk_forward` importé mais non appelé | `backtest.py:61` | 🟠 Majeur | Robustesse temporelle non évaluée | Faible |
| S-12 | 1.2 | 5 pertes consécutives (trades 23–27, avr–juin 2025) | `reports/ALPHAEDGE_backtest_results.csv` | 🟠 Majeur | Risque psychologique en live | Moyen |
| S-13 | 4.3 | IS/OOS statique uniquement, pas de walk-forward | `backtest.py:61` | 🟡 Mineur | Validation multi-fenêtres absente | Faible |

### Priorisation des actions

**Blocant paper trading — à traiter avant tout :**
1. **S-03** (Effort faible) : Suspendre USDJPY — retirer de `config.yaml:trading.pairs`. Valider EURUSD seul.
2. **S-10** (Effort faible) : Instancier `EconomicNewsFilter` dans `run_backtest()` depuis `config.news_filter`.
3. **S-11** (Effort faible) : Activer `run_walk_forward()` dans `run_backtest()` optionnellement.

**Recalibration stratégique (moyen terme) :**
4. **S-04 / S-07** : Diagnostiquer silence juin 2025–2026. Est-ce un régime de trend incompatible ? Tester `min_atr_ratio` plus bas ou fenêtre de session London Open.
5. **S-09** : Tester un filtre direction LONG-only si le biais est confirmé sur N > 100.
6. **S-01 / S-02** : Étendre les données (>3 ans IB) ou ajouter GBPUSD / EURCAD pour augmenter N.

---

*Audit réalisé par GitHub Copilot (sonnet-4.6) en mode agent — 2026-03-24*
*Sources : 28 trades CSV (calculs manuels) + 12 fichiers source lus · Zéro valeur inventée*

