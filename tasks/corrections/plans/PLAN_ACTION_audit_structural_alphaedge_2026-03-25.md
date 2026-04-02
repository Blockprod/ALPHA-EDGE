---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: PLAN_ACTION_audit_structural_alphaedge_2026-03-25.md
derniere_revision: 2026-03-25
creation: 2026-03-25
---

# PLAN D'ACTION — ALPHAEDGE — 2026-03-25
Sources : `tasks/audits/audit_structural_alphaedge.md`
Total : 🔴 2 · 🟠 4 · 🟡 4 · Effort estimé : 1.5 jours

---

## PHASE 1 — CRITIQUES 🔴

### [C-01] Supprimer `_fetch_pre_session_data()` — flux M5/M1 FCR résiduel

Fichier : `alphaedge/engine/strategy.py:200-219` + `alphaedge/engine/session_lifecycle.py:810`
Problème : `_fetch_pre_session_data()` envoie des requêtes M5+M1 à IB à chaque session live.
Ces données ne sont consommées par aucune étape du pipeline Momentum+Carry.
La méthode utilise `self._config.trading.fcr_lookback_candles` (paramètre FCR orphelin).
Correction :
  1. Supprimer la méthode `_fetch_pre_session_data()` dans `strategy.py`
  2. Supprimer l'appel à cette méthode dans `session_lifecycle.py:810`
  3. Supprimer le champ `entry_timeframe` de TradingConfig si son seul usage était cette méthode
  4. Vérifier qu'aucun autre site n'appelle `_fetch_pre_session_data()`
  5. Vérifier que `state.m5_candles`, `state.pre_session_m1_candles`, `state.m1_candles` ne sont plus peuplés
Validation :
  grep -r "_fetch_pre_session_data" alphaedge/   # doit retourner aucun résultat
  grep -r "m5_candles\|pre_session_m1_candles" alphaedge/engine/  # doit retourner aucun résultat
  make qa
  # Attendu : 0 erreurs lint/mypy/ruff · tests verts
Dépend de : Aucune
Statut : ✅

---

### [C-02] Supprimer `fcr_lookback_candles` de TradingConfig

Fichier : `alphaedge/config/loader.py:188,387,495-497`
Problème : `fcr_lookback_candles` est un paramètre FCR actif — lu depuis config.yaml,
validé au démarrage, mais dont le seul consommateur est `_fetch_pre_session_data()` (C-01 → supprimé).
Correction :
  1. Supprimer le champ `fcr_lookback_candles: int = 6` dans la dataclass `TradingConfig` (loader.py:188)
  2. Supprimer la ligne d'assignation `fcr_lookback_candles=int(...)` dans `_build_trading_config()` (loader.py:387)
  3. Supprimer le bloc de validation `if cfg.fcr_lookback_candles <= 0:` (loader.py:495-497)
  4. Vérifier config.yaml — si `structure.lookback_candles` n'est plus lu, documenter ou supprimer
  5. Vérifier qu'aucun autre module n'accède à `.fcr_lookback_candles`
Validation :
  grep -r "fcr_lookback_candles" alphaedge/  # doit retourner aucun résultat
  make qa
  # Attendu : 0 erreurs · tests verts
Dépend de : C-01 (doit être fait en second pour ne pas casser strategy.py en attente)
Statut : ✅

---

## PHASE 2 — MAJEURES 🟠

### [C-03] Supprimer les champs FCR orphelins de StrategyState

Fichier : `alphaedge/engine/strategy.py:52-54`
Problème : `m5_candles`, `pre_session_m1_candles`, `m1_candles` sont trois champs
dans la dataclass `StrategyState` qui ne sont plus peuplés après la suppression de C-01.
Ils polluent l'interface de `StrategyState` et créent de la confusion.
Correction :
  1. Supprimer les trois champs de la dataclass `StrategyState`
  2. Vérifier qu'aucun fichier du projet ne référence ces champs
  3. Si `StrategyState` est utilisée comme type dans les stubs, mettre à jour
Validation :
  grep -r "m5_candles\|pre_session_m1_candles\|m1_candles" alphaedge/  # aucun résultat attendu
  make qa
  # Attendu : 0 erreurs · tests verts
Dépend de : C-01
Statut : ✅

---

### [C-04] Remplacer `rr_ratio=3.0` hardcodé par `DEFAULT_RR_RATIO`

Fichier : `alphaedge/engine/backtest.py:635,716`
Problème : `rr_ratio: float = 3.0` est passé comme valeur par défaut dans deux fonctions.
`DEFAULT_RR_RATIO` dans `constants.py` vaut `2.5` — divergence silencieuse entre backtest et config.
Correction :
  1. Ajouter `from alphaedge.config.constants import DEFAULT_RR_RATIO` si non déjà importé
  2. Remplacer `rr_ratio: float = 3.0` par `rr_ratio: float = DEFAULT_RR_RATIO` aux lignes 635 et 716
  3. Vérifier que les tests existants qui passent `rr_ratio` explicitement ne sont pas impactés
