**Date :** 2026-03-22 à 18:30

## BLOC 1 — INTÉGRITÉ DU SIGNAL FCR

### 1.1 Pipeline all-or-nothing

- `detect_fcr()` retourne bien `None` quand aucun FCR n'est trouvé dans la chaîne de détection, et `detect_engulfing()` retourne immédiatement `None` si `state.fcr_result` est absent : `alphaedge/engine/signal_pipeline.py:52`, `alphaedge/engine/signal_pipeline.py:99`.
- Les tests confirment ce garde-fou sur `detect_engulfing()` : `alphaedge/tests/test_signal_pipeline.py:107`, `alphaedge/tests/test_signal_pipeline.py:117`.
- En live, le pipeline n'est toutefois pas strictement stoppé après un `detect_fcr() -> None`. La session reste active, la détection gap continue sur les nouvelles barres M1, puis l'engulfing est court-circuité plus tard faute de `fcr_result` : `alphaedge/engine/session_lifecycle.py:435`, `alphaedge/engine/session_lifecycle.py:448`, `alphaedge/engine/session_lifecycle.py:701`, `alphaedge/engine/signal_pipeline.py:99`.
- `detect_gap() -> detected=False` stoppe bien toute tentative d'engulfing live : `alphaedge/engine/session_lifecycle.py:444`.
- `detect_engulfing() -> None` ou absence de `signal['detected']` empêche bien toute exécution d'ordre : `alphaedge/engine/session_lifecycle.py:448`, `alphaedge/engine/session_lifecycle.py:452`.

Conclusion 1.1 : NON CONFORME. Le comportement est bien all-or-nothing du point de vue ordre émis, mais pas du point de vue pipeline déclaré, car l'étape gap continue même sans FCR préalable.

### 1.2 Paramètres FCR

- Les constantes de base sont bien centralisées dans `constants.py` : `DEFAULT_MIN_RANGE_PIPS`, `DEFAULT_FCR_LOOKBACK`, `DEFAULT_RR_RATIO`, `PIP_SIZES`, `DEFAULT_MAX_DAILY_LOSS_PCT`, `DEFAULT_MAX_TRADES_PER_SESSION` sont définies en `alphaedge/config/constants.py:55`, `alphaedge/config/constants.py:57`, `alphaedge/config/constants.py:58`, `alphaedge/config/constants.py:64`, `alphaedge/config/constants.py:109`, `alphaedge/config/constants.py:110`.
- Le live n'utilise pas les paramètres configurés pour plusieurs étages du signal. `SignalPipeline.detect_fcr()` force `DEFAULT_MIN_RANGE_PIPS`, `detect_gap()` force `DEFAULT_MIN_ATR_RATIO`, et `detect_engulfing()` force `DEFAULT_VOLUME_PERIOD` et `DEFAULT_MIN_VOLUME_RATIO` : `alphaedge/engine/signal_pipeline.py:54`, `alphaedge/engine/signal_pipeline.py:81`, `alphaedge/engine/signal_pipeline.py:111`, `alphaedge/engine/signal_pipeline.py:112`.
- À l'inverse, le backtest injecte bien les valeurs configurées `config.trading.min_range_pips`, `config.trading.min_atr_ratio`, `config.trading.min_volume_ratio_by_pair`, `config.trading.rr_ratio`, `config.trading.min_body_ratio`, `config.trading.max_wick_ratio` : `alphaedge/engine/backtest.py:155`, `alphaedge/engine/backtest.py:158`, `alphaedge/engine/backtest.py:166`, `alphaedge/engine/backtest.py:292`, `alphaedge/engine/backtest.py:296`, `alphaedge/engine/backtest.py:297`.
- `pip_size` par paire est bien centralisé dans `PIP_SIZES` et consommé côté live comme backtest : `alphaedge/config/constants.py:64`, `alphaedge/engine/backtest.py:317`, `alphaedge/engine/strategy.py:219`.
- `DEFAULT_FCR_LOOKBACK` existe mais n'est pas utilisé par le moteur live ou backtest. Le live fetch 30 minutes fixes de M5 pré-session et appelle `detect_fcr`, pas `detect_fcr_scan` : `alphaedge/config/constants.py:110`, `alphaedge/engine/strategy.py:195`, `alphaedge/engine/signal_pipeline.py:52`.

