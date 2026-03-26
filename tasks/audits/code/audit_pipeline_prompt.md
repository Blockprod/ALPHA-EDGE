---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: audit_pipeline_alphaedge.md
derniere_revision: 2026-03-25
creation: 2026-03-24 à 15:30
---

#codebase

Tu es un Senior Engineer spécialisé en systèmes de trading
algorithmique Forex et pipelines d'exécution.
Tu réalises un audit EXCLUSIVEMENT d'ingénierie du pipeline
Momentum+Carry sur ALPHAEDGE.

Ton objectif : vérifier que le câblage entre la configuration,
le pipeline signal, le backtest et le moteur live est cohérent,
sans dérive silencieuse de paramètre ni divergence de
comportement entre simulation et exécution réelle.

─────────────────────────────────────────────
ÉTAPE 0 — VÉRIFICATION PRÉALABLE (OBLIGATOIRE)
─────────────────────────────────────────────
Vérifie si ce fichier existe déjà :
  tasks/audits/resultats/audit_pipeline_alphaedge.md

Si trouvé, affiche :
"⚠️ Audit pipeline existant détecté :
 Fichier : tasks/audits/resultats/audit_pipeline_alphaedge.md
 Date    : [date modification]

 [NOUVEAU]  → audit complet (écrase l'existant)
 [MÀJOUR]   → compléter sections manquantes
 [ANNULER]  → abandonner"

Si absent → démarrer directement :
"✅ Aucun audit pipeline existant. Démarrage..."

─────────────────────────────────────────────
SOURCES — LIRE EN PREMIER
─────────────────────────────────────────────
1. config.yaml                                  ← paramètres actifs
2. alphaedge/config/constants.py                ← valeurs par défaut
3. alphaedge/engine/signal_pipeline.py          ← pipeline signal live
4. alphaedge/engine/backtest.py                 ← simulation
5. alphaedge/engine/carry_signal.py             ← filtre carry bias
6. alphaedge/engine/backtest_simulation.py      ← modèle de coûts backtest
7. alphaedge/engine/session_lifecycle.py        ← exécution live (spread, slippage)
8. alphaedge/engine/position_manager.py         ← sizing live
9. alphaedge/core/_stubs/risk_manager.py        ← interface risk
10. alphaedge/core/_stubs/order_manager.py      ← interface ordre
11. alphaedge/engine/strategy.py                ← état session live
12. alphaedge/core/_stubs/momentum_detector.py  ← interface momentum

─────────────────────────────────────────────
PÉRIMÈTRE STRICT
─────────────────────────────────────────────
ANALYSE :
- Cohérence des paramètres entre config.yaml, live et backtest
- Pipeline all-or-nothing (contrats de retour des détecteurs)
- Modélisation des coûts (spread / slippage)
- Alignement des données d'entrée (Daily bars)
- Garde-fous d'exécution (risk_manager, order_manager)
- Cohérence carry bias live ↔ backtest
- Expositions multi-paires simultanées

N'ANALYSE PAS : performance financière, métriques de backtest, DST/timezone,
sécurité credentials, architecture modules, Cython interne.

─────────────────────────────────────────────
CONTRAINTES ABSOLUES
─────────────────────────────────────────────
- Cite fichier:ligne pour CHAQUE point factuel
- Conclus chaque sous-section par : CONFORME / NON CONFORME / À VÉRIFIER
- Ne déduis PAS la logique interne des .pyx — traite leurs interfaces comme boîtes noires
- Ne lis PAS les fichiers .md, .txt, .rst, .csv
- Écris "À VÉRIFIER" si la preuve est absente du code

─────────────────────────────────────────────
BLOC 1 — COHÉRENCE DES PARAMÈTRES STRATÉGIQUES
─────────────────────────────────────────────
Source : config.yaml + constants.py
         + signal_pipeline.py + backtest.py

Pour chaque paramètre ci-dessous, vérifier à trois endroits :
(A) valeur déclarée dans config.yaml (section + clé)
(B) valeur injectée dans le backtest (backtest.py, fichier:ligne)
(C) valeur injectée dans le pipeline live (signal_pipeline.py, fichier:ligne)

Si (B) ≠ (A) ou (C) ≠ (A) → dérive de paramètre → 🔴

Paramètres à vérifier :

| Paramètre                    | Section config.yaml |
|------------------------------|---------------------|
| momentum_fast_period         | trading             |
| momentum_slow_period         | trading             |
| momentum_adx_period          | trading             |
| momentum_adx_threshold       | trading             |
| momentum_lookback_days       | trading             |
| carry_enabled                | trading             |
| carry_min_differential_pct   | trading             |
| carry_rates                  | carry               |
| rr_ratio                     | trading             |
| max_spread_pips              | trading             |
| risk_pct                     | trading             |
| max_trades_per_session       | trading             |
| max_daily_loss_pct           | trading             |

1.1 Backtest — injection des paramètres
    Pour chaque paramètre :
    - Lire la ligne d'injection dans backtest.py
    - Vérifier qu'elle consomme config.yaml (pas DEFAULT_* de constants.py)
    - Si un DEFAULT_* est passé à la place du config → 🔴

1.2 Live — injection des paramètres
    Pour chaque paramètre :
    - Lire la ligne d'injection dans signal_pipeline.py (ou strategy.py)
    - Vérifier qu'elle consomme config.yaml (pas DEFAULT_* de constants.py)
    - Si un DEFAULT_* est passé à la place du config → 🔴

1.3 Overrides carry par paire
    - config.yaml déclare-t-il des overrides `carry_rates` ou
      `momentum_adx_threshold` par paire ?
      → Pour chaque paire configurée : le backtest ET le live appliquent-ils l'override ?
      (fichier:ligne pour les deux)
    - Si l'override n'est pas lu par l'un des deux → 🟠

─────────────────────────────────────────────
BLOC 2 — PIPELINE ALL-OR-NOTHING
─────────────────────────────────────────────
Source : signal_pipeline.py + session_lifecycle.py + backtest.py

Règle : tout STOP dans la chaîne = zéro ordre, zéro trade.

2.1 detect_momentum() → None
    - Live : après None, y a-t-il un `return` ou `continue` explicite
      avant tout traitement carry ou sizing ? (fichier:ligne)
    - Backtest : même contrôle dans backtest.py (fichier:ligne)
    - CONFORME / NON CONFORME

2.2 carry bias conflict → STOP
    - Live : si carry direction contredit momentum direction,
      y a-t-il un garde-fou explicite avant sizing ? (fichier:ligne)
    - Backtest : même contrôle reproduit ? (fichier:ligne)
    - CONFORME / NON CONFORME

2.3 calculate_position_size() → is_valid=False
    - Live : l'ordre est-il refusé et loggé ? (fichier:ligne)
    - Backtest : ce contrôle est-il reproduit ? (fichier:ligne)
    - CONFORME / NON CONFORME

2.4 create_bracket_order() → is_valid=False
    - Live : rejection_reason loggé + ordre non soumis ? (fichier:ligne)
    - Backtest : ce contrôle est-il reproduit ? (fichier:ligne)
    - CONFORME / NON CONFORME

2.5 check_daily_limit() → halt_trading=True
    - Live : trading stoppé immédiatement + log CRITICAL ? (fichier:ligne)
    - Appelé à chaque cycle (pas seulement en début de session) ? (fichier:ligne)
    - CONFORME / NON CONFORME

─────────────────────────────────────────────
BLOC 3 — DONNÉES D'ENTRÉE (DAILY BARS)
─────────────────────────────────────────────
Source : signal_pipeline.py + backtest.py

3.1 Lookback window (Daily bars)
    - Backtest : combien de barres Daily sont passées à detect_momentum() ?
      (fichier:ligne dans backtest.py)
    - Live : combien de barres Daily sont récupérées ? (fichier:ligne dans data_feed.py
      ou session_lifecycle.py)
    - Doivent être identiques — sinon divergence de contexte Momentum → 🟠

3.2 Carry rates source
    - Backtest : les taux carry sont-ils lus depuis config.yaml à chaque trade ?
      (fichier:ligne dans backtest.py)
    - Live : même source ? (fichier:ligne dans signal_pipeline.py)
    - Si le live utilise state.carry_rates mais le backtest config.yaml
      — ou vice-versa — → divergence de filtre carry → 🟠

3.3 Cohérence du fallback carry
    - Si state.carry_rates est vide, le fallback config.trading.carry_rates
      est-il appliqué de façon identique live ET backtest ? (fichier:ligne)
    - Si le backtest n'a pas ce fallback → 🟠

─────────────────────────────────────────────
BLOC 4 — MODÈLE DE COÛTS
─────────────────────────────────────────────
Source : backtest_simulation.py + session_lifecycle.py + config.yaml

4.1 Spread — backtest
    - Méthode de simulation du spread dans backtest_simulation.py (fichier:ligne) :
      fixe / variable / fonction de l'ATR ?
    - Le filtre max_spread_pips est-il appliqué pour rejeter des trades en backtest ?
      (fichier:ligne dans backtest.py ou backtest_simulation.py)
    - Valeur de spread utilisée : cohérente avec max_spread_pips config.yaml ?

4.2 Spread — live
    - Méthode de vérification du spread en live (session_lifecycle.py, fichier:ligne)
    - Le buffer de spread est-il ajouté au SL ? (config.yaml → risk.slippage_buffer_pips)
      (fichier:ligne dans session_lifecycle.py ou position_manager.py)

4.3 Slippage — backtest vs live
    - Backtest : méthode de slippage (fichier:ligne dans backtest_simulation.py)
    - Live : méthode de slippage (fichier:ligne dans session_lifecycle.py)
    - Si les deux méthodes sont différentes → divergence de coût → 🟠
    - Quantifier l'écart potentiel si possible (pips par trade)

4.4 Divergence totale de coût backtest ↔ live
    - Le backtest modélise-t-il le même coût total (spread + slippage) que le live ?
    - Si la modélisation est différente mais documentée → À VÉRIFIER
    - Si elle est différente et non documentée → 🟠

─────────────────────────────────────────────
BLOC 5 — ALIGNEMENT VALIDATION EXÉCUTION
─────────────────────────────────────────────
Source : backtest.py + position_manager.py + risk_manager.py + order_manager.py

5.1 Le backtest passe-t-il par risk_manager ?
    - Chercher un appel à calculate_position_size() dans backtest.py (fichier:ligne)
    - Si absent : le sizing backtest est calculé directement → 🟠
      (les rejets de sizing live ne sont pas reproduits en simulation)

5.2 Le backtest passe-t-il par order_manager ?
    - Chercher un appel à create_bracket_order() dans backtest.py (fichier:ligne)
    - Si absent : les rejets de bracket order live ne sont pas testés → 🟠

5.3 Équivalence fonctionnelle documentée
    - Si risk_manager / order_manager sont absents du backtest :
      y a-t-il un commentaire ou un test qui documente explicitement ce périmètre et
      les invariants simulés vs réels ? (fichier:ligne)
    - Si non documenté → 🟡

─────────────────────────────────────────────
BLOC 6 — EXPOSITION MULTI-PAIRES
─────────────────────────────────────────────
Source : session_lifecycle.py + strategy.py + backtest.py

6.1 Trades simultanés inter-paires
    - Le système peut-il ouvrir un trade EURUSD et USDJPY simultanément ? (fichier:ligne)
    - Quel mécanisme empêche la double exposition USD ? (fichier:ligne)
    - Si aucun mécanisme → 🟠

6.2 Filtre de corrélation USD (config.yaml → trading.usd_correlation_filter)
    - Valeur actuelle dans config.yaml (true / false)
    - Si false : ce choix est-il documenté avec justification dans config.yaml ?
      (commentaire inline — fichier:ligne)
    - Quel code implémente ce filtre lorsqu'activé ? (fichier:ligne dans signal_pipeline.py)

6.3 max_trades_per_session
    - Valeur active (config.yaml → trading.max_trades_per_session)
    - Ce plafond s'applique-t-il par paire ou globalement sur la session ? (fichier:ligne)
    - Si global : un trade EURUSD peut-il bloquer un signal USDJPY valide (et vice-versa) ?

─────────────────────────────────────────────
SYNTHÈSE OBLIGATOIRE
─────────────────────────────────────────────

Score global : X / 10
  ≥ 8    → CONFORME — pipeline fiable en l'état
  5 – 7  → CONDITIONNEL — corrections 🔴 requises avant paper trading
  < 5    → NON CONFORME — dérives silencieuses compromettent les résultats

Tableau des anomalies (format strict) :
| ID | Bloc | Description courte | Fichier:Ligne | Sévérité | Impact | Effort |
|----|------|--------------------|---------------|----------|--------|--------|

Sévérité : 🔴 Critique · 🟠 Majeure · 🟡 Mineure
Impact : divergence backtest/live · signal manqué · ordre invalide · coût sous-estimé
Effort : XS (< 1h) · S (< 4h) · M (< 1j) · L (> 1j)

Verdict : CONFORME / NON CONFORME / CONDITIONNEL
Justification en 3 lignes max — faits du code uniquement, pas de métriques CSV.

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Crée le fichier :
  tasks/audits/resultats/audit_pipeline_alphaedge.md
Crée le dossier s'il n'existe pas.

Structure du fichier :
## BLOC 1 — COHÉRENCE DES PARAMÈTRES STRATÉGIQUES
## BLOC 2 — PIPELINE ALL-OR-NOTHING
## BLOC 3 — DONNÉES D'ENTRÉE (DAILY BARS)
## BLOC 4 — MODÈLE DE COÛTS
## BLOC 5 — ALIGNEMENT VALIDATION EXÉCUTION
## BLOC 6 — EXPOSITION MULTI-PAIRES
## SYNTHÈSE

Tableau synthèse :
| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact | Effort |

Sévérité : 🔴 Critique · 🟠 Majeur · 🟡 Mineur.

Confirme dans le chat uniquement :
"✅ tasks/audits/resultats/audit_pipeline_alphaedge.md créé
 🔴 X · 🟠 X · 🟡 X"
