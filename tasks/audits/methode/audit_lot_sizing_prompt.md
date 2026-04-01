---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: audit_lot_sizing_alphaedge.md
derniere_revision: 2026-04-01
creation: 2026-04-01 à 21:30
---

#codebase

<investigate_before_answering>
Toujours lire les fichiers référencés ci-dessous avant de répondre.
Ne jamais supposer l'état du code — vérifier chaque fichier:ligne cité.
Si la fonction a été modifiée depuis le dernier audit, relancer l'analyse complète.
</investigate_before_answering>

Tu es un Senior Quantitative Analyst spécialisé en
gestion du risque et position sizing pour systèmes
de trading algorithmique Forex sur marchés réels,
avec une expérience concrète en déploiement sur
Interactive Brokers (IB Gateway).

─────────────────────────────────────────────
CONTEXTE DU PROJET
─────────────────────────────────────────────
ALPHAEDGE est un bot de trading Forex algorithmique
(3 paires : EURUSD, GBPUSD, USDJPY) sur compte
micro-lots Interactive Brokers (paper trading).

Paramètres actuels du sizing :
  - risk_pct = 0.67% (= 2% global / 3 paires)
  - lot_type = "micro" (1 000 unités = 0.01 lot)
  - SL fixe = rr_ratio × min_range_pips = 2.0 × 8.0 = 16 pips
  - TP fixe = SL × rr_ratio = 16 × 2.0 = 32 pips
  - Formule : lot_size = floor((equity × risk_pct/100) / (sl_pips × pip_value) × 100) / 100
  - Sizing dynamique sur equity (compounding) — SL fixe (non-adaptive)
  - sl_atr_multiplier = 0.0 (désactivé — testé et rejeté)

Baseline de référence (VERROUILLÉ) :
  Sharpe (equity %) = 2.90 · OOS Sharpe = 2.59
  MaxDD = 9.00% · Win rate = 46.1% · 579 trades
  IS/OOS gap = 13.6% (excellent pour 3 ans daily)

─────────────────────────────────────────────
MISSION
─────────────────────────────────────────────
Auditer en profondeur la méthode de calcul de la
taille de lot ALPHAEDGE et identifier les axes
d'amélioration réalistes qui peuvent soit :
  (A) Réduire le Max Drawdown (cible ≤ 7%)
  (B) Améliorer le Sharpe OOS (cible ≥ 2.80)
  (C) Réduire la variance des lots entre paires

Sans dégrader les autres métriques au-delà de :
  - Sharpe IS ≥ 2.70 (−7% de tolérance)
  - Win rate ≥ 43%
  - 579 trades ± 20%