Conclusion 1.2 : NON CONFORME. Les paramètres stratégiques ne sont pas consommés de façon cohérente entre backtest et live, et le lookback FCR annoncé comme configurable n'est pas branché dans le pipeline.

### 1.3 Filtre de session NYSE

- La fenêtre NYSE est définie via `SESSION_START_HOUR=9`, `SESSION_START_MINUTE=30`, `SESSION_END_HOUR=10`, `SESSION_END_MINUTE=30` dans `constants.py` : `alphaedge/config/constants.py:24` à `alphaedge/config/constants.py:27`.
- `timezone.is_session_active()` délègue explicitement au `NYSE_SESSION.contains()` de `session_manager.py`, ce qui centralise la règle de fenêtre : `alphaedge/utils/timezone.py:157`, `alphaedge/utils/timezone.py:178`, `alphaedge/utils/timezone.py:180`, `alphaedge/utils/session_manager.py:56`.
- `SessionLifecycle.run_session()` gère l'ouverture/fermeture de session, la détection de fin, le shutdown quotidien et l'arrêt si un shutdown persistant a déjà été déclenché : `alphaedge/engine/session_lifecycle.py:716`, `alphaedge/engine/session_lifecycle.py:734`, `alphaedge/engine/session_lifecycle.py:756`.

Conclusion 1.3 : CONFORME.

---

## BLOC 2 — COHÉRENCE BACKTEST ↔ LIVE

- Le live et le backtest importent les détecteurs via le même point d'entrée `alphaedge.core`, donc reposent sur la même surface publique des modules core : `alphaedge/engine/strategy.py:85`, `alphaedge/engine/strategy.py:149`, `alphaedge/engine/backtest.py:373`.
- En revanche, le filtre gap n'est pas alimenté avec les mêmes données. Le live passe `state.m5_candles` comme `pre_session_m1`, alors que le backtest passe correctement `m1_pre` issu de la pré-session M1 : `alphaedge/engine/signal_pipeline.py:76`, `alphaedge/engine/backtest.py:385`, `alphaedge/engine/backtest.py:422`, `alphaedge/engine/backtest_filters.py:49`.
- Le backtest et le live ne partagent pas le même chaînage risque/ordre. Le live passe par `calculate_position_size()` puis `create_bracket_order()` avec rejets explicites, alors que le backtest transforme directement un signal en `TradeRecord` sans appeler `risk_manager` ni `order_manager` : `alphaedge/engine/position_manager.py:55`, `alphaedge/engine/position_manager.py:96`, `alphaedge/engine/backtest.py:316`, `alphaedge/engine/backtest.py:455`.
- Le spread/slippage est modélisé en backtest via `compute_variable_slippage()`, alors que le live vérifie le spread en temps réel puis ajoute un buffer fixe `DEFAULT_MARKET_SLIPPAGE_PIPS` au stop : `alphaedge/engine/backtest.py:316`, `alphaedge/engine/backtest_simulation.py:41`, `alphaedge/engine/session_lifecycle.py:103`, `alphaedge/engine/session_lifecycle.py:106`, `alphaedge/engine/session_lifecycle.py:506`.
- L'export backtest est cohérent et testé sur son propre périmètre: colonnes, comptage de trades et labels directionnels sont vérifiés : `alphaedge/engine/backtest_export.py:47`, `alphaedge/engine/backtest_export.py:62`, `alphaedge/tests/test_backtest_export.py:51`, `alphaedge/tests/test_backtest_export.py:67`, `alphaedge/tests/test_backtest_export.py:95`.

Conclusion Bloc 2 : NON CONFORME. Le chemin de signal et de coût n'est pas suffisamment aligné entre live et backtest, en particulier sur la baseline gap M1/M5 et sur les validations pré-ordre.

---

## BLOC 3 — RISK MANAGEMENT FINANCIER

