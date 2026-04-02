---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: audit_strategic_alphaedge.md
derniere_revision: 2026-03-26
creation: 2026-03-26 à 09:00
---

# AUDIT STRATÉGIQUE — ALPHAEDGE Momentum+Carry
**Date** : 2026-03-26 · **Analyste** : GitHub Copilot (sonnet-4.6) · **Score** : 2/10

> Source principale : `reports/ALPHAEDGE_backtest_results.csv` — 16 trades réels.
> Période couverte : 2024-01-02 → 2025-05-30 (17 mois, EURUSD uniquement).

---

## BLOC 1 — VALIDITÉ STATISTIQUE DE L'EDGE

### 1.1 Taille d'échantillon

**N = 16 trades** sur 17 mois. Source : `reports/ALPHAEDGE_backtest_results.csv`.

| Critère | Valeur | Verdict |
|---------|--------|---------|
| N total | 16 | 🔴 N < 30 — risque statistique maximum |
| N < 30 | Oui | 🔴 Intervalle de confiance non exploitable |

**IC 95% sur le win rate :**
- WR = 9/16 = 56.25%
- SE = √(0.5625 × 0.4375 / 16) = 0.1240
- IC = 56.25% ± 1.96 × 12.40% = **[31.9% ; 80.6%]**

→ 🔴 L'IC inclut 50% — **l'edge n'est pas prouvé statistiquement**.
→ 🔴 N = 16 < 30 — risque statistique rédhibitoire.

**VERDICT BLOC 1.1 : NON CONFORME**

---

### 1.2 Métriques d'edge

Calculs depuis `reports/ALPHAEDGE_backtest_results.csv` :

| Métrique | Valeur | Seuil | Verdict |
|----------|--------|-------|---------|
| Win rate | 56.25% (9/16) | — | ⚠️ IC overlaps 50% |
| Profit Factor | **3.39** (172.3 / 50.75 pips) | ≥ 1.5 | CONFORME |
| Avg win pips | 19.14 pips | — | — |
| Avg loss pips | 7.25 pips | — | — |
| Expectancy | **+7.60 pips/trade** | — | CONFORME |
| Max Drawdown | **7.64%** (equity 10000→9236.50) | ≤ 15% | CONFORME |
| Max consec. losses | 2 | ≤ 5 | CONFORME |

> Sharpe annualisé : non calculable de façon fiable sur 16 trades
> avec clustering extrême (6 trades sur une seule journée).

**Note critique :** Les métriques PF et Expectancy sont entièrement dominées
par la journée du 2025-04-11 (voir BLOC 3.4). Hors cette journée,
le PF est < 1.0 sur le reste de la période.

**VERDICT BLOC 1.2 : CONFORME** (métriques nominales) / **À VÉRIFIER** (robustesse)

---

### 1.3 Critère de Kelly

- WR = 0.5625, avg_win/avg_loss = 19.14 / 7.25 = **2.64**
- f* = 0.5625 − 0.4375 / 2.64 = **39.7%**
- Demi-Kelly = **19.8%**
- risk_pct actif = **3.0%** (`config.yaml:29`)

→ 3.0% << 19.8% → risk_pct très conservateur. **CONFORME**

**VERDICT BLOC 1.3 : CONFORME**

---

## BLOC 2 — FRÉQUENCE ET CONTINUITÉ DU SIGNAL

### 2.1 Taux de signal

Source : `reports/ALPHAEDGE_backtest_results.csv`.

| Période | Trades | Trimestres vides |
|---------|--------|-----------------|
| 2024-Q1 | 1 | — |
| 2024-Q2 | 0 | 🔴 |
| 2024-Q3 | 0 | 🔴 |
| 2024-Q4 | 0 | 🔴 |
| 2025-Q1 | 5 (mars uniquement) | — |
| 2025-Q2 | 10 (avr-mai) | — |
| 2025-Q3 | 0 | 🔴 |
| 2025-Q4 | 0 | 🔴 |
| 2026-Q1 | 0 (à ce jour) | 🔴 |

**Plus long silence actuel :** 2025-05-30 → 2026-03-26 = **~300 jours** → 🔴

