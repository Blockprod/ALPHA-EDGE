---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: PLAN_ACTION_audit_strategic_alphaedge_2026-03-24.md
derniere_revision: 2026-03-24
creation: 2026-03-24 à 17:30
---

# PLAN D'ACTION — ALPHAEDGE — 2026-03-24
**Créé le :** 2026-03-24 à 17:30
**Sources :** `tasks/audits/resultats/audit_strategic_alphaedge.md` (2026-03-24)
**Score audit :** 3/10 → NO-GO
**Total :** 🔴 7 · 🟠 5 · 🟡 1 · **Effort estimé : 4.5 jours**

> Anomalies couvertes par ce plan : S-03, S-07, S-09, S-10, S-11, S-12, S-13
> Anomalies structurelles (S-01, S-02, S-04, S-05, S-06) → résolution par données/recherche, détaillées en PHASE 4.

---

## PHASE 1 — CRITIQUES 🔴

### [C-01] Suspendre USDJPY — retirer de la liste des paires tradées
**Anomalie :** S-03
Fichier : `config.yaml` (section `trading.pairs`)
Problème : USDJPY PF = 0.47 sur 12 trades — détruit $1,657 USD soit 60% des gains EURUSD. Aucune hypothèse FCR validée sur USDJPY (silence structurel, WR = 25%).
Correction : retirer `USDJPY` de `trading.pairs` dans `config.yaml`. Garder la configuration USDJPY commentée pour reprise future après recalibration.
Validation :
  make qa
  # Attendu : 553 tests verts, aucune erreur config loader
  # Vérifier que config loader accepte 1 seule paire sans erreur
Dépend de : Aucune
Effort : XS (< 15 min)
Statut : ✅ 2026-03-24

---

### [C-02] Diagnostiquer et corriger le silence signal de 9 mois
**Anomalie :** S-07
Fichier : `config.yaml` (section `volatility`, `structure`) + `alphaedge/engine/backtest.py`
Problème : zéro signal depuis juin 2025 (9 mois). Surrestrictivité probable des filtres FCR/ATR sur les régimes post-choc tarifaire. USDJPY sans override `min_atr_ratio` subit le seuil 1.7× le plus restrictif.
Correction en deux sous-étapes :
  1. Lancer un backtest diagnostic EURUSD seul (post-retrait USDJPY via C-01) pour confirmer si le silence persiste sur EURUSD seul post-juin 2025.
  2. Si silence confirmé EURUSD : tester abaissement progressif `volatility.min_atr_ratio` de 1.7 → 1.3 → 1.0, ou assouplissement `structure.fcr_range_cv_max` de 0.5 → 0.6. Changer une variable à la fois, relancer le backtest, comparer PF et N.
Validation :
  make qa
  # Attendu : 553 tests verts
  # Backtest EURUSD seul doit montrer ≥ 1 signal post-juin 2025 pour valider
  # Si aucun signal EURUSD post-juillet 2025 : escalader en recherche (C-06)
Dépend de : C-01
Effort : M (0.5 jour diagnostic + 0.5 jour ajustements)
Statut : ✅ 2026-03-24

**RÉSULTATS DIAGNOSTIC (2026-03-24) :**
- Session EURUSD = London Open 08:00-09:00 UTC (NOT NYSE — critique pour tout diagnostic futur)
- Cache EURUSD : 1 104 165 bars M1, last=2026-03-24 → données complètes 3 ans
- Post-juin 2025 : 210 sessions London Open analysées
  - FCR fail : 186/210 (88.6%) — consolidation pré-session < 8 pips (dominant)
  - CV fail  : 15/210 (7.1%)
  - GAP fail : 3/210 (1.4%)
  - Engulfing OK : 2/210 (0.95%) — mais bloquées par _validate_backtest_signal
- Taux signal London Open : 2.1% pré-juin 2025 → 0.95% post-juin 2025
- Silence structurel confirmé : stratégie basse fréquence, FCR rarement formé à 08:00 UTC
- Bugs corrigés en parallèle :
  - UnicodeEncodeError crash backtest_stats.py — PROJECT_TITLE contient ⚡ (U+26A1)
    → Fix : strip ⚡ dans Text() de print_rich_summary + dashboard.py
- QA post-correction : 1106 tests passed ✅

**CONCLUSION C-02 :** Silence non pathologique — la stratégie est structurellement
basse fréquence sur EURUSD London Open (~1-2% de sessions produisent un signal).
Le "silence de 9 mois" correspond à une période de faible volatilité pré-London Open
(ranges FCR < 8 pips). Pas de correction de paramètres requise sans données
supplémentaires (⚠️ N trop faible pour ajustement paramétrique fiable).
Action suivante recommandée : Phase 4 — ajouter GBPUSD/AUDUSD pour hausse fréquence.