- `calculate_position_size()` borne bien la taille et expose `is_valid`; le live refuse l'exécution si le sizing est invalide : `alphaedge/core/_stubs/risk_manager.py:9`, `alphaedge/core/_stubs/risk_manager.py:27`, `alphaedge/engine/position_manager.py:55`, `alphaedge/engine/position_manager.py:66`.
- `create_bracket_order()` expose `is_valid` et `rejection_reason`; le live logue le rejet puis ignore l'ordre : `alphaedge/core/_stubs/order_manager.py:8`, `alphaedge/core/_stubs/order_manager.py:21`, `alphaedge/engine/position_manager.py:96`, `alphaedge/engine/position_manager.py:110`, `alphaedge/engine/position_manager.py:112`.
- `check_daily_limit()` coupe bien le trading immédiatement en cas de dépassement: `SessionLifecycle` annule les ordres, persiste l'état de shutdown et sort de la boucle : `alphaedge/core/_stubs/risk_manager.py:42`, `alphaedge/engine/strategy.py:251`, `alphaedge/engine/session_lifecycle.py:555`, `alphaedge/engine/session_lifecycle.py:570`, `alphaedge/engine/session_lifecycle.py:573`.
- Le log émis en cas de dépassement quotidien est `warning`, pas `critical` : `alphaedge/engine/session_lifecycle.py:557`.
- `max_daily_loss_pct` et `max_trades_per_session` sont bien définis dans `constants.py` : `alphaedge/config/constants.py:57`, `alphaedge/config/constants.py:58`.
- Le position sizing est un modèle fixed `risk_pct` cohérent avec le backtest, qui réapplique aussi un equity sizing fixe sur les trades : `alphaedge/engine/position_manager.py:57`, `alphaedge/engine/backtest.py:239`.

Conclusion Bloc 3 : PARTIELLEMENT CONFORME. Les garde-fous d'exécution sont présents et effectifs, mais le niveau de log attendu sur daily shutdown n'est pas respecté.

---

## BLOC 4 — TIMEZONE ET SESSION NYSE

- `zoneinfo` est utilisé exclusivement dans `timezone.py` et `session_manager.py`; aucun `pytz` n'est importé dans ces modules : `alphaedge/utils/timezone.py:12`, `alphaedge/utils/session_manager.py:15`.
- Aucun offset opérationnel hardcodé `+1` ou `+2` n'est utilisé pour calculer les fenêtres; les occurrences trouvées sont limitées à des commentaires/docstrings explicatifs : `alphaedge/utils/timezone.py:234`, `alphaedge/utils/timezone.py:252`, `alphaedge/utils/timezone.py:254`.
- Le mapping NYSE est calculé depuis `America/New_York`, converti en UTC, puis réutilisable pour Paris via `utc_to_tz(..., TZ_PARIS)` : `alphaedge/utils/timezone.py:110`, `alphaedge/utils/timezone.py:132`, `alphaedge/utils/timezone.py:151`, `alphaedge/utils/timezone.py:201`.
- Les tests couvrent l'hiver EST (`14:30–15:30 UTC`), l'été EDT (`13:30–14:30 UTC`), les weekends et la fenêtre de divergence EU/US de mars : `alphaedge/tests/test_timezone_dst.py:27`, `alphaedge/tests/test_timezone_dst.py:38`, `alphaedge/tests/test_timezone_dst.py:83`, `alphaedge/tests/test_timezone_weekend.py:20`.
- `run_session()` émet un warning explicite pendant la semaine de divergence DST EU/US : `alphaedge/engine/session_lifecycle.py:725`.

Conclusion Bloc 4 : CONFORME.

---

## BLOC 5 — ML FILTER

- `alphaedge/engine/ml_filter.py` n'est qu'un shim de ré-export vers `_experimental/ml_filter` et annonce lui-même que l'intégration live est en attente : `alphaedge/engine/ml_filter.py:8`, `alphaedge/engine/ml_filter.py:16`.
- Le pipeline live n'importe pas `ml_filter.py`. Le seul filtre actif côté stratégie est désormais `DailyRegimeFilter`, explicitement en observation-only : `alphaedge/engine/strategy.py:28`, `alphaedge/engine/strategy.py:166`, `alphaedge/engine/strategy.py:215`, `alphaedge/engine/regime_filter.py:209`.
- Aucune preuve de branchement de `MLSignalFilter` ou `walk_forward_ml` dans le pipeline live n'a été trouvée : `alphaedge/engine/ml_filter.py:20`, `alphaedge/engine/ml_filter.py:24`.

