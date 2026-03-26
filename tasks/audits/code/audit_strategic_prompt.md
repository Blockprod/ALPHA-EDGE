---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: audit_strategic_alphaedge.md
derniere_revision: 2026-03-25
creation: 2026-03-20 à 15:32
---

#codebase

Tu es un Quantitative Researcher spécialisé en trading
algorithmique Forex, stratégie Momentum+Carry et analyse
statistique de stratégies.
Tu réalises un audit STRATÉGIQUE complet sur ALPHAEDGE.

Ton objectif : déterminer si la stratégie Momentum+Carry génère un
edge statistiquement réel, si ses filtres sont correctement
calibrés, et si elle est prête pour le paper trading.

─────────────────────────────────────────────
ÉTAPE 0 — VÉRIFICATION PRÉALABLE (OBLIGATOIRE)
─────────────────────────────────────────────
Vérifie si ce fichier existe déjà :
  tasks/audits/resultats/audit_strategic_alphaedge.md

Si trouvé, affiche :
"⚠️ Audit stratégique existant détecté :
 Fichier : tasks/audits/resultats/audit_strategic_alphaedge.md
 Date    : [date modification]

 [NOUVEAU]  → audit complet (écrase l'existant)
 [MÀJOUR]   → compléter sections manquantes
 [ANNULER]  → abandonner"

Si absent → démarrer directement :
"✅ Aucun audit stratégique existant. Démarrage..."

─────────────────────────────────────────────
SOURCES DE DONNÉES — LIRE EN PREMIER
─────────────────────────────────────────────
Lis ces fichiers avant de rédiger quoi que ce soit :

1. reports/ALPHAEDGE_backtest_results.csv   ← trades réels du dernier backtest
2. config.yaml                              ← paramètres actifs de la stratégie
3. alphaedge/config/constants.py            ← defaults et valeurs de référence
4. alphaedge/engine/signal_pipeline.py      ← pipeline Momentum+Carry
5. alphaedge/engine/backtest.py             ← simulation
6. alphaedge/engine/carry_signal.py         ← filtre carry bias
7. alphaedge/engine/backtest_stats.py       ← calcul des métriques IS/OOS
8. alphaedge/engine/backtest_simulation.py  ← modélisation des coûts
9. alphaedge/engine/session_lifecycle.py    ← pipeline live (coûts, spreads)
10. alphaedge/core/_stubs/risk_manager.py   ← interfaces risk
11. alphaedge/core/_stubs/order_manager.py  ← interfaces ordre
12. alphaedge/engine/position_manager.py    ← sizing live

─────────────────────────────────────────────
PÉRIMÈTRE STRICT
─────────────────────────────────────────────
ANALYSE :
- Validité statistique de l'edge Momentum+Carry
- Fréquence et continuité du signal
- Performance par paire, direction et régime temporel
- Robustesse IS/OOS
- Calibration des filtres (momentum, carry, news)
- Modélisation des coûts (spread, slippage)
- Risk management financier
- Cohérence critique backtest ↔ live

N'ANALYSE PAS : sécurité, concurrence, Cython interne, CI/CD, modules.

─────────────────────────────────────────────
CONTRAINTES ABSOLUES
─────────────────────────────────────────────
- Lis reports/ALPHAEDGE_backtest_results.csv — c'est le jeu de données principal
- Cite fichier:ligne pour CHAQUE point factuel
- Conclus chaque sous-section par : CONFORME / NON CONFORME / À VÉRIFIER
- Calcule les métriques depuis le CSV — ne les invente jamais
- Écris "À VÉRIFIER" quand la preuve est absente du code
- Ne déduis PAS la logique interne des .pyx — traite leurs interfaces comme boîtes noires
- Ne lis PAS les fichiers .md / .rst

─────────────────────────────────────────────
BLOC 1 — VALIDITÉ STATISTIQUE DE L'EDGE
─────────────────────────────────────────────
Source : reports/ALPHAEDGE_backtest_results.csv

1.1 Taille d'échantillon
    - Nombre total de trades (N) sur la période testée ?
    - N ≥ 100 ? Si non, noter explicitement le risque statistique.
    - Calcule l'intervalle de confiance à 95% sur le win rate :
        WR ± 1.96 × sqrt(WR × (1 − WR) / N)
    - Si l'IC à 95% inclut 50% → 🔴 (edge non prouvé statistiquement)
    - Si N < 30 → 🔴 ; si 30 ≤ N < 60 → 🟠 ; si 60 ≤ N < 100 → 🟡

1.2 Métriques d'edge
    - Win rate global (%)
    - Profit factor (PF) — seuil minimal viable : PF ≥ 1.5
    - Expectancy pips/trade : (WR × avg_win_pips) − (1 − WR) × avg_loss_pips
    - Sharpe annualisé sur equity (seuil viable : ≥ 1.5)
    - Max drawdown (%) — seuil maximal acceptable : ≤ 15%
    - Runs de pertes consécutives ≥ 5 ? → risque psychologique live → 🟠

1.3 Critère de Kelly
    - Calcule f* = WR − (1 − WR) / (avg_win_pips / avg_loss_pips)
    - Comparer avec risk_pct actuel (config.yaml → trading.risk_pct)
    - Si risk_pct > f* → système sur-leveé → 🔴
    - Si risk_pct > f* × 0.5 (demi-Kelly) → 🟠

─────────────────────────────────────────────
BLOC 2 — FRÉQUENCE ET CONTINUITÉ DU SIGNAL
─────────────────────────────────────────────
Source : reports/ALPHAEDGE_backtest_results.csv
         + alphaedge/engine/carry_signal.py
         + alphaedge/engine/backtest.py

2.1 Taux de signal
    - Trades par an (global, EURUSD, USDJPY séparément)
    - Distribution trimestrielle : y a-t-il des trimestres entiers sans trade ?
    - Distribution mensuelle : mois sans aucun signal ?
    - Plus long silence consécutif (en jours calendaires) entre deux trades ?
      → Silence ≥ 60 jours : 🟠 (risque de décrochage psychologique en live)
      → Silence ≥ 90 jours : 🔴 (stratégie inactive de facto)

2.2 Cascade de filtres — diagnostic du silence
    Objectif : comprendre pourquoi certaines périodes sont vides.
    Pour chaque filtre actif dans carry_signal.py et backtest.py :
    - Identifier le filtre (nom, fichier:ligne)
    - Valeur seuil active (config.yaml ou constants.py) et sens du filtre
    - Les rejets sont-ils loggés avec motif (momentum / carry / spread / news / session) ?
      → Si non → À VÉRIFIER (silence indiagnosticable en production)
    Filtres à identifier obligatoirement :
      Momentum (momentum_fast_period, momentum_slow_period, momentum_adx_threshold)
      Carry (carry_enabled, carry_min_differential_pct)
      Spread (max_spread_pips)
      News (news_filter.enabled, blackout_minutes, impact_levels)
      Session globale (max_trades_per_session)

2.3 Surrestrictivité des filtres
    - Le filtre news_filter (config.yaml) est-il actif en backtest ? Est-il alimenté
      par le vrai calendrier économique ou désactivé faute de données ? (fichier:ligne)
    - momentum_adx_threshold (config.yaml → trading.momentum_adx_threshold) :
      ce filtre de qualité du signal est-il implémenté dans
      backtest.py ? Avec quelle valeur ? (fichier:ligne)
    - carry_min_differential_pct : y a-t-il un override par paire ?
      Sinon, les paires à faible carry subissent le même seuil → À VÉRIFIER

─────────────────────────────────────────────
BLOC 3 — PERFORMANCE PAR PAIRE ET RÉGIME
─────────────────────────────────────────────
Source : reports/ALPHAEDGE_backtest_results.csv

3.1 Performance par paire
    Pour chaque paire présente dans le CSV :
    - N trades, WR (%), PF, expectancy (pips/trade), P&L total (pips et USD)
    - Une paire avec PF < 1.0 détruit de la valeur → 🔴 (retrait recommandé)
    - Une paire avec PF ∈ [1.0, 1.3] est marginale → 🟠

3.2 Performance par direction (LONG / SHORT)
    Pour chaque paire et globalement :
    - WR LONG vs WR SHORT
    - PF LONG vs PF SHORT
    - Si une direction affiche systématiquement PF < 1.0 → 🟠

3.3 Évolution temporelle (edge decay)
    Grouper les trades par année depuis le CSV (colonne entry_time) :
    - 2023 : N, WR, PF
    - 2024 : N, WR, PF
    - 2025 : N, WR, PF
    - 2026 (partiel) : N, WR, PF
    - Si PF décroît chaque année successivement → 🟠 (edge decay potentiel)
    - Si la dernière année complète affiche PF < 1.0 → 🔴

3.4 Concentration du P&L
    - Les 3 meilleures journées de trading représentent quelle fraction du P&L total ?
    - Si > 50% du P&L net provient de ≤ 3 journées → 🔴 (effet jackpot, non reproductible)
    - Identifier ces journées (date, paire, direction, pnl_pips)

─────────────────────────────────────────────
BLOC 4 — ROBUSTESSE IS/OOS
─────────────────────────────────────────────
Source : reports/ALPHAEDGE_backtest_results.csv
         + alphaedge/engine/backtest_stats.py

4.1 Validité du split IS/OOS
    - Split effectué dans backtest_stats.py : ratio et date de coupure ? (fichier:ligne)
    - N_IS et N_OOS depuis le CSV :
      → N_OOS < 15 → 🔴 (métriques OOS statistiquement non-significatives)
      → N_OOS ∈ [15, 30] → 🟠 (résultats fragiles)
    - Dégradation IS→OOS sur WR, PF, Sharpe (seuil max acceptable : 30%) :
      → Dégradation WR > 30% → 🟠
      → Dégradation WR > 50% → 🔴 (forte suspicion d'overfitting)
      → PF OOS < 1.0 → 🔴 (stratégie perdante hors échantillon)

4.2 Cohérence temporelle du split
    - L'OOS couvre-t-il une période macro distincte de l'IS ?
      (ex : IS = marché pre-tariffs, OOS = régime post-tariffs 2025)
    - Si IS et OOS sont dans le même régime macro → À VÉRIFIER

4.3 Walk-forward
    - alphaedge/engine/walk_forward.py existe — est-il branché dans le backtest standard ?
      (fichier:ligne dans backtest.py ou __main__)
    - Si non → 🟡 (validation IS/OOS statique uniquement, sans robustesse temporelle)

─────────────────────────────────────────────
BLOC 5 — CALIBRATION DES FILTRES MOMENTUM+CARRY
─────────────────────────────────────────────
Source : config.yaml + constants.py
         + alphaedge/engine/signal_pipeline.py
         + alphaedge/engine/carry_signal.py
         + alphaedge/engine/backtest.py

5.1 Inventaire des paramètres actifs
    Pour chaque paramètre ci-dessous, relever :
    valeur active (config.yaml) / valeur default (constants.py) / sens (plus restrictif ?)

    | Paramètre                  | Section config.yaml | Constante default              |
    |----------------------------|---------------------|--------------------------------|
    | momentum_fast_period       | trading             | DEFAULT_MOMENTUM_FAST = 12     |
    | momentum_slow_period       | trading             | DEFAULT_MOMENTUM_SLOW = 26     |
    | momentum_adx_period        | trading             | DEFAULT_ADX_PERIOD = 14        |
    | momentum_adx_threshold     | trading             | DEFAULT_ADX_THRESHOLD = 25.0   |
    | momentum_lookback_days     | trading             | DEFAULT_LOOKBACK_DAYS = 20     |
    | carry_enabled              | trading             | True                           |
    | carry_min_differential_pct | trading             | DEFAULT_CARRY_MIN_DIFF = 0.5   |
    | rr_ratio                   | trading             | DEFAULT_RR_RATIO = 2.5         |
    | max_spread_pips            | trading             | DEFAULT_MAX_SPREAD_PIPS = 2.0  |
    | news_filter.enabled        | news_filter         | N/A                            |

5.2 Cohérence live ↔ backtest par paramètre
    Pour chaque paramètre de 5.1 :
    - Le backtest consomme-t-il la valeur de config.yaml ? (fichier:ligne backtest.py)
    - Le live consomme-t-il la valeur de config.yaml ? (fichier:ligne signal_pipeline.py)
    - Si l'un force la constante DEFAULT au lieu de config.yaml → 🔴

5.3 Analyse critique de rr_ratio
    - rr_ratio actuel (config.yaml → trading.rr_ratio)
    - Calculer avg_win_pips / avg_loss_pips depuis le CSV
    - Si le RR réalisé (CSV) < rr_ratio configuré → le TP est rarement atteint → 🟠
    - Si avg_win_pips / avg_loss_pips < 1.0 → edge négatif sans WR très élevé → 🔴
    - Calculer le WR minimum requis pour PF > 1.0 :
        WR_min = 1 / (1 + rr_ratio)

─────────────────────────────────────────────
BLOC 6 — MODÉLISATION DES COÛTS
─────────────────────────────────────────────
Source : alphaedge/engine/backtest_simulation.py
         + alphaedge/engine/session_lifecycle.py
         + config.yaml

6.1 Spread
    - Valeur de spread simulée en backtest (fixe ou variable ?) : fichier:ligne
    - Valeur max_spread_pips (config.yaml) vs réalité NYSE open :
        EURUSD ≈ 0.5–1.0 pip, USDJPY ≈ 1.0–1.5 pip
    - Le filtre max_spread_pips est-il actif en backtest ? Ou uniquement en live ? (fichier:ligne)
    - Si le backtest ignore le spread → les coûts sont sous-estimés → 🟠

6.2 Slippage
    - Méthode de slippage en backtest : fixe / variable / ATR-based ? (fichier:ligne)
    - Méthode de slippage en live (session_lifecycle.py) : (fichier:ligne)
    - Si les deux méthodes divergent → écart backtest/live non quantifiable → 🟠

6.3 Impact des coûts sur l'expectancy nette
    - Calculer le spread moyen modélisé depuis le CSV ou backtest_simulation.py
    - Expectancy brute (pips/trade depuis BLOC 1) vs expectancy nette
      (brute − spread_moyen − slippage_moyen)
    - Si expectancy nette ≤ 0 → la stratégie est perdante après frais réels → 🔴

─────────────────────────────────────────────
BLOC 7 — RISK MANAGEMENT FINANCIER
─────────────────────────────────────────────
Source : alphaedge/core/_stubs/risk_manager.py
         + alphaedge/engine/position_manager.py
         + config.yaml

7.1 Position sizing
    - Méthode active : fixed risk_pct sur equity (config.yaml → trading.risk_pct)
    - risk_pct actuel : compatible avec Kelly f* calculé en BLOC 1 ?
    - max_lot_size (config.yaml) : le plafond est-il jamais atteint ?
      Si oui → le sizing réel est différent du sizing théorique → biais backtest → 🟠

7.2 Garde-fous d'exécution
    - calculate_position_size() : is_valid=False → aucun ordre soumis ? (fichier:ligne)
    - check_daily_limit() : halt_trading=True → trading stoppé + log CRITICAL ? (fichier:ligne)
    - create_bracket_order() : is_valid=False → rejection_reason loggé + ordre ignoré ? (fichier:ligne)

7.3 Exposition simultanée multi-paires
    - EURUSD et USDJPY sont tous deux exposés au USD (corrélation non nulle)
    - Un trade EURUSD + un trade USDJPY peuvent-ils être ouverts simultanément ?
    - Quel mécanisme empêche la double exposition USD ? (fichier:ligne)
    - Si aucun mécanisme → risque de concentration USD en live → 🟠

─────────────────────────────────────────────
BLOC 8 — INTÉGRITÉ DU PIPELINE SIGNAL
─────────────────────────────────────────────
Source : alphaedge/engine/signal_pipeline.py
         + alphaedge/engine/backtest.py
(Contrôle rapide — l'audit d'ingénierie 2026-03-22 a couvert S-01 à S-08 ✅)

8.1 Pipeline all-or-nothing
    - detect_momentum() → None → pipeline stoppé avant traitement carry ? CONFORME / NON CONFORME
    - carry bias conflict → STOP → pipeline stoppé avant sizing ? CONFORME / NON CONFORME
    - calculate_position_size() → is_valid=False → aucun ordre émis ? CONFORME / NON CONFORME

8.2 Paramètres live vs backtest
    - Les paramètres de config.yaml sont-ils injectés de façon identique en live et en backtest ?
    - Citer les deux points d'injection (fichier:ligne backtest.py + fichier:ligne signal_pipeline.py)
    - CONFORME / NON CONFORME / À VÉRIFIER

─────────────────────────────────────────────
SYNTHÈSE OBLIGATOIRE
─────────────────────────────────────────────

Score global : X / 10
  ≥ 8    → GO production (paper trading autorisé)
  5 – 7  → CONDITIONNEL (corrections 🔴 requises avant paper)
  < 5    → NO-GO (refonte paramétrique ou stratégique nécessaire)

Tableau des anomalies (toutes priorités, format strict) :
| ID | Bloc | Description courte | Fichier:Ligne | Sévérité | Impact | Effort |
|----|------|--------------------|---------------|----------|--------|--------|

Verdict : GO / NO-GO / CONDITIONNEL
Justification en 3 lignes max — chiffres issus du CSV uniquement.

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Crée le fichier :
  tasks/audits/resultats/audit_strategic_alphaedge.md
Crée le dossier s'il n'existe pas.

Structure du fichier :
## BLOC 1 — VALIDITÉ STATISTIQUE DE L'EDGE
## BLOC 2 — FRÉQUENCE ET CONTINUITÉ DU SIGNAL
## BLOC 3 — PERFORMANCE PAR PAIRE ET RÉGIME
## BLOC 4 — ROBUSTESSE IS/OOS
## BLOC 5 — CALIBRATION DES FILTRES MOMENTUM+CARRY
## BLOC 6 — MODÉLISATION DES COÛTS
## BLOC 7 — RISK MANAGEMENT FINANCIER
## BLOC 8 — INTÉGRITÉ DU PIPELINE SIGNAL
## SYNTHÈSE

Tableau synthèse :
| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact | Effort |

Sévérité : 🔴 Critique · 🟠 Majeur · 🟡 Mineur.

Confirme dans le chat uniquement :
"✅ tasks/audits/resultats/audit_strategic_alphaedge.md créé
 🔴 X · 🟠 X · 🟡 X"
