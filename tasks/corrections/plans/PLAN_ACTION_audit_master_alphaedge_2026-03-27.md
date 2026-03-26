---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: PLAN_ACTION_audit_master_alphaedge_2026-03-27.md
derniere_revision: 2026-03-27
creation: 2026-03-27 à 14:30
---

# PLAN D'ACTION — ALPHAEDGE — 2026-03-27
Sources : `tasks/audits/audit_master_alphaedge.md`
Total : 🔴 0 · 🟠 2 · 🟡 5 · Effort estimé : 1.5 jours

---

## PHASE 1 — CRITIQUES 🔴
*Aucun finding critique.*

---

## PHASE 2 — MAJEURES 🟠

### [C-01] Corriger alert_daily_summary — wins/losses/pnl_usd hardcodés à 0
**Fichier :** `alphaedge/engine/session_lifecycle.py:912-921`
**Problème :** `alert_daily_summary(trades=..., wins=0, losses=0, pnl_usd=0.0)` codé en dur dans `_handle_session_end()`. L'opérateur reçoit une notification de fin de session structurellement fausse chaque jour — wins, losses et pnl_usd sont toujours 0 indépendamment des trades réels.
**Correction :**
1. Avant l'appel `alert_daily_summary`, agréger les métriques depuis `self._s._states` :
   ```python
   wins = sum(
       1 for s in self._s._states.values()
       # live_record is None at session end — use trade outcome tracking
   )
   ```
   Note : les `live_record` sont cleared à `_on_trade_closed`. Implémenter un compteur `wins_today` / `losses_today` / `pnl_usd_today` dans `StrategyState` (init à 0, incrémenté dans `_on_trade_closed` après calcul PnL).
2. Mettre à jour `_on_trade_closed` pour incrémenter ces compteurs après avoir déterminé `outcome` et `pnl_usd`.
3. Passer les valeurs réelles à `alert_daily_summary`.
**Validation :**
```powershell
make qa
# Attendu : 602+ tests pass · 0 Ruff · 0 Pyright
```
**Dépend de :** C-07 (tests de régression)
**Statut :** ✅ Complété — 2026-03-27

---

### [C-02] Bloquer _apply_cli_mode("live") si ALPHAEDGE_PAPER=true en ENV
**Fichier :** `alphaedge/engine/strategy.py:318-327`
**Problème :** `_apply_cli_mode()` set `config.ib.is_paper = False` sans vérifier si `ALPHAEDGE_PAPER=true` est positionné dans l'ENV. Exécuté après `load_config()` qui avait correctement lu l'ENV. Contours le garde primaire documenté.
**Correction :**
```python
def _apply_cli_mode(config: AppConfig, mode: str) -> None:
    """Apply an explicit CLI trading mode to the loaded config."""
    if mode == "paper":
        config.ib.is_paper = True
        config.ib.port = IB_PAPER_PORT
        config.mode = "paper"
        return

    # Guard: ALPHAEDGE_PAPER=true ENV overrides CLI --mode live
    env_paper = os.getenv("ALPHAEDGE_PAPER", "true").strip().lower()
    if env_paper == "true":
        print(
            "ERROR: ALPHAEDGE_PAPER=true is set in environment. "
            "Cannot switch to live mode via CLI. "
            "Unset ALPHAEDGE_PAPER to enable live trading."
        )
        raise SystemExit(1)

    config.ib.is_paper = False
    config.ib.port = IB_LIVE_PORT
    config.mode = "live"
```
Vérifier que `os` est déjà importé dans `strategy.py` (oui — standard lib).
**Validation :**
```powershell
make qa
# Attendu : 602+ tests pass · 0 Ruff · 0 Pyright
```
**Dépend de :** C-07 (tests de régression)
**Statut :** ✅ Complété — 2026-03-27

---

## PHASE 3 — MINEURES 🟡