Conclusion Bloc 5 : NON CONFORME au sens stratégique. `ml_filter.py` est du code orphelin côté pipeline live et constitue une dette technique tant qu'il reste publié comme point d'entrée sans intégration effective.

---

## SYNTHÈSE

### Verdict global

Le socle stratégique est robuste sur les garde-fous d'ordre, le fixed-risk sizing, la gestion timezone/DST et le filtre de session NYSE. Les écarts majeurs se situent sur la cohérence live/backtest du pipeline FCR: le live n'emploie pas les mêmes paramètres configurés que le backtest, et le filtre gap ne reçoit pas la même baseline temporelle. Ces deux points dégradent directement la validité statistique des résultats de backtest par rapport au comportement réel du moteur live.

### Tableau synthèse

| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact | Effort |
|----|------|-------------|---------------|----------|--------|--------|
| S-01 | BLOC 2 | Le live passe les bougies M5 pré-session comme baseline `pre_session_m1` au gap detector, alors que le backtest utilise bien la pré-session M1 | `alphaedge/engine/signal_pipeline.py:76` ; `alphaedge/engine/backtest.py:422` ; `alphaedge/engine/backtest_filters.py:49` | 🔴 | Divergence directe du filtre gap entre backtest et live | M |
| S-02 | BLOC 1 | Le live force des constantes pour `min_range_pips`, `min_atr_ratio`, `volume_period`, `min_volume_ratio`, tandis que le backtest consomme les paramètres de config | `alphaedge/engine/signal_pipeline.py:54,81,111,112` ; `alphaedge/engine/backtest.py:155-168,292-297` | 🔴 | Les réglages optimisés/backtestés ne sont pas ceux réellement appliqués en live | M |
| S-03 | BLOC 1 | Le pipeline n'est pas strictement stoppé après `detect_fcr() -> None`; la détection gap continue encore en live | `alphaedge/engine/session_lifecycle.py:435,448,701` ; `alphaedge/engine/signal_pipeline.py:99` | 🟠 | Contrat all-or-nothing partiellement violé, logique live moins nette que prévue | S |
| S-04 | BLOC 2 | Le backtest ne passe pas par `risk_manager`/`order_manager`, contrairement au live | `alphaedge/engine/position_manager.py:55-112` ; `alphaedge/engine/backtest.py:316-455` | 🟠 | Les filtres d'exécution live ne sont pas tous reflétés dans les résultats historiques | M |
| S-05 | BLOC 2 | Le modèle de coûts n'est pas identique: variable slippage en backtest, spread réel + buffer fixe en live | `alphaedge/engine/backtest.py:316` ; `alphaedge/engine/backtest_simulation.py:41` ; `alphaedge/engine/session_lifecycle.py:103,106,506` | 🟠 | Performance backtest moins comparable au live sur les coûts d'exécution | S |
| S-06 | BLOC 3 | Le dépassement de daily loss stoppe bien le trading, mais le log est `warning` et non `critical` | `alphaedge/engine/session_lifecycle.py:555-573` | 🟡 | Signal opérationnel moins fort qu'attendu en production | XS |
| S-07 | BLOC 1 | `DEFAULT_FCR_LOOKBACK` existe mais n'est pas branché dans le pipeline; `detect_fcr_scan()` n'est pas utilisé | `alphaedge/config/constants.py:110` ; `alphaedge/engine/strategy.py:195` ; `alphaedge/engine/signal_pipeline.py:52` | 🟡 | Paramètre annoncé configurable mais sans effet stratégique réel | S |
| S-08 | BLOC 5 | `ml_filter.py` reste publié mais n'est pas intégré au pipeline live | `alphaedge/engine/ml_filter.py:8-24` ; `alphaedge/engine/strategy.py:28,166,215` | 🟡 | Dette technique et faux signal sur une capacité ML supposée active | XS |
