---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: audit_migration_momentum_carry_alphaedge.md
derniere_revision: 2026-03-25
creation: 2026-03-25 à 10:00
---

#codebase

Tu es un Senior Quant Engineer spécialisé en trading algorithmique
institutionnel Forex. Tu réalises un audit de migration stratégique
complet sur ALPHAEDGE : cartographier précisément ce qui doit être
supprimé, conservé, et créé pour migrer de la stratégie FCR/SMC
vers une stratégie institutionnelle **Momentum + Carry FX (swing)**.

─────────────────────────────────────────────
ÉTAPE 0 — VÉRIFICATION PRÉALABLE (OBLIGATOIRE)
─────────────────────────────────────────────
Vérifie si ce fichier existe déjà :
  tasks/audits/resultats/audit_migration_momentum_carry_alphaedge.md

Si trouvé, affiche :
"⚠️ Audit migration existant détecté :
 Fichier : tasks/audits/resultats/audit_migration_momentum_carry_alphaedge.md
 Date    : [date modification]

 [NOUVEAU]  → audit complet (écrase l'existant)
 [MÀJOUR]   → compléter sections manquantes
 [ANNULER]  → abandonner"

Si absent → démarrer directement :
"✅ Aucun audit migration existant. Démarrage..."

─────────────────────────────────────────────
CONTEXTE STRATÉGIQUE — LIRE EN PREMIER
─────────────────────────────────────────────
La décision est prise : la stratégie FCR/SMC est abandonnée.
Elle est remplacée par une stratégie institutionnelle validée académiquement :
  • Time Series Momentum FX — Moskowitz / Ooi / Pedersen (2012)
  • FX Carry — Lustig / Roussanov / Verdelhan (2011)
  • Cross-sectional Momentum — Asness / Moskowitz / Pedersen (2013)

Horizon : swing trading (Daily / H4), positions overnight.
Conséquence directe : M1/M5 comme signal principal devient secondaire.

─────────────────────────────────────────────
SOURCES — LIRE AVANT DE RÉDIGER
─────────────────────────────────────────────
Lis ces fichiers dans cet ordre avant de rédiger quoi que ce soit :

1. alphaedge/core/fcr_detector.pyx          ← à supprimer (interfaces uniquement — boîte noire)
2. alphaedge/core/gap_detector.pyx          ← à supprimer (interfaces uniquement — boîte noire)
3. alphaedge/core/engulfing_detector.pyx    ← à supprimer (interfaces uniquement — boîte noire)
4. alphaedge/core/risk_manager.pyx          ← à conserver (interfaces uniquement — boîte noire)
5. alphaedge/core/order_manager.pyx         ← à conserver (interfaces uniquement — boîte noire)
6. alphaedge/core/_stubs/                   ← interfaces Python des modules Cython
7. alphaedge/engine/signal_pipeline.py      ← câblage FCR → à réécrire
8. alphaedge/engine/session_lifecycle.py    ← gestion session → analyser réutilisabilité
9. alphaedge/engine/data_feed.py            ← fetch M1/M5 → à adapter pour Daily/H4
10. alphaedge/engine/backtest.py            ← simulation → analyser réutilisabilité
11. alphaedge/engine/backtest_simulation.py ← modélisation coûts → carry overnight à intégrer
12. alphaedge/engine/backtest_filters.py    ← filtres FCR → cataloguer lesquels survivent
13. alphaedge/engine/regime_filter.py       ← EXISTE, inutilisé → rôle dans la nouvelle archi ?
14. alphaedge/engine/broker.py              ← soumission ordres IB → réutilisable tel quel ?
15. alphaedge/engine/position_manager.py    ← positions overnight → analyse compatibilité
16. alphaedge/engine/strategy.py            ← orchestrateur → à réécrire ou adapter
17. alphaedge/config/constants.py           ← paramètres FCR → cataloguer ce qui disparaît
18. config.yaml                             ← configuration active

─────────────────────────────────────────────
PÉRIMÈTRE STRICT
─────────────────────────────────────────────
TU ANALYSES :
- Inventaire exhaustif des modules FCR → à supprimer / adapter / conserver
- Compatibilité du backtest engine avec Daily/H4 bars
- Compatibilité de data_feed.py avec le fetch Daily IBKR
- Compatibilité de risk_manager + order_manager avec swing (positions overnight, carry)
- Paramètres FCR dans constants.py et config.yaml → lesquels deviennent obsolètes
- Ce que regime_filter.py implémente déjà et si c'est réutilisable
- Modules à créer from scratch : momentum_detector, carry_signal
- Points d'ancrage dans le code existant pour chaque nouveau module
- Risques de régression sur les modules conservés (QA coverage)

TU N'ANALYSES PAS :
- La logique interne des .pyx (boîtes noires — tu lis leurs interfaces stubs uniquement)
- La sécurité credentials IB
- Les résultats du backtest FCR passé
- Le dashboard / la présentation

─────────────────────────────────────────────
CONTRAINTES ABSOLUES
─────────────────────────────────────────────
- Cite fichier + numéro de ligne pour CHAQUE affirmation sur le code
- Ne propose JAMAIS de modifier core/*.pyx sans instruction explicite de l'utilisateur
- Ne hardcode JAMAIS de valeurs hors alphaedge/config/constants.py
- Toute proposition doit être compatible Python 3.11.9
- Utilise zoneinfo exclusivement (jamais pytz, jamais offsets hardcodés)
- ALPHAEDGE_PAPER=true doit rester intact dans toute proposition
- Ne déduis pas la logique interne des .pyx — traite leurs interfaces comme boîtes noires

─────────────────────────────────────────────
BLOC 1 — INVENTAIRE : CE QUI DISPARAÎT
─────────────────────────────────────────────
Source : core/*.pyx, engine/signal_pipeline.py, engine/backtest_filters.py,
         config/constants.py, config.yaml

1.1 Modules Cython FCR à désactiver
    Pour chaque module (fcr_detector, gap_detector, engulfing_detector) :
    - Interface publique (fonctions exportées dans _stubs/) → citées avec fichier:ligne
    - Modules qui l'importent → liste exhaustive avec fichier:ligne
    - Impact de la suppression sur le pipeline (signal_pipeline.py, backtest.py, session_lifecycle.py)
    - Y a-t-il des tests pytest qui couvrent ces modules ? → lister les fichiers test concernés

1.2 Paramètres FCR obsolètes dans constants.py
    - Lister tous les paramètres structurellement liés à FCR / gap / engulfing
    - Format : NOM_CONSTANTE (fichier:ligne) — valeur actuelle — raison de suppression
    - Distinguer : à supprimer / à renommer / à adapter (carry, momentum utilisent peut-être les mêmes)

1.3 Paramètres FCR obsolètes dans config.yaml
    - Même inventaire pour config.yaml
    - Lister les clés YAML (chemin complet, ex: structure.fcr_range_cv_max)
    - Distinguer : à supprimer / à renommer / à adapter

1.4 Logique FCR dans engine/
    Pour chaque fichier de engine/ qui contient une dépendance FCR :
    - Fichier + lignes exactes de la dépendance
    - Nature du changement nécessaire : suppression / remplacement / adaptation

─────────────────────────────────────────────
BLOC 2 — INVENTAIRE : CE QUI RESTE INTACT
─────────────────────────────────────────────
Source : engine/broker.py, engine/data_feed.py, engine/backtest.py,
         engine/backtest_simulation.py, core/risk_manager.pyx,
         core/order_manager.pyx, engine/position_manager.py

2.1 Infrastructure d'exécution (broker, order_manager)
    - broker.py : quelles fonctions sont stratégie-agnostiques ?
    - order_manager : quels types d'ordres sont supportés (bracket, market, limit) ?
    - Le module position_manager supporte-t-il des positions overnight sans modification ?
      → Chercher toute référence à la session (session_end, close_on_session_end)
    - Verdict par module : CONSERVÉ INTACT / CONSERVÉ AVEC ADAPTATION / À RÉÉCRIRE

2.2 Infrastructure backtest
    - backtest.py : le framework est-il stratégie-agnostique ou FCR-couplé ?
      → Identifier les couplages FCR (imports, appels, paramètres) avec fichier:ligne
    - backtest_simulation.py : le modèle de coûts inclut-il le coût overnight (swap/carry) ?
      → Si non : À CRÉER (point d'ancrage suggéré)
    - walk_forward, bayesian_optimizer, monte_carlo : réutilisables sans modification ?
    - Verdict par module : CONSERVÉ INTACT / CONSERVÉ AVEC ADAPTATION / À RÉÉCRIRE

2.3 Data pipeline
    - data_feed.py : supporte-t-il le fetch de barres Daily et H4 via IB Gateway ?
      → Quelle est la résolution minimale supportée aujourd'hui ? (fichier:ligne)
    - Le cache local supporte-t-il plusieurs résolutions simultanément (M1, Daily) ?
    - Y a-t-il un paramètre de timeframe dans data_feed.py ? (fichier:ligne)
    - Verdict : CONSERVÉ INTACT / CONSERVÉ AVEC ADAPTATION / À RÉÉCRIRE

2.4 Risk management
    - risk_manager : le sizing est-il couplé au pip target FCR ou générique ?
    - Les interfaces (calculate_position_size, check_daily_limit) restent-elles valides
      pour du swing ? (positions plus longues, SL plus larges)
    - Verdict : CONSERVÉ INTACT / CONSERVÉ AVEC ADAPTATION

─────────────────────────────────────────────
BLOC 3 — REGIME FILTER — ÉTAT ACTUEL
─────────────────────────────────────────────
Source : engine/regime_filter.py

3.1 Ce qui est déjà implémenté
    - Lister toutes les fonctions publiques avec fichier:ligne
    - Paramètres de détection de régime utilisés (ADX, volatilité, trend ?)
    - Timeframe utilisé pour la détection (M5, H1, Daily, autre ?)
    - Le module est-il importé quelque part aujourd'hui ? → fichier:ligne ou "inutilisé"

3.2 Réutilisabilité pour Momentum + Carry
    - Ce module est-il compatible Daily/H4 ou couplé M1/M5 ?
    - Peut-il servir de gate pour le signal momentum (ADX ≥ 25 comme condition d'entrée) ?
    - Quelles adaptations sont nécessaires pour l'intégrer dans la nouvelle stratégie ?
    - Verdict : RÉUTILISABLE INTACT / RÉUTILISABLE AVEC ADAPTATION / À RÉÉCRIRE

─────────────────────────────────────────────
BLOC 4 — MODULES À CRÉER
─────────────────────────────────────────────
Pour chaque nouveau module, préciser :
  - Nom du fichier cible (convention : alphaedge/core/ pour Cython, alphaedge/engine/ pour Python)
  - Interface publique minimale (fonctions, inputs, outputs typés)
  - Point d'ancrage dans le code existant (où l'appeler)
  - Dépendances requises (modules existants utilisés)
  - Complexité estimée : Simple / Modérée / Complexe

4.1 momentum_detector (Cython .pyx recommandé — signal critique path)
    Interface attendue :
      detect_momentum(bars: np.ndarray, fast_period: int, slow_period: int,
                      adx_period: int, adx_threshold: float) → MomentumSignal | None
    Traitement attendu :
    - EMA fast/slow sur barres Daily ou H4
    - ADX comme gate (ADX < threshold → pas de signal)
    - Direction : LONG si EMA_fast > EMA_slow, SHORT sinon
    - Force : valeur normalisée 0-1 (input pour sizing)
    → Point d'ancrage suggéré : signal_pipeline.py (remplace detect_fcr + detect_gap + detect_engulfing)

4.2 carry_signal (Python — dépendance API IBKR, pas besoin de Cython)
    Interface attendue :
      get_carry_bias(pair: str, rates: dict[str, float]) → CarrySignal
        # rates = {base_currency: rate%, quote_currency: rate%}
        → differential: float  # base_rate - quote_rate (annualisé)
        → direction: Literal["LONG", "SHORT", "NEUTRAL"]
        → daily_carry_pips: float  # carry estimé par jour ouvert
        → is_valid: bool
    Paires à supporter en priorité :
    - AUD/JPY : carry principal (RBA vs BoJ — différentiel ~4.5%)
    - EUR/USD : carry secondaire (différentiel variable)
    - GBP/USD : momentum pur (carry faible)
    → Point d'ancrage suggéré : signal_pipeline.py, après momentum_detector

4.3 Adaptation signal_pipeline.py
    - Nouvelle séquence du pipeline à proposer :
        1. momentum_detector(bars_daily)  → MomentumSignal | stop
        2. carry_signal(pair, rates)      → CarrySignal (biais directionnel)
        3. regime_filter (si adapté)      → gate optionnel
        4. risk_manager.calculate_position_size() → sizing (existant, inchangé)
        5. order_manager.create_bracket_order()   → ordre (existant, inchangé)
    - Identifier les lignes exactes de signal_pipeline.py à modifier (fichier:ligne)

─────────────────────────────────────────────
BLOC 5 — RISQUES DE RÉGRESSION QA
─────────────────────────────────────────────
Source : alphaedge/tests/

5.1 Tests impactés par la suppression FCR
    - Lister tous les fichiers test qui importent ou testent fcr_detector,
      gap_detector, engulfing_detector (fichier:ligne pour chaque import)
    - Ces tests doivent être supprimés ou migrés → distinguer les deux cas

5.2 Tests réutilisables pour la nouvelle stratégie
    - Tests de risk_manager, order_manager, backtest_stats, broker restent-ils valides ?
    - Y a-t-il des fixtures (conftest.py) couplées à FCR ? (fichier:ligne)

5.3 Couverture à maintenir
    - Coverage threshold actuelle : ≥ 80% sur config/, utils/, core/
    - Quelle couverture est attendue pour momentum_detector et carry_signal ?
    - Quels nouveaux tests sont à créer (liste des scenarios prioritaires) ?

─────────────────────────────────────────────
BLOC 6 — PLAN DE MIGRATION SÉQUENCÉ
─────────────────────────────────────────────
À partir des blocs 1 à 5, synthétise un plan de migration en phases :

Phase 1 — Nettoyage FCR (pré-requis)
    - Opérations de suppression / désactivation (NON modification de .pyx)
    - Tests à supprimer
    - Paramètres à vider dans constants.py et config.yaml
    - Validation QA après nettoyage : combien de tests subsistent ?

Phase 2 — Data pipeline Daily/H4
    - Modifications dans data_feed.py
    - Adaptation du cache
    - Test de fetch manuel (script de validation suggéré)

Phase 3 — momentum_detector (Cython)
    - Fichier à créer : alphaedge/core/momentum_detector.pyx
    - Interface minimale (depuis BLOC 4.1)
    - Tests unitaires à créer (convention test_momentum_detector_*.py)
    - make build → make qa obligatoire

Phase 4 — carry_signal (Python)
    - Fichier à créer : alphaedge/engine/carry_signal.py
    - Interface minimale (depuis BLOC 4.2)
    - Tests unitaires à créer (convention test_carry_signal_*.py)

Phase 5 — signal_pipeline.py rewrite
    - Nouveau câblage (depuis BLOC 4.3)
    - Intégration regime_filter si verdict RÉUTILISABLE

Phase 6 — Backtest walk-forward
    - Paramètres à configurer dans config.yaml
    - Seuil GO : Sharpe OOS ≥ 0.8, N ≥ 50
    - Seuil NO-GO : toute autre configuration → retour Phase 2

Pour chaque phase :
    - Durée estimée : Simple (< 1h) / Modérée (1-4h) / Complexe (> 4h)
    - Risque de régression : Faible / Moyen / Élevé
    - Critère de sortie (comment savoir que la phase est terminée)

─────────────────────────────────────────────
RÈGLES ABSOLUES
─────────────────────────────────────────────
- Cite toujours fichier + numéro de ligne avant toute affirmation sur le code
- Ne propose JAMAIS de modifier core/*.pyx sans instruction explicite de l'utilisateur
- Ne hardcode JAMAIS de valeurs hors alphaedge/config/constants.py
- Toute proposition doit être compatible Python 3.11.9
- ALPHAEDGE_PAPER=true doit rester intact dans toute proposition
- Ne lis PAS les fichiers .md / .rst

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Crée le fichier :
  tasks/audits/resultats/audit_migration_momentum_carry_alphaedge.md
Crée le dossier s'il n'existe pas.

Structure du fichier :
## BLOC 1 — Inventaire : ce qui disparaît
## BLOC 2 — Inventaire : ce qui reste intact
## BLOC 3 — Regime filter — état actuel
## BLOC 4 — Modules à créer
## BLOC 5 — Risques de régression QA
## BLOC 6 — Plan de migration séquencé
## SYNTHÈSE

Tableau synthèse :
| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact | Effort |

Sévérité : 🔴 Critique · 🟠 Majeur · 🟡 Mineur.

Confirme dans le chat uniquement :
"✅ tasks/audits/resultats/audit_migration_momentum_carry_alphaedge.md créé
 🔴 X · 🟠 X · 🟡 X"