**Plus long silence historique :** 2024-01-02 → 2025-03-05 = **~427 jours** → 🔴

→ La stratégie génère des signaux pendant environ **3 mois** (mars-mai 2025)
sur les 17 mois backtestés, soit **~18% du temps actif**.

**VERDICT BLOC 2.1 : NON CONFORME** — silences chroniques ≥ 90 jours × 2

---

### 2.2 Cascade de filtres — diagnostic du silence

| Filtre | Fichier:Ligne | Valeur active | Log du rejet |
|--------|--------------|---------------|--------------|
| Momentum ADX gate | `signal_pipeline.py:82` | adx_threshold=25.0 | Non loggé séparément (STOP silencieux) |
| ADX period | `loader.py:443−446` | adx_period=14 | — |
| Carry | `carry_signal.py:65+` | min_differential=0.5% | NEUTRAL = pass-through |
| **carry_rates** | `config.yaml:108−113` | **rates={} → inopérant** | ⚠️ silence indiagnosticable |
| News blackout | `backtest.py:185` | blackout=15 min, high only | Loggé si actif |
| Spread | `backtest.py:375` | max_spread_pips=2.0 | À VÉRIFIER (EURUSD spread réel ≤ 1 pip) |
| Session | `backtest.py:244` | max_trades_per_session=6 | Post-hoc, non bloquant signal |

→ Les rejets momentum (ADX < seuil) ne sont **pas loggés avec motif** dans
`_backtest_pair` — le silence multi-trimestres est indiagnosticable en production.

**VERDICT BLOC 2.2 : À VÉRIFIER** (absence de logging motif de rejet)

---

### 2.3 Surrestrictivité des filtres

- **News filter backtest** : actif (`backtest.py:185`, lit `config.news_filter_raw`).
  Alimenté par `data/economic_calendar.csv`. Chemin fichier non vérifié — À VÉRIFIER.
- **ADX threshold = 25.0** : confirme tendance minimale — valeur standard,
  probablement non surrestrictif sur EURUSD. Implémenté `signal_pipeline.py:82`. CONFORME.
- **carry_min_differential_pct = 0.5%** : pas d'override par paire.
  Identique pour EURUSD (différentiel EUR/USD historiquement élevé 2023-2025)
  et pour USDJPY (suspendu). À VÉRIFIER pour paires à faible carry.

**VERDICT BLOC 2.3 : À VÉRIFIER**

---

## BLOC 3 — PERFORMANCE PAR PAIRE ET RÉGIME

### 3.1 Performance par paire

Source : `reports/ALPHAEDGE_backtest_results.csv`.

| Paire | N | WR | PF | Expectancy (pips) | P&L (pips) | P&L (USD) |
|-------|---|----|----|------------------|-----------|----------|
| EURUSD | 16 | 56.25% | 3.39 | +7.60 | +121.55 | +$2,837 |
| USDJPY | 0 | — | — | — | — | — |

USDJPY suspendu au `config.yaml:26` (commentaire : PF=0.47, WR=25% — recalibration pending).
→ Ce chiffre historique USDJPY n'est pas présent dans le CSV courant.

**VERDICT BLOC 3.1 : CONFORME** (EURUSD seul, PF > 1.5)

---

### 3.2 Performance par direction

Source : `reports/ALPHAEDGE_backtest_results.csv`.

| Direction | N | Wins | WR | Win pips | Loss pips | PF |
|-----------|---|------|----|----------|----------|----|
| **LONG** | 12 | 9 | **75.0%** | 172.3 | 21.15 | **8.15** |
| **SHORT** | 4 | 0 | **0.0%** | 0 | 29.60 | **0.00** |

→ 🔴 **SHORT : WR = 0%, PF = 0** sur N=4 trades — perd systématiquement.
→ `config.yaml:39` : `direction_filter: "ALL"` — les SHORT sont autorisés en production.

**VERDICT BLOC 3.2 : NON CONFORME** — direction SHORT destructrice de valeur.

---

### 3.3 Évolution temporelle (edge decay)

| Année | N | WR | PF | Win pips | Loss pips |
|-------|---|----|----|---------|---------|
| 2024 | 1 | 0% | 0 | 0 | 6.85 |
| 2025 | 15 | 60% | 3.93 | 172.3 | 43.90 |
| 2026 | 0 | — | — | — | — |

