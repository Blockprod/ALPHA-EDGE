---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: audit_ia_ml_alphaedge.md
derniere_revision: 2026-03-20
---

#codebase

Tu es un Senior Quantitative Engineer spécialisé en
systèmes de trading algorithmique augmentés par l'IA,
avec une expérience concrète en déploiement de modèles
ML en production sur marchés Forex.

─────────────────────────────────────────────
MISSION
─────────────────────────────────────────────
Évaluer si l'intégration d'agents IA et/ou de
Machine Learning dans ALPHAEDGE est pertinente,
intelligente et réaliste — en te basant UNIQUEMENT
sur ce qui est déjà en place dans le code.

Ce n'est PAS un exercice théorique.
Chaque recommandation doit être justifiée par
un gain mesurable sur un système de trading Forex
réel sur Interactive Brokers (IB Gateway).

─────────────────────────────────────────────
CONTRAINTES ABSOLUES
─────────────────────────────────────────────
- Lis le code source réel avant toute conclusion
- Ne lis aucun fichier .md, .txt, .rst existant
- Cite fichier:ligne pour chaque observation
- Sois factuel et direct — zéro enthousiasme gratuit
- Si une idée est techniquement séduisante mais
  dangereuse en production réelle : dis-le clairement
- Ton verdict final doit être binaire :
  PERTINENT / NON PERTINENT pour chaque cas
