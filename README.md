<div align="center">

# ⚡ ALPHAEDGE

**Automated Forex trading bot · NYSE open session · Paper trading by default**

[![CI](https://github.com/Blockprod/ALPHA-EDGE/actions/workflows/ci.yml/badge.svg)](https://github.com/Blockprod/ALPHA-EDGE/actions)
![Python](https://img.shields.io/badge/Python-3.11.9-informational?style=flat&logo=python&logoColor=white&color=3776AB)
![Mode](https://img.shields.io/badge/Mode-Paper%20Trading-informational?style=flat&color=2ea44f)
![Broker](https://img.shields.io/badge/Broker-Interactive%20Brokers-informational?style=flat&color=E31837)
![Coverage](https://img.shields.io/badge/Coverage-%E2%89%A580%25-informational?style=flat&color=4CAF50)

</div>

---

## ⚡ What is ALPHAEDGE?

Momentum + carry signal on EURUSD · GBPUSD · USDJPY during the NYSE open
(15:30–16:30 CET). Executes bracket orders via IB Gateway with compound
position sizing. Paper trading by default — live mode requires explicit
confirmation.

---

## 📊 Baseline (2026-04-02 · 3-year backtest)

| Metric | In-Sample | Out-of-Sample |
|--------|:---------:|:-------------:|
| Sharpe | **3.06** | 2.59 |
| Max Drawdown | **6.72%** | 14.33% |
| Profit Factor | 1.48 | 1.40 |
| Win Rate | 46.7% | 44.8% |
| Trades | 405 | 174 |

$10,000 → $26,879 · +168% · 579 trades total

---

## 🛠 Stack

![Python](https://img.shields.io/badge/Code-Python_3.11-informational?style=flat&logo=python&logoColor=white&color=3776AB)
![Cython](https://img.shields.io/badge/Code-Cython_3.0-informational?style=flat&color=EFC050)
![IB](https://img.shields.io/badge/Broker-ib__insync-informational?style=flat&color=E31837)
![Loguru](https://img.shields.io/badge/Log-loguru-informational?style=flat&color=7B68EE)
![Rich](https://img.shields.io/badge/UI-Rich-informational?style=flat&color=41B3A3)
![vectorbt](https://img.shields.io/badge/Backtest-vectorbt-informational?style=flat&color=FF8C00)

---

## 🚀 Quickstart

```powershell
# 1 — Activate venv
.venv\Scripts\Activate.ps1

# 2 — Install Git hooks (first time only)
make install-hooks

# 3 — Run QA
make qa

# 4 — Backtest
python -m alphaedge.engine.backtest

# 5 — Paper trading (IB Gateway required on port 4002)
python -m alphaedge.engine.strategy --mode paper
```

<details>
<summary>Build Cython extensions</summary>

```powershell
make build   # required after any .pyx edit
```

</details>

---

## License

Proprietary — all rights reserved.