→ 2024 : 1 trade unique, non représentatif.
→ 2025 : tous les signaux concentrés sur 3 mois.
→ Aucun trade 2026 malgré 3 mois écoulés.
→ **Edge decay** : impossible à évaluer sur 2 ans + N=16. À VÉRIFIER.

**VERDICT BLOC 3.3 : À VÉRIFIER**

---

### 3.4 Concentration du P&L

Source : `reports/ALPHAEDGE_backtest_results.csv`.

| Date | Paires/Trades | P&L net USD | % du P&L total |
|------|--------------|------------|----------------|
| **2025-04-11** | EURUSD LONG ×6 | **+$2,788** | **98.3%** |
| 2025-04-23 | EURUSD LONG ×1 | +$676 | 23.8% |
| 2025-04-03 | EURUSD LONG ×1 | +$525 | 18.5% |

→ Les 3 meilleures journées : **$3,989** (140.6% du P&L net total de $2,837).
→ Hors 2025-04-11 : le P&L net sur les 15 autres trades = **−$1,152**.
→ 🔴 **Effet jackpot extrême** : la stratégie est structurellement perdante
sans la convergence de 6 signaux LONG favorables sur une journée unique.

**Analyse 2025-04-11 :** 6 trades en 35 minutes (08:15→08:50 UTC),
tous EURUSD LONG sur la même séance NYSE. Max_trades_per_session=6 atteint.
Contexte macro probable : Trump tariffs annonce (2025-04-09) → EURUSD +200 pips.
→ Cet edge est **événementiel**, non reproductible systématiquement.

**VERDICT BLOC 3.4 : NON CONFORME** — concentration jackpot critique.

---

## BLOC 4 — ROBUSTESSE IS/OOS

### 4.1 Validité du split IS/OOS

Split implémenté : `backtest_stats.py:283−304`, ratio `is_ratio=0.7`.
Méthode : chronologique, `split_idx = int(len(trades) × 0.7)`.

| Partition | N | WR | PF | Verdict |
|-----------|---|----|----|---------|
| IS (70%) | 11 | 63.6% | 2.60 | — |
| OOS (30%) | **5** | 60.0% | 6.01 | 🔴 N_OOS < 15 |

→ 🔴 **N_OOS = 5** — métriques OOS statistiquement non significatives.
→ Pas de dégradation apparente IS→OOS (WR 63.6%→60%, PF 2.60→6.01),
mais ce résultat est un artefact du splitting : les 2 derniers trades
April 11 ($677+$671) tombent en OOS → PF artificiellement gonflé.

**VERDICT BLOC 4.1 : NON CONFORME** — N_OOS = 5 → robustesse non évaluable.

---

### 4.2 Cohérence temporelle du split

- IS couvre : 2024-01-02 → 2025-04-11 (période pre-tariffs + tariffs)
- OOS couvre : 2025-04-11 → 2025-05-30 (post-annonce tariffs court terme)
→ IS et OOS chevauchent le même régime macro (tariffs 2025) → **À VÉRIFIER**.

**VERDICT BLOC 4.2 : À VÉRIFIER**

---

### 4.3 Walk-forward

- `walk_forward.py` existe et est branché : `backtest.py:147`.
- Condition : `config.trading.walk_forward_enabled` (`loader.py:209`).
- **walk_forward_enabled = False** dans config.yaml (non configuré).
- `sample_type` : colonne vide dans le CSV → walk-forward jamais exécuté.

→ 🟡 Walk-forward disponible mais désactivé — validation temporelle absente.

**VERDICT BLOC 4.3 : NON CONFORME** — walk-forward non exécuté.

---

## BLOC 5 — CALIBRATION DES FILTRES MOMENTUM+CARRY

### 5.1 Inventaire des paramètres actifs

