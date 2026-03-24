# AUDIT TECHNIQUE — ALPHAEDGE
**Date :** 2026-03-22 à 18:57

## 1. Vue d'ensemble

- Objectif réel inféré depuis le code : bot de trading Forex événementiel orienté ouverture de session, avec chaîne FCR M5 → gap ATR M1 → engulfing M1 → sizing → bracket order IB.
- Type : paper-ready robuste, backtestable, avec garde-fous live présents mais encore perfectibles côté outillage et observabilité.
- Niveau de maturité : élevé sur la logique opérationnelle et les sécurités de base, pas encore au niveau d'une base strictement durcie pour production capital réel sans réserve.
- Points forts réels :
  - séparation paper/live explicitement normalisée par `IBConfig` et `_apply_cli_mode` : `alphaedge/config/loader.py:235`, `alphaedge/engine/strategy.py:309`
  - pipeline live fail-closed sur FCR/gap/signal/sizing/order/fill : `alphaedge/engine/signal_pipeline.py:87`, `alphaedge/engine/position_manager.py:57`, `alphaedge/engine/position_manager.py:97`, `alphaedge/engine/session_lifecycle.py:104`, `alphaedge/engine/session_lifecycle.py:180`
  - persistance journalière atomique : `alphaedge/utils/state_persistence.py:34`
  - reconnect IB + réconciliation positions + contrôle ordres orphelins : `alphaedge/engine/session_lifecycle.py:214`, `alphaedge/engine/session_lifecycle.py:248`, `alphaedge/engine/session_lifecycle.py:279`
  - build Cython explicite et smoke check compilé en CI : `.github/workflows/ci.yml:28`, `.github/workflows/ci.yml:40`
- Signaux d'alerte globaux :
  - le niveau de typage reste en mode `basic`, pas strict : `pyrightconfig.json:1`
  - le seuil de couverture n'exerce ni `engine/` ni `core/_stubs/`, alors que la CI teste les stubs : `pyproject.toml:50`, `.github/workflows/ci.yml:47`, `alphaedge/core/__init__.pyi:1`
  - le runtime gère beaucoup d'erreurs par `except Exception`, ce qui protège le capital mais dégrade le diagnostic fin : `alphaedge/engine/broker.py:176`, `alphaedge/engine/data_feed.py:291`, `alphaedge/engine/session_lifecycle.py:227`
  - fallback automatique compiled → stubs sans contrôle de fraîcheur des artefacts : `alphaedge/core/__init__.py:24`
  - plusieurs fonctions structurantes restent massives et concentrent trop de responsabilités : `alphaedge/engine/data_feed.py:295`, `alphaedge/engine/backtest.py:403`, `alphaedge/engine/walk_forward.py:145`

## 2. Architecture & design système

- Pipeline réel :
  - collecte historique / realtime : `alphaedge/engine/data_feed.py:247`, `alphaedge/engine/data_feed.py:520`
  - orchestration stratégie : `alphaedge/engine/strategy.py:95`
  - session loop / exécution / reconnect : `alphaedge/engine/session_lifecycle.py:51`
  - chaîne signal pure : `alphaedge/engine/signal_pipeline.py:16`
  - sizing + bracket validation : `alphaedge/engine/position_manager.py:20`
  - exécution IB : `alphaedge/engine/broker.py:239`
- Couplage Cython ↔ Python : propre côté API publique avec `alphaedge.core` comme façade : `alphaedge/core/__init__.py:24`, `alphaedge/engine/strategy.py:71`.
- Violations SRP identifiées :
  - `HistoricalDataFeed.fetch_bars_chunked()` mélange pacing, cache, chunking, retry et fusion de résultats : `alphaedge/engine/data_feed.py:295`
  - `_backtest_pair()` mélange groupement session, filtres, signal, validation exécution et simulation : `alphaedge/engine/backtest.py:403`
  - `run_walk_forward()` concentre génération de fenêtres, entraînement/test et reporting : `alphaedge/engine/walk_forward.py:145`