### [C-03] Supprimer les 3 fichiers .pyx orphelins FCR legacy
**Fichiers :**
- `alphaedge/core/fcr_detector.pyx`
- `alphaedge/core/fcr_detector.c`
- `alphaedge/core/gap_detector.pyx`
- `alphaedge/core/gap_detector.c`
- `alphaedge/core/engulfing_detector.pyx`
- `alphaedge/core/engulfing_detector.c`
**Problème :** Fichiers FCR legacy non compilés (absents de `setup.py`), sans stubs dans `_stubs/`, non importés dans `core/__init__.py`. Code mort depuis la migration Momentum+Carry. Créent de la confusion à la maintenance et gonflent le repo de 6 fichiers inutiles.
**Correction :**
1. Supprimer les 6 fichiers listés ci-dessus.
2. Ajouter une entrée dans `architecture/decisions.md` : "ADR-XXX — Suppression modules FCR legacy (fcr_detector, gap_detector, engulfing_detector) — 2026-03-27 — Motivation : migration vers Momentum+Carry (audit #13)."
**Validation :**
```powershell
make qa
# Attendu : 602+ tests pass · 0 Ruff · 0 Pyright
# Vérifier : alphaedge/core/ ne contient plus que momentum_detector, risk_manager, order_manager (.pyx + .c + _stubs/)
```
**Dépend de :** Aucune
**Statut :** ✅ Complété — 2026-03-27

---