| Paramètre | Config.yaml | Default (constants.py) | Sens | Écart |
|-----------|-------------|----------------------|------|-------|
| momentum_fast_period | 12 (`momentum:fast_period`) | DEFAULT_MOMENTUM_FAST_PERIOD=12 | — | aucun |
| momentum_slow_period | 26 (`momentum:slow_period`) | DEFAULT_MOMENTUM_SLOW_PERIOD=26 | — | aucun |
| momentum_adx_period | 14 (`momentum:adx_period`) | DEFAULT_ADX_PERIOD=14 | — | aucun |
| momentum_adx_threshold | 25.0 (`momentum:adx_threshold`) | DEFAULT_ADX_THRESHOLD=25.0 | — | aucun |
| momentum_lookback_days | 252 (`momentum:lookback_days`) | DEFAULT_MOMENTUM_LOOKBACK_DAYS=252 | — | aucun |
| carry_enabled | true (`carry:enabled`) | True | — | aucun |
| carry_min_differential_pct | 0.5% (`carry:min_differential_pct`) | DEFAULT_CARRY_MIN_DIFFERENTIAL=0.5 | — | aucun |
| rr_ratio | **2.0** (`risk:reward_ratio`) | DEFAULT_RR_RATIO=2.5 | plus permissif | −0.5 |
| max_spread_pips | 2.0 (`trading:max_spread_pips`) | DEFAULT_MAX_SPREAD_PIPS=2.0 | — | aucun |
| news_filter.enabled | true (`news_filter:enabled`) | — | — | — |

**Injection loader** : `loader.py:437−458` — tous les paramètres momentum sont lus
depuis la section `momentum:` du YAML et injectés dans `TradingConfig`. CONFORME.

---

### 5.2 Cohérence live ↔ backtest par paramètre

- **ADX threshold** : backtest consomme `config.trading.momentum_adx_threshold`
  (`signal_pipeline.py:82`) — même objet que le live. **CONFORME**.
- **momentum_fast_period / slow_period** : `signal_pipeline.py:77−78`
  utilise `getattr(trading, "momentum_fast_period", DEFAULT)` — TradingConfig
  possède bien ce champ (`loader.py:214−215`) → getattr réussit toujours. **CONFORME**.
- **rr_ratio** : lecture `risk.reward_ratio` → fallback `trading.rr_ratio`
  (`loader.py:355−367`). Même valeur live et backtest. **CONFORME**.
- **carry_rates** : `loader.py:456` lit `carry.rates` → `{}` si absent.
  `carry_enabled=true` mais `rates={}` → `get_carry_bias()` retourne
  `CarrySignal(is_valid=False)` → filter silencieusement inactif. 🟠

**VERDICT BLOC 5.2 : CONFORME** (câblage) / 🟠 (carry rates vides)

---

### 5.3 Analyse critique de rr_ratio

- rr_ratio configuré = **2.0** (`config.yaml:risk.reward_ratio`)
- RR réalisé (CSV) = avg_win_pips / avg_loss_pips = 19.14 / 7.25 = **2.64**
- RR réalisé > rr_ratio configuré → le TP est atteint fréquemment. **CONFORME**
- WR_min pour PF > 1.0 = 1 / (1 + 2.0) = **33.3%**
- WR atteint = 56.25% >> 33.3%. **CONFORME**

**VERDICT BLOC 5.3 : CONFORME**

---

## BLOC 6 — MODÉLISATION DES COÛTS

### 6.1 Spread

- **Backtest** : `compute_variable_slippage()` (`backtest_simulation.py:62`).
  EURUSD normal : `BASE_SPREAD_BY_PAIR["EURUSD"] = 0.2 pip` (`constants.py:164`).
  NYSE open (first 5 min) : `NYSE_OPEN_SPREAD_PIPS = 1.5 pip` (`constants.py:158`).
  News : `NEWS_SPREAD_PIPS = 3.0 pip` (`constants.py:159`).
- **Filtre max_spread_pips** : actif en backtest (`backtest.py:375`)
  et en live (`session_lifecycle.py:723`). Seuil = 2.0 pips. **CONFORME**
- EURUSD réel NYSE open ≈ 0.5–1.0 pip → modélisation 0.2 pip normal
  est très conservatrice (sous-estimation légère des coûts off-peak).

**VERDICT BLOC 6.1 : CONFORME** (avec note légère sous-estimation off-peak)

---

### 6.2 Slippage

