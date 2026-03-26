---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: PLAN_ACTION_audit_pipeline_alphaedge_2026-03-26.md
derniere_revision: 2026-03-26
creation: 2026-03-26 à 00:00
---

# PLAN D'ACTION — ALPHAEDGE — 2026-03-26
Sources : `tasks/audits/resultats/audit_pipeline_alphaedge.md`
Total : 🔴 0 · 🟠 4 · 🟡 3 · Effort estimé : 1.5 jours

---

## PHASE 1 — CRITIQUES 🔴

*Aucune anomalie critique.*

---

## PHASE 2 — MAJEURES 🟠

### [P-01] Mauvais noms d'attributs dans `signal_pipeline.detect_momentum`

Fichier : `alphaedge/engine/signal_pipeline.py:85–86`
Problème : `getattr(trading, "adx_period", ...)` et `getattr(trading, "adx_threshold", ...)` utilisent des noms d'attributs inexistants sur `TradingConfig`. Les attributs réels sont `momentum_adx_period` et `momentum_adx_threshold`. Le `getattr` se rabat systématiquement sur les constantes par défaut (`DEFAULT_ADX_PERIOD=14`, `DEFAULT_ADX_THRESHOLD=25.0`). Tout tuning ADX via `config.yaml` est silencieusement ignoré en live.
Correction : Remplacer les deux `getattr` par l'accès direct aux attributs corrects :
  - `getattr(trading, "adx_period", DEFAULT_ADX_PERIOD)` → `trading.momentum_adx_period`
  - `getattr(trading, "adx_threshold", DEFAULT_ADX_THRESHOLD)` → `trading.momentum_adx_threshold`
  - Supprimer les imports `DEFAULT_ADX_PERIOD` et `DEFAULT_ADX_THRESHOLD` de `signal_pipeline.py` s'ils ne sont plus utilisés.
Validation :
  make qa
  # Attendu : 0 erreurs ruff · 0 erreurs pyright · 585+ tests pass
Dépend de : Aucune
Statut : ⏳

---

### [P-02] Fetch live limité à 30 jours — `momentum_lookback_days` ignoré

Fichier : `alphaedge/engine/session_lifecycle.py:900`
Problème : `_init_session_pairs` fetche les barres daily avec `duration="30 D"` (≈20 barres de trading). `config.trading.momentum_lookback_days = 252` est complètement ignoré. Le signal live est calculé sur une fenêtre 12× plus courte que le signal backtest, produisant des EMA et ADX non stabilisés sur le long terme.
Correction : Remplacer `duration="30 D"` par une durée dérivée de `momentum_lookback_days`. Utiliser une marge calendaire de ×1.5 (252 jours trading ≈ 365 jours calendaires, marge pour weekends/fériés) :
  - Calculer `lookback_days = self._s._config.trading.momentum_lookback_days`
  - `calendar_days = int(lookback_days * 1.5)`
  - Remplacer `duration="30 D"` par `duration=f"{calendar_days} D"`
  - Valeur effective : `252 * 1.5 = 378` → `duration="378 D"` ≈ 15–16 mois de Daily bars.
Validation :
  make qa
  # Attendu : 0 erreurs · 585+ tests pass
  # Vérifier que les tests de session_lifecycle existants passent toujours.
Dépend de : Aucune
Statut : ⏳

---

### [P-03] Carry conflict check absent du chemin d'exécution live

Fichier : `alphaedge/engine/strategy.py:~219` / `alphaedge/engine/signal_pipeline.py:103–129`
Problème : `SignalPipeline.get_carry()` et `is_carry_conflict()` sont implémentés dans `signal_pipeline.py` mais ne sont jamais appelés dans le pipeline live. `strategy._detect_momentum()` appelle uniquement `self._signal_pipeline.detect_momentum()`. Si `carry_rates` était peuplé (P-04), les conflits carry ne bloqueraient aucun trade live, contrairement au backtest.
Correction : Dans `strategy._detect_momentum()`, après l'appel à `self._signal_pipeline.detect_momentum()`, ajouter le check carry conflict si `result` est non-None et `config.trading.carry_enabled` :
  - Appeler `self._signal_pipeline.get_carry(state, self._config)` pour obtenir `carry`
  - Si `self._signal_pipeline.is_carry_conflict(result, carry)` → log INFO + retourner `None`
  - Écrire `state.signal_result = None` en cas de conflit (pour que `_on_new_m1_bar` skippe correctement)