- Ne jamais suggérer de modifier core/*.pyx
  sans signaler que make build est requis

─────────────────────────────────────────────
PHASE 1 — DIAGNOSTIC DE L'EXISTANT
─────────────────────────────────────────────
Avant toute recommandation, analyse ce qui est
déjà en place dans le code :

1.1 Signal FCR et pipeline actuel
    - Quels détecteurs Cython sont utilisés ?
      (fcr_detector, gap_detector, engulfing_detector)
    - Comment le signal d'entrée M1 est-il généré ?
    - Quels paramètres FCR sont configurables ?
      (min_range_pips, rr_ratio, atr_period,
       min_atr_ratio, volume_period, min_volume_ratio)
    - Y a-t-il déjà un filtre de régime de marché ?
      (gap_detector comme filtre ATR compte-t-il ?)
    - ml_filter.py : actif dans le pipeline live ?
      Connecté à strategy.py ou code orphelin ?

1.2 Données disponibles
    - Quelles données sont persistées ?
      (M5 bars, M1 bars, session state, logs)
    - Granularité temporelle FCR : M5 + M1
    - Profondeur historique via reqHistoricalData ?
    - Données de performance par paire disponibles ?
      (reports/ALPHAEDGE_backtest_results.csv)
    - Journal de trades backtest disponible ?

1.3 Infrastructure et contraintes techniques
    - Stack : Python 3.11.9, Cython 3.0,
      ib_insync, asyncio, Windows
    - Session Forex : NYSE 9h30–10h30 EST seulement
      (~1h de fenêtre par jour)
    - Contraintes IB Gateway : latence API,
      reconnexion asyncio
    - Contraintes temps réel : event-driven
      (pas de polling — push via reqRealTimeBars)
    - CPU/RAM disponibles sur la machine ?

1.4 Points de décision dans le pipeline actuel
    Identifie TOUS les endroits dans le code où
    une décision est prise de façon déterministe
    et qui pourrait bénéficier d'un modèle adaptatif :
    - Détection FCR : seuil min_range_pips
    - Filtre gap ATR : min_atr_ratio
    - Signal engulfing : min_volume_ratio
    - Sizing : risk_pct, lot_size min/max
    - Sélection de paire : liste fixe ou dynamique ?
    - Filtre de session NYSE : fixe ou adaptatif ?

Livrable Phase 1 : carte complète des points de
décision avec fichier:ligne pour chaque point.

─────────────────────────────────────────────
PHASE 2 — ÉVALUATION DES OPPORTUNITÉS IA/ML
─────────────────────────────────────────────
Pour chaque opportunité ci-dessous, évalue sa
pertinence sur ce projet spécifique.

Critères d'évaluation pour chaque opportunité :
  - Gain attendu mesurable (Sharpe, WinRate, MaxDD)
  - Complexité d'implémentation (XS/S/M/L)
  - Risque d'introduction en production IB
  - Compatibilité avec fenêtre NYSE 1h/jour
  - Données disponibles suffisantes (oui/non)
  - Incompatibilité avec pipeline Cython existant ?
  - Verdict : PERTINENT / NON PERTINENT + pourquoi

2.1 Machine Learning sur les signaux FCR

  A. Filtre ML sur la qualité du range FCR
     Classifier (Random Forest, XGBoost) entraîné
     sur les features du range FCR (taille, position
     dans la journée, contexte ATR) pour prédire
     si le range a une probabilité élevée d'être
     respecté → enrichit fcr_detector sans le modifier
     → Données historiques FCR suffisantes ?
     → Risque de surapprentissage sur petite fenêtre ?

  B. Filtre ML sur le signal engulfing
     Classifier qui valide ou rejette le signal
     detect_engulfing() en ajoutant des features
     contextuelles (volume relatif, distance au range,
     conditions macro)
     → Compatible avec le pipeline all-or-nothing ?
     → Peut-il réduire les faux signaux ?

  C. Détection de régime de marché Forex
     (clustering K-Means ou HMM sur volatilité ATR,
     spread bid-ask, momentum M5)
     → Peut-on améliorer le filtre gap_detector
     en détectant les jours à haute/faible volatilité ?
     → Données Forex NYSE session suffisantes ?

  D. Optimisation adaptative des paramètres FCR
     Optimisation bayésienne (Optuna) ou
     grid search sur min_range_pips, min_atr_ratio,
     rr_ratio — réévalué mensuellement
     → Améliore-t-il la stabilité OOS
     par rapport au baseline Sharpe=3.37 actuel ?
     → Risque de suroptimisation sur EUR/USD, GBP/USD ?

  E. Prédiction du sizing optimal
     Régression sur les conditions de marché
     (ATR, spread, heure dans la session NYSE)
     pour ajuster risk_pct dynamiquement
     → Compatible avec calculate_position_size() ?
     → Améliore le risk-adjusted return ?

2.2 Agents IA autonomes

  F. Agent de sélection de paires Forex
     Un agent qui sélectionne dynamiquement
     EUR/USD, GBP/USD, USD/JPY selon la volatilité
     et les corrélations intraday du jour
     → Données intraday suffisantes ?
     → Risque de sur-trading sur fenêtre 1h ?

  G. Agent de gestion dynamique du stop-loss
     Un agent qui ajuste le niveau SL de
     create_bracket_order() selon la volatilité
     ATR réalisée de la session en cours
     → Compatible avec la logique bracket order IB ?
     → Risque d'interaction avec is_valid check ?

  H. Agent LLM pour le sentiment macro Forex
     Utilisation d'un LLM pour analyser
     news économiques (NFP, CPI, Fed) et filtrer
     les signaux FCR les jours de forte volatilité
     → Latence compatible avec event-driven IB ?
     → Fiabilité sur Forex vs crypto ?
     → Calendrier économique suffit-il ?

2.3 Amélioration du backtest par ML

  I. SHAP values sur les paramètres FCR
     Analyse d'importance des features sur
     le dataset backtest reports/ pour identifier
     quels paramètres FCR contribuent réellement
     au Sharpe versus du bruit
     → Peut simplifier constants.py ?
     → Compatible avec stubs Cython en backtest ?

  J. Walk-forward adaptatif
     Ajustement automatique des fenêtres IS/OOS
     selon la volatilité détectée du marché Forex
     → Améliore-t-il la stabilité OOS sur EUR/USD ?
     → Déjà couvert par backtest.py ou absent ?

─────────────────────────────────────────────
PHASE 3 — RECOMMANDATION FINALE
─────────────────────────────────────────────
3.1 Tableau de décision

| ID | Opportunité | Verdict | Gain estimé | Complexité | Risque prod |
|----|-------------|---------|-------------|------------|-------------|
| A  | [titre]     | ✅/❌   | [métriques] | XS/S/M/L   | Faible/Moyen/Élevé |

3.2 Roadmap recommandée

Si des opportunités sont PERTINENTES, propose
une séquence d'implémentation réaliste :

NIVEAU 1 — Sans risque pour la production
  (peut tourner en parallèle du bot actuel,
   en mode observation uniquement,
   ALPHAEDGE_PAPER=true obligatoire)

NIVEAU 2 — Intégration progressive
  (paper trading d'abord, validation OOS,
   make qa doit passer à 100%,
   puis production avec capital réduit)

NIVEAU 3 — Remplacement de composants existants
  (uniquement si NIVEAU 2 validé sur 30+ sessions NYSE)

3.3 Ce qu'il ne faut PAS faire

Liste explicite des intégrations IA/ML à éviter
sur ce projet spécifique, avec justification :
- Trop complexe pour le gain attendu
- Risque de régression sur le Sharpe=3.37 baseline
- Incompatible avec les contraintes IB Gateway
- Nécessite modification de core/*.pyx :
  signaler le coût make build + risque régression

3.4 Verdict global

En 5 lignes maximum :
- Faut-il intégrer de l'IA/ML sur ALPHAEDGE ?
- Si oui, par quoi commencer et pourquoi ?
- Quel est le risque principal à surveiller ?

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Crée le fichier :
  tasks/audits/audit_ia_ml_alphaedge.md
Crée le dossier tasks/audits/ s'il n'existe pas.

Confirme dans le chat uniquement :
"✅ tasks/audits/audit_ia_ml_alphaedge.md créé
 ✅ PERTINENT : X opportunités
 ❌ NON PERTINENT : X opportunités"
