# ALPHAEDGE — Claude Context
# Pipeline complet · Modules · Contraintes

---

## Pipeline Signal (ordre d'exécution)

```
IB Gateway (port 4002 paper / 4001 live)
  └─► data_feed.py           — reqHistoricalData M5 + M1 (ib_insync)
        └─► fcr_detector.pyx  — détecte la range FCR sur M5 (lookback=6 bougies)
              si None → STOP
        └─► gap_detector.pyx  — filtre ATR spike (atr_period=14, min_atr_ratio=2.0)
              si detected=False → STOP
        └─► engulfing_detector.pyx — signal entrée M1 (RR=2.5, volume_ratio=1.0)
              si None → STOP
              └─► risk_manager.pyx — sizing (risk=2% equity, max_loss=3%/jour)
                    si is_valid=False → STOP, log WARNING
                    si halt_trading=True → STOP ALL, log CRITICAL
              └─► order_manager.pyx — bracket order (entry/SL/TP)
                    si is_valid=False → STOP, log rejection_reason
                    └─► broker.py — PlaceOrder via ib_insync
```

**Règle absolue : pipeline all-or-nothing. Un STOP à n'importe quelle étape annule le trade complet.**

---

## Modules — Responsabilités

| Module | Langage | Responsabilité |
|--------|---------|----------------|
| `core/fcr_detector.pyx` | Cython | Détection range FCR sur M5 |
| `core/gap_detector.pyx` | Cython | Filtre ATR spike / volatilité M1 |
| `core/engulfing_detector.pyx` | Cython | Signal engulfing M1 + qualité |
| `core/risk_manager.pyx` | Cython | Sizing position + daily loss limit |
| `core/order_manager.pyx` | Cython | Construction bracket order |
| `engine/broker.py` | Python | Connectivité IB Gateway (ib_insync) |
| `engine/data_feed.py` | Python | Abonnement barres temps réel M5+M1 |
| `engine/session_lifecycle.py` | Python | Boucle async principale par session |
| `engine/signal_pipeline.py` | Python | Orchestrateur pipeline signal |
| `engine/backtest.py` | Python | Boucle backtest historique |
| `engine/backtest_simulation.py` | Python | Simulation exit/slippage/spread |
| `engine/backtest_filters.py` | Python | Filtres session / corrélation USD |
| `engine/backtest_stats.py` | Python | Métriques : Sharpe, drawdown, PF |
| `engine/backtest_export.py` | Python | Export CSV + courbe equity |
| `engine/dashboard.py` | Python | Rich terminal UI |
| `engine/web_dashboard.py` | Python | FastAPI REST+WebSocket (standalone) |
| `engine/walk_forward.py` | Python | Walk-forward optimization |
| `engine/monte_carlo.py` | Python | Monte Carlo bootstrap OOS |
| `engine/ml_filter.py` | Python | Shim → _experimental/ml_filter.py |
| `engine/_experimental/ml_filter.py` | Python | ML filter (LogRegression, non intégré) |
| `config/constants.py` | Python | Tous les paramètres numériques |
| `config/loader.py` | Python | YAML config → AppConfig typé |
| `utils/timezone.py` | Python | Helpers DST-aware (zoneinfo uniquement) |
| `utils/session_manager.py` | Python | Fenêtres NYSE/London |
| `utils/alerting.py` | Python | Alerts Telegram + Discord |
| `utils/logger.py` | Python | Loguru UTC + Paris dual-time |
| `utils/state_persistence.py` | Python | daily_state.json (écriture atomique) |
| `utils/news_filter.py` | Python | Filtre news haute-impact |
| `utils/pair_correlation.py` | Python | Filtre corrélation USD |
| `utils/volatility_regime.py` | Python | Régime ATR marché |

---

## Paramètres Clés (source: constants.py)

| Paramètre | Valeur | Fichier |
|-----------|--------|---------|
| RR ratio défaut | 2.5 | `DEFAULT_RR_RATIO` |
| Risk % par trade | 2.0% | `DEFAULT_RISK_PCT` |
| Max daily loss | 3.0% | `DEFAULT_MAX_DAILY_LOSS_PCT` |
| Max trades/session | 2 | `DEFAULT_MAX_TRADES_PER_SESSION` |
| Max spread | 2.0 pips | `DEFAULT_MAX_SPREAD_PIPS` |
| FCR min range | 8.0 pips | `DEFAULT_MIN_RANGE_PIPS` |
| FCR lookback | 6 bougies M5 | `DEFAULT_FCR_LOOKBACK` |
| ATR period | 14 | `DEFAULT_ATR_PERIOD` |
| ATR min ratio | 2.0× | `DEFAULT_MIN_ATR_RATIO` |
| Volume ratio min | 1.0× | `DEFAULT_MIN_VOLUME_RATIO` |
| Session NYSE | 9:30–10:30 EST | `SESSION_START_*` / `SESSION_END_*` |
| Session London | 8:00–9:00 UTC | `LONDON_START_*` / `LONDON_END_*` |
| IB rate limit | 45 req/s sustained, burst 10 | `IB_TOKEN_BUCKET_*` |
| IB paper port | 4002 | `IB_PAPER_PORT` |
| IB live port | 4001 | `IB_LIVE_PORT` |

---

## Ce qui ne doit PAS changer sans benchmark

- `DEFAULT_RR_RATIO` : backtest de référence Sharpe ≥ baseline
- `DEFAULT_MIN_RANGE_PIPS` : sensibilité détection FCR mesurée
- `DEFAULT_ATR_PERIOD` + `DEFAULT_MIN_ATR_RATIO` : filtre volatilité calibré
- Toute logique dans `core/*.pyx` : stratégie propriétaire

---

## Paires supportées

`EURUSD`, `GBPUSD`, `USDJPY`, `AUDUSD`, `USDCAD`, `USDCHF`, `NZDUSD`, `EURJPY`, `GBPJPY`, `EURGBP`

Pip sizes : 0.0001 standard, 0.01 pour paires JPY.

---

## Architecture de test

- `alphaedge/core/_stubs/` : stubs Python purs (pas de Cython requis en test)
- `alphaedge/tests/` : 574 tests, couverture ≥ 80%
- `engine/` exclu de la couverture (nécessite IB Gateway)
- `make qa` : ruff + pyright + pytest --cov-fail-under=80