---

## PHASE 2 — MAJEURES 🟠

### [C-03] Instancier EconomicNewsFilter dans run_backtest()
**Anomalie :** S-10
Fichier : `alphaedge/engine/backtest.py` (~ligne 200, `run_backtest()`)
Problème : `config.yaml:news_filter.enabled = true` mais `EconomicNewsFilter` n'est jamais instancié dans `run_backtest()`. Le filtre reste `None` → ignoré silencieusement dans `_collect_session_trades()`. Divergence live/backtest : trades bloqués en live sur HIGH IMPACT peuvent figurer dans les 28 trades CSV.
Correction : dans `run_backtest()`, si `config.news_filter.enabled is True`, instancier `EconomicNewsFilter` depuis les paramètres de config et la passer à `_fetch_pair_trades()` → `_backtest_pair()` → `_collect_session_trades()`. L'import `EconomicNewsFilter` est déjà présent (ligne 72).
Validation :
  make qa
  # Attendu : 553 tests verts, lint propre
  # Vérifier que le backtest tourne sans erreur avec news_filter instancié
  # Comparer le nombre de trades résultant (attendu : ≤ 28 trades)
Dépend de : C-01
Effort : S (0.5 jour)
Statut : ✅ 2026-03-24

---

### [C-04] Activer run_walk_forward() depuis run_backtest()
**Anomalie :** S-11, S-13
Fichier : `alphaedge/engine/backtest.py` (~ligne 61-69, `run_walk_forward` importé)
Problème : `run_walk_forward` est importé mais jamais appelé dans `run_backtest()`. La validation temporelle repose uniquement sur un IS/OOS statique (vulnérable au point de coupure). N_OOS = 9 → non significatif.
Correction : ajouter dans `run_backtest()` un appel optionnel à `run_walk_forward()`, conditionnel à un paramètre `config.backtest.walk_forward_enabled` (à ajouter avec default `false`). Le walk-forward doit s'exécuter après le backtest principal et logguer ses métriques IS/OOS multi-fenêtres.
Validation :
  make qa
  # Attendu : 553 tests verts
  # Activer `walk_forward_enabled: true` dans config.yaml et lancer le backtest
  # Vérifier que le walk-forward produit une sortie lisible
Dépend de : C-03
Effort : S (0.5 jour)
Statut : ✅ 2026-03-24

---

### [C-05] Ajouter filtre direction LONG-only (conditionnel)
**Anomalie :** S-09
Fichier : `config.yaml` (section `trading`) + `alphaedge/engine/backtest.py` (filtre signal)
Problème : SHORT WR = 0% sur N = 4 trades. Biais directionnel FCR en ouverture NYSE : l'impulsion bullish post-FCR absorbe le gap ATR majoritairement en LONG. N = 4 est insuffisant pour conclure, mais la cohérence théorique (gap ATR → LONG en NYSE open) justifie un test.
Correction : ajouter `trading.direction_filter: "LONG"` dans `config.yaml` (default `"ALL"`). Dans `_validate_backtest_signal()` (backtest) et `check_signal_allowed()` (live), rejeter les signaux SHORT si `direction_filter == "LONG"`. Relancer le backtest EURUSD seul avec ce filtre activé.
Validation :
  make qa
  # Attendu : 553 tests verts
  # N résultant EURUSD LONG-only ≈ 9 (WR cible ≥ 50%)
  # PF cible EURUSD LONG-only > 3.0 (baseline EURUSD toutes directions = 3.39)
Dépend de : C-01, C-03
Effort : S (0.5 jour)
Statut : ✅ 2026-03-24

---

### [C-06] Circuit breaker — arrêt préventif après N pertes consécutives
**Anomalie :** S-12
Fichier : `alphaedge/engine/session_lifecycle.py` · `alphaedge/core/_stubs/risk_manager.py`
Problème : 5 pertes consécutives observées (trades 23-27, avr-juin 2025). L'arrêt quotidien (`check_daily_limit`) ne couvre pas le cas d'un glissement progressif multi-sessions.
Correction : ajouter dans `check_daily_limit()` (ou séparément dans `session_lifecycle.py`) un compteur de pertes consécutives (`consecutive_losses`) persistant entre sessions. Si `consecutive_losses ≥ config.risk.max_consecutive_losses` (à définir, défaut = 5), émettre `logger.critical(...)` et halter le trading. Ajouter `max_consecutive_losses: 5` dans `config.yaml:risk`.
Validation :
  make qa
  # Attendu : 553 tests verts
  # Test ciblé : simuler 5 pertes consécutives → vérifier halt et log CRITICAL
Dépend de : Aucune
Effort : S (0.5 jour)
Statut : ✅ 2026-03-24