- Fonctions > 100 lignes observées dans le code Python :
  - `alphaedge/engine/data_feed.py:295` — 165 lignes
  - `alphaedge/engine/backtest.py:403` — 152 lignes
  - `alphaedge/engine/backtest_stats.py:450` — 140 lignes
  - `alphaedge/engine/walk_forward.py:145` — 129 lignes
  - `alphaedge/engine/backtest_simulation.py:221` — 126 lignes
  - `alphaedge/engine/backtest_simulation.py:347` — 110 lignes
- Problèmes structurels bloquants : aucun blocage architectural immédiat relevé. Le design est exploitable, mais certaines zones restent surdimensionnées.

## 3. Qualité du code

- Duplication de logique : faible à modérée. La séparation `SignalPipeline` / `PositionManager` a réduit la duplication live, mais le backtest garde encore un flux parallèle spécialisé : `alphaedge/engine/backtest.py:467`, `alphaedge/engine/session_lifecycle.py:164`.
- `bare except` : aucun `except:` nu observé.
- `except Exception` : fréquent dans le runtime critique, avec stratégie fail-closed mais perte de granularité causale :
  - connexion et ordres IB : `alphaedge/engine/broker.py:176`, `alphaedge/engine/broker.py:362`, `alphaedge/engine/broker.py:400`, `alphaedge/engine/broker.py:410`, `alphaedge/engine/broker.py:426`, `alphaedge/engine/broker.py:443`, `alphaedge/engine/broker.py:472`
  - récupération de données : `alphaedge/engine/data_feed.py:291`, `alphaedge/engine/data_feed.py:575`, `alphaedge/engine/data_feed.py:641`, `alphaedge/engine/data_feed.py:671`
  - boucle de session : `alphaedge/engine/session_lifecycle.py:227`, `alphaedge/engine/session_lifecycle.py:323`, `alphaedge/engine/session_lifecycle.py:359`, `alphaedge/engine/session_lifecycle.py:518`, `alphaedge/engine/session_lifecycle.py:543`, `alphaedge/engine/session_lifecycle.py:556`, `alphaedge/engine/session_lifecycle.py:616`, `alphaedge/engine/session_lifecycle.py:798`
- Typage :
  - Pyright configuré en `basic` uniquement : `pyrightconfig.json:1`
  - les types publics sont globalement présents et cohérents dans `engine/`, `config/`, `utils/`
  - le point faible principal est l’outillage, pas l’absence d’annotations.
- Exemples précis de bonne qualité :
  - `TradingConfig` valide les bornes critiques : `alphaedge/config/loader.py:336`, `alphaedge/config/loader.py:396`
  - `SignalPipeline.detect_engulfing()` garde le contrat `None = STOP` : `alphaedge/engine/signal_pipeline.py:87`

## 4. Robustesse & fiabilité (TRADING-CRITICAL)

- `asyncio` / IB Gateway :
  - throttling token-bucket présent : `alphaedge/engine/broker.py:33`
  - circuit breaker de connexion présent : `alphaedge/engine/broker.py:126`
  - reconnexion exponentielle présente : `alphaedge/engine/broker.py:161`
  - réabonnement realtime après reconnexion : `alphaedge/engine/session_lifecycle.py:224`
- Persistance daily state : écriture atomique `.tmp -> os.replace()` : `alphaedge/utils/state_persistence.py:34`.
- Réconciliation positions au redémarrage : présente et testée via `_reconcile_positions()` : `alphaedge/engine/session_lifecycle.py:248`, `alphaedge/tests/test_strategy_p2_05.py:136`.
- Risques de crash silencieux dans `engine/` : modérés. La plupart des fautes runtime sont journalisées et fermées en sécurité, mais souvent trop génériquement via `except Exception`.
- Cohérence `.pyx` vs `.pyd` : bonne opérationnellement dans ce workspace, les 5 `.pyd` sont présents sous `alphaedge/core/`, et la CI force un smoke check compiled : `.github/workflows/ci.yml:40`, `setup.py:25`.

## 5. Interface IB Gateway & exécution des ordres

