# ALPHAEDGE — Module Responsibilities

> Source canonique du tableau des modules.
> Référencé par CLAUDE.md. Mis à jour ici uniquement.

| Module | Language | Role |
|--------|----------|------|
| `alphaedge/core/*.pyx` | Cython | Low-latency signal detection + execution logic |
| `alphaedge/engine/strategy.py` | Python | Main async loop, orchestration |
| `alphaedge/engine/broker.py` | Python | IB Gateway connectivity (ib_insync) |
| `alphaedge/engine/data_feed.py` | Python | Real-time bar subscription |
| `alphaedge/engine/backtest.py` | Python | Historical simulation engine |
| `alphaedge/engine/dashboard.py` | Python | Rich terminal UI |
| `alphaedge/config/constants.py` | Python | All magic numbers / thresholds |
| `alphaedge/config/loader.py` | Python | YAML config → typed AppConfig |
| `alphaedge/utils/logger.py` | Python | Loguru setup (UTC + Paris dual-time) |
| `alphaedge/utils/timezone.py` | Python | DST-aware session time helpers |
| `alphaedge/utils/session_manager.py` | Python | NYSE/London session windows |

## Dependency Flow

```
engine/  →  core/  →  config/  →  utils/
```

Top-down uniquement. Aucun import circulaire (vérifié pylint).

## Key Files

| Purpose | File |
|---------|------|
| All trading thresholds | `alphaedge/config/constants.py` |
| Runtime configuration | `config.yaml` |
| Environment variables | `.env.example` |
| Cython build | `setup.py` |
| QA pipeline | `Makefile` + `pyproject.toml` |
| Full technical audit | `docs/ALPHAEDGE_MASTER_AUDIT.md` |
| Open tasks / roadmap | `docs/ALPHAEDGE_STRUCTURAL_ACTION_PLAN.md` |
| AI lessons learned | `tasks/lessons.md` |
| Core interfaces + contracts | `docs/ALPHAEDGE_INTERFACES.md` |

*Mis à jour : 2026-03-24.*