- **Backtest** : variable via `compute_variable_slippage()` :
  normal = 0.3 pip, NYSE open = 0.6 pip, news = 1.5 pip. (`constants.py:152,154,156`)
- **Live** : fixe `slippage_buffer_pips = 0.5 pip` appliqué sur le SL uniquement
  (`session_lifecycle.py:118`, après P-06). Spread live = IB réel via `get_live_spread()`.
- Divergence documentée : voir `audit_pipeline_alphaedge.md — P-03`. 🟠

**VERDICT BLOC 6.2 : À VÉRIFIER** (divergence modèles, déjà noté audit 7b)

---

### 6.3 Impact des coûts sur l'expectancy nette

- Les pnl_pips du CSV sont **nets** : les niveaux SL/TP intègrent le spread
  via `apply_slippage_buffer()` dans le modèle backtest.
- Expectancy nette observée dans le CSV = **+7.60 pips/trade** → CONFORME.
- Cependant : expectancy hors 2025-04-11 = (121.55 − 127.8 nets April 11) / 10 trades
  ≈ −0.6 pips/trade → 🔴 **expectancy négative hors journée jackpot**.

**VERDICT BLOC 6.3 : NON CONFORME** (expectancy conditionelle à l'événement April 11)

---

## BLOC 7 — RISK MANAGEMENT FINANCIER

### 7.1 Position sizing

- Méthode : fixed risk_pct sur equity — `calculate_position_size()` (`risk_manager stub:8`)
- risk_pct = 3.0% << half-Kelly = 19.8% → sizing conservateur. **CONFORME**
- max_lot_size = 1000 micro lots (`config.yaml:47`).
  Sizing typique EURUSD 3%-risk / 10K equity / SL~7 pips :
  risk_amount = $300, pip_val ≈ $0.10/micro-pip → 300/(7×0.10) = 429 micro-lots
  → cap 1000 non atteint. **CONFORME**
- Si cap atteint : log WARNING et cap appliqué (`position_manager.py:70-73`). **CONFORME**

**VERDICT BLOC 7.1 : CONFORME**

---

### 7.2 Garde-fous d'exécution

| Garde-fou | Déclenché si | Comportement | Fichier:Ligne |
|-----------|-------------|-------------|---------------|
| `calculate_position_size()` | `is_valid=False` | Retourne None → aucun ordre | `risk_manager stub:35` |
| `check_daily_limit()` | `limit_breached=True` | `can_trade=False` → STOP | `risk_manager stub:50-60` |
| `create_bracket_order()` | `is_valid=False` | Retourne None → ordre ignoré | `backtest.py:379-381` |

**VERDICT BLOC 7.2 : CONFORME**

---

### 7.3 Exposition simultanée multi-paires

- Seul EURUSD actif (`config.yaml:25`). USDJPY suspendu.
- `check_pair_limit(max_open_pairs=1)` → une seule paire à la fois.
  (`session_lifecycle.py` — appel `risk_mod.check_pair_limit`).
- **Pas de risque de double exposition USD en configuration actuelle.** CONFORME.
- Note : si USDJPY réactivé, les deux paires sont corrélées USD.
  Mécanisme `usd_correlation_filter` disponible mais désactivé (`config.yaml:34`,
  `usd_correlation_filter: false`) — voir audit_pipeline P-05 pour divergence algorithme.

**VERDICT BLOC 7.3 : CONFORME** (configuration actuelle mono-paire)

---

## BLOC 8 — INTÉGRITÉ DU PIPELINE SIGNAL

### 8.1 Pipeline all-or-nothing

| Étape | Condition STOP | Behavior | Fichier:Ligne | Verdict |
|-------|--------------|---------|---------------|---------|
| `detect_momentum()` → None | ADX < seuil | Pipeline stoppé, aucun carry | `signal_pipeline.py:87` | CONFORME |
| Carry conflict | `is_carry_conflict()=True` | STOP avant sizing | `strategy.py:_detect_momentum` (P-03) | CONFORME |
| `calculate_position_size()` | `is_valid=False` | STOP — zéro ordre | `risk_manager stub:35` | CONFORME |
| `create_bracket_order()` | `is_valid=False` | STOP — log rejection | `backtest.py:379-381` | CONFORME |

**VERDICT BLOC 8.1 : CONFORME**

---

### 8.2 Paramètres live vs backtest

- **Injection backtest** : `loader.py:437−458` lit config.yaml → `TradingConfig`.
  Puis `_backtest_pair()` reçoit `config: AppConfig` → `config.trading.xxx`.
- **Injection live** : `signal_pipeline.py:77−86` reçoit le même `config: AppConfig`
  via `SwingStrategy._detect_momentum()`.
- **Même objet** `AppConfig` injecté live et backtest → paramètres identiques. **CONFORME**

**VERDICT BLOC 8.2 : CONFORME**

---

## SYNTHÈSE

### Score global : **2 / 10** → **NO-GO**

| Dimen­sion | Points | Raison |
|-----------|--------|--------|
| Validité statistique | 0/3 | N=16, IC inclut 50%, jackpot |
| Fréquence signal | 0/2 | 2 silences >90J, 85% inactif |
| IS/OOS | 0/2 | N_OOS=5, WF désactivé |
| Calibration | 1.5/2 | Carry inopérant, sinon conforme |
| Coûts & Risk | 0.5/1 | Divergence slippage, jackpot |

### Tableau des anomalies

| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact | Effort |
|----|------|-------------|---------------|----------|--------|--------|
| S-01 | 1 | N=16 — IC 95% WR inclut 50% — edge non prouvé | CSV | 🔴 | Confiance statistique nulle | Élevé (accumulation données) |
| S-02 | 3 | SHORT WR=0%, PF=0 (N=4) — direction_filter="ALL" autorise ces trades | CSV + config.yaml:39 | 🔴 | Pertes systématiques sur SHORT | Faible (<1h — configurer "LONG") |
| S-03 | 2 | Silences chroniques : 427J (2024Q2→2025Q1) + 300J (2025-06→) | CSV | 🔴 | Stratégie inactive >82% du temps | Stratégique |
| S-04 | 3 | P&L jackpot : 2025-04-11 = 98.3% du net ($2788/$2837) — sans ce jour net=−$1152 | CSV | 🔴 | Edge événementiel non reproductible | Stratégique |
| S-05 | 4 | N_OOS=5 — IS/OOS non significatif, walk-forward désactivé | backtest_stats.py:301 / loader.py:209 | 🔴 | Robustesse temporelle impossible à évaluer | Élevé (données + activer WF) |
| S-06 | 5 | carry_rates={} → carry filter inopérant malgré carry_enabled=true | config.yaml:108-113 | 🟠 | Biais carry absent du pipeline (signalé P-04) | Faible (peupler rates) |
| S-07 | 6 | Méthodes slippage divergentes backtest (variable) vs live (fixe SL buffer) | backtest_simulation.py:62 / session_lifecycle.py:118 | 🟠 | Écart coûts non quantifiable (signalé P-03) | Moyen |
| S-08 | 4 | Walk-forward disponible mais désactivé — validation temporelle absente | loader.py:209 | 🟡 | Robustesse temporelle non validée | Moyen (activer après >50 trades) |

---

### Verdict : **NO-GO**

**Score 2/10.** Trois raisons fondamentales, toutes issues du CSV :

1. **N=16** — aucune conclusion statistique ne peut être tirée. L'IC à 95% sur
   le WR (31.9%–80.6%) est compatible avec une pièce équilibrée.
2. **98.3% du P&L est concentré sur une journée unique (2025-04-11)** —
   l'edge observable est un biais événementiel (probable réaction macro tariffs),
   non une régularité systémique.
3. **Le SHORT est systématiquement perdant (WR=0%, N=4)** et la config actuelle
   (`direction_filter="ALL"`) autorise ces trades en production.

**Action prioritaire immédiate (avant paper trading) :**
- Désactiver le SHORT : `direction_filter: "LONG"` dans `config.yaml` (effort < 1h).
- Accumuler ≥ 100 trades avant toute décision statistique.

---

*Audit produit par GitHub Copilot (sonnet-4.6) — 2026-03-26*
*Sources : `reports/ALPHAEDGE_backtest_results.csv` + code source (fichiers cités)*