Validation :
  grep -n "rr_ratio.*3\.0" alphaedge/engine/backtest.py  # aucun résultat attendu
  make qa
  # Attendu : 0 erreurs · tests verts
Dépend de : Aucune
Statut : ✅

---

### [C-05] Nommer la constante du fallback pip_size

Fichier : `alphaedge/config/constants.py` + `alphaedge/engine/backtest.py:312,483,668` + `alphaedge/engine/session_lifecycle.py:306,527,674,813`
Problème : `PIP_SIZES.get(pair, 0.0001)` utilise `0.0001` comme fallback non nommé en 7 endroits.
Si une paire sans entrée dans `PIP_SIZES` est configurée, ce fallback s'applique silencieusement.
Correction :
  1. Ajouter dans `constants.py` : `DEFAULT_PIP_SIZE: float = 0.0001  # fallback pip size (non-JPY pair)`
  2. Remplacer les 7 occurrences de `PIP_SIZES.get(pair, 0.0001)` par `PIP_SIZES.get(pair, DEFAULT_PIP_SIZE)`
  3. Ajouter l'import dans les fichiers concernés si nécessaire
Validation :
  grep -n "get(pair, 0\.0001)" alphaedge/  # aucun résultat attendu
  make qa
  # Attendu : 0 erreurs · tests verts
Dépend de : Aucune
Statut : ✅

---

### [C-06] Documenter les cycles d'imports engine/ (mitigation TYPE_CHECKING)