Validation :
  make qa
  # Attendu : 0 erreurs · 585+ tests pass
  # Vérifier tests signal_pipeline existants (is_carry_conflict est déjà couvert).
Dépend de : P-04 (recommandé — carry_rates doit être peuplé pour que le check soit opérant)
Statut : ⏳

---

### [P-05] Algorithmes divergents pour `usd_correlation_filter` live vs backtest

Fichier : `alphaedge/engine/session_lifecycle.py:~615–630` / `alphaedge/engine/backtest.py:~259–265` / `alphaedge/engine/backtest_filters.py`
Problème : Le flag `usd_correlation_filter` active deux algorithmes fondamentalement différents :
  - **Live** : `check_signal_allowed` depuis `pair_correlation.py` — bloque un signal si une paire corrélée (corrélation historique des prix) est déjà ouverte.
  - **Backtest** : `_apply_usd_correlation_filter` — supprime les trades qui amplifient l'exposition USD directionnelle (same-direction sur paires USD).
  Ces comportements ne sont pas équivalents et produiraient des résultats divergents si le filtre était activé en multi-paires.
Correction : Documenter explicitement la divergence dans les deux algorithmes avec un commentaire inline expliquant les limites, et créer un ticket/note pour aligner les comportements si le multi-paires est activé. Alternativement, unifier les deux algorithmes sur la même logique (plus complexe, Effort L).
  Option minimale (M) : ajouter un commentaire `# NOTE: algorithme divergent du live — voir P-05` dans `backtest_filters.py` et `session_lifecycle.py`, et une entrée dans `tasks/lessons.md`.
  Option complète (L) : remplacer `_apply_usd_correlation_filter` dans le backtest par la même logique corrélation-pairwise — hors scope de ce plan.
Validation :
  make qa
  # Attendu : 0 erreurs · 585+ tests pass
  # Feature inactive (config false) — aucun résultat fonctionnel à vérifier.
Dépend de : Aucune
Statut : ⏳

---

## PHASE 3 — MINEURES 🟡

### [P-04] `carry.rates:` absent de config.yaml — carry filter inopérant

Fichier : `config.yaml:~106`
Problème : La section `carry:` dans `config.yaml` déclare `enabled: true` mais ne contient pas de clé `rates:`. `loader.py:451` lit `carry_section.get("rates", {})` → `{}`. Le garde `if carry_enabled and carry_rates:` dans le backtest (`backtest.py:536`) échoue systématiquement. Le carry filter est présenté comme actif mais est silencieusement désactivé.
Correction : Ajouter une clé `rates:` commentée dans la section `carry:` de `config.yaml` avec les taux de référence courants (BCE, Fed, BOJ) à titre informatif, clarifiant que la clé doit être peuplée pour activer réellement le filtre :
  ```yaml
  carry:
    enabled: true
    min_differential_pct: 0.5
    # rates: Populate to activate carry filter. Example (update periodically):
    #   EUR: 3.65   # ECB rate
    #   USD: 5.25   # Fed funds rate
    #   JPY: 0.10   # BOJ rate
    #   GBP: 5.25   # BOE rate
    #   AUD: 4.35   # RBA rate
  ```
Validation :
  make qa
  # Attendu : 0 erreurs · 585+ tests pass (config.yaml non parsé par les tests)
Dépend de : Aucune
Statut : ⏳

---

### [P-06] `risk.slippage_buffer_pips` orphelin dans config.yaml