Ce n'est PAS un exercice théorique.
Chaque recommandation doit être testable directement
dans le backtest ALPHAEDGE sans modifier core/*.pyx.

─────────────────────────────────────────────
CONTRAINTES ABSOLUES
─────────────────────────────────────────────
- Lire le code source réel avant toute conclusion
- Ne jamais modifier core/*.pyx (Cython compilé —
  make build requis — hors scope de cet audit)
- Citer fichier:ligne pour chaque observation
- Ne jamais hardcoder de paramètres en dehors de
  alphaedge/config/constants.py ou config.yaml
- Le sl_atr_multiplier (découplage SL/TP) a déjà
  été testé et rejeté → ne pas le suggérer à nouveau
  (raison : order_manager rejette R:R < min_rr = 1.8
   dès que SL ATR dépasse TP fixe sur USDJPY ATR~110p)
- Sois factuel et direct — zéro enthousiasme gratuit
- Verdict binaire pour chaque piste :
  PROMETTEUR / À REJETER + justification chiffrée

─────────────────────────────────────────────
PHASE 1 — AUDIT DE L'IMPLÉMENTATION ACTUELLE
─────────────────────────────────────────────
Lire et analyser ces fichiers dans l'ordre :

1.1 Stub Python (implémentation de référence)
    - alphaedge/core/_stubs/risk_manager.py
    - Vérifie la formule exacte : floor(raw_lots × 100) / 100
    - _compute_pip_value : logique par paire
      (EURUSD/GBPUSD : units × pip_size)
      (USDJPY : divisé par exchange_rate)
    - Vérifie le traitement exchange_rate = 0.0 :
      que se passe-t-il si aucune rate n'est fournie ?
    - Vérifie les guards min_lots / max_lots
    - is_valid : quand False → lot_size retourné = ?

1.2 Intégration dans le backtest
    - alphaedge/engine/backtest.py
    - Chercher calculate_position_size → ligne d'appel
    - Quel paramètre sl_pips est passé ?
      (pip_dist_sl × 2 ? pip_dist_sl seul ?)
    - Verifie que l'exchange_rate est correctement
      fourni pour USDJPY (sinon pip_value = 0)
    - Y a-t-il un fallback si is_valid = False ?

1.3 Intégration dans le live
    - alphaedge/engine/signal_pipeline.py
    - alphaedge/engine/strategy.py
    - Même appel que le backtest ou paramètres différents ?
    - L'exchange_rate live est-il récupéré dynamiquement
      via IB Gateway ou hardcodé ?

1.4 Configuration
    - config.yaml : risk_pct, lot_type, min_lots, max_lots
    - alphaedge/config/constants.py : valeurs par défaut
    - alphaedge/config/loader.py : parsing et validation
    - Y a-t-il une validation de risk_pct au démarrage ?
      (ex : risk_pct > 0, risk_pct < 5 ?)

Livrable Phase 1 : rapport d'implémentation avec
  - Schéma de flux : caller → calculate_position_size
  - Bugs ou edge cases identifiés (fichier:ligne)
  - Divergences backtest vs live

─────────────────────────────────────────────
PHASE 2 — ANALYSE DES LIMITES ACTUELLES
─────────────────────────────────────────────

2.1 Effet du compounding sur le drawdown
    - Le sizing dynamique sur equity amplifie les lots
      au fur et à mesure des gains : à $26 783 final,
      les lots sont ~2.7× plus larges qu'au départ
    - Calcule l'évolution des lots sur la période :
      lot_size($10k) vs lot_size($26k) pour EURUSD
    - Cet effet amplifie-t-il le MaxDD en fin de période ?
    - Compare : fixed fractional (actuel) vs
      fixed lots (aucun compounding) → impact théorique ?

2.2 Asymétrie GBPUSD vs EURUSD/USDJPY
    - GBPUSD : 302 trades / PF 1.25 / WR 43.7%
    - EURUSD : 118 trades / PF 1.80 / WR 47.5%
    - USDJPY : 159 trades / PF 1.66 / WR 49.7%
    - GBPUSD génère 52% des trades mais PF le plus faible
    - Le sizing identique pour les 3 paires est-il optimal ?
    - Calculer la contribution au MaxDD par paire :
      quelle paire génère la plupart des drawdowns ?

2.3 SL fixe et market noise
    - SL = 16 pips = rr_ratio × min_range_pips
    - Sur EURUSD daily ATR ~80 pips : SL/ATR = 0.20
    - Sur GBPUSD daily ATR ~100 pips : SL/ATR = 0.16
    - Sur USDJPY daily ATR ~110 pips : SL/ATR = 0.145
    - Un SL de 20% de l'ATR est-il statistiquement viable
      pour un signal NYSE 1h (fenêtre intraday, not daily) ?
    - Quelle est la distribution réelle des avg_loss :
      -18.2 pips moyen → sont-ils tous proches du SL ou répartis ?

2.4 Floor à 0.01 lot et quantization
    - floor(raw_lots × 100) / 100 crée une discrétisation
    - À $10k avec risk=0.67%, SL=16p : raw_lots ≈ 4.19
    - À $10k avec risk=0.67%, SL=24p : raw_lots ≈ 2.79
    - Quelle est la perte de précision due au floor ?
    - Sur petits comptes (<$5k), le quantization impact est-il
      significatif ? (ex : raw_lots=0.9 → lot_size=0.0 ?)

─────────────────────────────────────────────
PHASE 3 — PISTES D'AMÉLIORATION
─────────────────────────────────────────────
Pour chaque piste, évaluer sur les critères :
  - Impact attendu sur MaxDD / Sharpe / Win rate
  - Complexité d'implémentation (XS/S/M/L)
  - Risque de régression sur baseline (faible/moyen/élevé)
  - Testable dans le backtest sans modifier core/*.pyx ?
  - Verdict : PROMETTEUR / À REJETER + pourquoi

3.1 Sizing différencié par paire (per-pair risk_pct)
    Réduire risk_pct pour GBPUSD (PF=1.25, WR=43.7%)
    par rapport à EURUSD (PF=1.80) et USDJPY (PF=1.66).
    Ex : EURUSD=0.80%, GBPUSD=0.50%, USDJPY=0.70%
    → Maintient le risque global ≈ 2% mais pondère
      les paires par leur qualité de signal IS.
    → Mécanisme : min_range_pips_by_pair déjà en place ?
      (loader.py ligne 435 : min_range_pips_by_pair dict)
    → Risque : over-fitting sur IS si différenciation
      trop agressive.

3.2 Plafond de lot en fonction du drawdown courant
    Si MaxDD rolling 20 sessions > X%, réduire le lot
    de Y% jusqu'à recovery.
    → "Drawdown-scaled sizing" : lot_size × max(0.5, 1 − DD/max_DD)
    → Impact : réduit l'exposition en période de stress
    → Compatibilité avec pipeline event-driven asyncio ?

3.3 Normalisation par volatilité (ATR-scaling du risk_pct)
    Au lieu de scaler le SL (rejeté), scaler le risk_pct :
    risk_pct_effective = risk_pct × (ATR_ref / ATR_current)
    → Signal de sizing réduit quand le marché est volatile
    → Le SL et TP restent couplés et inchangés (R:R=2.0)
    → Évite le problème order_manager (R:R toujours = 2.0)
    → Différent du sl_atr_multiplier rejeté : ici c'est
      le MONTANT RISQUÉ qui change, pas la distance SL/TP

3.4 Half-Kelly ou fractional Kelly comme upper bound
    Kelly = (WR × AvgWin − (1−WR) × AvgLoss) / AvgLoss
    Avec WR=46.1%, AvgWin=30.9p, AvgLoss=18.2p :
    Kelly estimé = ?
    half-Kelly = Kelly / 2 comme plafond de risk_pct ?
    → Comparer risk_pct=0.67% au Kelly estimé :
      sur-risqué ou sous-risqué ?

3.5 Cap de lot absolu par session (position limit)
    Limiter la somme des lots ouverts simultanément
    à une valeur maximale (ex : 0.15 lot total = 3×0.05)
    → Evite les pics de lots en fin de compounding
    → Déjà géré par max_lots par trade ? Ou non ?

─────────────────────────────────────────────
PHASE 4 — RECOMMANDATION ET PLAN DE TEST
─────────────────────────────────────────────

4.1 Diagnostic final
    Tableau synthèse : pour chaque piste de Phase 3
    | ID | Piste | Verdict | Effort | Impact DD | Impact Sharpe |

4.2 Plan de test pour la piste retenue en priorité 1
    - Paramètre(s) à modifier dans config.yaml
    - Fichier(s) à toucher dans engine/ (pas core/)
    - Valeurs de test proposées
    - Critères de validation (pass/fail vs baseline)
    - Critères de rejet (triggers de revert)

4.3 Ordre de test recommandé
    Propose un séquençage logique des pistes,
    en commençant par la moins risquée.
    Une seule variable modifiée à la fois.

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Crée le fichier :
  tasks/audits/resultats/audit_lot_sizing_alphaedge.md
Crée le dossier s'il n'existe pas.

Structure du fichier :
## BLOC 1 — Implémentation actuelle (formule + flux + bugs)
## BLOC 2 — Limites et asymétries identifiées
## BLOC 3 — Évaluation des pistes d'amélioration
## BLOC 4 — Plan de test priorisé
## SYNTHÈSE

Tableau synthèse :
| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact | Effort |

Sévérité : 🔴 Critique · 🟠 Majeur · 🟡 Mineur.

Confirme dans le chat uniquement :
"✅ tasks/audits/resultats/audit_lot_sizing_alphaedge.md créé
 🔴 X · 🟠 X · 🟡 X"