- `ALPHAEDGE_PAPER=true` strictement séparé du live :
  - exemple d’environnement : `.env.example:18`
  - normalisation mode/port : `alphaedge/config/loader.py:235`
  - override CLI explicite : `alphaedge/engine/strategy.py:309`
- Bracket orders : validation `is_valid` avant envoi respectée : `alphaedge/engine/position_manager.py:97`, `alphaedge/engine/session_lifecycle.py:83`.
- Fill verification : implémentée avec attente du `filledEvent` et timeout 10s : `alphaedge/engine/session_lifecycle.py:104`, `alphaedge/tests/test_fill_verification.py:139`.
- Gestion timeout `reqHistoricalData` : partiellement robuste. Les timeouts remontent via le feed, mais la reprise reste générique : `alphaedge/engine/data_feed.py:247`, `alphaedge/engine/data_feed.py:291`.
- Return value contracts observés et respectés dans le flux live :
  - `detect_fcr -> None = STOP avant gap` : `alphaedge/engine/session_lifecycle.py:384`
  - `detect_gap -> detected=False = STOP` : `alphaedge/engine/session_lifecycle.py:397`, `alphaedge/engine/session_lifecycle.py:409`
  - `detect_engulfing -> None = STOP` : `alphaedge/engine/signal_pipeline.py:87`, `alphaedge/engine/session_lifecycle.py:412`
  - `calculate_position_size -> is_valid=False = STOP` : `alphaedge/engine/position_manager.py:57`
  - `check_daily_limit -> limit_breached=True = STOP ALL` : `alphaedge/core/_stubs/risk_manager.py:42`, `alphaedge/engine/session_lifecycle.py:555`
  - `create_bracket_order -> is_valid=False = STOP` : `alphaedge/core/_stubs/order_manager.py:19`, `alphaedge/engine/position_manager.py:97`

## 6. Risk management & capital protection

- `check_daily_limit()` appelé de façon périodique au coeur de la boucle de session, avec intervalle adaptatif 5s/30s : `alphaedge/engine/session_lifecycle.py:746`, `alphaedge/engine/session_lifecycle.py:778`.
- reset journalier correct : le fichier d’état d’un jour précédent est ignoré : `alphaedge/utils/state_persistence.py:57`.
- `halt_trading` persistant au redémarrage : oui, via `shutdown_triggered` avant toute connexion IB : `alphaedge/engine/session_lifecycle.py:725`, `alphaedge/utils/state_persistence.py:30`.
- `emergency_halt` implicite : oui via `_shutdown_requested`, annulation d’ordres et refus de démarrage après kill-switch : `alphaedge/engine/session_lifecycle.py:568`, `alphaedge/engine/session_lifecycle.py:728`.
- séparation paper/live dans `broker.py` : correcte par construction, `BrokerConnection` prend `IBConfig` déjà normalisé ; aucune bascule implicite observée dans le broker lui-même.
- Niveau de danger pour capital réel : modéré. Le code préserve le capital par défaut, mais l’observabilité et la rigueur de validation statique ne sont pas au niveau maximal.

## 7. Timezone & session NYSE

- `timezone.py` et `session_manager.py` utilisent `zoneinfo` uniquement : `alphaedge/utils/timezone.py:12`, `alphaedge/utils/session_manager.py:14`.
- Aucun hardcode opérationnel `UTC+1/UTC+2` dans le calcul des fenêtres ; les offsets n’apparaissent que dans les messages explicatifs : `alphaedge/utils/timezone.py:201`, `alphaedge/engine/session_lifecycle.py:712`.
- Fenêtre de divergence EU/US explicitement couverte par `is_dst_transition_week()` et consommée en session live : `alphaedge/utils/timezone.py:201`, `alphaedge/engine/session_lifecycle.py:709`.
- Mapping NYSE correct : calcul depuis `America/New_York` puis conversion UTC : `alphaedge/utils/timezone.py:93`.
- Tests DST présents, y compris la semaine de divergence mars : `alphaedge/tests/test_timezone_dst.py:22`, `alphaedge/tests/test_timezone_dst.py:81`.

## 8. Couverture des tests