Fichier : `config.yaml:~130` / `alphaedge/config/loader.py:~350–410` / `alphaedge/engine/session_lifecycle.py:105`
Problème : `config.yaml` déclare `risk.slippage_buffer_pips: 0.5` mais ce champ n'est pas lu par `_build_trading_config()` dans `loader.py` et n'existe pas dans `TradingConfig`. En live, `session_lifecycle.py:105` utilise `DEFAULT_MARKET_SLIPPAGE_PIPS` (constante hardcodée) au lieu de la valeur config.
Correction :
  1. Ajouter `slippage_buffer_pips: float = DEFAULT_MARKET_SLIPPAGE_PIPS` dans `TradingConfig` (`loader.py:~205`).
  2. Lire la valeur dans `_build_trading_config()` : `slippage_buffer_pips=float(risk_section.get("slippage_buffer_pips", DEFAULT_MARKET_SLIPPAGE_PIPS))`.
  3. Remplacer `slippage_pips=DEFAULT_MARKET_SLIPPAGE_PIPS` par `slippage_pips=self._s._config.trading.slippage_buffer_pips` dans `session_lifecycle.py:105`.
  4. Vérifier que `DEFAULT_MARKET_SLIPPAGE_PIPS` est bien défini dans `constants.py` (déjà importé dans `session_lifecycle.py`).
Validation :
  make qa
  # Attendu : 0 erreurs · 585+ tests pass
Dépend de : Aucune
Statut : ⏳

---

### [P-07] Code mort dans `_backtest_pair` — trade count toujours 0

Fichier : `alphaedge/engine/backtest.py:527–529`
Problème : Les lignes suivantes constituent du code mort (condition jamais vraie) :
  ```python
  daily_trade_count = 0
  if daily_trade_count >= max_trades_per_session:
      continue
  ```
  `daily_trade_count` est remis à zéro immédiatement avant la vérification — la condition `0 >= 6` est toujours `False`. La limite réelle est correctement appliquée en post-hoc par `_apply_global_session_limit`. Ce code crée une fausse impression que la limite est vérifiée par bar.
Correction : Supprimer les 3 lignes de code mort. La limite `max_trades_per_session` reste correctement appliquée par `_apply_global_session_limit`.
Validation :
  make qa
  # Attendu : 0 erreurs · 585+ tests pass
Dépend de : Aucune
Statut : ⏳

---

## SÉQUENCE D'EXÉCUTION

```
P-07  → P-04  → P-06  → P-01  → P-02  → P-03  → P-05
 ↑         ↑      ↑       ↑       ↑       ↑       ↑
XS        XS     XS      XS      S       XS      M
(dead    (config (loader (attr   (fetch  (carry  (doc)
 code)   doc)    wiring) names)  window) wiring)
```

Note : P-03 est recommandé après P-04 (carry_rates doit être peuplé pour valider le check en pratique). P-05 peut être exécuté en dernier ou différé.

Aucune correction ne touche un fichier `.pyx` — `make build` non requis.

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
| P-01 | Mauvais noms getattr ADX dans signal_pipeline | 🟠 | `signal_pipeline.py:85–86` | XS | ⏳ | — |
| P-02 | Fetch live 30 D — lookback_days ignoré | 🟠 | `session_lifecycle.py:900` | S | ⏳ | — |
| P-03 | Carry conflict check absent du live | 🟠 | `strategy.py:~219` | XS | ⏳ | — |
| P-05 | Algorithmes usd_correlation_filter divergents | 🟠 | `session_lifecycle.py:~615` / `backtest.py:~259` | M | ⏳ | — |
| P-04 | `carry.rates:` absent config.yaml | 🟡 | `config.yaml:~106` | XS | ⏳ | — |
| P-06 | `slippage_buffer_pips` orphelin config.yaml | 🟡 | `config.yaml:~130` / `loader.py` / `session_lifecycle.py:105` | XS | ⏳ | — |
| P-07 | Code mort daily_trade_count dans _backtest_pair | 🟡 | `backtest.py:527–529` | XS | ⏳ | — |