Fichier : `alphaedge/engine/strategy.py:28-31` + `signal_pipeline.py:24` + `position_manager.py:21` + `session_lifecycle.py:61`
Problème : Les cycles tripartites `strategy ↔ signal_pipeline`, `strategy ↔ position_manager`,
`strategy ↔ session_lifecycle` sont réels mais contenus par TYPE_CHECKING.
Le cycle `sensitivity.py ↔ backtest.py` est déclaré via `# pylint: disable=cyclic-import`.
La fragilité est structurelle : un import mal placé hors TYPE_CHECKING peut casser l'application silencieusement.
Correction :
  1. Dans chaque fichier concerné, ajouter un commentaire `# NOTE: import cycle mitigated by TYPE_CHECKING`
     juste au-dessus des imports qui créent le cycle (strategy.py:28-31, signal_pipeline.py:24,
     position_manager.py:21, session_lifecycle.py:61)
  2. S'assurer que les imports dans les corps de fonctions restent sous guard `if TYPE_CHECKING`
  3. ⚠️ Refactoring complet (extraction d'une base abstraite) : effort L — hors périmètre de ce plan
Note : Cette correction est documentaire, aucune logique ne change.
Validation :
  make qa
  # Attendu : 0 erreurs · tests verts
Dépend de : Aucune
Statut : ✅

---

## PHASE 3 — MINEURES 🟡

### [C-07] Ajouter `alphaedge/logs/*.txt` au `.gitignore`

Fichier : `.gitignore` racine
Problème : Les fichiers `backtest_result.txt`, `bt_final.txt`, `bt_full.txt`, `bt_stderr.txt`, `opt.txt`
dans `alphaedge/logs/` ne sont pas couverts par les règles `.gitignore` actuelles (`*.log` seulement).
Correction :
  Ajouter à `.gitignore` :
  ```
  alphaedge/logs/*.txt
  ```
Validation :
  git status  # les *.txt de alphaedge/logs/ ne doivent plus apparaître en untracked
  make qa
  # Attendu : 0 erreurs · tests verts
Dépend de : Aucune
Statut : ✅

---

### [C-08] Ajouter les artefacts sweep au `.gitignore`

Fichier : `.gitignore` racine + `scripts/` (sweep_output.txt, targeted_sweep.txt, sweep_done.txt)
Problème : Les fichiers de résultats de sweep dans `scripts/` ne sont pas couverts par `.gitignore`.
Correction :
  Ajouter à `.gitignore` :
  ```
  scripts/sweep_output.txt
  scripts/targeted_sweep.txt
  scripts/sweep_done.txt
  ```
  Ou en glob : `scripts/sweep*.txt` + `scripts/*_done.txt`
Validation :
  git status  # ces fichiers ne doivent plus apparaître en untracked
Dépend de : Aucune
Statut : ✅

---

### [C-09] Corriger le header/docstring FCR dans `backtest_filters.py`

Fichier : `alphaedge/engine/backtest_filters.py:1-14`
Problème : Le header et la docstring du fichier mentionnent "FCR/M1/M5"
alors que les fonctions restantes (`_apply_global_session_limit`, `_apply_usd_correlation_filter`)
sont génériques et compatibles Momentum+Carry.
Correction :
  Mettre à jour le header et la docstring pour refléter la stratégie Momentum+Carry.
  Supprimer les références à FCR, M1, M5 dans le module docstring.
Validation :
  make qa
  # Attendu : 0 erreurs · tests verts
Dépend de : Aucune
Statut : ✅

---

### [C-10] Corriger les headers "Momentum+Carry Forex Trading Bot" dans 8 fichiers

Fichier :
  - `alphaedge/engine/data_feed.py:1,11`
  - `alphaedge/engine/broker.py:1,11`
  - `alphaedge/engine/position_manager.py:1`
  - `alphaedge/config/constants.py:1,19`
  - `alphaedge/core/__init__.py:1,14`
Problème : Les headers de module mentionnent encore "Momentum+Carry Forex Trading Bot"
créant de la confusion lors des revues de code.
Correction :
  Remplacer "Momentum+Carry Forex Trading Bot" par "Momentum+Carry Forex Trading Bot"
  (ou "ALPHAEDGE — Momentum+Carry Strategy") dans les headers/docstrings de ces fichiers.
Validation :
  grep -r "Momentum+Carry Forex Trading Bot" alphaedge/  # aucun résultat attendu
  make qa
  # Attendu : 0 erreurs · tests verts
Dépend de : Aucune
Statut : ✅

---

## SÉQUENCE D'EXÉCUTION

```
C-02 (pre-check: lire les fichiers) → C-01 → C-02 → C-03   [Phase 1 — bloqués entre eux]
    ↓
C-04 · C-05 · C-06   [Phase 2 — indépendants, exécutables en parallèle]
    ↓
C-07 · C-08 · C-09 · C-10   [Phase 3 — indépendants, rapides]
    ↓
make qa (validation finale)
```

**Ordre strict Phase 1 :**
1. C-01 → supprimer `_fetch_pre_session_data()` et l'appel dans session_lifecycle.py
2. C-02 → supprimer `fcr_lookback_candles` (plus aucun consommateur après C-01)
3. C-03 → supprimer les champs FCR de StrategyState (dépend de C-01)

**Aucun fichier `.pyx` touché dans ce plan → `make build` non requis.**

---

## CRITÈRES PASSAGE EN PRODUCTION

- [ ] Zéro 🔴 ouvert
- [ ] `make qa` : 100% pass (lint + mypy + pytest ≥80%)
- [ ] Zéro credential dans les logs loguru
- [ ] `ALPHAEDGE_PAPER=true` intact dans `.env.example`
- [ ] Bracket order `is_valid` vérifié avant envoi IB
- [ ] `check_daily_limit()` appelé chaque cycle
- [ ] Aucune requête M5/M1 parasite vers IB en session live (C-01 validé)
- [ ] `fcr_lookback_candles` absent de TradingConfig (C-02 validé)
- [ ] Paper trading validé 5 sessions NYSE minimum

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier principal | Effort | Statut | Date |
|----|-------|----------|-------------------|--------|--------|------|
| C-01 | Supprimer `_fetch_pre_session_data()` | 🔴 | `strategy.py:200-219` | M (< 1j) | ✅ | 2026-03-25 |
| C-02 | Supprimer `fcr_lookback_candles` TradingConfig | 🔴 | `loader.py:188,387,495` | S (< 4h) | ✅ | 2026-03-25 |
| C-03 | Supprimer champs FCR orphelins StrategyState | 🟠 | `strategy.py:52-54` | XS (< 1h) | ✅ | 2026-03-25 |
| C-04 | `rr_ratio=3.0` → `DEFAULT_RR_RATIO` | 🟠 | `backtest.py:635,716` | XS (< 1h) | ✅ | 2026-03-25 |
| C-05 | Nommer constante fallback pip_size | 🟠 | `constants.py` + 7 sites | XS (< 1h) | ✅ | 2026-03-25 |
| C-06 | Documenter cycles d'imports engine/ | 🟠 | `strategy.py:28-31` + 3 | XS (< 1h) | ✅ | 2026-03-25 |
| C-07 | `.gitignore` — alphaedge/logs/*.txt | 🟡 | `.gitignore` | XS (< 15min) | ✅ | 2026-03-25 |
| C-08 | `.gitignore` — scripts/sweep*.txt | 🟡 | `.gitignore` | XS (< 15min) | ✅ | 2026-03-25 |
| C-09 | Header backtest_filters.py FCR→Momentum | 🟡 | `backtest_filters.py:1-14` | XS (< 15min) | ✅ | 2026-03-25 |
| C-10 | Headers "Momentum+Carry Forex Trading Bot" × 8 fichiers | 🟡 | 5 fichiers | XS (< 30min) | ✅ | 2026-03-25 |