- Exécution observée dans ce workspace : `547 passed`, couverture totale `92.33%`.
- Le seuil minimal de couverture est bien fixé à 80% : `pyproject.toml:44`, `.github/workflows/ci.yml:52`.
- Modules exclus du coverage : `engine/`, `tests/`, `logs/`, mais aussi `core/_stubs/` : `pyproject.toml:50`.
- Les stubs Cython restent cependant le backend de test en CI : `.github/workflows/ci.yml:47`, `alphaedge/core/__init__.pyi:1`.
- Parametrization : présente mais pas systématique ; bonne densité sur timezone, corrélation, ML et détecteurs.
- Scénarios manquants à risque :
  - pas de test e2e unique couvrant la chaîne complète live mockée du pré-open à la fermeture
  - pas de garde de couverture sur les stubs pourtant utilisés comme backend de test CI.

## 9. Build Cython & setup.py

- `setup.py` compile bien les 5 modules `.pyx` : `setup.py:25`.
- Build reproductible en CI : oui, avec `python setup.py build_ext --inplace` puis smoke check compiled : `.github/workflows/ci.yml:28`, `.github/workflows/ci.yml:40`.
- `.pyd` présents dans `alphaedge/core/` dans ce workspace pour les 5 modules.
- `_stubs/` correctement utilisés pour l’analyse statique via `.pyi` et pour les tests CI via `ALPHAEDGE_CORE_BACKEND=stubs` : `alphaedge/core/__init__.py:24`, `alphaedge/core/__init__.pyi:1`, `.github/workflows/ci.yml:47`.
- Point faible : absence de contrôle explicite de fraîcheur ou provenance entre `.pyx`, `.c` et `.pyd` hors discipline de build/CI.

## 10. Synthèse & priorités

| ID | Sévérité | Section | Description | Fichier:Ligne | Impact |
|----|----------|---------|-------------|---------------|--------|
| M-01 | 🟠 | 3 | Le niveau de type-checking Pyright reste en mode `basic`, ce qui réduit la capacité à détecter les dérives d’interface avant exécution. | pyrightconfig.json:1 | Dette de sûreté statique sur une base de trading critique. |
| M-02 | 🟠 | 8 | Le seuil de couverture n’exerce ni `engine/` ni `core/_stubs/`, alors que la CI exécute les tests contre les stubs. | pyproject.toml:50 ; .github/workflows/ci.yml:47 ; alphaedge/core/__init__.pyi:1 | Angle mort sur le backend effectivement testé et sur l’orchestration runtime Python. |
| M-03 | 🟠 | 4 | Le runtime critique repose largement sur `except Exception` dans broker/feed/session, ce qui protège le capital mais nuit au diagnostic précis et à la politique de reprise différenciée. | alphaedge/engine/broker.py:176 ; alphaedge/engine/data_feed.py:291 ; alphaedge/engine/session_lifecycle.py:227 | Pannes plus difficiles à qualifier, remédiation automatique moins fine. |
| M-04 | 🟡 | 9 | Le fallback automatique compiled → stubs peut masquer l’absence d’artefact compilé hors mode `compiled` forcé. | alphaedge/core/__init__.py:24 | Risque de faux sentiment de build sain hors CI stricte. |
| M-05 | 🟡 | 2 | Plusieurs fonctions dépassent 100 lignes et concentrent trop de responsabilités opérationnelles. | alphaedge/engine/data_feed.py:295 ; alphaedge/engine/backtest.py:403 ; alphaedge/engine/walk_forward.py:145 | Maintenabilité et auditabilité réduites dans les zones critiques. |
| M-06 | 🟡 | 3 | Les handlers de déconnexion restent typés en `Any`. | alphaedge/engine/broker.py:102 | Contrats callback moins sûrs pour les évolutions futures. |
| M-07 | 🟡 | 8 | Aucun test e2e unique ne couvre la chaîne complète live mockée du pré-open jusqu’au fill/close dans un seul scénario. | alphaedge/tests/test_fill_verification.py:118 ; alphaedge/tests/test_strategy_p2_05.py:136 | Le comportement global reste validé par fragments, pas par un seul invariant de bout en bout. |
