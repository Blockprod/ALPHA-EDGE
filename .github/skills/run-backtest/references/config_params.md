# Paramètres de configuration — ALPHAEDGE

> Référence pour `run-backtest`. Valeurs nominales actuelles (2026-03-26).
> Source de vérité : `alphaedge/config/constants.py` + `config.yaml`.
> **Ne jamais hardcoder ces valeurs ailleurs.**

---

## Paramètres de risque

| Paramètre | Source | Valeur nominale | Commentaire |
|-----------|--------|----------------|-------------|
| `risk_pct` | `config.yaml` | `3.0` | % de l'équité risqué par trade |
| `max_daily_loss_pct` | `config.yaml` | `3.0` | Halt auto si DD journalier atteint |
| `DEFAULT_RR_RATIO` | `constants.py:57` | `2.5` | RR par défaut (mais stratégie cible RR=2.0) |
| `DEFAULT_RISK_PCT` | `constants.py:58` | `2.0` | Fallback si config non chargée |
| `max_trades_per_session` | `config.yaml` | `6` | Plafond par session |
| `max_trades_per_day` | `config.yaml` | `3` | Garde jackpot par paire/jour |
| `max_lot_size` | `config.yaml` | `1000.0` | Micro-lots max (cap dynamique) |
| `lot_type` | `config.yaml` | `"micro"` | 1 micro-lot = 1 000 unités |

---

## Paramètres de spread

| Paramètre | Source | Valeur nominale | Commentaire |
|-----------|--------|----------------|-------------|
| `DEFAULT_MAX_SPREAD_PIPS` | `constants.py:61` | `2.0` | Seuil rejet trade |
| `max_spread_pips` | `config.yaml` | `2.0` | config runtime |
| `BASE_SPREAD_PIPS` | `constants.py:158` | `0.8` | Conditions normales EUR/USD |
| `NYSE_OPEN_SPREAD_PIPS` | `constants.py:159` | `1.5` | Fenêtre ouverture NYSE |
| `NEWS_SPREAD_PIPS` | `constants.py:160` | `3.0` | Événements haute impact |
| `spread_spike_multiplier` | `config.yaml` | `3.0` | WARNING si spread > 3× max |

---

## Sessions par paire

| Paire | Session | Heure UTC | Heure CET (hiver) | Heure CEST (été) |
|-------|---------|-----------|-------------------|-----------------|
| EURUSD | London Open | 08:00–09:00 | 09:00–10:00 CET | 10:00–11:00 CEST |
| USDJPY | NYSE Open | 14:30–15:30 | 15:30–16:30 CET | 14:30–15:30 CEST |
| NYSE (défaut) | NYSE Open | 14:30–15:30 | 15:30 CET | 14:30 CEST |

> ⚠️ **Piège : EURUSD ≠ NYSE.** Ne jamais diagnostiquer EURUSD sur la session NYSE.
> `config.yaml : session_start / session_end` = paramètres NYSE par défaut.
> Les sessions par paire sont dans `config.trading.pair_sessions[pair]`.

---

## Paramètres de signal

| Paramètre | Source | Valeur nominale | Commentaire |
|-----------|--------|----------------|-------------|
| `DEFAULT_ADX_PERIOD` | `constants.py:100` | `14` | Période de lissage ADX |
| `DEFAULT_ADX_THRESHOLD` | `constants.py:101` | `25.0` | ADX minimum pour confirmer tendance |
| `DEFAULT_MAX_TRADES_PER_SESSION` | `constants.py:60` | `2` | Fallback si config non chargée |
| `EUR_USD_RATE` | `constants.py:62` | `1.08` | Taux de conversion journal pnl_eur |
| `DEFAULT_PIP_SIZE` | `constants.py:67` | `0.0001` | Fallback non-JPY |

---

## Pip sizes par paire

| Paire | pip_size |
|-------|---------|
| EURUSD | 0.0001 |
| GBPUSD | 0.0001 |
| AUDUSD | 0.0001 |
| NZDUSD | 0.0001 |
| USDCAD | 0.0001 |
| USDCHF | 0.0001 |
| USDJPY | 0.01 |
| EURJPY | 0.01 |
| GBPJPY | 0.01 |

---

## Paramètres verrouillés (ne pas modifier)

| Paramètre | Valeur | Raison |
|-----------|--------|--------|
| `direction_filter` | `"LONG"` | SHORT WR=0%, PF=0.00 sur N=4 — revert à "ALL" seulement après ≥30 SHORT trades WR>40% paper |
| `excluded_days` | `[]` | Testé — résultat inférieur au baseline (WR 47.6% vs 54.5%) |
| `usd_correlation_filter` | `false` | Testé — bloque 49/69 trades sans amélioration statistique |
| `walk_forward_enabled` | `false` | Activer seulement après N ≥ 100 trades live accumulés |