### [C-04] Mettre à jour la documentation stale (pyproject.toml + .gitignore)
**Fichiers :**
- `pyproject.toml:4` — `description = "ALPHAEDGE — FCR Forex Trading Bot"`
- `pyproject.toml:16` — `description = "ALPHAEDGE — FCR Forex Trading Bot"`
- `.gitignore:4` — commentaire header "FCR Forex Trading Bot"
- `setup.py` — header commentaire projet (si applicable)
**Problème :** La description du projet dans `pyproject.toml` et le header `.gitignore` décrivent encore "FCR Forex Trading Bot" alors que la stratégie est Momentum+Carry depuis la migration (audit #13).
**Correction :**
Remplacer "FCR Forex Trading Bot" par "Momentum+Carry Forex Trading Bot" dans :
- `pyproject.toml:4` (section `[project]`)
- `pyproject.toml:16` (si doublon confirmé — vérifier avant)
- `.gitignore:4` (commentaire header)
- `setup.py:7` (commentaire "FCR Forex Trading Bot" en header)
**Validation :**
```powershell
make qa
# Attendu : 602+ tests pass · 0 Ruff · 0 Pyright
```
**Dépend de :** Aucune
**Statut :** ✅ Complété — 2026-03-27

---

### [C-05] Remplacer EUR_USD_RATE constant par config.trading.eur_usd_rate dans le live
**Fichier :** `alphaedge/engine/session_lifecycle.py:27,415,881`
**Problème :** `EUR_USD_RATE = 1.08` importé depuis `constants.py` et utilisé dans `_on_trade_closed` (ligne 415) et `_handle_session_end` (ligne 881) pour calculer `pnl_eur`. Le backtest utilise `config.trading.eur_usd_rate` (configurable via `config.yaml:eur_usd_rate`). Sources de vérité divergentes : si le taux réel s'éloigne de 1.08, le journal live indique un `pnl_eur` faux.
**Correction :**
1. Dans `session_lifecycle.py`, remplacer les 2 utilisations de `EUR_USD_RATE` par `self._s._config.trading.eur_usd_rate`.
2. Supprimer l'import `EUR_USD_RATE` de `constants.py` dans ce fichier (ligne 27) si plus utilisé nulle part ailleurs dans `session_lifecycle.py`.
3. Conserver `EUR_USD_RATE` dans `constants.py` — il reste la valeur de fallback du dataclass `TradingConfig`.
**Validation :**
```powershell
make qa
# Attendu : 602+ tests pass · 0 Ruff · 0 Pyright
```
**Dépend de :** Aucune
**Statut :** ✅ Complété — 2026-03-27

---

### [C-06] Documenter la divergence corrélation live/backtest dans l'action plan structurel
**Fichier :** `docs/ALPHAEDGE_STRUCTURAL_ACTION_PLAN.md`
**Problème :** L'algorithme de corrélation live (matrice Pearson ρ via `pair_correlation.py`) diffère de l'algorithme backtest (exposition USD directionnelle dans `backtest.py`). Documenté en commentaire `# NOTE` dans `session_lifecycle.py:~625`, mais non tracké comme dette ouverte dans le plan structurel.
**Correction :**
Ajouter une entrée dans `docs/ALPHAEDGE_STRUCTURAL_ACTION_PLAN.md` :
```
## Corrélation live/backtest — Divergence algorithme (🟡 Mineur)
Source : audit_master_alphaedge.md — M-06
Statut : Dette connue — à traiter avant activation multi-paire
Fichiers : session_lifecycle.py:~625 · backtest.py
Description : live = matrice Pearson ρ ; backtest = exposition USD directionnelle.
Impact : résultats backtest non reproductibles en live si multi-paire activé.
Action : aligner les deux algorithmes avant tout déploiement multi-paire.
```
**Validation :** Vérification manuelle — pas de `make qa` requis (fichier `.md` uniquement).
**Dépend de :** Aucune
**Statut :** ✅ Complété — 2026-03-27

---

### [C-07] Ajouter tests de régression pour C-01 et C-02
**Fichier :** `alphaedge/tests/` (nouveaux fichiers)
**Problème :** Les bugs M-01 et M-02 n'ont pas de tests de régression. Sans tests, les corrections C-01 et C-02 pourraient régresser silencieusement.
**Correction :**
Créer 2 fichiers de test :

**`test_session_lifecycle_daily_summary.py`** — vérifie que `_handle_session_end` agrège wins/losses/pnl_usd correctement depuis les états trades (mock `StrategyState` avec 2 trades : 1 win +50 USD, 1 loss -20 USD → assert wins=1, losses=1, pnl_usd=30.0).

**`test_strategy_cli_mode_paper_guard.py`** — vérifie que `_apply_cli_mode("live")` lève `SystemExit` si `ALPHAEDGE_PAPER=true` est dans l'ENV. Utilise `monkeypatch.setenv("ALPHAEDGE_PAPER", "true")`.

**Validation :**
```powershell
make qa
# Attendu : 604+ tests pass · 0 Ruff · 0 Pyright
# Les 2 nouveaux tests doivent être dans les résultats
```
**Dépend de :** C-01, C-02 (créer les tests après les corrections pour éviter les faux négatifs)
**Statut :** ✅ Complété — 2026-03-27

---

## SÉQUENCE D'EXÉCUTION

```
C-03  →  C-04  →  C-05            # Indépendants — pas de dépendances croisées
C-02                               # Guard ENV live — aucune dépendance
C-01                               # Nécessite compteurs dans StrategyState
C-07                               # Tests de régression — après C-01 et C-02
C-06                               # Documentation pure — en dernier
```

**Ordre recommandé :**
1. C-03 — Suppression fichiers orphelins (irréversible mais sans risque code)
2. C-04 — Mise à jour documentation stale (trivial)
3. C-05 — Remplacement EUR_USD_RATE (1 ligne × 2)
4. C-02 — Guard ENV dans `_apply_cli_mode` (critique pour la sécurité)
5. C-01 — Agrégation wins/losses/pnl_usd (plus complexe — ajouter champs StrategyState)
6. C-07 — Tests de régression pour C-01 et C-02
7. C-06 — Documentation dette corrélation

> ⚠️ Aucun `.pyx` modifié dans ce plan — `make build` non requis.

---

## CRITÈRES PASSAGE EN PRODUCTION
- [ ] Zéro 🔴 ouvert
- [ ] `make qa` : 100% pass (lint + mypy + pytest ≥80%)
- [ ] Zéro credential dans les logs loguru
- [ ] `ALPHAEDGE_PAPER=true` intact dans `.env.example`
- [ ] Bracket order `is_valid` vérifié avant envoi IB
- [ ] `check_daily_limit()` appelé chaque cycle
- [ ] Paper trading validé 5 sessions NYSE minimum

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier | Effort | Statut | Date |
|----|-------|----------|---------|--------|--------|------|
| C-01 | alert_daily_summary — valeurs réelles | 🟠 Majeur | `session_lifecycle.py:912-921` | 2h | ⏳ | — |
| C-02 | Guard ENV dans _apply_cli_mode("live") | 🟠 Majeur | `strategy.py:318-327` | 30min | ⏳ | — |
| C-03 | Supprimer .pyx orphelins FCR legacy | 🟡 Mineur | `core/*.pyx` + `core/*.c` | 20min | ⏳ | — |
| C-04 | Mise à jour doc stale pyproject + gitignore | 🟡 Mineur | `pyproject.toml` · `.gitignore` · `setup.py` | 10min | ⏳ | — |
| C-05 | EUR_USD_RATE → config.trading.eur_usd_rate | 🟡 Mineur | `session_lifecycle.py:415,881` | 20min | ⏳ | — |
| C-06 | Documenter divergence corrélation live/backtest | 🟡 Mineur | `ALPHAEDGE_STRUCTURAL_ACTION_PLAN.md` | 10min | ⏳ | — |
| C-07 | Tests régression C-01 et C-02 | 🟡 Mineur | `alphaedge/tests/` (2 nouveaux fichiers) | 1h | ⏳ | — |