---

## PHASE 3 — MINEURES 🟡

### [C-07] Configurer walk_forward_enabled dans config.yaml
**Anomalie :** S-13 (couvert conjointement par C-04)
Fichier : `config.yaml` (section `backtest`)
Problème : pas de clé `walk_forward_enabled` dans config. C-04 en dépend.
Correction : ajouter `walk_forward_enabled: false` sous `backtest:` dans `config.yaml`. Le loader doit exposer `config.backtest.walk_forward_enabled` (bool).
Validation :
  make qa
  # Attendu : 553 tests verts, loader sans KeyError
Dépend de : Aucune (prérequis de C-04)
Effort : XS (< 15 min)
Statut : ✅ 2026-03-24

---

## PHASE 4 — ANOMALIES STRUCTURELLES (RECHERCHE / DONNÉES)

> Ces anomalies n'ont pas de correction code directe. Elles nécessitent des données supplémentaires ou une recalibration stratégique.

| ID | Anomalie | Action | Responsable |
|----|----------|--------|-------------|
| S-01 | N = 28 < 30 | Étendre données IB (>3 ans) ou ajouter GBPUSD/EURCAD | Quant |
| S-02 | IC 95% WR inclut 50% | Résolu automatiquement si N augmente (S-01) | Quant |
| S-04 | P&L 261% concentré sur avr 11 2025 (Black Swan) | Documenter l'exclusion optionnelle du jour dans `backtest_stats.py` (flag `exclude_outlier_days`) | À ESTIMER |
| S-05 | PF_OOS = 0.71 | Résolu si N augmente + C-01 (retrait USDJPY) + C-04 (walk-forward multi-fenêtres) | Quant |
| S-06 | N_OOS = 9 < 15 | Résolu si N augmente (S-01) | Quant |
| S-08 | PF global = 1.234 < 1.5 | Réévaluer après C-01 (retrait USDJPY) — EURUSD seul : PF = 3.39 ✅ | Quant |

---

## SÉQUENCE D'EXÉCUTION

```
C-07 (config walk_forward_enabled)
  └─► C-01 (suspendre USDJPY)
        └─► C-02 (diagnostiquer silence signal — backtest EURUSD seul)
              └─► C-03 (instancier EconomicNewsFilter)
                    └─► C-04 (activer walk_forward)
                          └─► C-05 (filtre LONG-only — tester résultat)
C-06 (circuit breaker) — parallèle, indépendant
```

**Priorité absolue :** C-01 → C-03 → C-04 (faible effort, impact immédiat sur validité backtest)

---

## CRITÈRES PASSAGE EN PRODUCTION

- [ ] Zéro 🔴 ouvert
- [ ] `make qa` : 100% pass (lint + mypy + pytest ≥ 80%)
- [ ] USDJPY retiré de `config.yaml:trading.pairs` (C-01)
- [ ] `EconomicNewsFilter` instancié dans `run_backtest()` (C-03)
- [ ] Walk-forward activé et validé sur EURUSD seul (C-04)
- [ ] Backtest EURUSD-only post-corrections : PF > 1.5, N ≥ 20
- [ ] Silence signal post-juin 2025 diagnostiqué (C-02) — au moins 1 signal identifiable
- [ ] `ALPHAEDGE_PAPER=true` intact dans `.env.example`
- [ ] Bracket order `is_valid` vérifié avant envoi IB
- [ ] `check_daily_limit()` + circuit breaker consécutif appelés chaque cycle
- [ ] Paper trading validé 5 sessions NYSE minimum EURUSD seul

---

## TABLEAU DE SUIVI

| ID | Titre | Anomalie | Sévérité | Fichier | Effort | Statut | Date |
|----|-------|----------|----------|---------|--------|--------|------|
| C-07 | Config walk_forward_enabled | S-13 | 🟡 | `config.yaml` | XS | ✅ | 2026-03-24 |
| C-01 | Suspendre USDJPY | S-03 | 🔴 | `config.yaml` | XS | ✅ | 2026-03-24 |
| C-02 | Diagnostiquer silence signal | S-07 | 🔴 | `config.yaml` | M | ✅ | 2026-03-24 |
| C-03 | Instancier EconomicNewsFilter | S-10 | 🟠 | `backtest.py` | S | ✅ | 2026-03-24 |
| C-04 | Activer walk_forward | S-11, S-13 | 🟠 | `backtest.py` | S | ✅ | 2026-03-24 |
| C-05 | Filtre LONG-only | S-09 | 🟠 | `config.yaml` + `backtest.py` | S | ✅ | 2026-03-24 |
| C-06 | Circuit breaker consécutif | S-12 | 🟠 | `backtest.py` | S | ✅ | 2026-03-24 |
