# ALPHAEDGE — Architecture System Design

---

## Vue d'ensemble

ALPHAEDGE est un bot de trading Forex automatisé ciblant le signal FCR (Fair Competition Range) à l'ouverture de session NYSE et London. Il s'exécute sur Interactive Brokers via IB Gateway.

---

## Pipeline Signal

```
IB Gateway (TWS/IB Gateway)
    │
    ▼
data_feed.py  ─────────────  reqHistoricalData
    │                        M5 (FCR) + M1 (entry)
    │
    ├──► fcr_detector.pyx    FCR range detection
    │    lookback=6 M5 bars  min_range=8 pips
    │    → {range_high, range_low, range_size} | None
    │
    ├──► gap_detector.pyx    ATR spike / volatility filter
    │    atr_period=14       min_atr_ratio=2.0
    │    → {detected, gap_high, gap_low, direction}
    │
    └──► engulfing_detector.pyx  M1 entry signal
         rr_ratio=2.5            volume_ratio=1.0
         → {direction, entry, stop_loss, take_profit} | None
              │
              ├──► risk_manager.pyx  Position sizing
              │    risk_pct=2%       max_daily_loss=3%
              │    → {lot_size, is_valid} | halt_trading=True
              │
              └──► order_manager.pyx  Bracket order
                   spread validation  is_valid guard
                   → {entry, sl, tp, lot_size, is_valid}
                        │
                        ▼
                   broker.py  PlaceOrder → IB Gateway
```

---

## Flux de données

```
config.yaml + .env
    └──► loader.py → AppConfig (typed)
              └──► constants.py (all thresholds)
                        └──► tous les modules
```

---

## Sessions de trading

| Session | Paires | Horaire local | Horaire UTC |
|---------|--------|---------------|-------------|
| NYSE Open | USDJPY | 9:30–10:30 EST/EDT | 14:30–15:30 (été) / 15:30–16:30 (hiver) |
| London Open | EURUSD, GBPUSD | 8:00–9:00 UTC | 8:00–9:00 |

**DST gap** : EU et US changent leurs horaires sur des semaines différentes — offset Paris↔NYSE varie de ±1h pendant ~1 semaine deux fois par an.

---

## Modules Cython (runtime compilé)

| Module `.pyx` | Module runtime | Stub test |
|--------------|----------------|-----------|
| `fcr_detector.pyx` | `fcr_detector.pyd` | `_stubs/fcr_detector.py` |
| `gap_detector.pyx` | `gap_detector.pyd` | `_stubs/gap_detector.py` |
| `engulfing_detector.pyx` | `engulfing_detector.pyd` | `_stubs/engulfing_detector.py` |
| `risk_manager.pyx` | `risk_manager.pyd` | `_stubs/risk_manager.py` |
| `order_manager.pyx` | `order_manager.pyd` | `_stubs/order_manager.py` |

---

## Infrastructure de test

```
alphaedge/tests/        574 tests
    conftest.py         fixtures communes
    test_*.py           1 fichier = 1 scénario
alphaedge/core/_stubs/  stubs Python purs (pas de Cython en CI)
reports/                coverage HTML
```

**Exclusions couverture** : `engine/` (nécessite IB Gateway), `logs/`

---

## QA Pipeline

```
make qa
  ├── ruff check alphaedge/        (lint + isort)
  ├── pyright alphaedge/           (type checking)
  └── pytest --cov-fail-under=80  (574 tests, ≥80% coverage)

make qa-strict
  ├── make qa
  ├── pylint alphaedge/
  └── bandit -r alphaedge/ -ll    (sécurité Medium+)

make build
  └── setup.py build_ext --inplace  (Cython → .pyd)
```
